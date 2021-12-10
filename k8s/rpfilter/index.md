리눅스는 패킷의 출발지 주소를 마음대로 조작해서 공격하는 IP 스푸핑 공격을 막기위해 RPFilter (Reverse Path Filter) 라는 기능을 제공한다. **이 기능은 간단히 소개하면 특정 네트워크 장치로 들어온 패킷이 동일한 네트워크 장치로 나갈 수 있는지를 확인하는 것인데, 이는 해당 패킷의 출발지 주소를 목적지 주소로 하는 라우팅 정보(FIB)를 이용하여 확인한다.** 오늘은 이 기능으로 인해 발생한 문제에 대해 자세히 살펴보도록 하자.

## _어떠한 문제가 발생했는가???_

개발 서버에 쿠버네티스와 Cilium 을 설치하였는데 아래와 같이 coredns 가 동작하지 않는 문제가 발생하였다. 정확한 문제를 파악하기 위해 관련 정보들을 하나씩 분석해보도록 하자.

```bash
# kubectl get pods -o wide -n kube-system
NAMESPACE     NAME                              READY   STATUS    RESTARTS   AGE     IP              NODE    NOMINATED NODE   READINESS GATES
...
kube-system   coredns-749558f7dd-w6jdj          0/1     Running   0          2m59s   10.0.0.113      node0   <none>           <none>
kube-system   coredns-749558f7dd-xppfp          0/1     Running   0          2m59s   10.0.0.250      node0   <none>           <none>
...
```

아래와 같이 원인을 알 수 없는 이유로 상태 확인이 실패하고 있었다. 현재 상황에서 유추해볼 수 있는 것은 상태 확인을 하는 호스트(kubelet)와 Pod(coredns) 간의 네트워크에 어떠한 문제가 생긴 것이다. 그래서 호스트와 Pod(coredns) 양쪽에서 tcpdump 로 확인해보니, 호스트에서 보낸 패킷을 Pod(coredns) 에서 받은 후 응답 패킷을 보냈지만 호스트에서는 해당 응답 패킷을 받지 못하였다. 일단 호스트가 Pod(coredns) 에서 보낸 응답 패킷을 알 수 없는 이유로 드롭하고 있다고 볼 수 있다.

```bash
# kubectl describe pod coredns-749558f7dd-w6jdj -n kube-system
Name:                 coredns-749558f7dd-w6jdj
Namespace:            kube-system
...
Events:
  Type     Reason                  Age    From               Message
  ----     ------                  ----   ----               -------
  Warning  Unhealthy  4m51s                 kubelet  Readiness probe failed: Get "http://10.0.0.113:8181/ready": dial tcp 10.0.0.113:8181: i/o timeout (Client.Timeout exceeded while awaiting headers)
  Warning  Unhealthy  3m7s (x5 over 3m47s)  kubelet  Liveness probe failed: Get "http://10.0.0.113:8080/health": context deadline exceeded (Client.Timeout exceeded while awaiting headers)
```

이럴 경우 대부분은 패킷의 잘못된 출발지 주소로 인해 발생하는 마션소스(martian source) 문제이다. 해당 문제가 맞는지 확인해보자.

```bash
# sysctl -w net.ipv4.conf.all.log_martians=1

# journal -k -f
...
Dec 09 06:46:20 node0 kernel: IPv4: martian source 10.0.0.253 from 10.0.0.113, on dev lxc3c160d6c7aa0
Dec 09 06:46:20 node0 kernel: ll header: 00000000: 8a 95 96 c7 1f 85 0a 50 d2 29 32 ba 08 00
...
```

위와 같이 마션소스 로그를 활성화한 후 커널 로그를 확인해보니 예상대로 관련 로그를 찾을 수 있었다. 위의 로그는 lxc3c160d6c7aa0 네트워크 장치에서 출발지 주소(10.0.0.113)와 목적지 주소(10.0.0.253)인 패킷을 드롭했다는 내용이다. 이제 왜 이 패킷이 드롭되었는지 분석해보도록 하자.

우선 아래와 같이 Pod(coredns) 의 네트워크 장치와 연결된 호스트의 네트워크 장치(VETH)를 확인해보자. coredns 의 PID(556675) 를 이용하여 nsenter 로 네트워크 네임스페이스 변경 후 네트워크 장치를 확인해보면 416 번 네트워크 장치를 볼 수 있다.

```bash
# systemd-cgls
Control group /:
...
  │ ├─kubepods-burstable-poddcf43d8a_eee1_466f_be7e_59e917cb8528.slice
  │ │ └─crio-17b0acd8c8c28fa7daabfafa4b096fa0eb1bdc3f09dc25d206c507f7d2cf849d.scope …
  │ │   └─556675 /coredns -conf /etc/coredns/Corefile
...

# nsenter -t 556675 -n bash
# ip addr show
416: eth0@if417: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 0a:50:d2:29:32:ba brd ff:ff:ff:ff:ff:ff link-netns 621e8a57-2e46-4753-b9f1-c947fed6bdf6
    inet 10.0.0.113/32 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::850:d2ff:fe29:32ba/64 scope link
       valid_lft forever preferred_lft forever
```

해당 네트워크 장치 이름(eth0@if417)은 417 번 네트워크 장치와 연결된 장치라는 의미이고, 아래와 같이 호스트에서 해당 네트워크 장치인 lxc3c160d6c7aa0 를 찾을 수 있다. 즉, 위의 마션소스 로그는 Pod(coredns) 과 연결된 호스트의 네트워크 장치(lxc3c160d6c7aa0)에서 응답 패킷을 처리하는 동안 발생한 것이다.

```bash
# ip addr show
...
417: lxc3c160d6c7aa0@if416: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 8a:95:96:c7:1f:85 brd ff:ff:ff:ff:ff:ff link-netns 36b7afe0-19f3-47cc-be7b-842bbfe9c960
    inet6 fe80::8895:96ff:fec7:1f85/64 scope link
       valid_lft forever preferred_lft forever
```

그렇다면 왜 호스트의 네트워크 장치(lxc3c160d6c7aa0)에서 해당 응답 패킷을 드롭한 것일까? 이는 처음 소개했던 RPFilter 의 동작 원리를 이용하면 간단히 확인할 수 있다. 아래와 같이 응답 패킷의 출발지 주소(10.0.0.113)를 목적지 주소로 하는 라우팅 정보(FIB)를 확인해보자.

```bash
# ip route get 10.0.0.113
10.0.0.113 dev cilium_host src 10.0.0.253 uid 0

# ip addr show
...
5: cilium_host@cilium_net: <BROADCAST,MULTICAST,NOARP,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 32:a7:e5:1c:b8:a5 brd ff:ff:ff:ff:ff:ff
    inet 10.0.0.253/32 scope link cilium_host
       valid_lft forever preferred_lft forever
    inet6 fe80::30a7:e5ff:fe1c:b8a5/64 scope link
       valid_lft forever preferred_lft forever
```

위의 라우팅 정보를 보면 호스트에서 10.0.0.113 으로 패킷을 전송할 때는 10.0.0.253 을 출발지 주소로 이용하여 cilium_host 네트워크 장치로 보낸다는 것을 알 수 있다. 그리고 해당 라우팅 정보가 선택된 이유는 현재 라우팅 테이블이 아래와 같이 구성되어 있기 때문이다. 즉, 목적지 주소가 10.0.0.0/24 인 모든 패킷은 cilium_host 네트워크 장치로 전달된다.

```bash
# route -n
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
0.0.0.0         172.26.50.1     0.0.0.0         UG    0      0        0 eno1
10.0.0.0        10.0.0.253      255.255.255.0   UG    0      0        0 cilium_host
10.0.0.253      0.0.0.0         255.255.255.255 UH    0      0        0 cilium_host
10.0.1.0        172.26.50.201   255.255.255.0   UG    0      0        0 eno1
172.17.0.0      0.0.0.0         255.255.0.0     U     0      0        0 docker0
172.26.50.0     0.0.0.0         255.255.255.0   U     0      0        0 eno1
```

여기까지 분석한 내용들을 정리해보면, 호스트에서 패킷을 보낼 때는 cilium_host 네트워크 장치를 사용했지만, 응답 패킷은 lxc3c160d6c7aa0 네트워크 장치에서 처리하기 때문에 RPFilter 에 의해 해당 응답 패킷이 드롭되는 것이다. 하지만, 패킷을 보내는 장치와 받는 장치가 다른 것은 Cilium 에서는 일반적인 동작 방식 중 하나이기 때문에 Cilium 은 기본적으로 자신이 관리하는 모든 네트워크 장치에서 RPFilter 를 사용하지 않도록 설정해둔다. 즉, **해당 문제는 아래와 같이 Cilium 에서 사용하지 않도록 설정해둔 RPFilter 가 알 수 없는 이유로 사용되면서 발생한 문제이다.**

```bash
# sysctl net.ipv4.conf.lxc3c160d6c7aa0.rp_filter
net.ipv4.conf.lxc3c160d6c7aa0.rp_filter = 2
```

## _어떻게 문제가 발생했는가???_

Cilium 은 새로운 네트워크 장치를 만들 때 마다 RPFilter 를 사용하지 않도록 설정한다. 그런데 왜 RPFilter 가 사용된 것일까? 그 이유는 새로운 네트워크 장치가 추가될 때 마다 UDEV 에 의해 systemd-sysctl 이 실행되는데, 그 때 사용되는 모든 네트워크 장치의 기본 설정이 RPFilter 를 사용하는 것이기 때문이다. 즉, **Cilium 에서 새로운 네트워크 장치를 만든 직후 RPFilter 를 사용하지 않도록 설정하지만, 곧이어 UDEV 에 의해 실행되는 systemd-sysctl 이 해당 네트워크 장치의 RPFilter 를 다시 사용하도록 만들어 버린 것이다.**

```bash
# cat /usr/lib/udev/rules.d/99-systemd.rules
...
ACTION=="add", SUBSYSTEM=="net", KERNEL!="lo", RUN+="/lib/systemd/systemd-sysctl --prefix=/net/ipv4/conf/$name --prefix=/net/ipv4/neigh/$name --prefix=/net/ipv6/conf/$name --prefix=/net/ipv6/neigh/$name"

# cat /etc/sysctl.d/10-network-security.conf
net.ipv4.conf.default.rp_filter=2
net.ipv4.conf.all.rp_filter=2
```

## _어떻게 문제를 해결했는가???_

해당 문제를 해결할 수 있는 방법 두 가지를 소개하도록 하겠다.

첫 번째는 Cilium 이 제공하는 엔드포인트 라우팅 기능을 사용하는 것이다. 이 기능을 사용하면, 아래와 같이 각각의 엔드포인트를 위한 라우팅 정보가 추가된다. 즉, 목적지 주소가 10.0.0.0/24 인 모든 패킷을 cilium_host 네트워크 장치를 통해 전달하는 것이 아니고, 각각의 목적지 주소에 해당하는 Pod 과 연결된 네트워크 장치로 패킷을 바로 전달해버리는 것이다.

```bash
# route -n
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
0.0.0.0         172.26.50.1     0.0.0.0         UG    0      0        0 eno1
10.0.0.0        10.0.0.253      255.255.255.0   UG    0      0        0 cilium_host
10.0.0.40       0.0.0.0         255.255.255.255 UH    0      0        0 lxc3b28c7d86cd3
10.0.0.66       0.0.0.0         255.255.255.255 UH    0      0        0 lxc_health
10.0.0.244      0.0.0.0         255.255.255.255 UH    0      0        0 lxcd27b1006c4c8
10.0.0.253      0.0.0.0         255.255.255.255 UH    0      0        0 cilium_host
10.0.1.0        172.26.50.201   255.255.255.0   UG    0      0        0 eno1
172.17.0.0      0.0.0.0         255.255.0.0     U     0      0        0 docker0
172.26.50.0     0.0.0.0         255.255.255.0   U     0      0        0 eno1
```

아래의 Pod(coredns) 의 주소인 10.0.0.40 이 lxc3b28c7d86cd3 네트워크 장치로 바로 전달되는 라우팅 정보를 확인할 수 있다.

```bash
# kubectl get pods -o wide -n kube-system
NAMESPACE     NAME                              READY   STATUS    RESTARTS   AGE   IP              NODE    NOMINATED NODE   READINESS GATES
kube-system   coredns-749558f7dd-d96rn          1/1     Running   0          82s   10.0.0.40       node0   <none>           <none>
kube-system   coredns-749558f7dd-dhfdw          1/1     Running   0          82s   10.0.0.244      node0   <none>           <none>

# ip route get 10.0.0.40
10.0.0.40 dev lxc3b28c7d86cd3 src 172.26.50.200 uid 0
```

두 번째는 systemd-sysctl 이 사용하는 기본 설정을 변경해버리는 것이다. lxc 로 시작되는 이름을 가진 모든 네트워크 장치의 RPFilter 를 사용하지 않도록 설정해두면 된다.

```bash
# cat /etc/sysctl.d/99-override_cilium_rp_filter.conf
net.ipv4.conf.lxc*.rp_filter=0

# sysctl net.ipv4.conf.lxc3b28c7d86cd3.rp_filter
net.ipv4.conf.lxc3b28c7d86cd3.rp_filter = 0
```

여기까지 RPFilter 로 인해 발생하는 문제와 해결책에 대해 살펴보았다.
