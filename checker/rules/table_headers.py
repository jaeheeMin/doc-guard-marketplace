"""엑셀 표의 헤더 행이 템플릿과 같은지 본다.

어느 시트의 몇 행이 헤더인지는 규칙 파일이 지정하고, 그 자리에 무엇이 적혀 있어야 하는지는
템플릿에서 읽는다. 헤더 위치를 자동으로 찾지 않는 이유는 실제 템플릿에서 헛짚기 때문이다.
어떤 시트는 진짜 컬럼 헤더가 12행에 있고 그 위 5행은 '테이블ID | ZBTPA0010' 같은 레이블-값
쌍이라, '값이 여럿 있는 첫 행' 류의 어떤 heuristic 도 위쪽을 먼저 집는다.
"""
from __future__ import annotations

from pathlib import Path

from checker.model import ConfigError, Violation
from checker.readers.xlsx import read_row
from checker.rules import prepare, rule


def _target(params: dict) -> tuple[str, int]:
    sheet = params.get("시트") or params.get("sheet")
    row = params.get("헤더_행") or params.get("header_row")
    if not sheet or not row:
        raise ConfigError("table_headers 규칙에는 '시트' 와 '헤더_행' 이 모두 있어야 한다")
    return str(sheet), int(row)


@prepare("table_headers")
def from_template(params: dict, template: Path) -> dict:
    sheet, row = _target(params)
    expected = read_row(template, sheet, row)
    if expected is None:
        raise ConfigError(f"템플릿 {template.name} 에 '{sheet}' 시트가 없다")
    params = dict(params)
    params["_expected"] = expected
    return params


@rule("table_headers")
def check(path: Path, params: dict) -> list[Violation]:
    sheet, row = _target(params)
    expected = params.get("_expected") or []
    actual = read_row(path, sheet, row)

    if actual is None:
        return [
            Violation(
                rule="table_headers",
                expected=f"'{sheet}' 시트",
                actual="없음",
                message=f"'{sheet}' 시트가 없어 헤더를 볼 수 없다",
            )
        ]
    if actual == expected:
        return []
    return [
        Violation(
            rule="table_headers",
            expected=expected,
            actual=actual,
            message=f"'{sheet}' 시트 {row}행의 헤더가 템플릿과 다르다",
        )
    ]
