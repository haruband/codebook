최근 공개된 우분투 21.10 은 컨테이너와 관련된 상당히 큰 부분이 변경되었다. **마침내 CGroupV2 가 적용되었고, 도커도 업그레이드되면서 CGroup 네임스페이스의 기본값이 Private 으로 설정되었다.** 오늘은 이로 인해 발생한 문제에 대해 자세히 살펴보도록 하자.

## _어떠한 문제가 발생했는가???_

개발 서버에 우분투 21.10 을 설치한 후, 늘 쓰던대로 쿠버네티스와 Cilium 을 설치하였는데 갑자기 서비스가 정상동작하지 않는 문제가 발생하였다. 몇 가지를 확인해 본 후, Pod 네임스페이스와 호스트 네임스페이스 모두에서 Pod 의 ClusterIP 로는 통신이 되는데, 서비스의 ClusterIP 로는 통신이 되지 않는 현상을 발견하였다. 그래서 tcpdump 로 패킷을 확인해보니 서비스의 ClusterIP 가 소켓 기반 로드밸런싱을 통해 Pod 의 ClusterIP 로 변경되지 않고 그대로 남아있었다. 즉, 소켓 기반 로드밸런싱이 제대로 작동하지 않는 문제였다.

## _어떻게 문제가 발생했는가???_

문제의 원인은 비교적 쉽게 파악하였는데, 아래 쿠버네티스 노드의 모든 CGROUP 에 연결된 BPF 프로그램 목록을 살펴보자.

```bash
$ bpftool cgroup tree
CgroupPath
ID       AttachType      AttachFlags     Name
...
/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-podf8371831_8021_4722_af27_93c925d25a14.slice/docker-5cecdc399e2fa339d62a5b276331d8a5875fff7898a09d1ba1f5d710ecb12f13.scope
    62       device          multi
/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-podf8371831_8021_4722_af27_93c925d25a14.slice/docker-fbbef81081fd1fdf7653041c79cf8969be138b5bbd57db50de28cba35fd65910.scope
    68       device          multi
    728      connect4
    723      connect6
    730      post_bind4
    725      post_bind6
    731      sendmsg4
    726      sendmsg6
    732      recvmsg4
    727      recvmsg6
    729      getpeername4
    724      getpeername6
...
```

소켓 기반 로드밸런싱에 사용되는 BPF 프로그램이 루트 CGROUP 이 아닌 특정 컨테이너의 하위 CGROUP 에 연결되어 있었다. 그리고 아래 출력을 보면 알 수 있듯이, 해당 컨테이너는 다름 아닌 Cilium 에이전트 컨테이너였다. 이는 심각한 문제를 발생시키는데, 이유는 **소켓 시스템콜은 자신이 속한 CGROUP 만이 아니라 루트 CGROUP 까지 모든 부모 CGROUP 에 연결된 BPF 프로그램을 실행하므로, Cilium 에이전트는 루트 CGROUP 에만 필요한 BPF 프로그램을 연결하여 소켓 기반 로드밸런싱을 처리하기 때문이다.**

```bash
$ kubectl get pods cilium-mldd6 -n kube-system -o yaml
apiVersion: v1
kind: Pod
metadata:
...
status:
  containerStatuses:
  - containerID: docker://fbbef81081fd1fdf7653041c79cf8969be138b5bbd57db50de28cba35fd65910
    name: cilium-agent
...
```

소켓 기반 로드밸런싱에 사용되는 BPF 프로그램은 Cilium 에이전트에서 CGroupV2 파일시스템을 /run/cilium/cgroupv2 디렉토리에 마운트한 후 루트 CGROUP 인 최상위 디렉토리에 연결하는데, 우분투 21.10 에서는 도커의 CGroup 네임스페이스의 기본값이 Private 으로 변경되어 최상위 디렉토리가 루트 CGROUP 이 아닌 해당 컨테이너의 CGROUP 이 되면서 발생한 문제였다.

## _어떻게 문제를 해결했는가???_

```bash
$ bpftool cgroup tree
CgroupPath
ID       AttachType      AttachFlags     Name
/sys/fs/cgroup
1506     connect4
1501     connect6
1508     post_bind4
1503     post_bind6
1509     sendmsg4
1504     sendmsg6
1510     recvmsg4
1505     recvmsg6
1507     getpeername4
1502     getpeername6
...
/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-podf8371831_8021_4722_af27_93c925d25a14.slice/docker-5cecdc399e2fa339d62a5b276331d8a5875fff7898a09d1ba1f5d710ecb12f13.scope
    62       device          multi
/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-podf8371831_8021_4722_af27_93c925d25a14.slice/docker-fbbef81081fd1fdf7653041c79cf8969be138b5bbd57db50de28cba35fd65910.scope
    68       device          multi
...
```
