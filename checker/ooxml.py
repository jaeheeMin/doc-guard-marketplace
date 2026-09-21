"""오피스 파일의 본문이 아닌 자리를 들여다본다.

docx·xlsx·pptx 는 전부 XML 을 담은 zip 이다. `readers/` 는 본문(절, 시트, 레이아웃)을
뽑지만 여기서는 사람이 화면으로 볼 수 없는 자리를 본다. 작성자 정보, 외부 시스템이 심은
메타데이터, 복붙으로 쌓인 명명 스타일 같은 것들이다.

**왜 openpyxl 이나 python-docx 를 쓰지 않는가.** 그 라이브러리들은 문서 모형을 읽어
들였다가 다시 쓰는데, 그 과정에서 자기가 모르는 부분을 버린다. 실제로 openpyxl 로 열어
저장하면 이미지가 사라진다. 여기서는 읽기도 쓰기도 zip 항목을 그대로 다뤄, 손대지 않은
항목은 바이트 그대로 남긴다.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

OOXML_SUFFIXES = {".docx", ".xlsx", ".xlsm", ".pptx", ".dotx", ".xltx", ".potx"}

# 문서 속성 중 사람과 조직이 남는 자리.
_PROPERTY_FIELDS = ("dc:creator", "cp:lastModifiedBy", "Company", "Manager")

_CELL_STYLE = re.compile(r"<cellStyle\b[^>]*/>")
_STYLE_NAME = re.compile(r'name="([^"]*)"')
_COMMENT_AUTHOR = re.compile(r"<author(?:\s[^>]*)?>([^<]*)</author>")

# 같은 요소라도 파일을 만든 도구에 따라 이름공간 속성이 붙기도 한다.
# openpyxl 은 `<dc:creator xmlns:dc="...">` 로 쓰고 엑셀은 속성 없이 쓴다.
# 속성을 허용하지 않으면 도구에 따라 작성자 정보를 통째로 놓친다.
PROPERTY_PATTERN = r"<{field}(?:\s[^>]*)?>([^<]*)</{field}>"


def is_ooxml(path: Path) -> bool:
    return path.suffix.lower() in OOXML_SUFFIXES and zipfile.is_zipfile(path)


def _text(zf: zipfile.ZipFile, name: str) -> str:
    try:
        return zf.read(name).decode("utf-8", "ignore")
    except KeyError:
        return ""


def named_styles(zf: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    """명명 스타일을 내장과 비내장으로 가른다.

    깨끗한 파일은 `builtinId` 가 붙은 기본 스타일(표준, 쉼표, 통화 등) 몇 개뿐이다.
    비내장 스타일은 다른 파일에서 복붙할 때 딸려 온 것이고, 그 이름이 곧 그 파일이 어느
    사업의 것이었는지를 말한다.
    """
    source = _text(zf, "xl/styles.xml")
    builtin, imported = [], []
    for element in _CELL_STYLE.findall(source):
        m = _STYLE_NAME.search(element)
        if not m:
            continue
        (builtin if "builtinId=" in element else imported).append(m.group(1))
    return builtin, imported


def document_properties(zf: zipfile.ZipFile) -> dict[str, str]:
    """작성자·최종 수정자·회사·관리자 중 값이 남아 있는 것."""
    found = {}
    for part in ("docProps/core.xml", "docProps/app.xml"):
        source = _text(zf, part)
        for field in _PROPERTY_FIELDS:
            m = re.search(PROPERTY_PATTERN.format(field=field), source)
            if m and m.group(1).strip():
                found[field] = m.group(1).strip()
    return found


def comment_authors(zf: zipfile.ZipFile) -> list[str]:
    authors = []
    for name in zf.namelist():
        if "comments" in name and name.endswith(".xml"):
            for author in _COMMENT_AUTHOR.findall(_text(zf, name)):
                if author.strip() and author.strip() not in authors:
                    authors.append(author.strip())
    return authors


def custom_xml_parts(zf: zipfile.ZipFile) -> list[str]:
    """외부 시스템이 심은 자리 중 내용이 들어 있는 것. SharePoint 가 사용자 정보를 남긴다.

    항목의 존재 자체가 아니라 내용을 본다. 항목을 통째로 지우려면 `[Content_Types].xml`
    과 관계 파일까지 손봐야 해서 파일이 깨질 위험이 있으므로, 걷어낼 때는 내용만 비운다.
    빈 껍데기는 해롭지 않으니 그것까지 위반으로 보면 걷어내고도 계속 걸린다.
    """
    found = []
    for name in zf.namelist():
        if not (name.startswith("customXml/") and name.endswith(".xml")):
            continue
        body = re.sub(r"<[^>]*>", "", _text(zf, name))
        if body.strip():
            found.append(name)
    return found


def search_text(zf: zipfile.ZipFile, needles: list[str]) -> dict[str, list[str]]:
    """금지어가 어느 항목에 들어 있는지 찾는다. 구조적 신호를 보완하는 용도다."""
    hits: dict[str, list[str]] = {}
    for name in zf.namelist():
        if not name.endswith((".xml", ".rels")):
            continue
        source = _text(zf, name)
        for needle in needles:
            if needle and needle in source:
                hits.setdefault(needle, []).append(name)
    return hits
