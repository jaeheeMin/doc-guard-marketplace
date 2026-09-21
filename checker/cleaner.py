"""파일에서 외부 흔적을 걷어낸 새 파일을 만든다.

엔진의 다른 부분은 전부 읽고 판정만 한다. 여기만 쓴다. 그래서 훅이나 Actions 가 자동으로
부르지 않고 사람이 직접 부른다. 남의 산출물을 도구가 말없이 바꾸면 안 된다.

**원본을 덮지 않는다.** 오피스 파일은 잘못 건드리면 이미지와 서식이 날아가므로, 사람이
결과를 열어 보고 쓸지 정해야 한다.

**zip 항목을 그대로 다룬다.** openpyxl 이나 python-docx 로 열어 저장하면 그 라이브러리가
모르는 부분이 사라진다. 실제로 openpyxl 은 이미지를 버린다. 여기서는 손댈 항목만 바꾸고
나머지는 바이트 그대로 옮긴다.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from checker import ooxml

_EMPTY_CUSTOM_XML = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><root/>'
_CELL_STYLES_BLOCK = re.compile(r"<cellStyles count=\"\d+\">.*?</cellStyles>", re.S)
_CELL_STYLE = re.compile(r"<cellStyle\b[^>]*/>")


@dataclass
class CleanResult:
    source: Path
    output: Path
    removed: list[str] = field(default_factory=list)

    def summary(self) -> str:
        head = f"{self.source.name} → {self.output.name}"
        if not self.removed:
            return f"{head}: 걷어낼 것이 없었다"
        return head + "\n" + "\n".join(f"  - {line}" for line in self.removed)


def _clean_styles(source: str) -> tuple[str, int]:
    """`builtinId` 가 붙은 기본 스타일만 남긴다.

    셀의 서식 자체는 cellXfs 가 cellStyleXfs 를 가리켜 정해지고, cellStyles 는 이름 목록
    일 뿐이다. 그래서 이름을 덜어내도 서식은 그대로 남는다.
    """
    entries = _CELL_STYLE.findall(source)
    keep = [e for e in entries if "builtinId=" in e]
    dropped = len(entries) - len(keep)
    if dropped <= 0:
        return source, 0
    block = '<cellStyles count="%d">%s</cellStyles>' % (len(keep), "".join(keep))
    return _CELL_STYLES_BLOCK.sub(lambda _: block, source, count=1), dropped


def _blank_fields(source: str) -> tuple[str, list[str]]:
    cleared = []
    for field_name in ooxml._PROPERTY_FIELDS:
        pattern = ooxml.PROPERTY_PATTERN.format(field=field_name)
        m = re.search(pattern, source)
        if m and m.group(1).strip():
            cleared.append(f"{field_name}={m.group(1).strip()!r}")
            # 이름공간 속성이 붙어 있을 수 있으므로 여는 태그를 통째로 다시 쓰지 않고
            # 값만 비운다.
            source = re.sub(pattern, lambda mm: mm.group(0).replace(mm.group(1), "", 1), source)
    return source, cleared


def clean(path: Path, output: Path) -> CleanResult:
    result = CleanResult(source=path, output=output)
    if not ooxml.is_ooxml(path):
        raise ValueError(f"{path.name}: 오피스 파일이 아니라 걷어낼 것이 없다")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            name, data = item.filename, zin.read(item.filename)

            if name == "xl/styles.xml":
                text, dropped = _clean_styles(data.decode("utf-8", "ignore"))
                if dropped:
                    result.removed.append(f"딸려온 명명 스타일 {dropped}개 (xl/styles.xml)")
                    data = text.encode("utf-8")

            elif name.startswith("customXml/") and name.endswith(".xml"):
                if data != _EMPTY_CUSTOM_XML:
                    result.removed.append(f"외부 시스템 메타데이터 ({name})")
                    data = _EMPTY_CUSTOM_XML

            elif name in ("docProps/core.xml", "docProps/app.xml"):
                text, cleared = _blank_fields(data.decode("utf-8", "ignore"))
                if cleared:
                    result.removed.append(f"문서 속성 {', '.join(cleared)} ({name})")
                    data = text.encode("utf-8")

            elif "comments" in name and name.endswith(".xml"):
                text = data.decode("utf-8", "ignore")
                authors = re.findall(r"<author(?:\s[^>]*)?>([^<]*)</author>", text)
                named = [a for a in authors if a.strip()]
                if named:
                    result.removed.append(f"주석 작성자 {', '.join(named[:3])} ({name})")
                    text = re.sub(
                        r"(<author(?:\s[^>]*)?>)[^<]*(</author>)",
                        r"\1\2",
                        text,
                    )
                    data = text.encode("utf-8")

            zout.writestr(item, data)

    return result


def default_output(path: Path) -> Path:
    return path.with_name(f"{path.stem}.cleaned{path.suffix}")
