# PR #4 ScreenPostsSkill

## 요약

- 수집 게시글에서 숏폼 후보를 선택하는 `ScreenPostsSkill`을 도입한다.
- 실제 LLM 대신 교체 가능한 `PostEvaluator`에 평가 판단을 위임한다.
- Skill은 `is_candidate=True`인 평가 결과만 필터링한다.

## 주요 변경과 모델 의미

- `app/models/screen_posts.py`에 `ScreenPostsRequest`, `ScreeningResult`,
  `PostEvaluationResult`, `ScreenPostsData`, `ScreenPostsMetadata`를 추가한다.
- `app/evaluators`에 `PostEvaluator`, `MockPostEvaluator`를, Skill을 추가한다.
- `PostEvaluationResult.posts`는 모든 입력 게시글의 평가 결과이고,
  `ScreenPostsData.candidates`는 최종 숏폼 후보만 의미한다.
- `ScreeningResult`는 `post`, `score`, `is_candidate`, `reasons`를 포함한다.
  `reasons`는 enum이나 내부 코드가 아닌 사람이 읽을 수 있는 설명이다.

## 설계 규칙

- `PostEvaluator.evaluate(posts)`는 게시글 목록 전체를 한 번에 평가하며 구현체는 stateless다.
- Skill은 `evaluator.evaluate(request.posts)`를 호출하고 후보 여부만 필터링한다.
- 후보 수 제한, 점수 정렬, 카테고리 균형, 다양성 로직은 포함하지 않는다.
- 이후 후보 선택 정책 확장은 `PostEvaluator`가 아닌 `ScreenPostsSkill`에 둔다.

## 테스트와 범위 제외

- mock 평가 결과, 0..100 점수, 설명 문자열, 후보 필터, 입력 순서, 메타데이터,
  예외 전파와 Harness 실행을 검증한다.
- 실제 LLM, 프롬프트, OpenAI/Claude/Gemini, LangGraph, workflow, RAG, 벡터 검색은 제외한다.
