BPF 파일을 컴파일하면 BPF 코드가 생성된다. 이 BPF 코드는 자바 바이트코드처럼 특정 CPU 에 종속적이지 않은 일종의 중간코드이고, 리눅스 커널은 런타임에 몇 가지 방법으로 이 BPF 코드를 실행한다. 오늘은 리눅스 커널이 BPF 코드를 실행하는 방식에 대해 소개하고자 한다.

우선 간단히 [bcc](https://github.com/iovisor/bcc) 의 [filetop](https://github.com/iovisor/bcc/blob/master/libbpf-tools/filetop.bpf.c) 예제코드를 보면서 BPF 파일이 BPF 코드로 컴파일되고, BPF 코드가 커널에 로딩되어 실행되기 직전의 모습까지 살펴보도록 하자. 아래는 예제코드의 일부분이다.

```c
static int probe_entry(struct pt_regs *ctx, struct file *file, size_t count, enum op op)
{
  __u64 pid_tgid = bpf_get_current_pid_tgid();
  __u32 pid = pid_tgid >> 32;
  __u32 tid = (__u32)pid_tgid;

  ...

  return 0;
}

SEC("kprobe/vfs_read")
int BPF_KPROBE(vfs_read_entry, struct file *file, char *buf, size_t count, loff_t *pos)
{
  return probe_entry(ctx, file, count, READ);
}

SEC("kprobe/vfs_write")
int BPF_KPROBE(vfs_write_entry, struct file *file, const char *buf, size_t count, loff_t *pos)
{
  return probe_entry(ctx, file, count, WRITE);
}
```

위의 코드를 clang/llvm 을 이용하여 컴파일하면 아래와 같은 ELF 실행파일 구조로 만들어진 BPF 코드가 생성된다.

```
Disassembly of section .text:

0000000000000000 <probe_entry>:
       0:       7b 3a b8 ff 00 00 00 00 *(u64 *)(r10 - 72) = r3
       1:       7b 2a c0 ff 00 00 00 00 *(u64 *)(r10 - 64) = r2
       2:       7b 1a c8 ff 00 00 00 00 *(u64 *)(r10 - 56) = r1
       3:       85 00 00 00 0e 00 00 00 call 14
       4:       bf 08 00 00 00 00 00 00 r8 = r0
       5:       b7 01 00 00 00 00 00 00 r1 = 0
       6:       7b 1a e0 ff 00 00 00 00 *(u64 *)(r10 - 32) = r1
       7:       7b 1a d8 ff 00 00 00 00 *(u64 *)(r10 - 40) = r1
       8:       7b 1a d0 ff 00 00 00 00 *(u64 *)(r10 - 48) = r1
       9:       bf 89 00 00 00 00 00 00 r9 = r8
      10:       77 09 00 00 20 00 00 00 r9 >>= 32
      11:       18 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 r1 = 0 ll
      13:       61 12 00 00 00 00 00 00 r2 = *(u32 *)(r1 + 0)
      14:       15 02 02 00 00 00 00 00 if r2 == 0 goto +2 <LBB2_2>
      15:       61 11 00 00 00 00 00 00 r1 = *(u32 *)(r1 + 0)
      16:       5d 91 7c 00 00 00 00 00 if r1 != r9 goto +124 <LBB2_14>
      ...

Disassembly of section kprobe/vfs_read:

0000000000000000 <vfs_read_entry>:
       0:       79 12 60 00 00 00 00 00 r2 = *(u64 *)(r1 + 96)
       1:       79 11 70 00 00 00 00 00 r1 = *(u64 *)(r1 + 112)
       2:       b7 03 00 00 00 00 00 00 r3 = 0
       3:       85 10 00 00 ff ff ff ff call -1
       4:       b7 00 00 00 00 00 00 00 r0 = 0
       5:       95 00 00 00 00 00 00 00 exit

Disassembly of section kprobe/vfs_write:

0000000000000000 <vfs_write_entry>:
       0:       79 12 60 00 00 00 00 00 r2 = *(u64 *)(r1 + 96)
       1:       79 11 70 00 00 00 00 00 r1 = *(u64 *)(r1 + 112)
       2:       b7 03 00 00 01 00 00 00 r3 = 1
       3:       85 10 00 00 ff ff ff ff call -1
       4:       b7 00 00 00 00 00 00 00 r0 = 0
       5:       95 00 00 00 00 00 00 00 exit
```

이처럼 해당 예제코드를 컴파일하면 커널에 바로 로딩될 수 있는 두 개의 프로그램(BPF 코드)이 각각의 섹션에 존재하는 것을 볼 수 있다. 그리고 해당 프로그램 중 하나를 재배치 등 몇 가지 필요한 과정을 거쳐 커널에 로딩한 다음, 덤프해보면 아래와 같은 결과물을 볼 수 있다.

```
$ bpftool prog dump xlated id 17
int vfs_write_entry(struct pt_regs * ctx):
; int BPF_KPROBE(vfs_write_entry, struct file *file, const char *buf, size_t count, loff_t *pos)
   0: (79) r2 = *(u64 *)(r1 +96)
   1: (79) r1 = *(u64 *)(r1 +112)
; return probe_entry(ctx, file, count, WRITE);
   2: (b7) r3 = 1
   3: (85) call pc+2#bpf_prog_14ee69a88d05505b_F
; int BPF_KPROBE(vfs_write_entry, struct file *file, const char *buf, size_t count, loff_t *pos)
   4: (b7) r0 = 0
   5: (95) exit
int probe_entry(struct pt_regs * ctx, struct file * file, size_t count, enum op op):
; static int probe_entry(struct pt_regs *ctx, struct file *file, size_t count, enum op op)
   6: (7b) *(u64 *)(r10 -72) = r3
   7: (7b) *(u64 *)(r10 -64) = r2
   8: (7b) *(u64 *)(r10 -56) = r1
; __u64 pid_tgid = bpf_get_current_pid_tgid();
   9: (85) call bpf_get_current_pid_tgid#133744
  10: (bf) r8 = r0
  11: (b7) r1 = 0
; struct file_id key = {};
  12: (7b) *(u64 *)(r10 -32) = r1
  13: (7b) *(u64 *)(r10 -40) = r1
  14: (7b) *(u64 *)(r10 -48) = r1
; __u32 pid = pid_tgid >> 32;
  15: (bf) r9 = r8
  16: (77) r9 >>= 32
```

위의 결과물을 보면 알 수 있듯이, BPF 코드는 x86 CPU 에서 바로 실행될 수 있는 코드가 아니기 때문에 이를 실행하기 위해서 리눅스 커널은 크게 두 가지의 방법을 제공한다. 첫 번째는 간단하지만 실용적이진 않은 인터프리팅 방식이고, 두 번째는 실제로 주로 사용하게 될 JIT(Just-In-Time) 컴파일 방식이다. 이에 대한 자세한 설명을 하기 전에 잠깐 위와 같은 BPF 코드를 실행한다는 것이 무엇을 의미하는지 살펴보자.

우리가 어떤 목적을 가지고 개발한 프로그램은 최종적으로 머신코드로 변환되어 실행된다. 여기서 실행된다는 의미는 결국 메모리를 읽어서 필요한 연산을 수행한 다음 메모리에 쓰는 것이고, 메모리는 속도가 느리기 때문에 CPU 내에 있는 레지스터에 필요한 메모리의 값을 복사한 다음 레지스터를 이용하여 연산을 수행하고, 다시 레지스터에 있는 값을 메모리로 복사하는 것이 일반적인 과정이다. 즉, 어떤 코드를 어떤 방식으로 실행했냐가 중요한 것이 아니고, 메모리에서 어떤 값을 읽고, 어떤 연산을 하고, 메모리에 어떤 값을 썼냐가 중요한 것이다. 그렇기 때문에 x86 머신코드로 컴파일된 코드를 직접 실행하지 않더라도 동일한 방식으로 메모리를 읽고 쓴다면 결과는 동일하다는 말이다. 이것만 명확히 이해한다면 앞으로 설명할 두 가지 방식도 쉽게 이해할 수 있을 것이다.
