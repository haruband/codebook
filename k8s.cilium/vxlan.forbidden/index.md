우리 회사에서는 주로 의료데이터를 다루다보니 개인정보보호법에 의해 서비스를 운영하는 국가 외부로 데이터가 유출되면 안 된다. 그래서 한국이나 미국 같이 AWS 나 GCP 리전이 있는 국가들은 해당 서비스를 이용하여 운영할 수 있지만, 해당 국가에 리전이 없는 경우에는 쓸만한 IaaS 를 제공하는 클라우드 서비스가 있다면 해당 서비스를 활용하고, 이마저도 없을 경우에는 데이터 센터를 이용한다.

오늘은 최근에 어떤 국가의 기업에서 제공하는 VMWare 기반의 IaaS 를 이용하여 쿠버네티스 클러스터를 구축하던 중 발생했던 문제를 파악하고 해결했던 과정을 간단히 소개해보고자 한다. 해당 문제와 유사한 문제가 다행히(?) AWS EC2 에서도 발생하여 EC2 를 기준으로 설명하도록 하겠다.

## _어떠한 문제가 발생했는가???_

우리는 AWS 와 GCP 를 사용할때는 주로 매니지드 쿠버네티스 서비스를 활용하지만, 그렇지 않은 경우에는 kubespray 를 이용하여 쿠버네티스를 설치하고, kustomization 을 기반으로 개발한 IaC(InfrastructureasCode)를 이용하여 서비스를 배포한다. 그리고 CNI 는 개인적으로 문제 분석과 해결이 용이한 Cilium 을 주로 사용하고 있다.

일단 상황은 이렇다. 회사 내부에서 딥러닝/빅데이터 클러스터에서 꾸준히 사용해오던 쿠버네티스를 동일한 방식으로 EC2 에 설치했는데 이상한 현상이 발생했다. **처음 접했던 현상은 서비스 디스커버리가 잘(?) 되지 않는 문제였다.** 그래서 kibana 와 mongos 같이 서비스 디스커버리를 이용하여 다른 Pod 에 접근하는 서비스들이 동작하지 않는 문제가 발생했다. 이와 같은 현상의 원인을 파악하기 위해 일단은 서비스 디스커버리 쪽을 살펴보기로 했다.

원인 분석을 위해 클러스터 내부에 jupyterlab 을 설치하고 dig 를 이용하여 서비스 디스커버리가 잘 동작하는지 확인해보았다. nodelocaldns 를 사용 중이고, coredns 는 기본적으로 2개의 Pod 이 동작 중이다. 일단 nodelocaldns 쪽은 문제가 없다고 판단하여 바로 coredns 서비스로 dig 를 이용하여 질의를 해보았다. 동일한 도메인을 반복적으로 질의해보니 성공과 실패를 반복하는 이상한 현상이 발견되었다. 그래서 이번에는 두 개의 coredns Pod 으로 각각 직접 질의를 해보았다. **놀랍게도 하나의 Pod 은 항상 성공했지만, 다른 하나의 Pod 은 항상 실패했다.**

두 개의 Pod 는 하나의 coredns 디플로이먼트로 배포된 완전히 동일한 Pod 인데 왜 이런 문제가 발생한 것일까? 사실은 두 개의 Pod 이 완전히 동일한 상황은 아니다. 왜냐하면 두 개의 Pod 은 서로 다른 노드에 존재하고, 둘 중 하나의 노드에만 jupyterlab 이 존재하기 때문이다. jupyterlab 에서 동일한 방식으로 각각의 Pod 에 질의를 보냈지만, 결과적으로는 하나의 Pod 은 같은 노드에 있어서 로컬 통신으로 요청이 잘 처리되었고, 다른 Pod 은 다른 노드에 있어서 외부 통신을 하던 중 문제가 발생했던 것이다. **즉, 해당 문제는 우리가 처음 접했던 서비스 디스커버리의 문제가 아니고, 네트워킹의 문제였다.**

## _왜 이런 문제가 발생했는가???_

우선 쿠버네티스에서 실제 통신을 처리하는 CNI 를 살펴보았다. 우리는 CNI 로 Cilium 을 사용 중이기 때문에 관련 정보들이 정확히 구성되어있는지 분석해보았다.

```
$ kubectl get services -n kube-system
NAME             TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)                  AGE
coredns          ClusterIP   10.233.0.3      <none>        53/UDP,53/TCP,9153/TCP   3h14m
...
$ kubectl get pods -l k8s-app=kube-dns -o wide -n kube-system
NAME                       READY   STATUS    RESTARTS   AGE     IP              NODE    NOMINATED NODE   READINESS GATES
coredns-8474476ff8-d7pjv   1/1     Running   0          3h14m   10.233.64.125   node1   <none>           <none>
coredns-8474476ff8-nz2tt   1/1     Running   0          3h13m   10.233.65.250   node2   <none>           <none>
cilium(node1) $ cilium service list
ID   Frontend            Service Type   Backend
...
2    10.233.0.3:53       ClusterIP      1 => 10.233.64.125:53
                                        2 => 10.233.65.250:53
...
```

Cilium 의 2번 서비스를 보면 기본적인 coredns 서비스와 엔드포인트가 정확히 설정되어있는 것을 확인할 수 있다. 다음으로 노드 간 통신을 위해 VXLAN 을 사용 중이기 때문에 아래와 같이 터널링 정보도 확인해보았다.

```
node1 $ cilium bpf tunnel list
TUNNEL          VALUE
10.233.65.0:0   172.26.50.201:0
```

여기까지 살펴본 바로는 설정에는 아무런 문제가 없었다. 그럼 이제 실제 통신이 제대로 이루어지는지를 살펴보자. 확인은 node1 에 존재하는 jupyterlab 에서 node2 에 있는 coredns Pod 으로 dig 를 이용하여 질의를 보낼때 node1 과 node2 에서 tcpdump 로 VXLAN 이 사용 중인 8472 UDP 포트를 모니터링하였다.
