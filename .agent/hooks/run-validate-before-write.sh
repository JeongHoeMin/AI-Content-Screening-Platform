#!/usr/bin/env bash

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOK_SCRIPT="$PROJECT_ROOT/.agent/hooks/validate-before-write.py"
VENV_PYTHON_POSIX="$PROJECT_ROOT/.venv/bin/python"
VENV_PYTHON_WINDOWS="$PROJECT_ROOT/.venv/Scripts/python.exe"

# 검증기는 PyYAML을 필요로 한다. PATH의 python은 프로젝트 의존성을 갖고 있다는
# 보장이 없으므로 프로젝트 venv를 먼저 사용한다.
run_hook() {
  if [[ -x "$VENV_PYTHON_POSIX" ]]; then
    "$VENV_PYTHON_POSIX" -X utf8 "$HOOK_SCRIPT"
    return $?
  fi

  if [[ -f "$VENV_PYTHON_WINDOWS" ]]; then
    "$VENV_PYTHON_WINDOWS" -X utf8 "$HOOK_SCRIPT"
    return $?
  fi

  if command -v python >/dev/null 2>&1; then
    python -X utf8 "$HOOK_SCRIPT"
    return $?
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 -X utf8 "$HOOK_SCRIPT"
    return $?
  fi

  echo "AGENT_TASK_POLICY_DENIED: Hook 실행에 사용할 Python을 찾을 수 없습니다." >&2
  return 2
}

run_hook
EXIT_CODE=$?

# 성공한 경우에만 허용
if [[ $EXIT_CODE -eq 0 ]]; then
  exit 0
fi

# 정책 차단은 그대로 전달
if [[ $EXIT_CODE -eq 2 ]]; then
  exit 2
fi

# Python 오류, 모듈 누락, 경로 오류 등도 모두 차단으로 변환
echo "AGENT_TASK_POLICY_DENIED: Hook 검증기가 비정상 종료되었습니다. 원래 종료 코드: $EXIT_CODE" >&2
exit 2
