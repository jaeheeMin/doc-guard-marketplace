#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.githooks"

PASS=0
FAIL=0
RAN=0

# run_case <설명> <기대종료코드> <브랜치이름> [seed]
# 임시 저장소에서 해당 브랜치를 만들고 커밋을 시도한 뒤
# 종료 코드가 기대값과 같은지 확인한다.
# 네 번째 인자를 "noseed" 로 주면 커밋이 하나도 없는 상태를 그대로 검사한다.
run_case() {
  desc="$1"
  expected="$2"
  branch="$3"
  seed="${4:-seed}"

  tmp="$(mktemp -d)"
  git -C "$tmp" init -q -b main
  git -C "$tmp" config user.email "test@example.com"
  git -C "$tmp" config user.name "test"

  # 훅을 켜기 전에 초기 커밋을 만든다. 실제 저장소는 늘 커밋이 있는 상태에서
  # 작업이 시작되므로, 첫 커밋만 검사하면 정작 쓰이는 경로를 한 번도 보지 못한다.
  if [ "$seed" != "noseed" ]; then
    echo "초기" > "$tmp/seed.txt"
    git -C "$tmp" add seed.txt
    git -C "$tmp" commit -q -m "chore: 초기 커밋"
  fi

  git -C "$tmp" config core.hooksPath "$HOOKS_DIR"

  if [ "$branch" = "--detach" ]; then
    git -C "$tmp" checkout -q --detach HEAD
  elif [ "$branch" != "main" ]; then
    git -C "$tmp" checkout -q -b "$branch"
  fi

  echo "content" > "$tmp/file.txt"
  git -C "$tmp" add file.txt

  set +e
  git -C "$tmp" commit -q -m "chore: 검사용 커밋" >/dev/null 2>&1
  actual=$?
  set -e

  RAN=$((RAN + 1))
  if [ "$actual" -eq "$expected" ]; then
    PASS=$((PASS + 1))
    printf '  통과  %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    printf '  실패  %s (기대 종료코드 %s, 실제 %s)\n' "$desc" "$expected" "$actual"
  fi

  rm -rf "$tmp"
}

echo "git hook 검사를 시작합니다."

run_case "main 브랜치 커밋은 거부된다"              1 "main"
run_case "타입이 없는 브랜치 커밋은 거부된다"       1 "wip/foo"
run_case "이슈 번호가 없는 브랜치 커밋은 거부된다"  1 "feat/add-docs"
run_case "허용되지 않은 타입의 커밋은 거부된다"     1 "hotfix/12-urgent"
run_case "대문자가 섞인 브랜치 커밋은 거부된다"     1 "feat/12-Add-Docs"
run_case "규칙에 맞는 브랜치 커밋은 통과한다"       0 "feat/12-add-docs"
run_case "여러 단어로 된 요약도 통과한다"           0 "refactor/7-split-large-file"
run_case "커밋이 없는 저장소의 main 커밋도 거부된다" 1 "main" "noseed"
run_case "어느 브랜치에도 속하지 않은 상태의 커밋은 거부된다" 1 "--detach"

# run_push_case <설명> <기대종료코드> <원격 ref>
# pre-push 훅에 표준 입력을 직접 넣어 판정만 확인한다.
run_push_case() {
  desc="$1"
  expected="$2"
  remote_ref="$3"

  set +e
  printf '%s %s %s %s\n' \
    "refs/heads/work" "1111111111111111111111111111111111111111" \
    "$remote_ref" "0000000000000000000000000000000000000000" \
    | "$HOOKS_DIR/pre-push" origin "https://example.com/x.git" >/dev/null 2>&1
  actual=$?
  set -e

  RAN=$((RAN + 1))
  if [ "$actual" -eq "$expected" ]; then
    PASS=$((PASS + 1))
    printf '  통과  %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    printf '  실패  %s (기대 종료코드 %s, 실제 %s)\n' "$desc" "$expected" "$actual"
  fi
}

run_push_case "main 으로의 직접 푸시는 거부된다"  1 "refs/heads/main"
run_push_case "작업 브랜치 푸시는 통과한다"       0 "refs/heads/feat/12-add-docs"

# check_eol_lf <설명> <경로>
# Windows 의 core.autocrlf=true clone 이 셸 스크립트를 CRLF 로 바꾸면 훅과
# 스크립트가 그 자리에서 깨진다. .gitattributes 가 이 파일들의 eol 을 lf 로
# 고정하는지 git check-attr 로 확인한다.
check_eol_lf() {
  desc="$1"
  path="$2"

  attr="$(git -C "$REPO_ROOT" check-attr eol -- "$path" | sed 's/.*: eol: //')"

  RAN=$((RAN + 1))
  if [ "$attr" = "lf" ]; then
    PASS=$((PASS + 1))
    printf '  통과  %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    printf '  실패  %s (eol 속성: %s)\n' "$desc" "$attr"
  fi
}

for f in "$REPO_ROOT"/.githooks/*; do
  [ -f "$f" ] || continue
  check_eol_lf ".githooks/$(basename "$f") 의 eol 이 lf 로 고정된다" "$f"
done

for f in "$REPO_ROOT"/.claude/hooks/*.sh; do
  [ -f "$f" ] || continue
  check_eol_lf ".claude/hooks/$(basename "$f") 의 eol 이 lf 로 고정된다" "$f"
done

for f in "$REPO_ROOT"/scripts/*.sh; do
  [ -f "$f" ] || continue
  check_eol_lf "scripts/$(basename "$f") 의 eol 이 lf 로 고정된다" "$f"
done

EXPECTED_CASES=20
if [ "$RAN" -ne "$EXPECTED_CASES" ]; then
  printf '검사 건수가 기대와 다릅니다. 기대 %s건, 실제 %s건.\n' "$EXPECTED_CASES" "$RAN"
  exit 1
fi

printf '\n총 %s건 중 통과 %s건, 실패 %s건.\n' "$RAN" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
