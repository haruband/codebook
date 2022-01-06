오늘은 최근 회사에서 GitOps 를 적용하기 위해 ArgoCD 를 설치하던 중 발생했던 문제에 대해 살펴보고자 한다.

## _어떠한 문제가 발생했는가???_

Helm 을 이용하여 ArgoCD 를 설치하였는데 아래와 같이 두 개의 Pod 만 동작을 하지 않는 문제가 발생하였다.

```bash
# kubectl get pods -n argocd -o wide
NAME                                  READY   STATUS             RESTARTS       AGE   IP           NODE    NOMINATED NODE   READINESS GATES
argocd-application-controller-0       0/1     CrashLoopBackOff   29 (42s ago)   88m   10.0.1.185   node1   <none>           <none>
argocd-dex-server-6f7fd44b9d-s6rrk    1/1     Running            0              88m   10.0.1.94    node1   <none>           <none>
argocd-redis-84558bbb99-n6tmz         1/1     Running            0              88m   10.0.1.159   node1   <none>           <none>
argocd-repo-server-784b48858f-4zx42   0/1     CrashLoopBackOff   27 (87s ago)   88m   10.0.1.166   node1   <none>           <none>
argocd-server-74bf76596b-zgtgq        1/1     Running            0              88m   10.0.1.184   node1   <none>           <none>
```

아래처럼 호스트에서 Pod 로 접속이 되지 않는 문제였다.

```bash
# kubectl describe pods argocd-application-controller-0 -n argocd
Name:         argocd-application-controller-0
Namespace:    argocd
...
Events:
  Type     Reason     Age                 From     Message
  ----     ------     ----                ----     -------
  Warning  Unhealthy  41m (x61 over 88m)  kubelet  Readiness probe failed: Get "http://10.0.1.185:8082/healthz": context deadline exceeded (Client.Timeout exceeded while awaiting headers)
  Normal   Pulled     17m (x17 over 66m)  kubelet  (combined from similar events): Successfully pulled image "quay.io/argoproj/argocd:v2.2.2" in 2.525708797s
  Warning  BackOff    2m (x302 over 77m)  kubelet  Back-off restarting failed container
```

엔드포인트 라우팅을 사용 중이고, 라우팅 설정은 아래처럼 문제가 없다.

```bash
# route -n
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
0.0.0.0         172.26.50.1     0.0.0.0         UG    0      0        0 eno1
10.0.0.0        172.26.50.200   255.255.255.0   UG    0      0        0 eno1
10.0.1.0        10.0.1.106      255.255.255.0   UG    0      0        0 cilium_host
10.0.1.184      0.0.0.0         255.255.255.255 UH    0      0        0 lxc5ac784021fb3
10.0.1.185      0.0.0.0         255.255.255.255 UH    0      0        0 lxcfae959439981

# ip route get 10.0.1.185
10.0.1.185 dev lxcfae959439981 src 172.26.50.201 uid 0
    cache
```

Cilium 이 제공하는 모니터링 기능을 이용하여 확인해보니 패킷이 드롭되고 있었다.

```bash
# cilium node1 cilium monitor
Policy verdict log: flow 0x48357586 local EP ID 211, remote ID world, proto 6, ingress, action deny, match none, 172.26.50.201:60556 -> 10.0.1.185:8082 tcp SYN
xx drop (Policy denied) flow 0x48357586 to endpoint 211, , identity world->15435: 172.26.50.201:60556 -> 10.0.1.185:8082 tcp SYN
```

여기서 이상한 점은 호스트(172.26.50.201)에서 패킷을 보내는데 ID 가 Host 이어야 하는데 World 로 보여진다. 그런데 왜 두 개의 Pod 만 동작하지 않을까?

```bash
# cilium node1 cilium monitor
-> endpoint 1562 flow 0x76403eb7 , identity world->11803 state new ifindex 0 orig-ip 172.26.50.201: 172.26.50.201:56134 -> 10.0.1.184:8080 tcp SYN
-> stack flow 0xe8858480 , identity 11803->host state reply ifindex 0 orig-ip 0.0.0.0: 10.0.1.184:8080 -> 172.26.50.201:56134 tcp SYN, ACK
```

위도 마찬가지로 ID 가 World 로 잘못되어있지만 전송은 잘 된다. 왜 이런 현상이 발생한 것일까?

```bash
# cilium node1 cilium bpf policy get -n 211
Defaulted container "cilium-agent" out of: cilium-agent, mount-cgroup (init), clean-cilium-state (init)
POLICY   DIRECTION   IDENTITY   PORT/PROTO   PROXY PORT   BYTES    PACKETS
Allow    Ingress     1          ANY          NONE         60201    687
Allow    Ingress     4086       8082/TCP     NONE         0        0
Allow    Ingress     11803      8082/TCP     NONE         0        0
Allow    Ingress     14155      8082/TCP     NONE         0        0
Allow    Ingress     15435      8082/TCP     NONE         0        0
Allow    Ingress     19965      8082/TCP     NONE         0        0
Allow    Ingress     60530      8082/TCP     NONE         0        0
Allow    Egress      0          ANY          NONE         446824   3633

# cilium node1 cilium bpf policy get -n 1562
Defaulted container "cilium-agent" out of: cilium-agent, mount-cgroup (init), clean-cilium-state (init)
POLICY   DIRECTION   IDENTITY   PORT/PROTO   PROXY PORT   BYTES     PACKETS
Allow    Ingress     0          ANY          NONE         1024489   8391
Allow    Ingress     1          ANY          NONE         71946     649
Allow    Egress      0          ANY          NONE         1581964   11146
```

argocd-application-controller 는 ingress 가 설정되어 있기 때문에 접근이 허영된 Pod 과 호스트만 접속 가능하고, argocd-server 는 모두 접근이 가능하다. 그래서 ID 가 잘못되었어도 argocd-server 는 접근이 가능한 것이다. 아래는 ArgoCD 설치 시 자동으로 배포된 네트워크 정책이다.

```bash
# kubectl describe networkpolicy argocd-application-controller-network-policy -n argocd
Name:         argocd-application-controller-network-policy
Namespace:    argocd
Spec:
  PodSelector:     app.kubernetes.io/name=argocd-application-controller
  Allowing ingress traffic:
    To Port: 8082/TCP
    From:
      NamespaceSelector: <none>
  Not affecting egress traffic
  Policy Types: Ingress

# kubectl describe networkpolicy argocd-server-network-policy -n argocd
Name:         argocd-server-network-policy
Namespace:    argocd
Spec:
  PodSelector:     app.kubernetes.io/name=argocd-server
  Allowing ingress traffic:
    To Port: <any> (traffic allowed to all ports)
    From: <any> (traffic not restricted by source)
  Not affecting egress traffic
  Policy Types: Ingress
```

그렇다면 왜 ID 가 잘못됐을까?

## _어떻게 문제가 발생했는가???_

Cilium 에서는 호스트에서 보내는 패킷이 0xc00 을 마킹하는데, 이를 iptables 를 이용한다. 그런데 --install-iptables-rules 설정이 해제되어 있어서 제대로 마킹이 되지 않았던 것이다.

## _어떻게 문제를 해결했는가???_

--install-iptables-rules 를 설정하면 아래와 같은 정책을 볼 수 있다.

```bash
# iptables -t filter -L
Chain OUTPUT (policy ACCEPT)
target     prot opt source               destination
CILIUM_OUTPUT  all  --  anywhere             anywhere             /* cilium-feeder: CILIUM_OUTPUT */
KUBE-FIREWALL  all  --  anywhere             anywhere

Chain CILIUM_OUTPUT (1 references)
target     prot opt source               destination
ACCEPT     all  --  anywhere             anywhere             mark match 0xa00/0xfffffeff /* cilium: ACCEPT for proxy return traffic */
MARK       all  --  anywhere             anywhere             mark match ! 0xe00/0xf00 mark match ! 0xd00/0xf00 mark match ! 0xa00/0xe00 /* cilium: host->any mark as from host */ MARK xset 0xc00/0xf00
```

호스트에서 보내는 패킷에 0xc00 이 마킹되고 Cilium 은 0xc00 이 마킹된 패킷의 ID 는 Host 로 인식한다.

```bash
# cilium node1 cilium monitor
-> endpoint 1999 flow 0x6cac68b2 , identity host->15435 state established ifindex 0 orig-ip 172.26.50.201: 172.26.50.201:43164 -> 10.0.1.185:8082 tcp ACK
-> stack flow 0x9628293d , identity 15435->host state reply ifindex 0 orig-ip 0.0.0.0: 10.0.1.185:8082 -> 172.26.50.201:43164 tcp ACK
```
