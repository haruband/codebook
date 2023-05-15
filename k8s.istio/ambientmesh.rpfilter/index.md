오늘은 Istio 에서 공개한 AmbientMesh 를 처음 설치할 때 겪었던 문제에 대해 소개하고자 한다. 주로 사용하는 Cilium 은 아직 지원되지 않기 때문에 Calico(+IPTables)를 CNI 로 사용하였다.

간단히 AmbientMesh 를 설치했는데, Ztunnel 이 정상적인 동작을 하지 않았고, 아래와 같은 로그가 반복적으로 출력되고 있었다.

```bash
...
2023-05-11T08:37:59.078700Z  WARN xds{id=1}: ztunnel::xds::client: XDS client connection error: gRPC connection error (Unknown error): client error (Connect), retrying in 20ms
...
```

정확한 원인을 파악하기 위해, Ztunnel 의 네트워크 네임스페이스(nsenter)에서 송수신 패킷을 확인(tcpdump)해보니, 아래와 같이 DNS 요청은 나가는데 응답이 오지 않는 상황이었다. 그래서 호스트 네트워크 네임스페이스에서 확인해보니 DNS 요청이 외부로 나가지 않고 있었다. 이런 경우에는 요청 패킷이 호스트에서 드롭되고 있을 가능성이 높고, 주요 원인으로 생각해볼 수 있는 것은 바로 RPFilter 이다.

RPFilter 는 해커들이 DDoS 공격을 할 때 주로 사용하는 IP 스푸핑(Spoofing)을 막기 위해 사용되는 기술이다. IP 스푸핑은 패킷의 출발지 주소를 임의로 조작하여 원하는 결과를 얻어내는 기술이고, RPFilter 는 응답 패킷을 출발지 주소로 동일한 네트워크 장치를 이용하여 전달할 수 있는지를 확인해서 IP 스푸핑을 방지하는 기술이다.

```bash
$ nsenter -t $(pidof ztunnel) -n
$ tcpdump -xxx -n
...
01:30:01.942451 IP 10.69.11.13.53562 > 172.16.0.10.53: 9568+ A? istiod.istio-system.svc.istio-system.svc.cluster.local. (72)
...
```

```bash
$ sysctl -a | grep "\.rp_filter"
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.cali0eff241a9cd.rp_filter = 0
net.ipv4.conf.cali3cd40f41ebe.rp_filter = 0
net.ipv4.conf.cali60c4dd4afb0.rp_filter = 0
net.ipv4.conf.calic30bcf0776f.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
net.ipv4.conf.enp1s0.rp_filter = 2
net.ipv4.conf.lo.rp_filter = 0
```

```bash
$ iptables -t raw -L --line-numbers
Chain PREROUTING (policy ACCEPT)
num  target     prot opt source               destination
1    cali-PREROUTING  all  --  anywhere             anywhere             /* cali:6gwbT8clXdHdC1b1 */

Chain OUTPUT (policy ACCEPT)
num  target     prot opt source               destination
...

Chain cali-OUTPUT (1 references)
num  target     prot opt source               destination
...

Chain cali-PREROUTING (1 references)
num  target         prot opt source             destination
...
3    cali-rpf-skip  all  --  anywhere           anywhere    /* cali:PWuxTAIaFCtsg5Qa */ mark match 0x40000/0x40000
4    DROP           all  --  anywhere           anywhere    /* cali:fSSbGND7dgyemWU7 */ mark match 0x40000/0x40000 rpfilter validmark invert
...

Chain cali-from-host-endpoint (1 references)
num  target     prot opt source               destination

Chain cali-rpf-skip (1 references)
num  target     prot opt source               destination

Chain cali-to-host-endpoint (1 references)
num  target     prot opt source               destination
```

```bash
$ route -n
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
...
10.69.11.6      0.0.0.0         255.255.255.255 UH    0      0        0 calia3ea794220c
10.69.11.7      0.0.0.0         255.255.255.255 UH    0      0        0 cali51535a04511
10.69.11.9      0.0.0.0         255.255.255.255 UH    0      0        0 cali5cb21c4c214
10.69.11.10     0.0.0.0         255.255.255.255 UH    0      0        0 caliaa9bb384cef
10.69.11.14     0.0.0.0         255.255.255.255 UH    0      0        0 cali3b3bee917c9
...
```

```bash
$ ip route get 10.69.11.7
10.69.11.7 dev cali51535a04511 src 192.168.122.202 uid 1000

$ ip route get 10.69.11.13
RTNETLINK answers: Invalid argument
```

```bash
apiVersion: v1
kind: Pod
metadata:
  annotations:
    ambient.istio.io/redirection: disabled
    cni.projectcalico.org/allowedSourcePrefixes: '["10.0.0.0/8"]'
...
  labels:
    app: ztunnel
...
```

```bash
FELIX_WORKLOADSOURCESPOOFING=Any
```

```bash
$ route -n
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
...
10.69.11.6      0.0.0.0         255.255.255.255 UH    0      0        0 calia3ea794220c
10.69.11.7      0.0.0.0         255.255.255.255 UH    0      0        0 cali51535a04511
10.69.11.9      0.0.0.0         255.255.255.255 UH    0      0        0 cali5cb21c4c214
10.69.11.10     0.0.0.0         255.255.255.255 UH    0      0        0 caliaa9bb384cef
10.69.11.13     0.0.0.0         255.255.255.255 UH    0      0        0 cali3010ec13e30
10.69.11.14     0.0.0.0         255.255.255.255 UH    0      0        0 cali3b3bee917c9
...
```

```bash
$ iptables -t raw -L --line-numbers
Chain PREROUTING (policy ACCEPT)
num  target     prot opt source               destination
1    cali-PREROUTING  all  --  anywhere             anywhere             /* cali:6gwbT8clXdHdC1b1 */

Chain OUTPUT (policy ACCEPT)
num  target     prot opt source               destination
...

Chain cali-OUTPUT (1 references)
num  target     prot opt source               destination
...

Chain cali-PREROUTING (1 references)
num  target         prot opt source             destination
...
3    cali-rpf-skip  all  --  anywhere           anywhere    /* cali:PWuxTAIaFCtsg5Qa */ mark match 0x40000/0x40000
4    DROP           all  --  anywhere           anywhere    /* cali:fSSbGND7dgyemWU7 */ mark match 0x40000/0x40000 rpfilter validmark invert
...

Chain cali-from-host-endpoint (1 references)
num  target     prot opt source               destination

Chain cali-rpf-skip (1 references)
num  target     prot opt source               destination
1    ACCEPT     all  --  10.0.0.0/8           anywhere             /* cali:bSgSJ0C4gCLn3ilJ */

Chain cali-to-host-endpoint (1 references)
num  target     prot opt source               destination
```
