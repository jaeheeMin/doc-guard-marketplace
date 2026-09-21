#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FAIL=0
RAN=0

echo "문서 참조 검사를 시작합니다."

# 1) rules/ 의 모든 파일이 CLAUDE.md 에서 참조되는지 확인한다.
for f in rules/*.md; do
  RAN=$((RAN + 1))
  if grep -q "$f" CLAUDE.md 2>/dev/null; then
    printf '  통과  %s 가 CLAUDE.md 에서 참조된다\n' "$f"
  else
    FAIL=$((FAIL + 1))
    printf '  실패  %s 가 CLAUDE.md 어디에서도 참조되지 않는다\n' "$f"
  fi
done

# 2) 문서가 가리키는 저장소 내부 경로가 실재하는지 확인한다.
for doc in CLAUDE.md README.md rules/*.md .claude/skills/*/SKILL.md; do
  [ -f "$doc" ] || continue
  refs="$(grep -oE '`(rules|scripts|\.githooks|\.claude)/[A-Za-z0-9_./-]+`' "$doc" 2>/dev/null | tr -d '`' | sort -u || true)"
  for ref in $refs; do
    RAN=$((RAN + 1))
    if [ -e "$ref" ]; then
      printf '  통과  %s 가 가리키는 %s 가 실재한다\n' "$doc" "$ref"
    else
      FAIL=$((FAIL + 1))
      printf '  실패  %s 가 없는 경로를 가리킨다: %s\n' "$doc" "$ref"
    fi
  done
done

# 3) 스킬 문서가 frontmatter 를 갖추었는지 확인한다.
for skill in .claude/skills/*/SKILL.md; do
  [ -f "$skill" ] || continue
  RAN=$((RAN + 1))
  head_line="$(head -1 "$skill")"
  if [ "$head_line" = "---" ] && grep -q '^name:' "$skill" && grep -q '^description:' "$skill"; then
    printf '  통과  %s 가 frontmatter 를 갖추었다\n' "$skill"
  else
    FAIL=$((FAIL + 1))
    printf '  실패  %s 에 name 또는 description frontmatter 가 없다\n' "$skill"
  fi
done

if [ "$RAN" -lt 6 ]; then
  printf '검사 건수가 너무 적습니다(%s건). rules 문서가 없거나 참조가 하나도 없습니다.\n' "$RAN"
  exit 1
fi

printf '\n총 %s건 중 실패 %s건.\n' "$RAN" "$FAIL"
[ "$FAIL" -eq 0 ]
