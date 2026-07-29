# PR-26 dotenv OpenAI 설정

## 요약

OpenAI 모드는 기존 OpenAI 설정을 검증하기 전에 repository root의 선택적 `.env`를 읽는다.
Mock 모드는 dotenv나 OpenAI 설정을 읽지 않는다.

## 설정

loader는 `app/config/openai.py`에서 유도한 경로를 사용하므로 터미널 현재 디렉터리에 의존하지 않는다.
선택 파일은 `override=False`로 읽어 export된 shell 환경 변수가 우선한다.

```dotenv
OPENAI_API_KEY="..."
OPENAI_MODEL="gpt-4o-mini"
OPENAI_TIMEOUT_SECONDS="60"
OPENAI_MAX_RETRIES="2"
```

`.env`는 Git에서 무시하며 커밋하면 안 된다. `.env`가 없는 것은 정상이다.
최종 병합 환경에 API key가 없거나 OpenAI 설정값이 잘못된 경우에만 설정이 실패한다.

## 실패 정책

존재하는 dotenv 파일을 읽을 수 없어 dotenv가 `OSError`를 발생시키면, 파일 내용·경로·API key를 노출하지 않는
안전한 `ConfigurationError`를 발생시킨다. dotenv 로드는 import 시점이 아니라 OpenAI workflow 조립 중에만 수행한다.
