#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

current="$(git config --get core.hooksPath || true)"

if [ "$current" = ".githooks" ]; then
  echo "git hook 이 이미 설치되어 있습니다."
  exit 0
fi

git config core.hooksPath .githooks

hook_files="$(ls .githooks 2>/dev/null || true)"
if [ -z "$hook_files" ]; then
  echo "경고: .githooks 에 훅 파일이 없습니다. 훅 파일이 추가된 뒤 이 스크립트를 다시 실행하십시오." >&2
else
  if ! chmod +x .githooks/*; then
    echo "오류: 훅 파일에 실행 권한을 주지 못했습니다. .githooks 디렉터리의 권한을 확인하십시오." >&2
    exit 1
  fi
fi

echo "git hook 을 설치했습니다. 이제 아래가 적용됩니다."
echo "  - main 브랜치에는 직접 커밋할 수 없습니다."
echo "  - 브랜치 이름은 feat/12-작업요약 형식이어야 합니다."
echo "  - main 으로 직접 푸시할 수 없습니다."
