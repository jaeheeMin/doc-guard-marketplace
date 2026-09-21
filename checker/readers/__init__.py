"""형식별 본문 추출.

리더는 확장자로 고른다. 같은 리더가 템플릿과 검사 대상 문서를 모두 읽는다. 템플릿을
다른 형식으로 변환해 두지 않는 이유가 여기 있다 — 변환하면 검사하려던 구조가 사라진다.

새 형식을 지원하려면 이 패키지에 모듈을 하나 넣고 `@reader(".확장자")` 를 붙이면 된다.
엔진도 로더도 고치지 않는다.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Callable

from checker.model import ConfigError

_READERS: dict[str, Callable[[Path], dict]] = {}
_loaded = False


def reader(*extensions: str):
    """확장자에 리더 함수를 등록하는 장식자."""

    def register(fn):
        for ext in extensions:
            _READERS[ext.lower()] = fn
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


def read(path: Path) -> dict:
    """문서를 읽어 형식에 맞는 구조를 돌려준다.

    돌려주는 사전의 열쇠는 형식마다 다르다. md/docx 는 `sections`, xlsx 는 `sheets`,
    pptx 는 `layouts` 를 담는다. 규칙 모듈은 자기가 쓰는 열쇠만 본다.
    """
    _load_all()
    ext = path.suffix.lower()
    fn = _READERS.get(ext)
    if fn is None:
        raise ConfigError(
            f"{path.name}: '{ext}' 형식을 읽을 리더가 없다. "
            f"지원하는 형식: {', '.join(sorted(_READERS)) or '없음'}"
        )
    return fn(path)


def supported() -> list[str]:
    _load_all()
    return sorted(_READERS)
