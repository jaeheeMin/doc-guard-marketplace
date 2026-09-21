"""내보내도 되는 파일인지 본다.

다른 규칙 종류와 묻는 것이 다르다. 나머지는 "이 회사 템플릿과 룰대로 썼나" 를 보지만
이것은 "이거 내보내도 되나" 를 본다. 템플릿을 완벽히 따른 문서에도 흔적이 있을 수 있고,
템플릿을 어긴 문서가 깨끗할 수도 있어 서로 독립이다.

**거래처 이름 목록을 맞춰 보지 않는다.** 목록은 계속 관리해야 하고 목록에 없는 새
거래처는 영영 못 잡는다. 대신 구조적 신호를 본다 — "정상적인 파일이라면 이런 모양이
아니다" 를 잡으므로 목록 없이 성립한다.

**이것은 템플릿을 쓰지 않는 첫 규칙 종류다.** 기대값이 템플릿이 아니라 "깨끗한 상태"
라는 보편적 기준에서 나오기 때문이다. `prepare` 를 등록하지 않아도 규칙이 성립한다는 것을
이 모듈이 보인다.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from checker import ooxml
from checker.model import Violation
from checker.rules import rule

# 깨끗한 엑셀의 명명 스타일은 기본 몇 개뿐이다. 실제로 문제가 된 파일은 54,653개였고
# 그중 54,651개가 복붙으로 딸려온 것이었다. 넉넉히 잡아도 이 선을 넘을 이유가 없다.
DEFAULT_MAX_IMPORTED_STYLES = 20


def _limit(params: dict) -> int:
    value = params.get("최대_명명_스타일") or params.get("max_imported_styles")
    return int(value) if value is not None else DEFAULT_MAX_IMPORTED_STYLES


@rule("external_traces")
def check(path: Path, params: dict) -> list[Violation]:
    if not ooxml.is_ooxml(path):
        return []

    violations: list[Violation] = []
    with zipfile.ZipFile(path) as zf:
        # 1) 복붙으로 쌓인 명명 스타일. 이름 자체가 어느 사업의 것이었는지를 말한다.
        _, imported = ooxml.named_styles(zf)
        limit = _limit(params)
        if len(imported) > limit:
            samples = ", ".join(repr(n) for n in imported[:5])
            violations.append(Violation(
                rule="external_traces",
                expected=f"{limit}개 이하",
                actual=f"{len(imported)}개",
                message="다른 파일에서 딸려온 명명 스타일이 너무 많다(xl/styles.xml). "
                        f"이름 자체가 거래처와 사업명인 경우가 많다. 예: {samples}",
            ))

        # 2) 외부 시스템이 심은 자리. 우리가 만드는 문서에 있을 이유가 없다.
        parts = ooxml.custom_xml_parts(zf)
        if parts:
            violations.append(Violation(
                rule="external_traces",
                expected="없음",
                actual=", ".join(parts[:4]),
                message="외부 시스템이 심은 메타데이터가 남아 있다(customXml/). "
                        "SharePoint 는 여기에 사용자 이름과 소속을 남긴다",
            ))

        # 3) 사람과 조직이 남는 자리.
        for field, value in ooxml.document_properties(zf).items():
            violations.append(Violation(
                rule="external_traces",
                expected="비어 있음",
                actual=value,
                message=f"문서 속성에 {field} 가 남아 있다",
            ))

        authors = ooxml.comment_authors(zf)
        if authors:
            violations.append(Violation(
                rule="external_traces",
                expected="없음",
                actual=", ".join(authors[:5]),
                message="주석 작성자에 실명이 남아 있다",
            ))

        # 4) 구조적 신호로 잡히지 않는 것을 고객사별로 더한다. 없어도 규칙은 성립한다.
        banned = params.get("금지어") or params.get("banned") or []
        for needle, where in ooxml.search_text(zf, list(banned)).items():
            violations.append(Violation(
                rule="external_traces",
                expected=f"'{needle}' 없음",
                actual=", ".join(where[:4]),
                message=f"금지어 '{needle}' 가 파일 안에 남아 있다",
            ))

    return violations
