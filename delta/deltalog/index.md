스파크로 유명한 데이터브릭스에서 몇 년전에 공개한 델타레이크(DeltaLake)라는 기술은 데이터레이크와 데이터웨어하우스의 장점을 합친 레이크하우스 아키텍처의 핵심 기술이다. 이는 기존에 (기술적인/비용적인 한계로 인해) 원시 데이터는 데이터레이크에, 가공 데이터는 데이터웨어하우스에 저장하던 방식에서 원시/가공 데이터 모두를 하나의 레이크하우스에 저장하는 방식으로 개선하여 효율적으로 빅데이터 플랫폼을 구축 및 관리할 수 있게 만들고 있다. 오늘은 데이터브릭스에서 레이크하우스의 핵심 기술로 개발하고 있는 델타레이크의 가장 중요한 부분인 델타로그(DeltaLog)에 대해 간단히 살펴보도록 하자.

레이크하우스를 한 마디로 표현하면 ACID(Atomic, Isolated, Consistent, Durable)를 지원하는 데이터레이크라고 볼 수 있다. 즉, 데이터레이크에서 주로 사용하는 저렴한 스토리지를 이용하여 데이터웨어하우스만의 장점인 ACID 를 지원하는 것이 핵심이다. 그럼 어떻게 일반적인 스토리지 위에서 안정적인 트랜잭션을 지원할 수 있는 것일까? 그 해답이 바로 델타로그이다.

델타레이크는 한 번의 쓰기 작업에서 반드시 하나의 로그 파일을 생성한다. 파티셔닝이나 파일당 크기 제한 등으로 인해 여러 개의 데이터 파일이 생성되더라도 해당 쓰기 작업의 모든 행위(Action)는 하나의 로그 파일에 모두 기록된다. 간단한 예제를 통해 조금 더 자세히 살펴보자.

아래는 스파크로 개발한 간단한 예제 프로그램을 실행한 결과이다. 보이는 것처럼 한 번의 쓰기 작업에 총 6 개의 데이터 파일과 1 개의 로그 파일이 생성되었다. (델타레이크는 모든 로그 파일을 \_delta_log 폴더 아래에 생성한다.)

```bash
_delta_log:
00000000000000000000.json

year=2000:
gender=female
gender=male

year=2000/gender=female:
part-00006-26150ffe-fdf8-4c02-9d85-01b90ee89a1f.c000.snappy.parquet
part-00008-b15e93a7-b28b-4cf3-83ff-6801ee091dfe.c000.snappy.parquet

year=2000/gender=male:
part-00001-cbe08f85-1931-41ad-b717-801b41be7365.c000.snappy.parquet
part-00003-56fab23c-5a87-4ed7-8834-b96d866d9e9f.c000.snappy.parquet
part-00004-a0465a5a-6592-4dde-a8c3-8716462d8d90.c000.snappy.parquet

year=2020:
gender=female

year=2020/gender=female:
part-00009-1d1c1c04-838f-407e-b722-6a46d4a8c992.c000.snappy.parquet
```

그리고 아래는 위의 로그 파일의 내용이다. 다른 내용은 생략하고, 총 6 개의 데이터 파일이 추가(add)되었다는 내용만 남겨두었다.

```bash
...
{"add":{"path":"year=2000/gender=male/part-00001-cbe08f85-1931-41ad-b717-801b41be7365.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"male"},"size":1221,"modificationTime":1665794476795,"dataChange":true,"stats":"{\"numRecords\":1,\"minValues\":{\"firstname\":\"James\",\"middlename\":\"\",\"lastname\":\"Smith\",\"salary\":3000},\"maxValues\":{\"firstname\":\"James\",\"middlename\":\"\",\"lastname\":\"Smith\",\"salary\":3000},\"nullCount\":{\"firstname\":0,\"middlename\":0,\"lastname\":0,\"salary\":0}}"}}
{"add":{"path":"year=2000/gender=male/part-00003-56fab23c-5a87-4ed7-8834-b96d866d9e9f.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"male"},"size":1228,"modificationTime":1665794476795,"dataChange":true,"stats":"{\"numRecords\":1,\"minValues\":{\"firstname\":\"Michael\",\"middlename\":\"Rose\",\"lastname\":\"\",\"salary\":4000},\"maxValues\":{\"firstname\":\"Michael\",\"middlename\":\"Rose\",\"lastname\":\"\",\"salary\":4000},\"nullCount\":{\"firstname\":0,\"middlename\":0,\"lastname\":0,\"salary\":0}}"}}
{"add":{"path":"year=2000/gender=male/part-00004-a0465a5a-6592-4dde-a8c3-8716462d8d90.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"male"},"size":1249,"modificationTime":1665794476795,"dataChange":true,"stats":"{\"numRecords\":1,\"minValues\":{\"firstname\":\"Robert\",\"middlename\":\"\",\"lastname\":\"Williams\",\"salary\":4000},\"maxValues\":{\"firstname\":\"Robert\",\"middlename\":\"\",\"lastname\":\"Williams\",\"salary\":4000},\"nullCount\":{\"firstname\":0,\"middlename\":0,\"lastname\":0,\"salary\":0}}"}}
{"add":{"path":"year=2000/gender=female/part-00006-26150ffe-fdf8-4c02-9d85-01b90ee89a1f.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"female"},"size":1248,"modificationTime":1665794476796,"dataChange":true,"stats":"{\"numRecords\":1,\"minValues\":{\"firstname\":\"Maria\",\"middlename\":\"Anne\",\"lastname\":\"Jones\",\"salary\":4000},\"maxValues\":{\"firstname\":\"Maria\",\"middlename\":\"Anne\",\"lastname\":\"Jones\",\"salary\":4000},\"nullCount\":{\"firstname\":0,\"middlename\":0,\"lastname\":0,\"salary\":0}}"}}
{"add":{"path":"year=2000/gender=female/part-00008-b15e93a7-b28b-4cf3-83ff-6801ee091dfe.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"female"},"size":1248,"modificationTime":1665794476795,"dataChange":true,"stats":"{\"numRecords\":1,\"minValues\":{\"firstname\":\"Jennifer\",\"middlename\":\"\",\"lastname\":\"Cherry\",\"salary\":4200},\"maxValues\":{\"firstname\":\"Jennifer\",\"middlename\":\"\",\"lastname\":\"Cherry\",\"salary\":4200},\"nullCount\":{\"firstname\":0,\"middlename\":0,\"lastname\":0,\"salary\":0}}"}}
{"add":{"path":"year=2020/gender=female/part-00009-1d1c1c04-838f-407e-b722-6a46d4a8c992.c000.snappy.parquet","partitionValues":{"year":"2020","gender":"female"},"size":1234,"modificationTime":1665794476795,"dataChange":true,"stats":"{\"numRecords\":1,\"minValues\":{\"firstname\":\"Jen\",\"middlename\":\"Mary\",\"lastname\":\"Brown\",\"salary\":-1},\"maxValues\":{\"firstname\":\"Jen\",\"middlename\":\"Mary\",\"lastname\":\"Brown\",\"salary\":-1},\"nullCount\":{\"firstname\":0,\"middlename\":0,\"lastname\":0,\"salary\":0}}"}}
...
```

그렇다면 기존 데이터를 삭제하거나 변경하면 어떻게 될까? 이 또한 간단하다. 아래는 기존 데이터를 변경했을 때 추가로 생성된 로그 파일의 내용이다.

```bash
...
{"remove":{"path":"year=2000/gender=male/part-00001-cbe08f85-1931-41ad-b717-801b41be7365.c000.snappy.parquet","deletionTimestamp":1665795385572,"dataChange":true,"extendedFileMetadata":true,"partitionValues":{"year":"2000","gender":"male"},"size":1221}}
{"add":{"path":"year=2000/gender=male/part-00001-53b311c3-d70e-495e-9868-82b4fc8c1ed9.c000.snappy.parquet","partitionValues":{"year":"2000","gender":"male"},"size":1221,"modificationTime":1665795383719,"dataChange":true,"stats":"{\"numRecords\":1,\"minValues\":{\"firstname\":\"James\",\"middlename\":\"\",\"lastname\":\"Smith\",\"salary\":3000},\"maxValues\":{\"firstname\":\"James\",\"middlename\":\"\",\"lastname\":\"Smith\",\"salary\":3000},\"nullCount\":{\"firstname\":0,\"middlename\":0,\"lastname\":0,\"salary\":0}}"}}
...
```

마찬가지로 다른 내용은 생략하고, 기존 데이터 파일은 삭제(remove)되고 변경된 데이터 파일이 추가(add)되었다는 내용만 남겨두었다.

이처럼 쓰기 작업은 간단하지만, 모든 로그 기반 시스템이 그렇듯이, 읽기 작업은 간단하지 않다. 기본적으로 모든 로그 히스토리를 순차적으로 분석해서 마지막 상태 정보를 담고 있는 스냅샷(Snapshot)을 만드는 작업이 필요한데, 쓰기 작업이 반복될수록 로그 파일이 많아져서 스냅샷을 만드는 작업이 점점 더 오래 걸릴 수 밖에 없어진다. 이 문제를 개선하기 위해 델타레이크는 체크포인트(Checkpoint)라는 기능을 제공한다. 이는 간단히 말하면 해당 시점까지의 모든 로그를 가지고 있는 하나의 파일(Parquet)을 만드는 것이다.

아래는 25 번의 쓰기 작업이 실행된 결과이다. 0~24 까지 총 25 개의 로그 파일이 생성되었지만, 10 번마다 체크포인트 파일이 추가된걸 볼 수 있다. 델타레이크는 10 의 배수에 해당하는 로그 파일을 쓸 때 과거 모든 기록을 담고 있는 체크포인트 파일도 같이 추가한다. 그리고 마지막에 보이는 \_last_checkpoint 파일은 마지막에 생성한 체크포인트의 번호를 가지고 있다.

```bash
_delta_log:
00000000000000000000.json
00000000000000000001.json
00000000000000000002.json
00000000000000000003.json
00000000000000000004.json
00000000000000000005.json
00000000000000000006.json
00000000000000000007.json
00000000000000000008.json
00000000000000000009.json
00000000000000000010.checkpoint.parquet
00000000000000000010.json
00000000000000000011.json
00000000000000000012.json
00000000000000000013.json
00000000000000000014.json
00000000000000000015.json
00000000000000000016.json
00000000000000000017.json
00000000000000000018.json
00000000000000000019.json
00000000000000000020.checkpoint.parquet
00000000000000000020.json
00000000000000000021.json
00000000000000000022.json
00000000000000000023.json
00000000000000000024.json
_last_checkpoint
```

정리하면, 델타레이크에서 읽기 작업이 이루어지는 과정은 아래와 같다.

1. \_last_checkpoint 파일에서 마지막 체크포인트 번호를 가져온다.
2. 마지막 체크포인트 파일을 읽는다.
3. 마지막 체크포인트 파일 이후에 생성된 로그 파일들을 읽는다.

그래서 로그 파일이 아무리 많이 쌓이더라도 스냅샷을 만들 때 필요한 파일은 최대 11 개뿐이다. (\_last_checkpoint, checkpoint file, x1~x9.json files)
