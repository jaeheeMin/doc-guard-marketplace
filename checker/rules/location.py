"""문서가 있어야 할 곳에 있는지 본다."""
from __future__ import annotations

from pathlib import PurePosixPath, Path

from checker.model import ConfigError, Violation
from checker.rules import rule


@rule("location")
def check(path: Path, params: dict) -> list[Violation]:
    expected = params.get("있어야_할_곳") or params.get("under")
    if not expected:
        raise ConfigError("location 규칙에 '있어야_할_곳' 이 없다")

    # 경로 구분자를 한쪽으로 맞춘다. 훅은 Windows 에서, Actions 는 Linux 에서 돈다.
    actual = PurePosixPath(params["_relative"].replace("\\", "/"))
    wanted = PurePosixPath(str(expected).replace("\\", "/").rstrip("/"))

    if wanted in actual.parents:
        return []
    return [
        Violation(
            rule="location",
            expected=f"{wanted}/ 아래",
            actual=str(actual.parent),
            message="문서가 있어야 할 곳에 있지 않다",
        )
    ]
