```bash
...
2023-05-11T08:37:59.078700Z  WARN xds{id=1}: ztunnel::xds::client: XDS client connection error: gRPC connection error (Unknown error): client error (Connect), retrying in 20ms
...
```

```bash
node0 $ iptables -t raw -L --line-numbers
Chain PREROUTING (policy ACCEPT)
num  target     prot opt source               destination
1    cali-PREROUTING  all  --  anywhere             anywhere             /* cali:6gwbT8clXdHdC1b1 */

Chain OUTPUT (policy ACCEPT)
num  target     prot opt source               destination
1    cali-OUTPUT  all  --  anywhere             anywhere             /* cali:tVnHkvAo15HuiPy0 */

Chain cali-OUTPUT (1 references)
num  target     prot opt source               destination
1    MARK       all  --  anywhere             anywhere             /* cali:njdnLwYeGqBJyMxW */ MARK and 0xfff0ffff
2    cali-to-host-endpoint  all  --  anywhere             anywhere             /* cali:rz86uTUcEZAfFsh7 */
3    ACCEPT     all  --  anywhere             anywhere             /* cali:pN0F5zD0b8yf9W1Z */ mark match 0x10000/0x10000

Chain cali-PREROUTING (1 references)
num  target     prot opt source               destination
1    MARK       all  --  anywhere             anywhere             /* cali:XFX5xbM8B9qR10JG */ MARK and 0xfff0ffff
2    MARK       all  --  anywhere             anywhere             /* cali:EWMPb0zVROM-woQp */ MARK or 0x40000
3    cali-rpf-skip  all  --  anywhere             anywhere             /* cali:PWuxTAIaFCtsg5Qa */ mark match 0x40000/0x40000
4    DROP       all  --  anywhere             anywhere             /* cali:fSSbGND7dgyemWU7 */ mark match 0x40000/0x40000 rpfilter validmark invert
5    cali-from-host-endpoint  all  --  anywhere             anywhere             /* cali:ImU0-4Rl2WoOI9Ou */ mark match 0x0/0x40000
6    ACCEPT     all  --  anywhere             anywhere             /* cali:lV4V2MPoMBf0hl9T */ mark match 0x10000/0x10000

Chain cali-from-host-endpoint (1 references)
num  target     prot opt source               destination

Chain cali-rpf-skip (1 references)
num  target     prot opt source               destination

Chain cali-to-host-endpoint (1 references)
num  target     prot opt source               destination
```

```bash
node0 $ sysctl -a | grep "\.rp_filter"
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.cali0eff241a9cd.rp_filter = 0
net.ipv4.conf.cali3cd40f41ebe.rp_filter = 0
net.ipv4.conf.cali60c4dd4afb0.rp_filter = 0
net.ipv4.conf.calic30bcf0776f.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
net.ipv4.conf.enp1s0.rp_filter = 2
net.ipv4.conf.lo.rp_filter = 0
net.ipv4.conf.tunl0.rp_filter = 2
```

```bash
node0 $ iptables -t raw -L --line-numbers
Chain PREROUTING (policy ACCEPT)
num  target     prot opt source               destination
1    cali-PREROUTING  all  --  anywhere             anywhere             /* cali:6gwbT8clXdHdC1b1 */

Chain OUTPUT (policy ACCEPT)
num  target     prot opt source               destination
1    cali-OUTPUT  all  --  anywhere             anywhere             /* cali:tVnHkvAo15HuiPy0 */

Chain cali-OUTPUT (1 references)
num  target     prot opt source               destination
1    MARK       all  --  anywhere             anywhere             /* cali:njdnLwYeGqBJyMxW */ MARK and 0xfff0ffff
2    cali-to-host-endpoint  all  --  anywhere             anywhere             /* cali:rz86uTUcEZAfFsh7 */
3    ACCEPT     all  --  anywhere             anywhere             /* cali:pN0F5zD0b8yf9W1Z */ mark match 0x10000/0x10000

Chain cali-PREROUTING (1 references)
num  target     prot opt source               destination
1    MARK       all  --  anywhere             anywhere             /* cali:XFX5xbM8B9qR10JG */ MARK and 0xfff0ffff
2    MARK       all  --  anywhere             anywhere             /* cali:EWMPb0zVROM-woQp */ MARK or 0x40000
3    cali-rpf-skip  all  --  anywhere             anywhere             /* cali:PWuxTAIaFCtsg5Qa */ mark match 0x40000/0x40000
4    DROP       all  --  anywhere             anywhere             /* cali:fSSbGND7dgyemWU7 */ mark match 0x40000/0x40000 rpfilter validmark invert
5    cali-from-host-endpoint  all  --  anywhere             anywhere             /* cali:ImU0-4Rl2WoOI9Ou */ mark match 0x0/0x40000
6    ACCEPT     all  --  anywhere             anywhere             /* cali:lV4V2MPoMBf0hl9T */ mark match 0x10000/0x10000

Chain cali-from-host-endpoint (1 references)
num  target     prot opt source               destination

Chain cali-rpf-skip (1 references)
num  target     prot opt source               destination
1    ACCEPT     all  --  10.0.0.0/8           anywhere             /* cali:bSgSJ0C4gCLn3ilJ */

Chain cali-to-host-endpoint (1 references)
num  target     prot opt source               destination
```