데이터를 분석할 때 가장 많이 사용하는 기능은 대부분 집계일 것이다. 특히, 시계열 데이터를 분석할 때는 시간대별 통계를 자주 사용하기 때문에 무엇보다 집계의 성능이 중요하다. 그래서 오늘은 Datafusion 에서 이러한 집계가 어떤 과정으로 이루어지는지, 그리고 어떤 방법으로 최적화가 이루어지는지 살펴보도록 하자.

간단한 집계를 위한 SQL 쿼리를 실행해보자. 아래는 국가별/직업별 최소 수입과 평균 수입을 구하는 쿼리이다.

```sql
select country, job, min(salary), avg(salary) from table group by country, job
```

위의 쿼리는 아래와 같은 논리 계획으로 변환된다.

```
Aggregate: groupBy=[[table.country, table.job]], aggr=[[min(table.salary), avg(CAST(table.salary AS Float64))]]
  TableScan: table projection=[country, job, salary]
```

위의 논리 계획은 테이블에서 세 개의 컬럼[country, job, salary]을 읽어서 두 개의 컬럼[country, job]으로 정렬한 다음, 그룹별 최소 수입[min(salary)]과 평균 수입[avg(salary)]을 구하는 것이다. 위의 논리 계획은 아래와 같은 실행 계획으로 변환된다.

```
AggregateExec: mode=Single, gby=[country@0 as country, job@1 as job], aggr=[min(table.salary), avg(table.salary)]
  CsvExec: file_groups={1 group: [[salary.csv]]}, projection=[country, job, salary], has_header=true
```

위의 실행 계획은 데이터(CSV) 파일을 읽는 **CsvExec** 실행 계획과 모든 입력을 받아서 집계를 구하는 **AggregateExec(Single)** 실행 계획으로 구성되어 있다.
