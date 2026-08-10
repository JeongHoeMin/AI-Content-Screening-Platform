# PR #5 GenerateScriptSkill

## 요약

- 심사된 후보에서 스크립트를 생성하는 `GenerateScriptSkill`을 도입한다.
- 실제 LLM 대신 교체 가능한 `ScriptGenerator`에 생성을 위임한다.
- Skill은 Generator 결과를 추가 비즈니스 로직 없이 감싼다.

## 구조

```text
CollectPostsSkill -> Post[] -> ScreenPostsSkill -> ScreeningResult[] -> GenerateScriptSkill -> GeneratedScript[]
```

## 주요 변경과 모델 의미

- `app/models/generate_script.py`에 `GenerateScriptRequest`, `GeneratedScript`,
  `ScriptGenerationResult`, `GenerateScriptData`, `GenerateScriptMetadata`를 추가한다.
- `app/generators`에 `ScriptGenerator`, `MockScriptGenerator`와 Skill을 추가한다.
- `GenerateScriptRequest.candidates`는 ScreenPosts 후보를 받고 `GeneratedScript`는 원본 `Post`를 보관한다.
- `GeneratedScript`는 `ScreeningResult`에 직접 의존하지 않으며,
  `ScriptGenerationResult`는 Generator 출력, `GenerateScriptData`는 Skill 비즈니스 출력이다.

## 설계 규칙

- `ScriptGenerator.generate(candidates)`는 전체 후보 목록을 한 번에 받고 내부에서 반복한다.
- `GenerateScriptSkill`은 후보를 직접 반복하거나 스크립트를 생성하지 않는다.
- mock Generator는 stateless이며 단순 템플릿만 사용한다.
- 빈 후보는 `ScriptGenerationResult(scripts=[])`를 반환한다.
- 프롬프트, 모델 선택, 외부 API, 품질 판단, 후처리는 구현하지 않는다.

## 테스트와 범위 제외

- 생성 수, title/hook/body/ending, 원본 Post 참조, 빈 입력, 단일 위임 호출,
  메타데이터, 예외 전파, Harness 실행을 검증한다.
- OpenAI/Claude/Gemini, 프롬프트, workflow, LangGraph, 품질 평가·재생성,
  이미지·TTS, retry, 부분 성공은 제외한다.
