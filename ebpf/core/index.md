최근 몇 년간 리눅스 커널 커뮤니티에서 가장 주목받고 있는 기능은 누가 뭐래도 eBPF 일 것이다. 리눅스 커널에 안정성과 확장성, 그리고 생산성을 동시에 부여하는 혁신적인 기술로, 대표적인 쿠버네티스의 CNI 인 [Cilium](https://cilium.io/)과 [Falco](https://falco.org/), [Pixie](https://pixielabs.ai/) 등 다양한 오픈소스 프로젝트의 기반 기술로 이미 자리잡고 있으며, 점점 더 활용분야를 넓혀나가고 있다. 오늘은 최근 eBPF 커뮤니티에서 가장 중요한 기능 중에 하나인 CO-RE(Compile Once - Run Everywhere)에 대해 간단히 소개하고자 한다. 우선 해당 기술이 왜 필요한지부터 살펴보도록 하자.

아래 코드는 [bcc](https://github.com/iovisor/bcc) 의 [runqslower](https://github.com/iovisor/bcc/blob/master/libbpf-tools/runqslower.bpf.c) 예제코드 중 일부이다. 아래 함수는 리눅스 커널에서 문맥전환(context-switching)이 일어날때 실행되는 trace_sched_switch() 함수에서 호출되는 BPF 함수이다. (섹션 이름인 tp_btf/sched_switch 가 sched_switch 트레이스포인트에 해당 함수를 추가하라는 의미이다.)

```c
SEC("tp_btf/sched_switch")
int handle__sched_switch(u64 *ctx)
{
  struct task_struct *prev = (struct task_struct *)ctx[1];
  struct task_struct *next = (struct task_struct *)ctx[2];
  ...

  if (prev->state == TASK_RUNNING)
    trace_enqueue(prev->tgid, prev->pid);

  ...
  return 0;
}
```

위의 코드를 보면, 리눅스의 프로세스 자료구조(task_struct 구조체)에서 현재 상태(state)를 확인하는 부분이 있다. 이 C 코드를 BPF 로 컴파일하면 아래와 같다.

```
Disassembly of section tp_btf/sched_switch:

0000000000000000 handle__sched_switch:
       0:       bf 16 00 00 00 00 00 00 r6 = r1
       1:       79 68 10 00 00 00 00 00 r8 = *(u64 *)(r6 + 16)
       2:       79 67 08 00 00 00 00 00 r7 = *(u64 *)(r6 + 8)
      10:       79 71 10 00 00 00 00 00 r1 = *(u64 *)(r7 + 16)
      11:       55 01 1c 00 00 00 00 00 if r1 != 0 goto +28 <LBB2_7>
      ...
```

위의 BPF 코드를 간단히 해석해보면 r7 레지스터에 prev 구조체의 포인터를 저장한 다음 r1 레지스터에 prev 의 state 필드의 값을 저장하고, r1 레지스터의 값이 TASK_RUNNING(0) 인지를 확인해서 분기한다. 여기서 10번 줄을 살펴보면 prev 구조체 포인터에서 state 필드를 접근할 때 16 이라는 오프셋을 사용하는데, 이는 무슨 의미일까? 이 코드를 컴파일할 때 사용한 커널 헤더 파일은 아래와 같다.

```
struct thread_info {
  long unsigned int flags;
  u32 status;
};

struct task_struct {
  struct thread_info thread_info;
  volatile long int state;
  void *stack;
  ...
}
```

위의 헤더 파일을 살펴보면, task_struct 구조체에서 state 필드는 thread_info 필드 다음에 있기 때문에 thread_info 필드의 사이즈(12 바이트)에 16 바이트로 정렬을 하면 16 바이트가 된다. 즉, task_struct 구조체 포인터로부터 16 바이트 떨어진 위치의 8 바이트 메모리가 state 필드의 값인 것이다.
