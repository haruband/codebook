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

```
RELOCATION RECORDS FOR [kprobe/vfs_read]:
OFFSET           TYPE                     VALUE
0000000000000018 R_BPF_64_32              .text

RELOCATION RECORDS FOR [kprobe/vfs_write]:
OFFSET           TYPE                     VALUE
0000000000000018 R_BPF_64_32              .text
```

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
