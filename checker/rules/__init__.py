"""규칙 종류 등록소.

규칙 *종류* 는 여기 모듈로 구현하고, 규칙 *자체* 는 고객사별 규칙 파일에 데이터로 적는다.
새 규칙 종류를 더할 때 이 패키지에 파일을 하나 넣고 `@rule("이름")` 을 붙이면 끝이고,
`engine.py` 는 건드리지 않는다. 엔진 코드를 고쳐야 규칙이 늘어난다면 설계가 어긋난 것이다.

규칙 함수의 모양은 `(path, params) -> list[Violation]` 하나뿐이다. 문서 유형이나 템플릿
경로를 인자로 받지 않는다. `filename` 과 `location` 은 유형이 무엇인지 알 필요가 없는데
유형을 넘기면 그 둘까지 유형 개념에 묶이기 때문이다. 템플릿에서 뽑아낸 기대값은 로더가
미리 `params` 에 넣어 준다.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Callable

from checker.model import ConfigError, Violation

RuleFn = Callable[[Path, dict], list]

_RULES: dict[str, RuleFn] = {}
_PREPARE: dict[str, Callable[[dict, Path], dict]] = {}
_loaded = False


def rule(kind: str):
    """규칙 종류를 이름에 등록하는 장식자."""

    def register(fn: RuleFn) -> RuleFn:
        _RULES[kind] = fn
        return fn

    return register


def prepare(kind: str):
    """템플릿에서 기대값을 뽑아 `params` 에 채우는 함수를 등록하는 장식자.

    로더가 규칙 파일을 펼칠 때 한 번 부른다. `(params, template_path) -> params` 모양이며,
    등록하지 않은 규칙 종류는 규칙 파일에 적힌 `params` 를 그대로 쓴다.
    """

    def register(fn):
        _PREPARE[kind] = fn
        return fn

    return register


def _load_all() -> None:
    global _loaded
    if _loaded:
        return
    for mod in pkgutil.iter_modules(__path__):
        if not mod.name.startswith("_"):
            importlib.import_module(f"{__name__}.{mod.name}")
    _loaded = True


def get(kind: str) -> RuleFn:
    _load_all()
    fn = _RULES.get(kind)
    if fn is None:
        raise ConfigError(
            f"'{kind}' 는 모르는 규칙 종류다. 아는 것: {', '.join(sorted(_RULES))}"
        )
    return fn


def get_prepare(kind: str):
    _load_all()
    return _PREPARE.get(kind)


def known() -> list[str]:
    _load_all()
    return sorted(_RULES)
