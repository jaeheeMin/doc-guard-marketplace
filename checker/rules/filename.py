"""파일 이름이 정해진 형식을 따르는지 본다.

관할 glob 은 느슨하게 두고 이 패턴은 엄격하게 둔다. 둘을 같게 만들면 이름을 틀린 파일이
어느 유형에도 걸리지 않아 조용히 무시되고, 정작 이 규칙이 잡아야 할 파일을 놓친다.
"""
from __future__ import annotations

import re
from pathlib import Path

from checker.model import ConfigError, Violation
from checker.rules import rule


@rule("filename")
def check(path: Path, params: dict) -> list[Violation]:
    pattern = params.get("패턴") or params.get("pattern")
    if not pattern:
        raise ConfigError("filename 규칙에 '패턴' 이 없다")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ConfigError(f"filename 규칙의 '패턴' 이 올바른 정규식이 아니다: {exc}") from exc

    if compiled.search(path.name):
        return []
    return [
        Violation(
            rule="filename",
            expected=pattern,
            actual=path.name,
            message="파일 이름이 정해진 형식과 다르다",
        )
    ]
