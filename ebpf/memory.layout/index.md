BPF 는 일반적인 프로그램과 유사한 방식으로 개발하기 때문에 유사한 실행파일 및 메모리 구조를 가지고 있지만, 커널 안에서 제한된 환경으로 실행되기 때문에 로딩(loading)하는 과정은 상당히 다르다. 오늘은 BPF 의 실행파일 및 메모리 구조에 대해 간단히 살펴본 후, 이를 로딩하는 과정에 대해 분석해보도록 하자.

일반적인 실행파일에서 가장 중요한 두 가지는 코드와 데이터이다. 코드는 말그대로 상위언어를 컴파일한 머신코드를 의미하고, 데이터는 실행시 코드가 참고하는 메모리를 의미한다. 데이터는 스택과 힙같이 실행시 메모리가 할당/해제되는 동적 데이터와 전역변수처럼 코드에서 선언되는 정적 데이터로 나뉘는데, 정적 데이터는 실행파일을 로딩할 때 메모리가 할당되고 해당 메모리를 참고하는 코드도 재배치된다. 그리고 정적 데이터는 크게 읽기전용 변수, 초기화된 전역변수 그리고 초기화되지 않은 전역변수로 구분되는데, 아래 코드([bcc](https://github.com/iovisor/bcc) 의 [runqslower](https://github.com/iovisor/bcc/blob/master/libbpf-tools/runqslower.bpf.c) 예제코드를 약간 변형한 것이다.)를 보면서 설명하도록 하겠다.

```c
...
int data0 = 0;
int data1 = 1;
int bss0;
const char rodata0[] = "ebpf";

SEC("tp_btf/sched_switch")
int handle__sched_switch(u64 *ctx)
{
  /* TP_PROTO(bool preempt, struct task_struct *prev,
   *      struct task_struct *next)
   */
  struct task_struct *prev = (struct task_struct *)ctx[1];
  struct task_struct *next = (struct task_struct *)ctx[2];
  struct event event = {};
  u64 *tsp, delta_us;
  long state;
  u32 pid;

  /* ivcsw: treat like an enqueue event and store timestamp */
  if (prev->state == data1)
    trace_enqueue(prev->tgid, prev->pid);

  pid = next->pid;
  ...
}
...
```

우선 읽기전용 변수는 rodata0 처럼 const 로 선언된 전역변수를 의미하고, 해당 메모리에 대한 쓰기 작업을 금지하기 위해 읽기전용의 페이지를 할당받아 사용한다. 그리고 data0 과 data1 같이 초기값을 가지고 있는 전역변수는 초기화된 전역변수로 분류되고, bss0 과 같이 초기값을 가지고 있지 않은 전역변수는 초기화되지 않은 전역변수로 분류된다. 아래는 위의 예제코드를 컴파일한 후 objdump 를 이용해서 섹션 테이블과 심볼 테이블을 출력한 것이다.

```
.output/runqslower.bpf.o:       file format elf64-bpf

architecture: bpfel
start address: 0x0000000000000000

Program Header:

Dynamic Section:
Sections:
Idx Name                        Size     VMA              Type
  0                             00000000 0000000000000000
  1 .text                       00000000 0000000000000000 TEXT
  2 tp_btf/sched_wakeup         000000f8 0000000000000000 TEXT
  3 tp_btf/sched_wakeup_new     000000f8 0000000000000000 TEXT
  4 tp_btf/sched_switch         00000318 0000000000000000 TEXT
  5 .rodata                     00000015 0000000000000000 DATA
  6 .data                       00000008 0000000000000000 DATA
  7 .maps                       00000038 0000000000000000 DATA
  8 license                     00000004 0000000000000000 DATA
  9 .bss                        00000004 0000000000000000 BSS
 10 .BTF                        00005e0c 0000000000000000
 11 .BTF.ext                    0000068c 0000000000000000
 12 .symtab                     000002a0 0000000000000000
 13 .reltp_btf/sched_wakeup     00000030 0000000000000000
 14 .reltp_btf/sched_wakeup_new 00000030 0000000000000000
 15 .reltp_btf/sched_switch     00000080 0000000000000000
 16 .rel.BTF                    000000a0 0000000000000000
 17 .rel.BTF.ext                00000630 0000000000000000
 18 .llvm_addrsig               00000009 0000000000000000
 19 .strtab                     0000017c 0000000000000000

SYMBOL TABLE:
0000000000000000 g     O .bss   0000000000000004 bss0
0000000000000000 g     O .data  0000000000000004 data0
0000000000000004 g     O .data  0000000000000004 data1
0000000000000000 g     F tp_btf/sched_switch    0000000000000318 handle__sched_switch
0000000000000010 g     O .rodata        0000000000000005 rodata0
...
```

리눅스에서 주로 사용하는 ELF 실행파일 구조이고, 용도에 따라 다양한 섹션으로 구성되어 있다. 심볼 테이블을 보면 읽기전용 변수인 rodata0 은 읽기전용 데이터 섹션인 .rodata 에 속해있고, 초기화된 전역변수인 data0 과 data1 은 .data 섹션에, 그리고 초기화되지 않은 전역변수인 bss0 은 .bss 섹션에 포함되어 있는 것을 볼 수 있다. 여기서 .data 섹션과 .bss 섹션의 차이점은 .data 섹션은 실제 초기값들을 실행파일 안에 포함하고 있지만, .bss 섹션은 초기값이 없기 때문에 실행파일 안은 비어있고 로딩 시에 메모리를 할당받은 후 0 으로 초기화한다.
