최근 몇 년간 리눅스 커널 커뮤니티에서 가장 핫한 기능은 누가 뭐래도 eBPF 일 것이다. 대표적인 쿠버네티스의 CNI 인 [Cilium](https://cilium.io/)과 [Falco](https://falco.org/), [Pixie](https://pixielabs.ai/) 등 다양한 오픈소스 프로젝트의 기반 기술로 이미 자리잡고 있으며, 점점 더 활용분야를 넓혀나가고 있다. 오늘은 최근 eBPF 커뮤니티에서 가장 핫한 기능 중에 하나인 CO-RE(Compile Once - Run Everywhere)에 대해 간단히 소개하고자 한다. 우선 해당 기술이 왜 필요한지에 대해서 살펴보도록 하자.

아래 코드는 bcc 의 [runqslower](https://github.com/iovisor/bcc/blob/master/libbpf-tools/runqslower.bpf.c) 예제코드 중 일부이다. 아래 함수는 리눅스 커널에서 문맥전환(context-switching)이 일어날때 실행되는 trace_sched_switch() 함수에

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

위의 코드를 보면
