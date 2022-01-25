Cilium 이 최근 공개한 eBPF 기반의 서비스 메쉬에서 중요하게 언급하고 있는 것 중에 하나는 Pod 마다 사이드카 형태로 프록시를 추가하지 말고 노드별로 하나씩만 설치해서 사용하자는 것이다. 이는 특히 대규모의 클러스터에서 많은 사이드카 프록시로 인해 발생하는 자원 소모를 줄일 수 있을 것으로 기대되는데, 오늘은 Cilium 에서 노드별 프록시(Per-Node Proxy)가 어떤 방식으로 동작하는지 살펴보도록 하자. (일반적으로 가장 많이 사용하는 엔보이(Envoy)를 기준으로 설명하겠다.)

원활한 설명을 위해 Cilium 이 제공하는 인그레스(Ingress) 예제를 이용하여 설명하도록 하겠다. 해당 예제는 Istio 의 BookInfo 예제를 기반으로 동작하며, 아래와 같은 간단한 인그레스 설정을 제공한다.

```bash
# kubectl get ingress basic-ingress -o yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: basic-ingress
  namespace: default
spec:
  ingressClassName: cilium
  rules:
  - http:
      paths:
      - backend:
          service:
            name: details
            port:
              number: 9080
        path: /details
        pathType: Prefix
      - backend:
          service:
            name: productpage
            port:
              number: 9080
        path: /
        pathType: Prefix
```

위의 인그레스를 등록하면 Cilium 오퍼레이터는 자동으로 아래와 같은 CiliumEnvoyConfig 를 만들고, Cilium 에이전트는 CiliumEnvoyConfig 를 기반으로 엔보이에 필요한 설정을 추가한다.

```bash
# kubectl get ciliumenvoyconfig cilium-ingress-default-basic-ingress -o yaml
apiVersion: cilium.io/v2alpha1
kind: CiliumEnvoyConfig
metadata:
  creationTimestamp: "2022-01-24T00:33:08Z"
  generation: 1
  name: cilium-ingress-default-basic-ingress
  resourceVersion: "1133"
  uid: 4cd02f0f-a89e-4e15-82d5-8ec7b95e0c37
spec:
  backendServices:
  - name: productpage
    namespace: default
  - name: details
    namespace: default
  resources:
  - '@type': type.googleapis.com/envoy.config.listener.v3.Listener
    filterChains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typedConfig:
          '@type': type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          httpFilters:
          - name: envoy.filters.http.router
          rds:
            routeConfigName: cilium-ingress-default-basic-ingress_route
          statPrefix: basic-ingress
    name: cilium-ingress-default-basic-ingress
  - '@type': type.googleapis.com/envoy.config.route.v3.RouteConfiguration
    name: cilium-ingress-default-basic-ingress_route
    virtualHosts:
    - domains:
      - '*'
      name: '*'
      routes:
      - match:
          prefix: /details
        route:
          cluster: default/details
      - match:
          prefix: /
        route:
          cluster: default/productpage
  - '@type': type.googleapis.com/envoy.config.cluster.v3.Cluster
    connectTimeout: 5s
    name: default/productpage
    type: EDS
    ...
  - '@type': type.googleapis.com/envoy.config.cluster.v3.Cluster
    connectTimeout: 5s
    name: default/details
    type: EDS
    ...
  services:
  - listener: cilium-ingress-default-basic-ingress
    name: cilium-ingress-basic-ingress
    namespace: default
```

엔보이에 대한 자세한 설명은 본문 내용과는 어울리지 않으니 관련 자료를 참고하시고 여기서는 오늘 설명할 내용을 이해하기 위해 꼭 필요한 내용만 간단히 소개하도록 하겠다. 엔보이는 리스너(Listener)를 통해 트래픽을 전달받아서 필요한 처리를 한 다음, 클러스터(Cluster)로 트래픽을 전달한다. 위의 인그레스 예제는 리스너로 들어온 HTTP 요청의 URL 을 확인하여 /details 는 default 네임스페이스의 details 서비스(default/details 클러스터)로 전달하고, 나머지는 모두 default 네임스페이스의 productpage 서비스(default/productpage 클러스터)로 전달하라는 의미이다. 두 개의 클러스터는 EDS 타입으로 설정되어있고, Cilium 에이전트가 해당 클러스터의 엔드포인트 정보를 자동으로 업데이트한다.

간단히 Cilium 이 제공하는 인그레스 예제를 이용하여 엔보이의 리스너가 전달받은 트래픽을 어떻게 처리하는지 살펴보았으니, 이제 어떻게 엔보이의 리스너로 트래픽을 전달하는지 살펴보도록 하자.

기존의 사이드카 방식의 프록시는 IPTables 를 이용하여 모든 트래픽을 엔보이의 특정 리스너로 전달하는 방식을 사용하지만, Cilium 의 노드별 프록시는 특정 서비스(cilium-ingress-basic-ingress)로 들어오는 트래픽을 특정 리스너(cilium-ingress-default-basic-ingress)로 전달하는 방식을 사용하고 있다. Cilium 에이전트는 엔보이에 리스너를 등록하기 전에 임의의 포트를 할당하고, 리스너와 연결된 서비스에 해당 포트를 설정해둔다. 이후에는 해당 서비스로 들어오는 모든 트래픽은 리스너가 할당받은 포트로 전달된다.

위의 인그레스 예제를 좀 더 살펴보면, 아래와 같이 리스너와 연결된 서비스를 확인할 수 있고, 해당 서비스로 접속하면 위에서 설정한대로 default 네임스페이스의 details 서비스와 productpage 서비스로 연결되는 것을 확인할 수 있다.

```bash
# kubectl get services
NAME                           TYPE           CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE
cilium-ingress-basic-ingress   LoadBalancer   10.103.218.167   <pending>     80:31907/TCP   23h
...

# curl http://172.26.50.200:31907/details/1
{"id":1,"author":"William Shakespeare","year":1595,"type":"paperback","pages":200,"publisher":"PublisherA","language":"English","ISBN-10":"1234567890","ISBN-13":"123-1234567890"}

# curl http://172.26.50.200:31907/
<!DOCTYPE html>
<html>
  <head>
    <title>Simple Bookstore App</title>
    ...
</html>
```

Cilium 은 서비스로 들어온 트래픽을 리스너로 전달하기 위해 두 가지 방식을 제공하고 있다. 첫 번째는 IPTables 를 이용하는 방식이고, 두 번째는 eBPF 를 이용하는 방식이다. 지금부터 이 두 가지 방식이 각각 어떻게 동작하는지 하나씩 살펴보도록 하자.

## _IPTables 기반 트래픽 전달_

## _eBPF 기반 트래픽 전달_
