오늘은 Istio 에서 공개한 AmbientMesh 를 처음 설치할 때 겪었던 문제에 대해 소개하고자 한다. 주로 사용하는 Cilium 은 아직 지원되지 않기 때문에 Calico(+IPTables)를 CNI 로 사용하였다.

간단히 AmbientMesh 를 설치했는데, Ztunnel 이 정상적인 동작을 하지 않았고, 아래와 같은 로그가 반복적으로 출력되고 있었다.

```bash
...
2023-05-11T08:37:59.078700Z  WARN xds{id=1}: ztunnel::xds::client: XDS client connection error: gRPC connection error (Unknown error): client error (Connect), retrying in 20ms
...
```

정확한 원인을 파악하기 위해, Ztunnel 의 네트워크 네임스페이스(nsenter)에서 송수신 패킷을 확인(tcpdump)해보니, 아래와 같이 DNS 요청은 나가는데 응답이 오지 않는 상황이었다. 그래서 호스트 네트워크 네임스페이스에서 확인해보니 DNS 요청이 외부로 나가지 않고 있었다. 이런 경우에는 요청 패킷이 호스트에서 드롭되고 있을 가능성이 높고, 주요 원인으로 생각해볼 수 있는 것은 바로 RPFilter 이다. 이유는 Ztunnel 이 투명하게 동작하기 위해 패킷을 전달할 때 출발지 주소로 원래의 출발지 주소를 사용해서 RPFilter 에 의해 문제가 발생할 가능성이 높기 때문이다.

RPFilter 는 해커들이 DDoS 공격을 할 때 주로 사용하는 IP 스푸핑(Spoofing)을 막기 위해 사용되는 기술이다. IP 스푸핑은 패킷의 출발지 주소를 임의로 조작하여 원하는 결과를 얻어내는 기술이고, RPFilter 는 응답 패킷을 동일한 네트워크 장치를 이용하여 출발지 주소로 전달할 수 있는지를 확인해서 IP 스푸핑을 방지하는 기술이다.

```bash
$ nsenter -t $(pidof ztunnel) -n tcpdump -xxx -n
...
01:30:01.942451 IP 10.69.11.13.53562 > 172.16.0.10.53: 9568+ A? istiod.istio-system.svc.istio-system.svc.cluster.local. (72)
...
```

우선, 리눅스의 네트워크 스택에 포함되어 있는 RPFilter 기능을 사용하고 있는지를 확인해보았다. 아래와 같이 모든 파드의 호스트 네트워크 장치는 RPFilter 기능을 사용하지 않았고, 이는 Calico 에서 해당 기능 대신 IPTables 가 제공하는 RPFilter 기능을 사용하기 때문이었다.

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

아래는 Calico 가 사용하고 있는 RPFilter 관련된 IPTables 체인 목록이다. 보시는 것처럼 cali-PREROUTING 체인의 4번 룰에서 RPFilter 를 이용하여 패킷을 드롭하는 걸 볼 수 있다.

```bash
$ iptables -t raw -L --line-numbers
Chain PREROUTING (policy ACCEPT)
num  target     prot opt source               destination
1    cali-PREROUTING  all  --  anywhere             anywhere             /* cali:6gwbT8clXdHdC1b1 */

Chain cali-PREROUTING (1 references)
num  target         prot opt source             destination
...
3    cali-rpf-skip  all  --  anywhere           anywhere    /* cali:PWuxTAIaFCtsg5Qa */ mark match 0x40000/0x40000
4    DROP           all  --  anywhere           anywhere    /* cali:fSSbGND7dgyemWU7 */ mark match 0x40000/0x40000 rpfilter validmark invert
...

Chain cali-rpf-skip (1 references)
num  target     prot opt source               destination
```

그렇다면 Calico 에서도 AmbientMesh 를 사용할 수 없는 것일까? 그건 아니었고, 아래를 보면 Ztunnel 파드에 이를 해결하기 위한 설정(allowedSourcePrefixes)이 들어있는 것을 볼 수 있다. 해당 설정은 RPFilter 를 우회하기 위한 설정으로, 등록된 주소 대역은 출발지 주소로 사용할 수 있다는 의미이다. 즉, 아래와 같이 설정되었다면 Ztunnel 파드는 패킷의 출발지 주소로 10.0.0.0/8 의 주소 대역을 사용할 수 있다는 것이다.

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

그런데, Ztunnel 파드에 필요한 설정이 들어있음에도 불구하고, 왜 정상적으로 동작하지 않은 것일까? 이유는 해당 설정을 Calico 에서 사용하지 않고 있었기 때문이었다. 해당 기능을 활성화하기 위해서는 Calico 파드(calico-node)에 아래의 환경 변수를 추가해야 한다.

```bash
FELIX_WORKLOADSOURCESPOOFING=Any
```

Calico 에 해당 기능을 추가한 다음, 다시 IPTables 체인 목록을 확인해보면 4번 룰(DROP)보다 앞에 있는 3번 룰(cali-rpf-skip)의 체인에 새로운 룰이 추가된 것을 볼 수 있다. cali-rpf-skip 체인에 추가된 1번 룰은 위에서 설정한 대로 출발지 주소가 10.0.0.0/8 이면 패킷을 허용(ACCEPT)한다는 의미이다.

```bash
$ iptables -t raw -L --line-numbers
Chain PREROUTING (policy ACCEPT)
num  target     prot opt source               destination
1    cali-PREROUTING  all  --  anywhere             anywhere             /* cali:6gwbT8clXdHdC1b1 */

Chain cali-PREROUTING (1 references)
num  target         prot opt source             destination
...
3    cali-rpf-skip  all  --  anywhere           anywhere    /* cali:PWuxTAIaFCtsg5Qa */ mark match 0x40000/0x40000
4    DROP           all  --  anywhere           anywhere    /* cali:fSSbGND7dgyemWU7 */ mark match 0x40000/0x40000 rpfilter validmark invert
...

Chain cali-rpf-skip (1 references)
num  target     prot opt source               destination
1    ACCEPT     all  --  10.0.0.0/8           anywhere             /* cali:bSgSJ0C4gCLn3ilJ */
```

지금까지 AmbientMesh 를 처음 설치하면서 겪었던 문제에 대해 소개하였다. AmbientMesh 뿐 아니라 대부분의 CNI 는 패킷을 조작하여 원하는 기능을 수행하는 경우가 많기 때문에 RPFilter 에 대해서는 충분히 이해하고 있을 필요가 있다.
