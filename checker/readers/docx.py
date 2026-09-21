"""워드 리더.

제목 스타일이 붙은 문단을 절로 본다. 실제 고객사 docx 템플릿을 아직 구하지 못해
이 가정 위에서 만들었다. 굵은 글씨로만 절을 구분하는 템플릿이라면 다시 설계해야 한다.
"""
from __future__ import annotations

import re
from pathlib import Path

from checker.readers import reader

# 한국어판은 '제목 1', 영문판은 'Heading 1'. 둘 다 받는다.
_HEADING_STYLE = re.compile(r"^(?:heading|제목)\s*(\d+)$", re.IGNORECASE)


@reader(".docx")
def read_docx(path: Path) -> dict:
    import docx  # 무거우므로 필요할 때 읽어 들인다

    document = docx.Document(str(path))
    sections = []
    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").strip() if para.style is not None else ""
        m = _HEADING_STYLE.match(style)
        if m:
            sections.append({"level": int(m.group(1)), "title": text})
    return {"sections": sections}
