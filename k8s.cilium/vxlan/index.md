Wow! I love blogging so much already.

Did you know that "despite its name, salted duck eggs can also be made from
chicken eggs, though the taste and texture will be somewhat different, and the
egg yolk will be less rich."?

![cilium.vxlan](./cilium-vxlan.png)

Yeah, I didn't either.

```
haruband@master:~$ route -n
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
0.0.0.0         172.26.50.1     0.0.0.0         UG    0      0        0 eno1
10.0.0.0        10.0.0.147      255.255.255.0   UG    0      0        0 cilium_host
10.0.0.147      0.0.0.0         255.255.255.255 UH    0      0        0 cilium_host
10.0.1.0        10.0.0.147      255.255.255.0   UG    0      0        0 cilium_host
172.17.0.0      0.0.0.0         255.255.0.0     U     0      0        0 docker0
172.26.50.0     0.0.0.0         255.255.255.0   U     0      0        0 eno1
```
