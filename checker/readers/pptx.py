"""파워포인트 리더.

슬라이드마다 어떤 레이아웃을 썼는지, 그리고 마스터가 어떤 레이아웃을 정의하는지를 읽는다.
문서 쪽에서는 쓴 레이아웃을, 템플릿 쪽에서는 정의된 레이아웃을 본다.
"""
from __future__ import annotations

from pathlib import Path

from checker.readers import reader


@reader(".pptx")
def read_pptx(path: Path) -> dict:
    from pptx import Presentation

    prs = Presentation(str(path))
    defined = []
    for master in prs.slide_masters:
        for layout in master.slide_layouts:
            if layout.name not in defined:
                defined.append(layout.name)
    used = []
    for slide in prs.slides:
        name = slide.slide_layout.name
        if name not in used:
            used.append(name)
    return {"layouts": {"defined": defined, "used": used}}
