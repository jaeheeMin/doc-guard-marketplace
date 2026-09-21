"""엑셀 문서에 있어야 할 시트가 있는지 본다.

시트 목록만은 템플릿에서 뽑을 수 없어 규칙 파일이 나열한다. 실제 템플릿을 뜯어보니 빈
양식은 시트가 7개인데 이를 채운 산출물은 10개였다. 늘어난 셋은 프로그램마다 새로 생기는
화면 레이아웃 시트다. 즉 어느 시트가 필수이고 어느 시트가 그때그때 붙는 것인지는 템플릿이
말해 주지 않는다.
"""
from __future__ import annotations

from pathlib import Path

from checker.model import ConfigError, Violation
from checker.readers import read
from checker.rules import rule


@rule("required_sheets")
def check(path: Path, params: dict) -> list[Violation]:
    required = params.get("필수") or params.get("required")
    if not required:
        raise ConfigError("required_sheets 규칙에 '필수' 시트 목록이 없다")

    sheets = read(path).get("sheets", [])
    missing = [name for name in required if name not in sheets]
    if not missing:
        return []
    return [
        Violation(
            rule="required_sheets",
            expected=name,
            actual=f"있는 시트: {', '.join(sheets)}",
            message=f"'{name}' 시트가 없다",
        )
        for name in missing
    ]
