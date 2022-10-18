델타레이크는 효율적인 읽기 작업을 위해 여러 가지 최적화 기법을 제공한다. 최적화 기법은 크게 델타로그를 이용해서 데이터 파일을 필터링하는 방식과 파케이(Parquet)가 제공하는 필터링 기능을 이용하는 방식으로 나뉜다. 오늘은 필수적인 최적화 기법들을 하나씩 살펴보고자 한다.
(델타레이크의 모든 데이터 파일은 파케이 형식이다.)

## Partition Pruning

델타레이크는 사용 중인 파티션 필드에 대한 정보를 메타데이타(metadata) 로그에 담고 있다. 아래 예제를 보면 두 개의 파티션 필드(year, gender)를 사용하고 있는 것을 알 수 있다.

```python
{"metaData":{..., "partitionColumns":["year","gender"], ...}}
```

각각의 데이터 파일에 대한 파티션 정보는 아래와 같이 파일 추가(add) 로그에 저장하고 있다. partitionValues 필드에 각각의 파티션 정보를 가지고 있는데, 아래 예제에서 첫 번째 데이터 파일의 year 필드는 "2000" 이고 gender 필드는 "male" 이다.

```python
...
{"add":{"path":"year=2000/gender=male/part-00001-bb169a3b-6b2f-4432-a686-c5c596526780.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"male"}, ...}
{"add":{"path":"year=2000/gender=male/part-00003-e0c02983-d88b-4a70-9855-42cc1a8766a5.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"male"}, ...}
{"add":{"path":"year=2000/gender=male/part-00004-73109c31-e7e3-4674-8e8e-24c2bed9da35.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"male"}, ...}
...
```

델타레이크는 내부적으로 필요한 로그 정보를 스파크의 데이터프레임으로 관리하고 있고, 위의 파일 추가(add) 로그만을 모은 데이터프레임에서 partitionValues 필드를 필터링하는 방식으로 동작하기 때문에 파일의 수가 많아도 빠르게 병렬 처리가 가능하다.

## Predicate Pushdown

### DeltaLog

### Parquet

## Projection Pruning
