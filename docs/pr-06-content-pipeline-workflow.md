# PR #6 ContentPipelineWorkflow

## 요약

- 여러 Skill을 순차 파이프라인으로 실행하는 `ContentPipelineWorkflow`를 도입한다.
- Workflow는 Harness로 Skill을 실행하고 순서와 데이터 전달만 관리한다.
- 최종 출력은 원시 `SkillResult`가 아닌 `ContentPipelineResult`다.

## 구조와 주요 변경

```text
ContentPipelineWorkflow -> Harness -> CollectPostsSkill -> ScreenPostsSkill -> GenerateScriptSkill
                                                   -> ContentPipelineResult
```

- `app/models/workflow.py`에 `ContentPipelineRequest`, `ContentPipelineResult`를 추가한다.
- `app/workflows`에 `Workflow`, `ContentPipelineWorkflow`를 추가한다.
- 요청은 `sources: List[CommunityType]`, `limit`, `period: timedelta`,
  `category: Optional[str]`를 포함하며 별도 `Source` 모델은 만들지 않는다.
- 결과는 `posts`, `candidates`, `scripts`를 포함한다.

## 실행 흐름

1. `ContentPipelineRequest`로 `CollectPostsRequest`를 만든다.
2. Harness로 `CollectPostsSkill`을 실행한다.
3. 수집 게시글로 `ScreenPostsRequest`를 만들고 Skill을 실행한다.
4. 후보로 `GenerateScriptRequest`를 만들고 Skill을 실행한다.
5. 조합한 `ContentPipelineResult`를 반환한다.

## 설계 규칙과 테스트

- Workflow는 Harness와 모든 Skill을 생성자 주입받고 직접 생성하지 않는다.
- 모든 Skill 실행은 `harness.run()`을 거치며 Workflow는 순차·무상태이고 SkillResult를 반환하지 않는다.
- 실행 순서, 단계 간 데이터 전달, 결과 조합, collect/screen/generate 실패 전파를 검증한다.

## 범위 제외

- OpenAI/Claude/Gemini, 프롬프트, retry, guardrail, reflection, model routing,
  LangGraph, 병렬·부분 성공, 상태 저장, 핵심 계약·Harness·기존 Skill 변경.
