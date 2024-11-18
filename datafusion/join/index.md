대부분의 SQL 엔진에서 성능 향상을 위해 가장 많이 신경쓰는 부분은 바로 조인(Join)일 것이다. 다양한 조건의 조인을 처리하기 위해 여러 가지 동작 방식이 존재하며, 오늘은 Datafusion 에서 어떤 방식으로 조인을 처리하는지, 어떤 방법으로 최적화하는지 살펴보도록 하자.

SQL 엔진에서는 크게 보면 3 가지 정도의 방식으로 조인을 처리한다.

![join0.png](./join0.png)

![join1.png](./join1.png)

![join2.png](./join2.png)

![join.strategies.png](./join.strategies.png)
