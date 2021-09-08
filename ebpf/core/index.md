최근 몇 년간 리눅스 커널 커뮤니티에서 가장 주목받고 있는 기능은 누가 뭐래도 eBPF 일 것이다. 리눅스 커널에 안정성과 확장성, 그리고 생산성을 동시에 부여하는 혁신적인 기술로, 대표적인 쿠버네티스의 CNI 인 [Cilium](https://cilium.io/)과 [Falco](https://falco.org/), [Pixie](https://pixielabs.ai/) 등 다양한 오픈소스 프로젝트의 기반 기술로 이미 자리잡고 있으며, 점점 더 활용분야를 넓혀나가고 있다. 오늘은 최근 eBPF 커뮤니티에서 가장 중요한 기능 중의 하나로 인식되고 있는 CO-RE(Compile Once - Run Everywhere)에 대해 간단히 소개하고자 한다. 우선 해당 기술이 왜 필요한지부터 살펴보도록 하자.

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

위의 코드를 보면, 리눅스의 프로세스 자료구조(task_struct 구조체)에서 현재 상태(state)를 확인하는 부분이 있다. 이 C 코드를 BPF 코드로 컴파일하면 아래와 같다.

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

위의 BPF 코드를 간단히 해석해보면 (2:) r7 레지스터에 prev 구조체의 포인터를 저장한 다음 (10:) r1 레지스터에 prev 의 state 필드의 값을 저장하고, (11:) r1 레지스터의 값이 TASK_RUNNING(0) 인지를 확인해서 분기한다. 여기서 (10:)을 살펴보면 prev 구조체 포인터에서 state 필드를 접근할 때 16 이라는 오프셋을 사용하는데, 이는 무슨 의미일까? 이 코드를 컴파일할 때 사용한 커널 헤더 파일을 살펴보자.

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

위의 헤더 파일을 살펴보면, task_struct 구조체에서 state 필드의 오프셋은 thread_info 필드 다음에 있기 때문에 thread_info 필드의 사이즈(12 바이트)를 16 바이트로 정렬해서 16 바이트가 된다. 즉, task_struct 구조체 포인터로부터 16 바이트 떨어진 위치의 8 바이트 메모리가 state 필드의 값인 것이다.

여기서 문제가 하나 발생하는데 그것은 task_struct 구조체가 어떤 버전의 커널을 쓰는지, 어떤 설정으로 쓰는지에 따라서 조금씩 달라진다는 것이다. 아래는 필자가 사용 중인 개발서버 중 한 대의 커널 헤더 파일이다.

```
struct thread_info {
  long unsigned int flags;
  long unsigned int syscall_work;
  u32 status;
};

struct task_struct {
  struct thread_info thread_info;
  volatile long int state;
  void *stack;
  ...
}
```

앞에서 BPF 파일을 컴파일할 때 사용했던 커널 헤더와 달리 thread_info 구조체에 syscall_work 라는 필드가 추가되어있다. 이 개발서버에서 앞에서 컴파일한 BPF 파일을 그대로 사용하다면 state 필드의 오프셋이 잘못되어있기 때문에 심각한 오류가 발생할 것이다. 기존에는 이러한 문제를 해결하기 위해 BPF 파일을 사용하는 서버에서 매번 직접 BPF 파일을 컴파일해서 사용을 했다. 하지만 BPF 파일을 컴파일하기 위해서는 clang/llvm 라이브러리를 항상 같이 배포해야하고, 컴파일하는데도 많은 자원과 시간이 소모된다. 이러한 문제를 해결하기 위해 나온 것이 CO-RE(Compile Once - Run Everywhere), 즉 한번 컴파일된 BPF 파일이 어디서든 실행되게 만드는 기술이다.

**CO-RE 는 간단히 설명하면, BPF 파일을 실행하기 위한 준비 단계에서 특정 구조체의 필드에 접근하는 모든 명령어를 현재 사용 중인 커널 설정에 맞게 변경하는 것이다.** 위의 예제를 이용하여 구체적인 동작 과정을 살펴보자. 우선 BPF 파일에는 컴파일시 사용된 다양한 메타정보를 포함하고 있는 BTF(BPF Type Format)가 있다. (BTF 는 리눅스 커널에서 범용적이고 복잡한 DWARF 대신에 효율적으로 BPF 를 지원하기 위해 만든 것이다.) 아래는 runqslower BPF 파일의 BTF 를 출력한 것이다.

```
...
[23] STRUCT 'task_struct' size=6784 vlen=168
        'thread_info' type_id=24 bits_offset=0
        'state' type_id=26 bits_offset=128
        'stack' type_id=28 bits_offset=192
...
```

위에는 해당 BPF 파일을 컴파일할 때 사용한 구조체에 대한 구체적인 정보가 담겨있다. 앞에서 살펴본 것처럼 task_struct 구조체의 state 필드의 오프셋이 16 바이트(128 비트)인 것을 확인할 수 있다. 그리고 어떤 명령어에서 특정 구조체의 필드를 접근했는지에 대한 정보도 가지고 있는데, 이는 대략 아래와 같이 구성되어 있다.

| InstOff |  TypeName   | AccessStr |
| :-----: | :---------: | --------: |
|   10    | task_struct |       0:1 |

이를 해석해보면 (10:) 명령어에서 task_struct 구조체의 0:1 필드를 참고한다는 의미이다. 여기서 0:1 은 복잡한 구조체에서 특정 필드를 찾아가는 일종의 경로라고 보면 된다. 0 은 자기 자신을 의미하고 다음 1 은 두 번째 필드를 의미하기 때문에 0:1 은 task_struct 구조체의 state 필드를 의미한다. 즉, (10:) 명령어에서 task_struct 구조체의 state 필드를 참고한다는 의미이다. (일반적으로 구조체 안에 간단한 자료형뿐 아니라 구조체나 배열이 들어가는 경우가 많기 때문에 이러한 표현법을 사용한다.)
