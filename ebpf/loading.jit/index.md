BPF 파일을 컴파일하면 BPF 코드가 생성된다. 이 BPF 코드는 자바 바이트코드처럼 특정 CPU 에 종속적이지 않은 일종의 중간코드이고, 리눅스 커널은 런타임에 몇 가지 방법으로 이 BPF 코드를 실행한다. 오늘은 리눅스 커널이 BPF 코드를 실행하는 방식에 대해 소개하고자 한다.

[bcc](https://github.com/iovisor/bcc) 의 [filetop](https://github.com/iovisor/bcc/blob/master/libbpf-tools/filetop.bpf.c) 예제코드를 이용하여 BPF 파일이 BPF 코드로 컴파일된 후 커널에서 실행되는 과정을 살펴보도록 하자. 아래는 예제코드의 일부분이다.

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

이처럼 해당 예제코드를 컴파일하면 커널에서 바로 실행할 수 있는 두 개의 프로그램(BPF 코드)이 각각의 섹션에 존재하는 것을 볼 수 있다. 그리고 해당 프로그램 중 하나를 재배치 등 몇 가지 필요한 과정을 거쳐 커널에 로딩한 다음, 덤프해보면 아래와 같은 결과물을 볼 수 있다.

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

위의 결과물을 보면 알 수 있듯이, BPF 코드는 x86 CPU 에서 바로 실행될 수 있는 코드가 아니기 때문에 이를 실행하기 위해서 리눅스 커널은 크게 두 가지 방법을 제공한다. 첫 번째는 간단하지만 실용적이진 않은 인터프리팅 방식이고, 두 번째는 실제로 주로 사용하게 될 JIT(Just-In-Time) 컴파일 방식이다. 이에 대한 자세한 설명을 하기 전에 잠깐 위와 같은 BPF 코드를 실행한다는 것이 무엇을 의미하는지 살펴보자.

우리가 어떤 목적을 가지고 개발한 프로그램은 최종적으로 머신코드로 변환되어 실행된다. 여기서 실행된다는 의미는 결국 메모리를 읽어서 필요한 연산을 수행한 다음 메모리에 쓰는 것이고, 메모리는 속도가 느리기 때문에 CPU 내에 있는 레지스터에 필요한 메모리의 값을 복사한 다음 레지스터를 이용하여 연산을 수행하고, 다시 레지스터에 있는 값을 메모리로 복사하는 것이 일반적인 과정이다. 즉, 어떤 코드를 어떤 방식으로 실행했냐가 중요한 것이 아니고, 메모리에서 어떤 값을 읽고, 어떤 연산을 하고, 메모리에 어떤 값을 썼냐가 중요한 것이다. 그렇기 때문에 x86 머신코드로 컴파일해서 x86 CPU 에서 직접 실행하지 않더라도 동일한 방식으로 메모리를 읽고 쓴다면 결과는 동일하다. 이것만 명확히 이해한다면 앞으로 설명할 두 가지 방식도 쉽게 이해할 수 있을 것이다.

우선 간단히 인터프리팅 방식에 대해 알아보자. 이 방식은 이름 그대로 BPF 코드를 차례대로 읽으면서 실행하는 방식으로, 리눅스 커널에서 아직 JIT 컴파일을 지원하지 않는 CPU 를 사용하거나, 강제로 JIT 컴파일을 막은 경우에만 사용된다. 아래는 리눅스 커널에 포함되어 있는 [BPF 인터프리터](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/kernel/bpf/core.c)의 일부분이다.

```c
struct bpf_insn {
  __u8  code;   /* opcode */
  __u8  dst_reg:4;  /* dest register */
  __u8  src_reg:4;  /* source register */
  __s16 off;    /* signed offset */
  __s32 imm;    /* signed immediate constant */
};

static u64 ___bpf_prog_run(u64 *regs, const struct bpf_insn *insn, u64 *stack)
{
  static const void * const jumptable[256] __annotate_jump_table = {
    [0 ... 255] = &&default_label,
    /* Now overwrite non-defaults ... */
    BPF_INSN_MAP(BPF_INSN_2_LBL, BPF_INSN_3_LBL),
    /* Non-UAPI available opcodes. */
    [BPF_JMP | BPF_CALL_ARGS] = &&JMP_CALL_ARGS,
    [BPF_JMP | BPF_TAIL_CALL] = &&JMP_TAIL_CALL,
    [BPF_LDX | BPF_PROBE_MEM | BPF_B] = &&LDX_PROBE_MEM_B,
    [BPF_LDX | BPF_PROBE_MEM | BPF_H] = &&LDX_PROBE_MEM_H,
    [BPF_LDX | BPF_PROBE_MEM | BPF_W] = &&LDX_PROBE_MEM_W,
    [BPF_LDX | BPF_PROBE_MEM | BPF_DW] = &&LDX_PROBE_MEM_DW,
  };

#define CONT   ({ insn++; goto select_insn; })

select_insn:
  goto *jumptable[insn->code];

  ...
  JMP_CALL:
    /* Function call scratches BPF_R1-BPF_R5 registers,
     * preserves BPF_R6-BPF_R9, and stores return value
     * into BPF_R0.
     */
    BPF_R0 = (__bpf_call_base + insn->imm)(BPF_R1, BPF_R2, BPF_R3,
                   BPF_R4, BPF_R5);
    CONT;
  ...
}
```

리눅스 커널 코드답게(?) 매크로가 남발되어 있는 것을 볼 수 있다. 일단 bpf_insn 구조체가 하나의 BPF 명령어를 표현하는 구조체이다. 전체 크기는 64 비트이고, 명령어의 종류를 의미하는 code 필드와 원본 레지스터(src_reg), 목적 레지스터(dst_reg), 그리고 off/imm 상수 필드로 구성되어 있다. 그리고 \_\_bpf_prog_run 함수가 실제로 BPF 명령어를 인터프리팅하는 함수인데, jumptable 배열에 각각의 명령어에 해당하는 라벨이 등록되어 있고 select_insn 라벨에서 현재 명령어의 code 필드를 인덱스로 이용해서 jumptable 배열에 등록되어 있는 라벨로 점프하는 것을 볼 수 있다. 즉, 현재 명령어의 code 필드가 JMP_CALL 에 해당하는 값이면 JMP_CALL 라벨로 점프하여 필요한 작업을 수행하고, 현재 명령어를 다음 명령어로 변경한 다음 select_insn 라벨로 점프(CONT 매크로)하는 반복적인 구조이다.

앞에서 소개한 [filetop](https://github.com/iovisor/bcc/blob/master/libbpf-tools/filetop.bpf.c)의 커널에 로딩된 BPF 코드 중 (0:) 명령어를 인터프리팅 방식으로 어떻게 실행하는지 살펴보자. 해당 명령어의 code 는 0x79 이고, 이는 원본(r1) 레지스터에 오프셋(96)을 더한 주소에 있는 메모리를 읽어서 목적(r2) 레지스터에 저장하라는 뜻이다. 실제 이를 처리하는 커널 코드를 간단히 살펴보자.

```c
#define DST regs[insn->dst_reg]
#define SRC regs[insn->src_reg]

static u64 ___bpf_prog_run(u64 *regs, const struct bpf_insn *insn, u64 *stack)
{
  ...
  LDX_MEM_DW:
    DST = *(SIZE *)(unsigned long) (SRC + insn->off);
    CONT;
  ...
}
```

0x79 명령어에 해당하는 라벨은 LDX_MEM_DW 이고, 이는 SRC 레지스터(src_reg)에 off 상수값을 더한 주소에 해당하는 메모리의 값을 읽어와서 DST 레지스터(dst_reg)로 저장한다. 여기서 SRC/DST 레지스터는 매크로로 정의되어 있는데, 인터프리팅 방식에서는 실제 CPU 를 이용하는 것이 아니기 때문에 레지스터 또한 변수에 불과하고, 총 10개의 레지스터를 나타내는 배열(regs)을 이용하여 레지스터를 흉내낸다. 즉, SRC 매크로는 레지스터 배열에서 현재 명령어의 원본 레지스터(src_reg)를 의미하고, DST 매크로는 레지스터 배열에서 현재 명령어의 목적 레지스터(dst_reg)를 의미한다.

이처럼 인터프리팅 방식은 명령어 하나를 처리하기 위해 몇 번의 분기를 하면서 상당히 많은 x86 머신코드를 실행하고, 레지스터도 메모리에 저장되어 있는 변수일뿐이기 때문에 굉장히 느릴 수 밖에 없다. 그래서 이 방식은 실제 사용하기 위한 용도라기 보다는 검증 및 준비 단계에서 사용되는 방식이라고 볼 수 있다.

이제 JIT 컴파일 방식에 대해 알아보자. 이 방식은 간단히 말하면 미리 BPF 코드를 x86 머신코드로 변환해놓고, BPF 프로그램이 실행될때마다 미리 변환해놓은 x86 머신코드를 바로 실행하는 것이다. 아래는 리눅스 커널에 포함되어 있는 [BPF-to-x86 JIT 컴파일러](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/arch/x86/net/bpf_jit_comp.c)의 일부분이다.

```c
static const int reg2hex[] = {
  [BPF_REG_0] = 0,  /* RAX */
  [BPF_REG_1] = 7,  /* RDI */
  [BPF_REG_2] = 6,  /* RSI */
  [BPF_REG_3] = 2,  /* RDX */
  [BPF_REG_4] = 1,  /* RCX */
  [BPF_REG_5] = 0,  /* R8  */
  [BPF_REG_6] = 3,  /* RBX callee saved */
  [BPF_REG_7] = 5,  /* R13 callee saved */
  [BPF_REG_8] = 6,  /* R14 callee saved */
  [BPF_REG_9] = 7,  /* R15 callee saved */
  [BPF_REG_FP] = 5, /* RBP readonly */
  [BPF_REG_AX] = 2, /* R10 temp register */
  [AUX_REG] = 3,    /* R11 temp register */
  [X86_REG_R9] = 1, /* R9 register, 6th function argument */
};

static u8 add_1reg(u8 byte, u32 dst_reg)
{
  return byte + reg2hex[dst_reg];
}

static void emit_mov_imm32(u8 **pprog, bool sign_propagate, u32 dst_reg, const u32 imm32)
{
  ...
  EMIT1_off32(add_1reg(0xB8, dst_reg), imm32);
  ...
}

static int emit_call(u8 **pprog, void *func, void *ip)
{
  return emit_patch(pprog, func, ip, 0xE8);
}

static int do_jit(struct bpf_prog *bpf_prog, int *addrs, u8 *image, int oldproglen, struct jit_context *ctx, bool jmp_padding)
{
  for (i = 1; i <= insn_cnt; i++, insn++) {
    ...
    switch (insn->code) {
      case BPF_ALU64 | BPF_MOV | BPF_K:
        emit_mov_imm32(&prog, BPF_CLASS(insn->code) == BPF_ALU64, dst_reg, imm32);
        break;

      case BPF_JMP | BPF_CALL:
        func = (u8 *) __bpf_call_base + imm32;
        ...
        if (!imm32 || emit_call(&prog, func, image + addrs[i - 1]))
          return -EINVAL;
        break;
    }
    ...
  }
```

위의 do_jit 함수는 리눅스 커널에서 BPF 코드를 x86 머신코드로 JIT 컴파일하는 함수이다. 기본적인 동작 원리는 적당한 크기의 버퍼를 미리 생성해놓고 BPF 코드를 하나씩 x86 머신코드로 변환해서 버퍼를 순서대로 채워나가는 방식이다.

우선, 가장 간단한 레지스터에 상수값을 저장하는 명령어가 어떻게 변환되는지 살펴보자. 아래는 상수값을 레지스터에 저장하는 (2:) 명령어가 x86 머신코드로 변환된 결과를 보여주고 있다.

```c
$ bpftool prog dump xlated id 17
int vfs_write_entry(struct pt_regs * ctx):
  ...
   2: (b7) r3 = 1
   ...

$ bpftool prog dump jited id 17
int vfs_write_entry(struct pt_regs * ctx):
  ...
  13:	mov    $0x1,%edx
  ...
```

상수값을 레지스터에 저장하는 명령어의 코드는 BPF_ALU64 | BPF_MOV | BPF_K (0xb7) 이다. do_jit 함수에서 해당 케이스를 살펴보면, emit_mov_imm32 함수를 호출하는데, 해당 함수에서는 상수값을 레지스터에 저장하는 x86 명령어의 코드인 0xb8 과 r3 레지스터에 해당하는 edx 레지스터와 상수값(1)을 이용하여 x86 머신코드를 버퍼에 추가하는 것을 볼 수 있다. 인터프리팅 방식과 달리 JIT 컴파일러는 실제 x86 CPU 에서 바로 실행될 수 있는 x86 머신코드를 생성하기 때문에 BPF 코드의 레지스터를 x86 CPU 에서 바로 사용가능한 레지스터로 변환한다. 이 레지스터 할당은 위의 reg2hex 배열에 선언된 것처럼 1:1 로 매칭되기 때문에 오버헤드 없이 진행이 가능하다. 즉, JIT 컴파일 방식은 BPF 코드를 x86 머신코드로 미리 변환해놓고, x86 CPU 레지스터도 바로 할당해서 사용하기 때문에 인터프리팅 방식에 비해 월등히 성능이 좋을 수 밖에 없다.

다음으로, 메인함수(vfs_write_entry)에서 공통함수((probe_entry)를 호출하는 명령어가 어떻게 변환되는지 살펴보자. 아래는 해당 명령어가 x86 머신코드로 변환된 결과를 보여주고 있다.

```c
$ bpftool prog dump xlated id 17
int vfs_write_entry(struct pt_regs * ctx):
  ...
   3: (85) call pc+2
  ...

int probe_entry(struct pt_regs * ctx, struct file * file, size_t count, enum op op):
   6: (7b) *(u64 *)(r10 -72) = r3
   7: (7b) *(u64 *)(r10 -64) = r2
  ...

$ bpftool prog dump jited id 17
int vfs_write_entry(struct pt_regs * ctx):
  ...
  18:	callq  0x00000000000020c8
  ...

int probe_entry(struct pt_regs * ctx, struct file * file, size_t count, enum op op):
   0:	nopl   0x0(%rax,%rax,1)
   5:	xchg   %ax,%ax
  ...
```

함수를 호출하는 명령어의 코드는 BPF_JMP | BPF_CALL (0x85) 이다.
