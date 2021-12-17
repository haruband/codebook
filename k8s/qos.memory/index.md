쿠버네티스는 리눅스 커널이 제공하는 CGroupV2 기능을 이용하여 다양한 QoS 기능을 제공하고 있다.

## _프로세스가 새로운 메모리를 요청할 때 무슨 일이 생기는가?_

- 새로운 메모리를 할당받는다. (익명 페이지 or 페이지 캐시)
- 현재 CGROUP 의 메모리 사용량을 확인한다.
- 메모리 초과 사용시, 초과된 메모리를 모두 반환한다.
- 메모리 반환 실패시, 해당 프로세스는 종료된다.

## _누가/왜 프로세스를 강제로 종료시키는가?_

- 커널은 프로세스가 속해있는 CGROUP 의 메모리 한도를 초과한 프로세스를 종료한다.
- 커널은 전체 메모리 한도를 초과했을 때 우선순위를 계산해서 특정 프로세스 혹은 특정 CGROUP 을 종료한다.
- 쿠버네티스는 설정해놓은 메모리 한도를 초과했을 때 우선순위를 계산해서 특정 Pod 을 종료한다.

## _메모리를 초과해서 사용하면 무슨 일이 생기는가?_

페이지 캐시는 언제든 반환할 수 있기 때문에 CGROUP 이 메모리를 초과해서 사용하면 반환해서 종료를 피할 수 있다. 하지만 익명 페이지는 스왑이 없으면 반환이 불가능하기 때문에 메모리를 초과해서 사용하면 해당 프로세스는 종료된다.

1G 메모리에서 4G 파일을 두 번째 읽을 때.

```bash
# cat /sys/fs/cgroups/.../memory.stat
anon=59322368 file=1003139072

# cat /sys/fs/cgroups/.../io.stat
rbytes=5329436672 wbytes=5749862400 rios=42989 wios=350636 dbytes=0 dios=0

$ md5sum file
real    0m29.512s
user    0m11.805s
sys     0m2.344s

# cat /sys/fs/cgroups/.../memory.stat
anon=59322368 file=1003167744

# cat /sys/fs/cgroups/.../io.stat
rbytes=9624522752 wbytes=5749862400 rios=59394 wios=350636 dbytes=0 dios=0
```

8G 메모리에서 4G 파일을 두 번째 읽을 때.

```bash
# cat /sys/fs/cgroups/.../memory.stat
anon=59346944 file=4297256960

# cat /sys/fs/cgroups/.../io.stat
rbytes=4326559744 wbytes=4294987776 rios=20574 wios=4135 dbytes=0 dios=0

$ md5sum file
real    0m6.500s
user    0m5.949s
sys     0m0.544s

# cat /sys/fs/cgroups/.../memory.stat
anon=59346944 file=4297871360

# cat /sys/fs/cgroups/.../io.stat
rbytes=4327174144 wbytes=4294987776 rios=20724 wios=4135 dbytes=0 dios=0
```

1G 메모리에서 4G 힙을 스왑없이 사용할 때.

```bash
$ stress-ng --vm 1 --vm-bytes 4096M --vm-keep --vm-hang 0

# journalctl -k -f
Dec 17 01:54:19 node1 kernel: Memory cgroup out of memory: Killed process 1158401 (stress-ng-vm) total-vm:4240664kB, anon-rss:984988kB, file-rss:768kB, shmem-rss:32kB, UID:0 pgtables:2004kB oom_score_adj:1000
Dec 17 01:54:19 node1 kernel: oom_reaper: reaped process 1158401 (stress-ng-vm), now anon-rss:0kB, file-rss:0kB, shmem-rss:32kB
```

1G 메모리에서 4G 힙을 사용할 때

```bash
$ stress-ng --vm 1 --vm-bytes 4096M --vm-keep --vm-hang 0

# cat /sys/fs/cgroups/.../io.stat
rbytes=18944565248 wbytes=8100360192 rios=173696 wios=924488 dbytes=0 dios=0
rbytes=18953256960 wbytes=8375779328 rios=175064 wios=991729 dbytes=0 dios=0
rbytes=18953256960 wbytes=8481820672 rios=175064 wios=1017618 dbytes=0 dios=0
rbytes=18953256960 wbytes=8700641280 rios=175064 wios=1071041 dbytes=0 dios=0
rbytes=18953256960 wbytes=8781262848 rios=175064 wios=1090724 dbytes=0 dios=0
rbytes=18953256960 wbytes=8872636416 rios=175064 wios=1113032 dbytes=0 dios=0
rbytes=18953256960 wbytes=8979091456 rios=175064 wios=1139022 dbytes=0 dios=0
rbytes=18953256960 wbytes=9043832832 rios=175064 wios=1154828 dbytes=0 dios=0
rbytes=18953256960 wbytes=9128165376 rios=175064 wios=1175417 dbytes=0 dios=0
```

## _페이지 캐시는 누구의 소유인가?_

스택과 힙에 사용되는 익명 페이지는 해당 프로세스의 소유이지만, 페이지 캐시는 누구나 사용할 수 있기 때문에 어떤 프로세스의 소유인지가 애매하다. 커널은 간단히 페이지 캐시를 처음 접근해서 페이지를 할당한 프로세스의 소유로 한다. 그래서 여러 군데서 사용되는 페이지 캐시를 소유할 수록 불리하다. 왜냐하면 다른 프로세스도 사용하는데 해당 프로세스의 메모리 사용량만 줄어들기 때문이다.

## _주의해야할 사항_

높은 우선순위를 가진 Pod 도 커널에 의해 종료될 수 있다. 전체 메모리가 부족해서 실행되는 커널이나 쿠버네티스의 OOM 에 의해 종료되진 않겠지만, 메모리 한도까지 익명 페이지를 사용한다면. 최근 쿠버네티스에 추가된 스왑 기능을 이용하면 개선할 수 있다.

높은 우선순위를 가진 Pod 이 낮은 우선순위를 가진 Pod 에 의해 방해받을 수 있다. 커널은 메모리가 부족해지면 메모리를 반환하기 시작하는데 이때 루트 CGROUP 부터 PRE-ORDER 방식으로 순회하면서 LRU 리스트를 뒤지면서 반환하기 때문에 우선순위가 높은 Pod 의 자주 사용하지 않는 페이지가 반환될 수 있다.

낮은 우선순위를 가진 Pod 이 메모리를 반환하기 위해 과도한 쓰기 작업을 수행하면 병목 현상이 발생할 수 있다. 이를 해결하기 위해 CGroupV2 에는 IO 한도를 설정할 수 있는 기능이 추가되었지만, 아직 쿠버네티스에서는 이를 활용하고 있지 않는다.
