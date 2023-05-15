```bash
...
2023-05-11T08:37:59.078700Z  WARN xds{id=1}: ztunnel::xds::client: XDS client connection error: gRPC connection error (Unknown error): client error (Connect), retrying in 20ms
...
```

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
