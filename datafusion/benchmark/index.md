[Datafusion](https://github.com/apache/datafusion) 은 [Arrow](https://arrow.apache.org) 를 이용하여 Rust 기반으로 개발 중인 임베딩 SQL 엔진이다. 그래서 Scala 기반으로 개발되어 JVM 위에서 동작하는 [Spark](https://spark.apache.org) 에 비해 아래와 같은 장점을 가진다.

* GC 없이 메모리 안정성 보장
* 컬럼 기반 데이터 포맷 사용 (Arrow)
* LLVM 기반 최적화 (Vectorization, ...)

그렇다면 이러한 장점들이 실제 성능에는 얼마나 영향을 주는지 알아보도록 하자. 오늘은 단일 머신에서의 성능만을 비교하고, 추후에 [Ballista](https://datafusion.apache.org/ballista) 와 같은 Datafusion 기반의 분산 처리 기술을 이용하여 분산 처리 성능도 비교해보도록 하겠다.

실험은 OLAP 성능 검증을 위해 자주 사용되는 TPC-H (SF1000) 를 이용하였다. 실험 결과는 처리 시간과 메모리 사용량을 이용하여 분석하였으며, 최대 메모리 사용량(JVM)에 영향을 많이 받는 Spark 는 8 ~ 64 GB 까지 최대 메모리 사용량을 변경해가면서 성능을 측정하였다.

첫 번째 실험은 하나의 테이블에서 몇 가지 조건절을 이용하여 데이터를 필터링한 다음 합계를 구하는 쿼리(TPC-H-Q6)이다.

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

아래는 처리 시간을 보여주고 있다. Datafusion 이 Spark 에 비해 대략 10 배 정도 좋은 성능을 보여주고 있다.

![tpch.q6.png](./tpch.q6.png)

아래는 실제 메모리 사용량을 측정한 결과이다. Datafusion 은 최대 1.8 GB 정도의 메모리를 사용하였으며, Spark 는 최대 메모리 사용량(-Xmx)이 클수록 실제 메모리 사용량이 커지면서 오히려 성능이 약간 떨어지는 모습을 볼 수 있다. Spark 는 중간 결과나 재활용될 수 있는 데이터를 메모리에 최대한 유지하는 정책을 취하기 때문에 메모리 사용량이 증가하지만, 이러한 정책이 오히려 GC(GarbageCollection) 오버헤드를 증가시키는 등 안 좋은 결과를 보여줄 수도 있다. (최대 메모리 사용량이 8 GB 일때는 GC 에 1.5 초를 소요했지만, 64 GB 일때는 2.4 초를 소요했다.)

![memory.q6.png](./memory.q6.png)

두 번째 실험은 하나의 테이블에서 그룹별 집계를 구하는 쿼리(TPC-H-Q1)이다.

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

Datafusion 이 Spark 에 비해 대략 10 ~ 12 배 정도 좋은 성능을 보여주고 있다.

![tpch.q1.png](./tpch.q1.png)

Datafusion 은 최대 2 GB 정도의 메모리를 사용하였으며, Spark 는 앞의 실험과 유사한 결과를 보여주지만 그룹별 집계가 메모리 사용량이 많기 때문에 성능이 나빠지는 정도가 훨씬 심해진 것을 볼 수 있다. (최대 메모리 사용량이 8 GB 일때는 GC 에 21 초를 소요했지만, 64 GB 일때는 40 초를 소요했다.)

![memory.q1.png](./memory.q1.png)

세 번째 실험은 두 개의 테이블을 조인하는 쿼리(TPC-H-Q12)이다. 등가(Equal) 조인을 처리하는 방식은 BroadcastJoin, HashJoin, SortMergeJoin 등이 있는데, 이번 실험에서는 최적화가 충분치 않은 Datafusion 의 SortMergeJoin 과 데이터 크기가 커서 사용할 수 없는 Spark 의 BroadcastJoin 은 제외하고 진행하였다.

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

Datafusion 의 BroadcastJoin 이 가장 좋은 성능을 보여주고 있으며, Spark 에 비해 대략 7.6 배 정도 좋은 성능을 보여주고 있다.

![tpch.q12.png](./tpch.q12.png)

Datafusion 은 BroadcastJoin 과 HashJoin 에서 2.5 GB 정도의 메모리를 사용하였으며, Spark 는 HashJoin 에서 64 GB 의 메모리도 부족하여 파티션을 두 배(400)로 늘려서 실험하였다.

![memory.q12.png](./memory.q12.png)

실험 결과를 종합해보면, Datafusion 이 훨씬 적은 메모리를 사용하면서도 10 배 정도 좋은 성능을 보여주고 있다. 또한, Spark 는 최대 메모리 사용량에 따른 실제 메모리 사용량과 처리 시간을 예측하기 힘들고, 최대 메모리 사용량이 부족하면 예기치 못한 OOM(OutOfMemory) 도 자주 발생하기 때문에 사용하기가 매우 까다롭다.

마지막으로 Datafusion 이 어떻게 좋은 성능을 보여주는지 살펴보도록 하자.

첫 번째 이유는 GC 를 사용하지 않기 때문이다. GC 를 사용하면 메모리를 반환하더라도 GC 에 의해 해제되기 전까지 재사용이 불가능하기 때문에 실제 메모리 사용량보다 많은 메모리를 사용할 수 밖에 없고, 실제 메모리 사용량을 정확히 예측하기 어렵다. 그리고 최대 메모리 사용량을 늘릴수록 GC 에 의해 관리되는 영역이 커지기 때문에 그만큼 오버헤드도 증가하게 된다. 반면에, GC 를 사용하지 않고 시스템 메모리를 바로 사용하면 메모리를 반환하는 즉시 재사용이 가능하고, 최대 메모리를 별도로 설정할 필요없이 시스템 메모리를 최대로 활용할 수 있으며 스왑까지 충분히 활용한다면 이론적으로는 OOM 은 발생하지 않는다.

두 번째 이유는 컬럼 기반 데이터 포맷을 사용하기 때문이다. 이로 인해 캐시 효율이 높아지고, 아래 소개할 LLVM 을 이용한 AutoVectorization 도 가능해진다.

세 번째 이유는 LLVM 을 이용하여 최적화하기 때문이다. Spark 는 바이트코드로 배포되어 JIT(JustInTime) 기술을 이용하여 실행되기 때문에 충분한 최적화를 하기가 힘들지만, Datafusion 은 LLVM 으로 컴파일한 네이티브코드를 배포하기 때문에 충분한 최적화를 할 수 있다. 이로 인해 컬럼 기반 데이터 포맷을 사용하는 Datafusion 에서는 각각의 컬럼이 연속된 메모리 공간을 차지하기 때문에 최소한의 노력으로 Vectorization 과 같은 하드웨어 가속을 바로 사용할 수 있게 된다.

8 개 정수의 합을 구하는 간단한 예제를 통해 LLVM 이 어떻게 연속된 메모리에 대한 반복 연산을 최적화하는지 살펴보자.

```rust
pub fn loop_simple(a: &[i32; 8]) -> i32 {
    let mut r: i32 = 0;
    for var in a.iter() {
        r += var;
    }
    r
}
```

아래는 위의 코드를 최적화 없이 컴파일한 결과이다. 많은 명령어와 메모리 접근이 빈번하게 발생하는 것을 볼 수 있다.

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

아래는 Vectorization 이 적용된 결과이다. 위의 코드에 비해 훨씬 적은 명령어와 메모리 접근이 발생하는 것을 볼 수 있다.

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

지금까지 몇 가지 실험을 통해 Datafusion 과 Spark 의 성능을 검증 및 분석해보았다. Datafusion 은 아직 공개된지 오래되지 않았고, 매우 활발하게 개발 중이기 때문에 앞으로 더 좋은 성능을 보여줄 것으로 기대하고 있다. 그리고 Spark 와 Trino 도 자바의 한계를 벗어나기 위해 핵심 쿼리 엔진을 [Photon](https://www.databricks.com/product/photon) 이나 [Velox](https://github.com/facebookincubator/velox) 로 교체하려는 시도를 하고 있고, [Spark 의 쿼리 엔진을 Datafusion 으로 교체하려는 시도](https://github.com/apache/datafusion-comet)도 이미 진행 중이기 때문에 앞으로 많은 변화가 있을 것으로 기대된다.