"""마크다운 리더. 외부 의존성이 없어 리더 이음매의 기준점 역할을 한다."""
from __future__ import annotations

import re
from pathlib import Path

from checker.readers import reader

# ``#`` 로 시작하는 제목 줄. 울타리 친 코드 블록 안은 세지 않는다.
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@reader(".md", ".markdown")
def read_md(path: Path) -> dict:
    sections = []
    in_fence = False
    # 인코딩을 명시한다. Windows 기본 코드페이지에 맡기면 한글 제목이 깨진다.
    for line in path.read_text(encoding="utf-8").splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING.match(line)
        if m:
            sections.append({"level": len(m.group(1)), "title": m.group(2).strip()})
    return {"sections": sections}
