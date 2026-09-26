#!/usr/bin/env bash
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"

input="$(cat)"

# 거부는 jq 없이도 낼 수 있어야 한다. 이 훅이 막아야 하는 상황 중 하나가
# jq 부재이기 때문이다. 그래서 사유 문자열에 큰따옴표와 역슬래시를 쓰지 않는다.
deny() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$1"
  exit 0
}

if ! command -v jq >/dev/null 2>&1; then
  # 판단할 수 없을 때 통과시키지 않는다. 통과시키면 정확히 이 상황에서
  # 보호가 사라진다. 다만 검사 대상이 git 명령이므로 그 밖의 명령은 막지 않는다.
  case "$input" in
    *git*)
      deny "jq 가 없어 git 명령을 검사하지 못했습니다. 검사할 수 없는 상태로 통과시키지 않습니다. jq 를 설치한 뒤 다시 시도하십시오."
      ;;
    *)
      exit 0
      ;;
  esac
fi

set +e
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)"
jq_rc=$?
set -e

if [ "$jq_rc" -ne 0 ]; then
  deny "훅이 입력을 해석하지 못해 이 명령을 검사할 수 없었습니다. 검사할 수 없는 상태로 통과시키지 않습니다. 저장소 관리자에게 알리십시오."
fi

# Windows 네이티브 jq.exe 는 텍스트 모드로 출력해 LF 를 CRLF 로 바꾼다.
# 명령 치환은 끝의 LF 만 벗기므로 CR 이 하위 명령 토큰 끝에 남아 비교가
# 어긋난다(`push\r` 는 `push` 와 다른 문자열이다).
cmd="$(printf '%s' "$cmd" | tr -d '\r')"

if [ -z "$cmd" ]; then
  exit 0
fi

# git 명령의 하위 명령을 찾는다. git 과 하위 명령 사이에는 -C 나 -c 나
# --no-pager 같은 전역 옵션이 올 수 있으므로 둘이 붙어 있는지를 보지 않고,
# git 뒤의 첫 비옵션 토큰을 하위 명령으로 본다. 토큰을 그냥 훑기만 하면
# `git log --grep push` 같은 조회 명령까지 막혀 사람들이 훅을 꺼 버린다.
#
# 이 방식에도 원리적 한계가 있다. 이 함수는 문자열을 공백으로 쪼개 볼 뿐,
# 실제로 셸이 그 문자열을 어떻게 실행하는지는 모른다. `git push$IFS--force`
# 처럼 IFS 를 다른 문자로 바꿔 치환하거나 `x=push; git $x --force` 처럼
# 변수로 하위 명령을 감추면 이 함수도 알아채지 못한다. 이런 형태를 막는
# 최종 방어선은 이 훅이 아니라 `.githooks/pre-push` 와 GitHub 브랜치 보호
# 규칙이다. 이 훅은 그 앞에서 흔히 쓰는 형태를 걸러내는 첫 번째 방어선일
# 뿐이다.
git_subcommand() {
  set -f
  found=0
  skip_next=0
  for tok in $1; do
    # 셸이 벗겨 줄 따옴표가 문자열에는 남아 있으므로 여기서 벗긴다.
    tok="${tok#\"}"; tok="${tok%\"}"
    tok="${tok#\'}"; tok="${tok%\'}"
    if [ "$skip_next" -eq 1 ]; then skip_next=0; continue; fi
    if [ "$found" -eq 0 ]; then
      # Windows 는 `git.exe` 로 부르고 경로 구분자로 `\` 를 쓴다. `/` 와 `\`
      # 양쪽 기준으로 마지막 경로 성분을 떼어 내고, 대소문자와 `.exe` 확장자
      # 차이를 없앤 뒤에 git 인지 비교한다. bash 3.2 호환을 위해 `${var,,}`
      # 대신 tr 을 쓴다.
      base="${tok##*/}"
      base="${base##*\\}"
      base="$(printf '%s' "$base" | tr '[:upper:]' '[:lower:]')"
      case "$base" in
        *.exe) base="${base%.exe}" ;;
      esac
      case "$base" in
        git) found=1 ;;
      esac
      continue
    fi
    case "$tok" in
      -C|-c) skip_next=1 ;;
      -*) : ;;
      *) set +f; printf '%s' "$tok"; return 0 ;;
    esac
  done
  set +f
  return 0
}

sub="$(git_subcommand "$cmd")"

# 1) 되돌릴 수 없는 강제 푸시는 어떤 경우에도 거부한다. 선언 접두어보다 먼저
#    검사하는 이유는, 접두어가 이 동작까지 열어 주는 문이 되지 않게 하기
#    위해서다. 짧은 옵션은 -f 로도 -uf 로도 묶여 쓰이므로, 붙임표 하나로
#    시작하는 토큰 안에 f 가 있으면 강제로 본다. --force-with-lease 는 붙임표
#    둘로 시작하고 --force 뒤에 공백이 오지 않아 이 패턴에 걸리지 않는다.
if [ "$sub" = "push" ] && [[ "$cmd" =~ (^|[[:space:]])(-[a-zA-Z]*f[a-zA-Z]*|--force)([[:space:]]|$) ]]; then
  deny "git push --force 는 이 저장소에서 금지되어 있습니다. 리베이스로 이력이 바뀐 경우에는 --force-with-lease 를 쓰고, 그 절차는 /deliver 가 수행합니다."
fi

# 2) main 에서의 커밋도 선언 접두어와 무관하게 거부한다. 브랜치 규칙은
#    /deliver 의 절차가 아니라 이 저장소의 전제이기 때문이다.
if [ "$sub" = "commit" ]; then
  branch="$(git symbolic-ref --short -q HEAD || echo 알수없음)"
  if [ "$branch" = "main" ]; then
    deny "main 브랜치에는 직접 커밋할 수 없습니다. /start 를 실행해 이슈를 만들고 규칙에 맞는 브랜치에서 작업하십시오."
  fi
fi

# 3) /deliver 스킬이 절차를 따르고 있다는 선언이면 여기서 통과시킨다.
#    위의 두 검사를 지난 뒤라 강제 푸시와 main 커밋은 이미 걸러져 있다.
case "$cmd" in
  DELIVER=1*)
    exit 0
    ;;
esac

# 4) 스킬을 거치지 않은 푸시를 거부한다.
if [ "$sub" = "push" ]; then
  deny "푸시는 /deliver 스킬이 수행합니다. /deliver 는 커밋과 fetch 와 rebase 와 푸시와 PR 생성을 한 번에 처리합니다. 스킬 절차를 따르는 중이라면 명령 앞에 DELIVER=1 을 붙이십시오."
fi

exit 0
