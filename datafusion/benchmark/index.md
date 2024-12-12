[Datafusion](https://github.com/apache/datafusion) 은 [Arrow](https://arrow.apache.org) 를 이용하여 Rust 기반으로 개발 중인 임베딩 SQL 엔진이다. 그래서 Scala 기반으로 개발되어 JVM 위에서 동작하는 [Spark](https://spark.apache.org) 에 비해 아래와 같은 장점을 가진다.

* Column 기반 데이터 처리 (Arrow)
* GC 없이 메모리 안정성 보장
* LLVM 기반 최적화 (Vectorization, ...)

그렇다면 이러한 장점들이 실제 성능에는 얼마나 영향을 주는지 알아보도록 하자. 오늘은 단일 머신에서의 성능만을 비교하고, 추후에 [Ballista](https://datafusion.apache.org/ballista) 와 같은 Datafusion 기반의 분산 처리 기술을 이용하여 분산 처리 성능도 비교해보도록 하겠다.

실험은 OLAP 성능 검증을 위해 자주 사용되는 TPC-H (SF1000) 를 이용하였다.

```sql
select
    sum(l_extendedprice * l_discount) as revenue
from
    lineitem
where
    l_shipdate >= date '1994-01-01'
    and l_shipdate < date '1995-01-01'
    and l_discount between 0.06 - 0.01 and 0.06 + 0.01
    and l_quantity < 24;
```

![tpch.q6.png](./tpch.q6.png)

![memory.q6.png](./memory.q6.png)

```sql
select
    l_returnflag,
    l_linestatus,
    sum(l_quantity) as sum_qty,
    sum(l_extendedprice) as sum_base_price,
    sum(l_extendedprice * (1 - l_discount)) as sum_disc_price,
    sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) as sum_charge,
    avg(l_quantity) as avg_qty,
    avg(l_extendedprice) as avg_price,
    avg(l_discount) as avg_disc,
    count(*) as count_order
from
    lineitem
where
    l_shipdate <= date '1998-09-02'
group by
    l_returnflag,
    l_linestatus
order by
    l_returnflag,
    l_linestatus;
```

![tpch.q1.png](./tpch.q1.png)

![memory.q1.png](./memory.q1.png)

```sql
select
    l_shipmode,
    sum(case
            when o_orderpriority = '1-URGENT'
                or o_orderpriority = '2-HIGH'
                then 1
            else 0
        end) as high_line_count,
    sum(case
            when o_orderpriority <> '1-URGENT'
                and o_orderpriority <> '2-HIGH'
                then 1
            else 0
        end) as low_line_count
from
    lineitem
    join orders on l_orderkey = o_orderkey
where
    l_shipmode in ('MAIL', 'SHIP')
    and l_commitdate < l_receiptdate
    and l_shipdate < l_commitdate
    and l_receiptdate >= date '1994-01-01'
    and l_receiptdate < date '1995-01-01'
group by
    l_shipmode
order by
    l_shipmode;
```

![tpch.q12.png](./tpch.q12.png)

![memory.q12.png](./memory.q12.png)

```rust
pub fn loop_simple(a: &[i32; 8]) -> i32 {
    let mut r: i32 = 0;
    for var in a.iter() {
        r += var;
    }
    r
}
```

```
       0: 48 83 ec 38                   subq  $56, %rsp
       4: 48 89 7c 24 28                movq  %rdi, 40(%rsp)
       9: c7 44 24 0c 00 00 00 00       movl  $0, 12(%rsp)
      11: be 08 00 00 00                movl  $8, %esi
      16: ff 15 00 00 00 00             callq *(%rip)
      1c: 48 89 c7                      movq  %rax, %rdi
      1f: 48 89 d6                      movq  %rdx, %rsi
      22: ff 15 00 00 00 00             callq *(%rip)
      28: 48 89 44 24 10                movq  %rax, 16(%rsp)
      2d: 48 89 54 24 18                movq  %rdx, 24(%rsp)
      32: 48 8d 7c 24 10                leaq  16(%rsp), %rdi
      37: ff 15 00 00 00 00             callq *(%rip)
      3d: 48 89 44 24 20                movq  %rax, 32(%rsp)
      42: 48 8b 54 24 20                movq  32(%rsp), %rdx
      47: b8 01 00 00 00                movl  $1, %eax
      4c: 31 c9                         xorl  %ecx, %ecx
      4e: 48 83 fa 00                   cmpq  $0, %rdx
      52: 48 0f 44 c1                   cmoveq  %rcx, %rax
      56: 48 83 f8 00                   cmpq  $0, %rax
      5a: 75 09                         jne 0x65
      5c: 8b 44 24 0c                   movl  12(%rsp), %eax
      60: 48 83 c4 38                   addq  $56, %rsp
      64: c3                            retq
      65: 48 8b 74 24 20                movq  32(%rsp), %rsi
      6a: 48 89 74 24 30                movq  %rsi, 48(%rsp)
      6f: 48 8d 7c 24 0c                leaq  12(%rsp), %rdi
      74: 48 8d 15 00 00 00 00          leaq  (%rip), %rdx
      7b: e8 00 00 00 00                callq 0x80
      80: eb b0                         jmp 0x32
      ...
```

```
       0: f3 0f 6f 07                   movdqu  (%rdi), %xmm0
       4: f3 0f 6f 4f 10                movdqu  16(%rdi), %xmm1
       9: 66 0f fe c8                   paddd   %xmm0, %xmm1
       d: 66 0f 70 c1 ee                pshufd  $238, %xmm1, %xmm0
      12: 66 0f fe c1                   paddd   %xmm1, %xmm0
      16: 66 0f 70 c8 55                pshufd  $85, %xmm0, %xmm1
      1b: 66 0f fe c8                   paddd   %xmm0, %xmm1
      1f: 66 0f 7e c8                   movd    %xmm1, %eax
      23: c3                            retq
```