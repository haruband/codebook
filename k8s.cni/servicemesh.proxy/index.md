Cilium 이 최근 공개한 eBPF 기반의 서비스 메쉬에서 중요하게 언급하고 있는 것 중에 하나는 Pod 마다 사이드카 형태로 프록시를 추가하지 말고 노드별로 하나씩만 설치해서 사용하자는 것이다. 이는 특히 대규모의 클러스터에서 많은 사이드카 프록시가 사용하는 자원 소모를 줄일 수 있을 것으로 기대되는데, 오늘은 Cilium 에서 노드별 프록시(Per-Node Proxy)가 어떤 방식으로 동작하는지 살펴보도록 하자. (일반적으로 가장 많이 사용하는 엔보이(Envoy)를 기준으로 설명하겠다.)

좀 더 쉬운 이해를 위해 Cilium 이 제공하는 인그레스(Ingress) 예제를 이용하여 설명하도록 하겠다. 해당 예제는 Istio 의 BookInfo 예제를 기반으로 동작하며, 아래와 같은 간단한 인그레스 설정을 제공한다.

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
    outlierDetection:
      consecutiveLocalOriginFailure: 2
      splitExternalLocalOriginErrors: true
    type: EDS
    typedExtensionProtocolOptions:
      envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
        '@type': type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
        useDownstreamProtocolConfig:
          http2ProtocolOptions: {}
  - '@type': type.googleapis.com/envoy.config.cluster.v3.Cluster
    connectTimeout: 5s
    name: default/details
    outlierDetection:
      consecutiveLocalOriginFailure: 2
      splitExternalLocalOriginErrors: true
    type: EDS
    typedExtensionProtocolOptions:
      envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
        '@type': type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
        useDownstreamProtocolConfig:
          http2ProtocolOptions: {}
  services:
  - listener: cilium-ingress-default-basic-ingress
    name: cilium-ingress-basic-ingress
    namespace: default
```

엔보이에 대한 자세한 설명은 본문 내용과는 어울리지 않으니 관련 자료를 참고하시고 여기서는 간단히만 소개하도록 하겠다. 엔보이는 리스너(Listener)를 통해 트래픽을 전달받아서 필요한 처리를 한 다음, 클러스터(Cluster)로 트래픽을 전달한다. 위의 인그레스 예제는 리스너로 들어온 HTTP 요청의 URL 을 확인하여 /details 는 default 네임스페이스의 details 서비스로 전달하고, 나머지는 모두 default 네임스페이스의 productpage 서비스로 전달하라는 의미이다.

그래서 Pod 에서 나가는 트래픽을 엔보이의 리스너로 전달하는 것이 중요한데, 이를 위해 Cilium 은 IPTables 를 이용하는 방식과 eBPF 를 이용하는 방식을 제공하고 있다.

## _IPTables 기반 트래픽 전달_

## _eBPF 기반 트래픽 전달_