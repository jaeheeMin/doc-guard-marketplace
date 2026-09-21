"""템플릿에 있는 절이 문서에도 있는지 본다. md 와 docx 가 함께 쓴다.

절 목록을 규칙 파일에 받아적지 않는다. 그러면 기준이 템플릿과 규칙 파일 두 벌이 되고,
누가 템플릿에 절을 추가하고 규칙 파일을 안 고치면 철 지난 목록으로 검사하면서 아무 경고도
하지 않는다. 그래서 목록은 템플릿에서 읽고, 규칙 파일에는 예외(선택 섹션)만 적는다.
"""
from __future__ import annotations

from pathlib import Path

from checker.model import Violation
from checker.readers import read
from checker.rules import prepare, rule


def _min_level(params: dict) -> int:
    """비교를 시작할 제목 수준.

    1수준은 문서 자신의 이름이라 템플릿(`# 제안서`)과 문서(`# 로그인 개선 제안서`)가
    다른 것이 정상이다. 그래서 기본은 2수준부터 본다.
    """
    return int(params.get("최소_수준") or params.get("min_level") or 2)


@prepare("required_sections")
def from_template(params: dict, template: Path) -> dict:
    low = _min_level(params)
    titles = [s["title"] for s in read(template).get("sections", []) if s["level"] >= low]
    optional = set(params.get("선택_섹션") or params.get("optional") or [])
    params = dict(params)
    params["_required"] = [t for t in titles if t not in optional]
    return params


@rule("required_sections")
def check(path: Path, params: dict) -> list[Violation]:
    required = params.get("_required") or []
    low = _min_level(params)
    found = {s["title"] for s in read(path).get("sections", []) if s["level"] >= low}
    missing = [t for t in required if t not in found]
    if not missing:
        return []
    return [
        Violation(
            rule="required_sections",
            expected=t,
            actual="없음",
            message=f"템플릿에 있는 '{t}' 절이 문서에 없다",
        )
        for t in missing
    ]
