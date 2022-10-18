델타레이크는 효율적인 읽기 작업을 위해 여러 가지 최적화 기법을 제공한다. 최적화 기법은 크게 델타로그를 이용해서 데이터 파일을 필터링하는 방식과 파케이(Parquet)가 제공하는 필터링 기능을 이용하는 방식으로 나뉜다. 오늘은 아래 예제를 이용해서 필수적인 최적화 기법들이 어떻게 적용되는지 하나씩 살펴보자.
(델타레이크의 모든 데이터 파일은 파케이(Parquet) 형식이다.)

```python
...
df = df
    .where(df.year == "2000")
    .where(df.gender == "male")
    .where(df.salary >= 4000)
    .select("year", "gender", "salary")
...
```

## Partition Pruning

델타레이크는 사용 중인 파티션 필드에 대한 정보를 메타데이타(metadata) 로그에 담고 있다. 아래 로그를 보면 두 개의 파티션 필드(year, gender)를 사용하고 있는 것을 알 수 있다.

```json
{"metaData": {"partitionColumns": ["year", "gender"]}}
```

각각의 데이터 파일에 대한 파티션 정보는 아래와 같이 파일추가(add) 로그에 저장되어 있다. partitionValues 필드에 각각의 파티션 정보를 가지고 있는데, 아래 로그에서 첫 번째 데이터 파일의 year 필드는 "2000" 이고 gender 필드는 "male" 인 것을 볼 수 있다. 그래서 데이터 파일의 경로(path)는 "year=2000/gender=male/.." 로 시작한다.

```json
{"add":{"path":"year=2000/gender=male/part-00001-bb169a3b-6b2f-4432-a686-c5c596526780.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"male"}}
{"add":{"path":"year=2000/gender=male/part-00003-e0c02983-d88b-4a70-9855-42cc1a8766a5.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"male"}}
```

델타레이크는 내부적으로 필요한 로그 정보를 스파크의 데이터프레임으로 관리하고 있고, 위의 파일추가(add) 로그만을 모은 데이터프레임에서 partitionValues 필드를 필터링하는 방식으로 동작하기 때문에 파일의 수가 많아도 빠르게 병렬 처리가 가능하다.

아래는 예제의 물리적 실행 계획에서 파티션 프루닝이 적용된 모습이다. 예제의 조건문(where) 중에서 파티션 필드에 해당하는 year, gender 필드만 추가되어있다.

```
+- FileScan parquet PartitionFilters: [isnotnull(year#502), isnotnull(gender#503), (year#502 = 2000), (gender#503 = male)], ...
```

## Predicate Pushdown

델타레이크에서 조건절 푸시다운(Predicate Pushdown)은 크게 두 단계로 동작한다. 첫 번째 단계는 델타로그의 파일추가 로그에 있는 통계 정보를 이용하여 데이터 파일을 필터링하는 것이고, 두 번째 단계는 파케이가 제공하는 푸시다운 기능을 이용하여 행 그룹을 필터링하는 것이다.

우선 델타로그부터 살펴보자. 아래 파일추가 로그에서 통계 정보인 stats 필드를 보면 각 필드의 최대값(maxValues)과 최소값(minValues)을 알 수 있기 때문에, 파티션 프루닝과 마찬가지로 파일추가 로그만을 모은 데이터프레임에서 stats 필드를 필터링하는 방식으로 빠르게 조건에 맞는 파일들을 찾을 수 있다.

```json
{"add":{"path":"year=2000/gender=male/part-00001-bb169a3b-6b2f-4432-a686-c5c596526780.c000.snappy.parquet","stats":"{\"numRecords\":1,\"minValues\":{\"firstname\":\"James\",\"middlename\":\"\",\"lastname\":\"Smith\",\"salary\":3000},\"maxValues\":{\"firstname\":\"James\",\"middlename\":\"\",\"lastname\":\"Smith\",\"salary\":3000},\"nullCount\":{\"firstname\":0,\"middlename\":0,\"lastname\":0,\"salary\":0}}"}}
{"add":{"path":"year=2000/gender=male/part-00003-e0c02983-d88b-4a70-9855-42cc1a8766a5.c000.snappy.parquet","stats":"{\"numRecords\":1,\"minValues\":{\"firstname\":\"Michael\",\"middlename\":\"Rose\",\"lastname\":\"\",\"salary\":4000},\"maxValues\":{\"firstname\":\"Michael\",\"middlename\":\"Rose\",\"lastname\":\"\",\"salary\":4000},\"nullCount\":{\"firstname\":0,\"middlename\":0,\"lastname\":0,\"salary\":0}}"}}
```

아래는 예제의 물리적 실행 계획에서 조건절 푸시다운이 적용된 모습이다. 예제의 조건문 중에서 파티션 필드를 제외한 salary 필드만 추가되어있다.

```
+- FileScan parquet DataFilters: [isnotnull(salary#504L), (salary#504L >= 4000)], ...
```

그리고 스파크가 이미 파케이 파일에 대한 푸시다운 기능을 제공하고 있기 때문에 이를 활용하면, 데이터 파일 전체가 아닌 필요한 행 그룹만을 빠르게 가져올 수 있다. 아래는 예제의 물리적 실행 계획에서 조건절 푸시다운이 적용된 모습이다. 파티션 필드는 파케이 파일에 포함되어 있지 않기 때문에 파티션 필드를 제외한 salary 필드만 추가되어있다.

```
+- FileScan parquet PushedFilters: [IsNotNull(salary), GreaterThanOrEqual(salary,4000)], ...
```

## Projection Pruning

파케이 파일에서 특정 필드만 읽는 기능도 스파크가 이미 제공하고 있기 때문에 이를 활용하면 불필요한 필드를 가져오는 비용을 줄일 수 있다. 아래는 예제의 물리적 실행 계획에서 프로젝션 프루닝이 적용된 모습이다. 예제의 선택문(select) 중에서 파티션 필드는 파케이 파일에 포함되어 있지 않기 때문에 파티션 필드를 제외한 salary 필드만 추가되어있다.

```
+- FileScan parquet ReadSchema: struct<salary:bigint>, ...
```

지금까지 소개한 최적화 기법을 이용하면 델타레이크를 통해 필요한 데이터 파일에서, 필요한 행 그룹에서, 필요한 필드만을 효과적으로 가져와서 처리할 수 있다.
