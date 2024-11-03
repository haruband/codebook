[Datafusion](https://github.com/apache/datafusion) 은 최근 빅데이터 분야에서 널리 사용되고 있는 [Arrow](https://arrow.apache.org/) 를 이용하여 Rust 기반으로 개발 중인 임베딩 SQL 엔진이다. 이미 다양한 분야에서 활용되고 있는 [DuckDB](https://github.com/duckdb/duckdb) 와 유사한 목적을 가지고 있지만, Rust 로 개발 중이기 때문에 메모리 관리가 편리하고 확장성이 굉장히 뛰어나다는 장점이 있다. 이러한 장점들로 인해 최근 Datafusion 을 이용하여 기존 솔루션보다 탁월한 성능을 보여주는 새로운 오픈소스들이 많이 등장하고 있고, 특히 Java/Scala 중심의 빅데이터 분야에서 많은 변화를 주도할 것으로 기대된다. 그럼 이제 Datafusion 에 대해 자세히 살펴보도록 하자.

우선, 오랜 시간 널리 사용되고 있는 Spark 와 비교했을 때 어떤 부분이 차이가 있는지 살펴보도록 하자. (Spark 와 비교하는 이유는, Datafusion 을 Pandas 와 비교할 수도 있겠지만 개인적으로 Spark 의 대체제로 활용하고 있기 때문이다.)

### 설치/운영

Spark 는 대규모 클러스터 환경에서 빅데이터를 처리하기 위해 개발되었기 때문에 설치와 운영에 높은 전문 지식과 노력이 필요하다. 하지만 Datafusion 은 어디에나 임베딩할 수 있기 때문에 비교적 간단하게 사용할 수 있고, 수백대에서 수천대의 대규모 클러스터에서 처리하는 데이터를 처리하긴 힘들지만 수십대의 클러스터에서 처리하는 데이터는 처리할 수 있다. 그리고 서버에 설치할 수 있는 CPU 와 메모리가 늘어날수록 처리할 수 있는 데이터는 지속적으로 늘어날 것이다. (참고로, Datafusion 을 [분산 클러스터 환경에서 사용하려는 시도](https://github.com/apache/datafusion-ray)도 있긴 하다.)

### 데이터 구조

Spark 는 기본적으로 Row 기반으로 동작하기 때문에 Column 단위로 분석하는 요청에서는 효율이 떨어진다. 이러한 문제를 해결하기 위해 C++ 를 이용한 Column 기반의 [새로운 엔진](https://www.databricks.com/product/photon)과 Arrow 기반의 [Velox](https://github.com/facebookincubator/velox) 를 실행 엔진으로 사용하려는 시도가 있지만, 아직 여러 가지 제약 사항이 많다. 하지만 Arrow 기반의 Datafusion 은 Column 단위로 동작하기 때문에 대부분의 분석 쿼리에서 효율적으로 동작한다. 여기에는 연속된 메모리에 대한 반복 처리를 자동으로 Vectorization 해주는 LLVM 의 AutoVectorization 이 큰 역할을 하고 있다.

### 메모리 관리

Java 에서 메모리 관리를 도와주는 GC (Garbage Collection) 는 다양한 문제를 유발한다. GC 가 동작할 때마다 시스템 자원을 낭비하고 예측할 수 없는 지연시간을 발생시키기도 하며, 예상하기 힘든 OOM (Out-Of-Memory) 의 원인이 되기도 한다. 그리고 더 많은 메모리가 필요해서 JVM 이 사용하는 힙(Heap)의 크기를 늘리면 GC 에 의해 관리되는 영역도 늘어나기 때문에 앞서 언급한 문제들이 더욱 심각해질 수 있다. 하지만 Rust 는 GC 없이 메모리 안정성을 보장하기 때문에 필요한 만큼 시스템 메모리를 사용할 수 있고, 스왑 메모리도 효과적으로 사용할 수 있다. Java 는 GC 에 의해 메모리를 적절히 정리하지 않으면 예기치 못한 OOM 이 발생하지만, Rust 는 커널이 직접 제공하는 스왑 기능 덕분에 충분한 시스템 메모리와 스왑 메모리만 있다면 OOM 은 발생하지 않는다.

### 실행 방식

Java 는 바이트 코드로 컴파일되어 배포되기 때문에 성능을 높이기 위해 JIT (Just-In-Time) 방식을 사용하고 있다. 이는 자주 실행되는 바이트 코드를 런타임에 컴파일하여 네이티브 코드(x86, arm, ...)로 변환하는 기술인데, 이를 위한 준비 과정이 필요하며 LLVM 과 같은 컴파일러에 비해 충분한 최적화가 이루어지지 않는 문제가 있다. 하지만 Rust 는 네이티브 코드로 컴파일되어 배포되기 때문에 LLVM 이 제공하는 높은 수준의 최적화를 충분히 활용할 수 있다.

아래 그림은 Datafusion 이 동작하는 방식을 간단히 보여주고 있다. (대부분의 SQL 엔진이 비슷한 방식으로 동작한다.)

![overview.png](./overview.png)

동작 과정을 정리해보면 아래와 같다.

1. SQL 쿼리 혹은 DataFrame 을 논리 계획으로 변환
2. 논리 계획 최적화 (ConstantFolding, CommonSubexpressionElimination, ...)
3. 논리 계획을 실행 계획으로 변환
4. 실행 계획 최적화 (Sort, Aggregation, Join, ...)
5. 실행 계획에서 스트림 추출
6. 스트림에서 데이터 수집

일반적인 컴파일러가 동작하는 방식과 유사한 부분이 많은데, 논리 계획(LogicalPlan)은 상위 수준 중간 언어(IR)라고 보면 되고 실행 계획(ExecutionPlan)은 하위 수준 중간 언어라고 보면 된다. 논리 계획과 실행 계획은 실제 데이터를 수집 및 처리하는 역할을 하는 스트림(Stream)을 생성하고, 하나의 스트림은 하나의 파티션을 하나의 스레드에서 처리한다고 생각하면 간단하다. 데이터는 현재 표준처럼 널리 사용되고 있는 Arrow 의 RecordBatch 형식을 사용한다.

간단한 예제를 보면서, SQL 쿼리가 논리 계획과 실행 계획으로 어떻게 변환되는지, 최적화에 의해 실행 계획과 스트림이 어떻게 변환되는지 살펴보도록 하자.

데이터(Parquet) 파일을 읽어서 정렬한 후 두 개의 컬럼을 보여주는 간단한 SQL 쿼리를 실행해보자.

```sql
select company,score from table order by score asc
```

위의 쿼리는 아래와 같은 논리 계획으로 변환된다.

```
Sort: table.score ASC NULLS LAST
  TableScan: table projection=[company, score]
```

위의 논리 계획은 테이블에서 두 개의 컬럼[company, score]을 읽어서 전달하는 부분(TableScan)과 전달받은 데이터를 정렬하는 부분(Sort)으로 구성되어 있다. (실제 데이터는 아래에서 위로 전달된다.) 위의 논리 계획은 아래와 같은 실행 계획으로 변환된다.

```
SortExec: expr=[score@1 ASC NULLS LAST], preserve_partitioning=[false]
  ParquetExec: file_groups={1 group: [[file0.parquet, file1.parquet]]}, projection=[company, score]
```

테이블을 읽는 논리 계획(TableScan)은 데이터(Parquet) 파일의 형식에 따라 실행 계획(ParquetExec)으로 변환되었고, 정렬하는 논리 계획(Sort)은 여러 가지 상황에 따라 실행 계획(SortExec)으로 변환되었다. 논리 계획도 마찬가지이지만, 최적화 옵션이나 여러 가지 상황에 따라서 실행 계획은 달라진다. 위의 실행 계획이 실행되면, SortExec 가 아래 그림의 SortStream 을, ParquetExec 가 아래 그림의 FileStream 을 생성한다.

![streams0.png](./streams0.png)

체인 형태로 연결된 스트림은 유효한 데이터가 더 이상 없을때까지 반복적으로 실행되면서 데이터를 뒤에서 앞으로 전달하는 방식으로 동작한다. FileStream 은 두 개의 데이터 파일을 읽어서 SortStream 으로 전달하고, SortStream 은 모든 데이터를 수집한 다음 정렬한 결과를 전달한다.

위의 예제를 자세히 살펴보면, 두 개의 파일을 하나의 스트림에서 읽는 것을 볼 수 있다. 이를 조금 더 개선할 수 있는 방법은 없을까? 두 개의 파일을 두 개의 스트림에서 각각 읽는다면 성능이 개선될 수 있지 않을까? Datafusion 에서는 파티션 개수를 조절하여 이를 개선할 수 있다. 아래는 두 개의 파티션을 사용하도록 설정했을 때의 실행 계획을 보여준다.

```
SortExec: expr=[score@1 ASC NULLS LAST],
preserve_partitioning=[false]
  CoalescePartitionsExec
    ParquetExec: file_groups={2 groups: [[file0.parquet], [file1.parquet]]}, projection=[company, score]
```

두 개의 파티션을 사용하도록 설정했더니 ParquetExec 에서 두 개의 파일 그룹이 생성된 것을 볼 수 있다. 이 실행 계획은 아래 그림처럼 각각의 파일 그룹을 처리하는 두 개의 FileStream 을 생성한다.

![streams1.png](./streams1.png)

이제 두 개의 FileStream 은 각각 하나의 데이터 파일을 읽고, CoalesceStream 에서 두 개의 FileStream 을 하나로 합쳐서 SortStream 에 전달한다.

위의 실행 계획은 어떤 문제를 가지고 있을까? 여러 데이터 파일을 병렬로 읽는 부분은 좋지만, 이를 하나로 합쳐서 정렬하는 부분은 개선의 여지가 있어보인다. Datafusion 에서는 파티션별로 먼저 정렬하는 병합 정렬(MergeSort)을 지원하기 때문에 이를 활용하여 실행 계획을 조금 더 개선해보자.

```
SortPreservingMergeExec: [score@1 ASC NULLS LAST]
  SortExec: expr=[score@1 ASC NULLS LAST], preserve_partitioning=[true]
    ParquetExec: file_groups={2 groups: [[file0.parquet], [file1.parquet]]}, projection=[company, score]
```

위의 실행 계획은 아래와 같은 스트림을 생성한다.

![streams2.png](./streams2.png)

두 개의 FileStream 이 각각 하나의 데이터 파일을 읽고 SortStream 에서 각각 정렬한 다음, SortPreservingMergeStream 이 합쳐서 최종적으로 정렬한다.

지금까지 Datafusion 이 어떻게 동작하는지를 하나의 예제를 통해 살펴보았다. 이외에도 다양한 쿼리와 최적화를 지원하고 있고, 이미 충분히 좋은 성능을 보여주고 있지만 굉장히 활발하게 새로운 기능이 추가되고 개선되고 있다. Datafusion 을 기반으로 새롭게 등장한 여러 솔루션처럼 Datafusion 은 여러 가지 문제에 대한 새로운 가능성으로 충분히 자리매김할 것으로 기대된다.
