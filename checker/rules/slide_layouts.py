"""발표 자료가 공식 템플릿에서 시작되었는지 본다.

슬라이드마다 규율을 잡는 규칙이 아니다. 실제 템플릿이 정의하는 레이아웃은 셋뿐이고 자료
61장 중 51장이 그중 하나를 쓰므로, 슬라이드 단위로는 아무것도 걸러내지 못한다. 대신 문서가
쓴 레이아웃 집합이 템플릿이 정의한 집합 안에 들어오는지를 보면, 그 파일이 공식 템플릿에서
시작되었는지가 드러난다. PowerPoint 를 새로 열어 만든 자료는 '제목 및 내용' 같은 오피스
기본 레이아웃 이름이 나오므로 바로 걸린다.

테마 이름은 지문이 되지 못한다. 공식 템플릿과 그것으로 만든 자료가 둘 다 'Office Theme' 였다.
"""
from __future__ import annotations

from pathlib import Path

from checker.model import ConfigError, Violation
from checker.readers import read
from checker.rules import prepare, rule


@prepare("slide_layouts")
def from_template(params: dict, template: Path) -> dict:
    defined = read(template).get("layouts", {}).get("defined", [])
    if not defined:
        raise ConfigError(f"템플릿 {template.name} 에서 슬라이드 레이아웃을 찾지 못했다")
    params = dict(params)
    params["_allowed"] = defined
    return params


@rule("slide_layouts")
def check(path: Path, params: dict) -> list[Violation]:
    allowed = set(params.get("_allowed") or [])
    used = read(path).get("layouts", {}).get("used", [])
    outside = [name for name in used if name not in allowed]
    if not outside:
        return []
    return [
        Violation(
            rule="slide_layouts",
            expected=sorted(allowed),
            actual=outside,
            message="템플릿이 정의하지 않은 레이아웃을 쓴 슬라이드가 있다. "
            "공식 템플릿에서 시작하지 않은 자료로 보인다",
        )
    ]
