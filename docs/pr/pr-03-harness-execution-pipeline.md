# PR #3 Harness 실행 파이프라인

## 요약

- Skill 실행 공통 진입점으로 `Harness`를 도입한다.
- Harness v1은 의도적으로 최소 기능만 제공하며 `skill.execute(request)`에 실행을 위임한다.
- Harness는 상태를 보관하지 않는다.

## 주요 변경

- `app/harness` 패키지를 추가한다.
- `Harness.run()` 계약은 다음과 같다.

```python
async def run(
    self,
    skill: Skill[RequestT, DataT, MetadataT],
    request: RequestT,
) -> SkillResult[DataT, MetadataT]:
    ...
```

현재 구현은 `return await skill.execute(request)`다.

## 설계 규칙과 테스트

- Harness는 실행 상태를 저장하지 않고 전달받은 Skill과 Request만 사용한다.
- 하나의 Harness 인스턴스를 여러 번 재사용해도 이전 결과가 누출되지 않는다.
- 직접 Skill 실행과 Harness 실행의 동등성 및 async `anyio` 테스트를 검증한다.

## 범위 제외

- Hook, retry, 로깅, 메트릭, tracing, LangGraph, workflow, 다중 Skill·병렬 실행,
  이벤트 시스템, DI container.
