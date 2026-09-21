#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_DIR="$REPO_ROOT/.claude/hooks"

PASS=0
FAIL=0
RAN=0

# make_fixture
# 훅을 실행할 임시 저장소를 만들고 그 경로를 표준 출력에 쓴다.
# 실제 저장소를 픽스처로 쓰면 두 가지가 깨진다. 훅이 개발자의 git 설정을
# 실제로 바꾸고, 검사가 저장소의 그때그때 상태에 결합된다. 그래서 검사마다
# 새 저장소를 만들고 끝나면 지운다.
make_fixture() {
  fixture="$(mktemp -d)"
  git -C "$fixture" init -q -b main
  git -C "$fixture" config user.email "test@example.com"
  git -C "$fixture" config user.name "test"
  mkdir -p "$fixture/scripts" "$fixture/.githooks"
  cp "$REPO_ROOT/scripts/install-hooks.sh" "$fixture/scripts/"
  cp "$REPO_ROOT/.githooks/pre-commit" "$fixture/.githooks/"
  cp "$REPO_ROOT/.githooks/pre-push" "$fixture/.githooks/"
  echo "초기" > "$fixture/seed.txt"
  git -C "$fixture" add -A
  git -C "$fixture" commit -q -m "chore: 초기 커밋"
  printf '%s' "$fixture"
}

# expect_contains <설명> <스크립트> <입력JSON> <포함되어야_할_문자열> <작업디렉터리>
expect_contains() {
  desc="$1"
  script="$2"
  input="$3"
  needle="$4"
  workdir="$5"

  set +e
  out="$(printf '%s' "$input" | CLAUDE_PROJECT_DIR="$workdir" bash "$script" 2>&1)"
  rc=$?
  set -e

  RAN=$((RAN + 1))

  if [ "$rc" -ne 0 ]; then
    FAIL=$((FAIL + 1))
    printf '  실패  %s (종료 코드 %s. 훅은 항상 0 을 반환해야 한다)\n' "$desc" "$rc"
    return 0
  fi

  case "$out" in
    *"$needle"*)
      PASS=$((PASS + 1))
      printf '  통과  %s\n' "$desc"
      ;;
    *)
      FAIL=$((FAIL + 1))
      printf '  실패  %s\n' "$desc"
      printf '        기대한 문자열: %s\n' "$needle"
      printf '        실제 출력: %s\n' "$out"
      ;;
  esac
}

# expect_not_contains <설명> <스크립트> <입력JSON> <나오면_안_되는_문자열> <작업디렉터리>
expect_not_contains() {
  desc="$1"
  script="$2"
  input="$3"
  needle="$4"
  workdir="$5"

  set +e
  out="$(printf '%s' "$input" | CLAUDE_PROJECT_DIR="$workdir" bash "$script" 2>&1)"
  rc=$?
  set -e

  RAN=$((RAN + 1))

  if [ "$rc" -ne 0 ]; then
    FAIL=$((FAIL + 1))
    printf '  실패  %s (종료 코드 %s. 훅은 항상 0 을 반환해야 한다)\n' "$desc" "$rc"
    return 0
  fi

  case "$out" in
    *"$needle"*)
      FAIL=$((FAIL + 1))
      printf '  실패  %s\n' "$desc"
      printf '        나오면 안 되는 문자열이 나왔습니다: %s\n' "$needle"
      ;;
    *)
      PASS=$((PASS + 1))
      printf '  통과  %s\n' "$desc"
      ;;
  esac
}

echo "Claude Code 훅 검사를 시작합니다."

SESSION_START='{"hook_event_name":"SessionStart","source":"startup"}'

F="$(make_fixture)"
expect_contains "세션 시작 훅이 현재 브랜치를 보고한다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "현재 브랜치: main" "$F"
rm -rf "$F"

F="$(make_fixture)"
expect_contains "원격이 없으면 그 사실을 분명히 알린다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "원격 저장소가 연결되어 있지 않습니다" "$F"
rm -rf "$F"

F="$(make_fixture)"
expect_contains "main 에서는 커밋할 수 없다고 안내한다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "main 에서는 커밋할 수 없습니다" "$F"
rm -rf "$F"

F="$(make_fixture)"
expect_contains "git hook 이 설치되지 않았으면 자동으로 설치한다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "git hook 을 자동으로 설치했습니다" "$F"
rm -rf "$F"

F="$(make_fixture)"
echo "변경" > "$F/changed.txt"
expect_contains "커밋되지 않은 변경이 있으면 알린다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "커밋되지 않은 변경이 있습니다" "$F"
rm -rf "$F"

F="$(make_fixture)"
expect_not_contains "깨끗한 상태에서는 미커밋 변경을 말하지 않는다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "커밋되지 않은 변경이 있습니다" "$F"
rm -rf "$F"

STOP_IDLE='{"hook_event_name":"Stop","stop_hook_active":false}'
STOP_RESUMED='{"hook_event_name":"Stop","stop_hook_active":true}'

F="$(make_fixture)"
echo "변경" > "$F/changed.txt"
expect_contains "미커밋 변경이 있으면 /deliver 를 지시한다" \
  "$HOOK_DIR/stop-deliver.sh" "$STOP_IDLE" "/deliver" "$F"
rm -rf "$F"

F="$(make_fixture)"
echo "변경" > "$F/changed.txt"
expect_contains "지시는 decision:block 형식으로 나간다" \
  "$HOOK_DIR/stop-deliver.sh" "$STOP_IDLE" "\"decision\": \"block\"" "$F"
expect_not_contains "최상위 continue 키는 내보내지 않는다" \
  "$HOOK_DIR/stop-deliver.sh" "$STOP_IDLE" "\"continue\"" "$F"
rm -rf "$F"

F="$(make_fixture)"
echo "변경" > "$F/changed.txt"
expect_contains "이미 되돌려 보낸 뒤에도 남아 있으면 경고를 남긴다" \
  "$HOOK_DIR/stop-deliver.sh" "$STOP_RESUMED" "경고" "$F"
rm -rf "$F"

F="$(make_fixture)"
echo "변경" > "$F/changed.txt"
expect_not_contains "이미 되돌려 보낸 뒤에는 다시 지시하지 않는다" \
  "$HOOK_DIR/stop-deliver.sh" "$STOP_RESUMED" "\"decision\": \"block\"" "$F"
rm -rf "$F"

F="$(make_fixture)"
expect_not_contains "깨끗한 상태에서는 아무 말도 하지 않는다" \
  "$HOOK_DIR/stop-deliver.sh" "$STOP_IDLE" "deliver" "$F"
rm -rf "$F"

# 세션 종료 경고가 다음 세션까지 전달되는지를 두 훅을 이어 붙여 확인한다.
# 종료 코드 0 으로 끝나는 훅의 표준 오류는 사용자 화면에 닿지 않으므로,
# 이 연결이 끊기면 경고는 아무에게도 보이지 않는다.
F="$(make_fixture)"
echo "변경" > "$F/changed.txt"
printf '%s' "$STOP_RESUMED" | CLAUDE_PROJECT_DIR="$F" bash "$HOOK_DIR/stop-deliver.sh" >/dev/null 2>&1
expect_contains "세션 종료 경고가 다음 세션 시작 때 전달된다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "지난 세션에서 남은 경고가 있습니다" "$F"
rm -rf "$F"

# 연결된 워크트리에서도 인수인계가 동작하는지 확인한다. 워크트리에서는 `.git`
# 이 파일이므로 경로를 잘못 잡으면 훅이 그 자리에서 죽는다.
F="$(make_fixture)"
WT_PARENT="$(mktemp -d)"
WT="$WT_PARENT/wt"
git -C "$F" worktree add -q -b feat/1-worktree-check "$WT"
echo "변경" > "$WT/changed.txt"
printf '%s' "$STOP_RESUMED" | CLAUDE_PROJECT_DIR="$WT" bash "$HOOK_DIR/stop-deliver.sh" >/dev/null 2>&1
expect_contains "연결된 워크트리에서도 경고가 다음 세션에 전달된다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "지난 세션에서 남은 경고가 있습니다" "$WT"
git -C "$F" worktree remove --force "$WT" >/dev/null 2>&1 || true
rm -rf "$WT_PARENT" "$F"

F="$(make_fixture)"
printf '[경고] 지난 세션에서 남긴 내용\n' > "$(git -C "$F" rev-parse --absolute-git-dir)/doc-guard-unfinished"
expect_contains "인수인계 파일의 내용을 그대로 전한다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "지난 세션에서 남긴 내용" "$F"
expect_not_contains "한 번 전한 경고는 다시 전하지 않는다" \
  "$HOOK_DIR/session-start-sync.sh" "$SESSION_START" "지난 세션에서 남은 경고가 있습니다" "$F"
rm -rf "$F"

GUARD="$HOOK_DIR/pre-bash-git-guard.sh"

# 명령 문자열에 큰따옴표가 들어갈 수 있으므로 JSON 을 손으로 잇지 않고 jq 로
# 만든다. 이어 붙이면 따옴표가 든 명령에서 JSON 이 깨져, 정상 동작하는 훅이
# 실패로 나온다.
bash_input() {
  jq -n --arg c "$1" \
    '{hook_event_name:"PreToolUse",tool_name:"Bash",tool_input:{command:$c}}'
}

# PowerShell 도 Bash 와 같은 tool_input.command 모양으로 명령을 실어 보낸다.
powershell_input() {
  jq -n --arg c "$1" \
    '{hook_event_name:"PreToolUse",tool_name:"PowerShell",tool_input:{command:$c}}'
}

F="$(make_fixture)"
expect_contains "force 푸시는 거부된다" \
  "$GUARD" "$(bash_input 'git push --force origin HEAD')" "deny" "$F"
expect_contains "짧은 옵션으로 쓴 force 푸시도 거부된다" \
  "$GUARD" "$(bash_input 'git push -f origin HEAD')" "deny" "$F"
expect_contains "다른 짧은 옵션과 묶인 force 푸시도 거부된다" \
  "$GUARD" "$(bash_input 'DELIVER=1 git push -uf origin HEAD')" "deny" "$F"
expect_contains "선언 접두어가 있어도 force 푸시는 거부된다" \
  "$GUARD" "$(bash_input 'DELIVER=1 git push --force origin HEAD')" "deny" "$F"
expect_contains "맨손 푸시는 거부되고 /deliver 를 안내한다" \
  "$GUARD" "$(bash_input 'git push origin HEAD')" "/deliver" "$F"
expect_contains "main 에서의 커밋은 거부되고 /start 를 안내한다" \
  "$GUARD" "$(bash_input 'git commit -m "chore: 무언가"')" "/start" "$F"
expect_contains "선언 접두어가 있어도 main 커밋은 거부된다" \
  "$GUARD" "$(bash_input 'DELIVER=1 git commit -m "chore: 무언가"')" "/start" "$F"
expect_not_contains "선언 접두어가 붙은 일반 푸시는 통과한다" \
  "$GUARD" "$(bash_input 'DELIVER=1 git push origin HEAD')" "deny" "$F"
expect_not_contains "force-with-lease 는 선언이 있으면 통과한다" \
  "$GUARD" "$(bash_input 'DELIVER=1 git push --force-with-lease origin HEAD')" "deny" "$F"
expect_not_contains "git 과 무관한 명령은 통과한다" \
  "$GUARD" "$(bash_input 'ls -la')" "deny" "$F"

# 문자열 부분일치 판정은 git 과 하위 명령 사이에 전역 옵션이 하나만 끼어도
# 뚫린다. 토큰 기반 판정으로 바뀐 뒤 이 네 가지가 실제로 막히는지 확인한다.
expect_contains "-C 전역 옵션이 낀 force 푸시도 거부된다" \
  "$GUARD" "$(bash_input 'git -C /tmp/foo push --force origin main')" "deny" "$F"
expect_contains "-c 전역 옵션이 낀 force 푸시도 거부된다" \
  "$GUARD" "$(bash_input 'git -c http.sslVerify=false push --force origin work')" "deny" "$F"
expect_contains "선언 접두어와 -c 전역 옵션이 함께 낀 force 푸시도 거부된다" \
  "$GUARD" "$(bash_input 'DELIVER=1 git -c x=y push --force origin main')" "deny" "$F"
expect_contains "--no-pager 전역 옵션이 낀 main 커밋도 거부된다" \
  "$GUARD" "$(bash_input 'git --no-pager commit -m "chore: 무언가"')" "/start" "$F"

# 토큰을 그냥 훑기만 하던 방식은 두 가지를 놓쳤다. 하위 명령을 따옴표로
# 감싸거나(`git "push"`) 다른 명령을 거쳐 실행하면(`sh -c "..."`) 공백으로
# 감싼 토큰 검사를 피해 간다. git 뒤의 첫 비옵션 토큰을 하위 명령으로 보는
# 방식으로 바뀐 뒤 이 두 가지도 막히는지 확인한다.
expect_contains "따옴표로 감싼 하위 명령도 거부된다" \
  "$GUARD" "$(bash_input 'git "push" --force origin main')" "deny" "$F"
expect_contains "sh -c 로 감싼 force 푸시도 거부된다" \
  "$GUARD" "$(bash_input 'sh -c "git push --force origin main"')" "deny" "$F"

# 반대로 토큰을 그냥 훑는 방식은 `git log --grep push` 같은 흔한 조회
# 명령까지 push 로 오판해 막아 버린다. 하위 명령 파싱으로 바뀐 뒤 이런
# 과탐이 사라졌는지 확인한다.
expect_not_contains "push 를 인자로 쓰는 조회 명령은 막지 않는다" \
  "$GUARD" "$(bash_input 'git log --grep push')" "deny" "$F"
expect_not_contains "무관한 하위 명령은 막지 않는다" \
  "$GUARD" "$(bash_input 'git branch -a')" "deny" "$F"
expect_not_contains "-u 옵션이 붙은 정상 푸시는 통과한다" \
  "$GUARD" "$(bash_input 'DELIVER=1 git push -u origin HEAD')" "deny" "$F"

# Windows 는 git 을 `git.exe` 로 부르고 경로 구분자로 `\` 를 쓴다. 마지막
# 경로 성분을 basename 으로 떼어 내고 대소문자와 .exe 확장자를 무시하는
# 비교로 바뀐 뒤 이 형태들도 막히는지 확인한다.
expect_contains "git.exe 로 부른 force 푸시도 거부된다" \
  "$GUARD" "$(bash_input 'git.exe push --force origin main')" "deny" "$F"
expect_contains "따옴표로 감싼 Windows 절대경로 git.exe 호출도 거부된다" \
  "$GUARD" "$(bash_input '"C:\Program Files\Git\cmd\git.exe" push --force origin main')" "deny" "$F"
expect_contains "git.exe 로 부른 main 커밋도 거부된다" \
  "$GUARD" "$(bash_input 'git.exe commit -m "chore: 무언가"')" "/start" "$F"
expect_contains "git.exe 로 부른 맨손 푸시도 거부되고 /deliver 를 안내한다" \
  "$GUARD" "$(bash_input 'git.exe push origin HEAD')" "/deliver" "$F"

# tool_input 의 모양은 Bash 와 PowerShell 이 같다(둘 다 tool_input.command).
# matcher 를 Bash|PowerShell 로 넓힌 뒤, PowerShell 에서 흔한 호출 형태도
# 이 훅이 그대로 걸러내는지 확인한다.
expect_contains "PowerShell 입력으로 온 force 푸시도 거부된다" \
  "$GUARD" "$(powershell_input 'git push --force')" "deny" "$F"
expect_contains "PowerShell 호출 연산자(&)로 시작한 git.exe 푸시도 거부된다" \
  "$GUARD" "$(powershell_input '& git.exe push origin HEAD')" "/deliver" "$F"
expect_contains "PowerShell 에는 DELIVER=1 접두 문법이 없어 이 형태도 거부된다" \
  "$GUARD" "$(powershell_input '$env:DELIVER=1; git push origin HEAD')" "/deliver" "$F"
rm -rf "$F"

# jq 를 찾을 수 없는 환경을 만들어, 안전장치가 스스로 꺼지지 않는지 본다.
# 검사할 수 없을 때 통과시키면 정확히 그 상황에서 보호가 사라진다.
F="$(make_fixture)"
NOJQ_BIN="$(mktemp -d)"
for c in git bash cat; do
  ln -s "$(command -v "$c")" "$NOJQ_BIN/$c"
done
set +e
nojq_out="$(bash_input 'git push --force origin HEAD' \
  | PATH="$NOJQ_BIN" CLAUDE_PROJECT_DIR="$F" bash "$GUARD" 2>&1)"
nojq_rc=$?
set -e
RAN=$((RAN + 1))
case "$nojq_out" in
  *deny*)
    if [ "$nojq_rc" -eq 0 ]; then
      PASS=$((PASS + 1))
      printf '  통과  jq 가 없으면 git 명령을 통과시키지 않는다\n'
    else
      FAIL=$((FAIL + 1))
      printf '  실패  jq 가 없을 때 종료 코드가 %s 다. 훅은 항상 0 이어야 한다\n' "$nojq_rc"
    fi
    ;;
  *)
    FAIL=$((FAIL + 1))
    printf '  실패  jq 가 없으면 검사가 통째로 꺼진다\n'
    printf '        출력: %s\n' "$nojq_out"
    ;;
esac
rm -rf "$NOJQ_BIN" "$F"

# Windows 네이티브 jq.exe 는 텍스트 모드로 출력해 각 줄 끝에 CR 을 남긴다.
# 실제 jq 를 감싸 CR 을 붙이는 가짜 jq 로 흉내 내, 그 CR 이 하위 명령
# 비교와 stop_hook_active 비교를 어긋나게 하지 않는지 확인한다.
REAL_JQ="$(command -v jq)"
REAL_SED="$(command -v sed)"
CRJQ_BIN="$(mktemp -d)"
printf '#!/usr/bin/env bash\nexec "%s" "$@" | "%s" '"'"'s/$/\\r/'"'"'\n' "$REAL_JQ" "$REAL_SED" \
  > "$CRJQ_BIN/jq"
chmod +x "$CRJQ_BIN/jq"

F="$(make_fixture)"
set +e
crjq_out="$(bash_input 'git push' \
  | PATH="$CRJQ_BIN:$PATH" CLAUDE_PROJECT_DIR="$F" bash "$GUARD" 2>&1)"
crjq_rc=$?
set -e
RAN=$((RAN + 1))
case "$crjq_out" in
  *deny*)
    if [ "$crjq_rc" -eq 0 ]; then
      PASS=$((PASS + 1))
      printf '  통과  CR 을 남기는 jq 아래에서도 맨손 push 가 거부된다\n'
    else
      FAIL=$((FAIL + 1))
      printf '  실패  CR 을 남기는 jq 아래에서 종료 코드가 %s 다\n' "$crjq_rc"
    fi
    ;;
  *)
    FAIL=$((FAIL + 1))
    printf '  실패  CR 을 남기는 jq 아래에서 맨손 push 가 통과됐다\n'
    printf '        출력: %s\n' "$crjq_out"
    ;;
esac
rm -rf "$F"

F="$(make_fixture)"
echo "변경" > "$F/changed.txt"
set +e
crjq_stop_out="$(printf '%s' "$STOP_RESUMED" \
  | PATH="$CRJQ_BIN:$PATH" CLAUDE_PROJECT_DIR="$F" bash "$HOOK_DIR/stop-deliver.sh" 2>&1)"
set -e
RAN=$((RAN + 1))
if ! printf '%s' "$crjq_stop_out" | grep -q 'decision'; then
  PASS=$((PASS + 1))
  printf '  통과  CR 을 남기는 jq 아래에서도 stop_hook_active:true 는 다시 block 하지 않는다\n'
else
  FAIL=$((FAIL + 1))
  printf '  실패  CR 을 남기는 jq 아래에서 stop_hook_active:true 인데도 다시 block 했다\n'
  printf '        출력: %s\n' "$crjq_stop_out"
fi
rm -rf "$F" "$CRJQ_BIN"

# stop-deliver.sh 는 jq 가 없어도 fail-open 하면 안 된다. jq 를 뺀 PATH 에서
# 세 경로(변경 있음/재진입/변경 없음)를 확인한다.
NOJQ_BIN2="$(mktemp -d)"
for c in git bash cat grep tr; do
  ln -s "$(command -v "$c")" "$NOJQ_BIN2/$c"
done

F="$(make_fixture)"
echo "변경" > "$F/changed.txt"
set +e
nojq_block_out="$(printf '%s' "$STOP_IDLE" \
  | PATH="$NOJQ_BIN2" CLAUDE_PROJECT_DIR="$F" bash "$HOOK_DIR/stop-deliver.sh" 2>&1)"
nojq_block_rc=$?
set -e
RAN=$((RAN + 1))
if [ "$nojq_block_rc" -eq 0 ] \
  && printf '%s' "$nojq_block_out" | grep -q '"decision":"block"' \
  && printf '%s' "$nojq_block_out" | "$REAL_JQ" . >/dev/null 2>&1; then
  PASS=$((PASS + 1))
  printf '  통과  jq 가 없어도 미커밋 변경이 있으면 유효한 JSON 으로 block 한다\n'
else
  FAIL=$((FAIL + 1))
  printf '  실패  jq 가 없을 때 미커밋 변경을 block 하지 못했다\n'
  printf '        출력: %s\n' "$nojq_block_out"
fi
rm -rf "$F"

F="$(make_fixture)"
echo "변경" > "$F/changed.txt"
set +e
nojq_resumed_out="$(printf '%s' "$STOP_RESUMED" \
  | PATH="$NOJQ_BIN2" CLAUDE_PROJECT_DIR="$F" bash "$HOOK_DIR/stop-deliver.sh" 2>&1)"
set -e
RAN=$((RAN + 1))
if ! printf '%s' "$nojq_resumed_out" | grep -q '"decision":"block"'; then
  PASS=$((PASS + 1))
  printf '  통과  jq 가 없고 stop_hook_active:true 이면 다시 block 하지 않는다\n'
else
  FAIL=$((FAIL + 1))
  printf '  실패  jq 가 없어도 stop_hook_active:true 인데 다시 block 했다\n'
  printf '        출력: %s\n' "$nojq_resumed_out"
fi
rm -rf "$F"

F="$(make_fixture)"
set +e
nojq_clean_out="$(printf '%s' "$STOP_IDLE" \
  | PATH="$NOJQ_BIN2" CLAUDE_PROJECT_DIR="$F" bash "$HOOK_DIR/stop-deliver.sh" 2>&1)"
set -e
RAN=$((RAN + 1))
if [ -z "$nojq_clean_out" ]; then
  PASS=$((PASS + 1))
  printf '  통과  jq 가 없고 변경도 없으면 조용히 끝난다\n'
else
  FAIL=$((FAIL + 1))
  printf '  실패  jq 가 없고 변경도 없는데 출력이 나왔다: %s\n' "$nojq_clean_out"
fi
rm -rf "$F" "$NOJQ_BIN2"

EXPECTED_CASES=48
if [ "$RAN" -ne "$EXPECTED_CASES" ]; then
  printf '검사 건수가 기대와 다릅니다. 기대 %s건, 실제 %s건.\n' "$EXPECTED_CASES" "$RAN"
  exit 1
fi

printf '\n총 %s건 중 통과 %s건, 실패 %s건.\n' "$RAN" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
