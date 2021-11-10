오늘은 [지난 글](https://velog.io/@haruband/K8S-NAT-%EB%A3%A8%ED%94%84%EB%B0%B1-%EB%AC%B8%EC%A0%9C-%EB%B6%84%EC%84%9D)에서 소개했던 NAT 루프백 문제에 대해 다시 소개하고자 한다. 이유는 몇 개 국가의 IDC 혹은 클라우드에서 NAT 루프백 문제를 해결하기 위해 라우터에 필요한 설정을 추가했음에도 불구하고 원인을 정확히 알 수 없는 이유로 동작하지 않는 문제가 발생해서 다른 해결책을 찾을 필요가 있었기 때문이다.

외부 환경에 의존하지 않고 우리 스스로 해당 문제를 해결할 수 있는 방법은 클러스터 내부에서 외부 IP 를 사용하지 않는 것이다. 이를 위해 우리가 선택할 수 있는 옵션은 첫 번째는 내부 DNS 를 사용하는 것이고, 두 번째는 eBPF (혹은 IPTables) 를 사용하여 외부 IP 를 강제로 내부 IP 로 리다이렉션(redirection)하는 것이다. 그리고 해당 문제는 Pod 에서 외부 IP 를 접근하는 경우 뿐 아니라, 호스트 네트워크를 사용하는 Pod 이나 Kubelet 에서 외부 IP 를 접근하는 경우도 고려할 필요가 있을 수 있다. (우리 같은 경우는 클러스터 내부에 컨테이너 레지스트리 서버를 운영 중이고, Kubelet 에서 컨테이너 이미지를 가져올 때 컨테이너 레지스트리 서버의 외부 도메인 주소를 이용하고 있었다.)

우선 첫 번째 내부 DNS 를 사용하는 경우를 살펴보자.

가장 간단한 방법은 모든 노드의 /etc/hosts 를 이용하여 외부 도메인 주소를 강제로 내부 IP 로 변경해버리는 것이다. 하지만 이는 IP 만 변경해주는 것이기 때문에 외부에서 접근하는 포트와 내부에서 접근하는 포트가 다른 경우에는 사용할 수 없다.

두 번째는 Cilium 에서 제공하는 LRP(LocalRedirectPolicy) 라는 기능을 사용하는 경우이다.

호스트 네트워크를 사용하는 Pod 이나 Kubelet 의 경우는 [다른 글](https://velog.io/@haruband/K8SCilium-Socket-Based-LoadBalancing-%EA%B8%B0%EB%B2%95)에서 소개했던 소켓 기반 로드밸런싱 기능을 이용하면 해결할 수 있다.

```
apiVersion: "cilium.io/v2"
kind: CiliumLocalRedirectPolicy
metadata:
  name: nginx-lrp
spec:
  redirectFrontend:
    addressMatcher:
      ip: "10.10.10.10"
      toPorts:
        - port: "8080"
          protocol: TCP
  redirectBackend:
    localEndpointSelector:
      matchLabels:
        run: nginx
    toPorts:
      - port: "80"
        protocol: TCP
```

```bash
$ kubectl get pods -o wide
NAME    READY   STATUS    RESTARTS   AGE     IP             NODE     NOMINATED NODE   READINESS GATES
nginx   1/1     Running   0          7m36s   192.168.0.80   master   <none>           <none>

node0 $ cilium service list
ID   Frontend              Service Type    Backend
1    10.96.0.1:443         ClusterIP       1 => 172.26.50.200:6443
2    10.96.0.10:53         ClusterIP       1 => 192.168.1.96:53
                                           2 => 192.168.1.219:53
3    10.96.0.10:9153       ClusterIP       1 => 192.168.1.96:9153
                                           2 => 192.168.1.219:9153
4    10.108.175.91:80      ClusterIP       1 => 192.168.0.80:80
5    172.26.50.235:80      LoadBalancer    1 => 192.168.0.80:80
6    172.26.50.200:30904   NodePort        1 => 192.168.0.80:80
7    0.0.0.0:30904         NodePort        1 => 192.168.0.80:80
8    10.10.10.10:8080      LocalRedirect   1 => 192.168.0.80:80
```

```bash
node0 $ curl http://10.10.10.10:8080
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
html { color-scheme: light dark; }
body { width: 35em; margin: 0 auto;
font-family: Tahoma, Verdana, Arial, sans-serif; }
</style>
</head>
<body>
<h1>Welcome to nginx!</h1>
<p>If you see this page, the nginx web server is successfully installed and
working. Further configuration is required.</p>

<p>For online documentation and support please refer to
<a href="http://nginx.org/">nginx.org</a>.<br/>
Commercial support is available at
<a href="http://nginx.com/">nginx.com</a>.</p>

<p><em>Thank you for using nginx.</em></p>
</body>
</html>
```
