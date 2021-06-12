tunnel

![tunnel.benchmark](./tunnel.benchmark.png)

dsr

| datapath | target | DSR | http_req_duration (msecs) |
| :------- | :----- | :-- | ------------------------: |
| direct   | local  | X   |                     0.554 |
| direct   | remote | X   |                     0.818 |
| direct   | remote | O   |                     0.650 |
| vxlan    | local  | X   |                     0.542 |
| vxlan    | remote | X   |                     1.896 |
| vxlan    | remote | O   |                     1.263 |
