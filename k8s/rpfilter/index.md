리눅스는 패킷의 출발지 주소를 마음대로 조작해서 공격하는 IP 스푸핑 공격을 막기위해 RPFilter (Reverse Path Filter) 라는 기능을 제공한다. **이 기능은 간단히 소개하면 특정 네트워크 장치로 들어온 패킷이 동일한 네트워크 장치로 나갈 수 있는지를 확인하는 것인데, 이는 해당 패킷의 출발지 주소를 목적지 주소로 하는 라우팅 정보(FIB)를 이용하여 확인한다.** 오늘은 이 기능으로 인해 발생한 문제에 대해 자세히 살펴보도록 하자.

## _어떠한 문제가 발생했는가???_

```bash
# kubectl get pods -o wide -n kube-system
NAMESPACE     NAME                              READY   STATUS    RESTARTS   AGE     IP              NODE    NOMINATED NODE   READINESS GATES
...
kube-system   coredns-749558f7dd-w6jdj          0/1     Running   0          2m59s   10.0.0.113      node0   <none>           <none>
kube-system   coredns-749558f7dd-xppfp          0/1     Running   0          2m59s   10.0.0.250      node0   <none>           <none>
...

# kubectl describe pod coredns-749558f7dd-w6jdj -n kube-system
Name:                 coredns-749558f7dd-w6jdj
Namespace:            kube-system
...
Events:
  Type     Reason                  Age    From               Message
  ----     ------                  ----   ----               -------
  Warning  Unhealthy  4m51s                 kubelet  Readiness probe failed: Get "http://10.0.0.113:8181/ready": dial tcp 10.0.0.113:8181: i/o timeout (Client.Timeout exceeded while awaiting headers)
  Warning  Unhealthy  3m7s (x5 over 3m47s)  kubelet  Liveness probe failed: Get "http://10.0.0.113:8080/health": context deadline exceeded (Client.Timeout exceeded while awaiting headers)

# systemd-cgls
Control group /:
...
  │ ├─kubepods-burstable-poddcf43d8a_eee1_466f_be7e_59e917cb8528.slice
  │ │ └─crio-17b0acd8c8c28fa7daabfafa4b096fa0eb1bdc3f09dc25d206c507f7d2cf849d.scope …
  │ │   └─556675 /coredns -conf /etc/coredns/Corefile
...

# nsenter -t 556675 -n bash
<556675> # ip addr show
416: eth0@if417: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 0a:50:d2:29:32:ba brd ff:ff:ff:ff:ff:ff link-netns 621e8a57-2e46-4753-b9f1-c947fed6bdf6
    inet 10.0.0.113/32 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::850:d2ff:fe29:32ba/64 scope link
       valid_lft forever preferred_lft forever

# ip addr show
2: eno1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether a4:ae:12:2c:26:31 brd ff:ff:ff:ff:ff:ff
    altname enp0s31f6
    inet 172.26.50.200/24 brd 172.26.50.255 scope global eno1
       valid_lft forever preferred_lft forever
    inet6 fe80::a6ae:12ff:fe2c:2631/64 scope link
       valid_lft forever preferred_lft forever
5: cilium_host@cilium_net: <BROADCAST,MULTICAST,NOARP,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 32:a7:e5:1c:b8:a5 brd ff:ff:ff:ff:ff:ff
    inet 10.0.0.253/32 scope link cilium_host
       valid_lft forever preferred_lft forever
    inet6 fe80::30a7:e5ff:fe1c:b8a5/64 scope link
       valid_lft forever preferred_lft forever
...
417: lxc3c160d6c7aa0@if416: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 8a:95:96:c7:1f:85 brd ff:ff:ff:ff:ff:ff link-netns 36b7afe0-19f3-47cc-be7b-842bbfe9c960
    inet6 fe80::8895:96ff:fec7:1f85/64 scope link
       valid_lft forever preferred_lft forever

# route -n
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
0.0.0.0         172.26.50.1     0.0.0.0         UG    0      0        0 eno1
10.0.0.0        10.0.0.253      255.255.255.0   UG    0      0        0 cilium_host
10.0.0.253      0.0.0.0         255.255.255.255 UH    0      0        0 cilium_host
10.0.1.0        172.26.50.201   255.255.255.0   UG    0      0        0 eno1
172.17.0.0      0.0.0.0         255.255.0.0     U     0      0        0 docker0
172.26.50.0     0.0.0.0         255.255.255.0   U     0      0        0 eno1

# ip route get 10.0.0.113
10.0.0.113 dev cilium_host src 10.0.0.253 uid 0
    cache

# journal -k -f
...
Dec 09 06:46:20 node0 kernel: IPv4: martian source 10.0.0.253 from 10.0.0.113, on dev lxc3c160d6c7aa0
Dec 09 06:46:20 node0 kernel: ll header: 00000000: 8a 95 96 c7 1f 85 0a 50 d2 29 32 ba 08 00
...
```

## _어떻게 문제가 발생했는가???_

```bash
# cat /etc/sysctl.d/10-network-security.conf
net.ipv4.conf.default.rp_filter=2
net.ipv4.conf.all.rp_filter=2

# cat /usr/lib/udev/rules.d/99-systemd.rules
...
# Apply sysctl variables to network devices (and only to those) as they appear.
ACTION=="add", SUBSYSTEM=="net", KERNEL!="lo", RUN+="/lib/systemd/systemd-sysctl --prefix=/net/ipv4/conf/$name --prefix=/net/ipv4/neigh/$name --prefix=/net/ipv6/conf/$name --prefix=/net/ipv6/neigh/$name"
...

# sysctl net.ipv4.conf.lxc3c160d6c7aa0.rp_filter
net.ipv4.conf.lxc3c160d6c7aa0.rp_filter = 2
```

## _어떻게 문제를 해결했는가???_

```bash
# kubectl get pods -o wide -n kube-system
NAMESPACE     NAME                              READY   STATUS    RESTARTS   AGE   IP              NODE    NOMINATED NODE   READINESS GATES
kube-system   coredns-749558f7dd-d96rn          1/1     Running   0          82s   10.0.0.40       node0   <none>           <none>
kube-system   coredns-749558f7dd-dhfdw          1/1     Running   0          82s   10.0.0.244      node0   <none>           <none>

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

# ip route get 10.0.0.40
10.0.0.40 dev lxc3b28c7d86cd3 src 172.26.50.200 uid 0
    cache
```

```bash
# cat /etc/sysctl.d/99-override_cilium_rp_filter.conf
net.ipv4.conf.lxc*.rp_filter=0

# sysctl net.ipv4.conf.lxc3b28c7d86cd3.rp_filter
net.ipv4.conf.lxc3b28c7d86cd3.rp_filter = 0
```
