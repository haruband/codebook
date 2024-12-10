[Datafusion](https://github.com/apache/datafusion) 은 [Arrow](https://arrow.apache.org) 를 이용하여 Rust 기반으로 개발 중인 임베딩 SQL 엔진이다. 그래서 Scala 기반으로 개발되어 JVM 위에서 동작하는 [Spark](https://spark.apache.org) 에 비해 아래와 같은 장점을 가진다.

* Column 기반 데이터 처리 (Arrow)
* GC 없이 메모리 안정성 보장
* LLVM 기반 최적화 (Vectorization, ...)

그렇다면 이러한 장점들이 실제 성능에는 얼마나 영향을 주는지 알아보도록 하자. 오늘은 단일 머신에서의 성능만을 비교하고, 추후에 [Ballista](https://datafusion.apache.org/ballista) 와 같은 Datafusion 기반의 분산 처리 기술을 이용하여 분산 처리 성능도 비교해보도록 하겠다.

실험은 OLAP 성능 검증을 위해 자주 사용되는 TPC-H (SF1000) 를 이용하였다.

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