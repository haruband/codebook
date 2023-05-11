```bash
$ kubectl logs istio-cni-node-smkbc -n istio-system
...
2023-05-11T08:58:12.311527Z	info	install	CNI config: {
  "cniVersion": "0.3.1",
  "name": "istio-cni",
  "type": "istio-cni",
  "log_level": "info",
  "log_uds_address": "/var/run/istio-cni/log.sock",
  "ambient_enabled": true,
  "kubernetes": {
      "kubeconfig": "/etc/cni/net.d/ZZZ-istio-cni-kubeconfig",
      "cni_bin_dir": "/opt/cni/bin",
      "exclude_namespaces": [ "kube-system" ]
  }
}
2023-05-11T08:58:12.311944Z	info	install	CNI config file /host/etc/cni/net.d/05-cilium.conflist exists. Proceeding.
2023-05-11T08:58:12.312576Z	info	install	Created CNI config /host/etc/cni/net.d/05-cilium.conflist
2023-05-11T08:58:12.312586Z	info	install	CNI configuration and binaries reinstalled.
2023-05-11T08:58:12.312965Z	info	install	Detect changes to the CNI configuration and binaries, attempt reinstalling...
...
```

```bash
$ kubectl logs cilium-62984 -n kube-system
...
level=info msg="Activity in /host/etc/cni/net.d/, re-generating CNI configuration" subsys=cni-config
level=info msg="Activity in /host/etc/cni/net.d/, re-generating CNI configuration" subsys=cni-config
level=info msg="Generating CNI configuration file with mode none" subsys=cni-config
level=info msg="Activity in /host/etc/cni/net.d/, re-generating CNI configuration" subsys=cni-config
level=info msg="Activity in /host/etc/cni/net.d/, re-generating CNI configuration" subsys=cni-config
...
```

```bash
node0 $ cat /etc/cni/net.d/05-cilium.conflist
{
  "cniVersion": "0.3.1",
  "name": "cilium",
  "plugins": [
    {
      "enable-debug": true,
      "log-file": "/var/run/cilium/cilium-cni.log",
      "type": "cilium-cni"
    },
    {
      "ambient_enabled": true,
      "kubernetes": {
        "cni_bin_dir": "/opt/cni/bin",
        "exclude_namespaces": [
          "kube-system"
        ],
        "kubeconfig": "/etc/cni/net.d/ZZZ-istio-cni-kubeconfig"
      },
      "log_level": "info",
      "log_uds_address": "/var/run/istio-cni/log.sock",
      "name": "istio-cni",
      "type": "istio-cni"
    }
  ]
}
```
