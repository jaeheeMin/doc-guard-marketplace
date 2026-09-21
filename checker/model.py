"""엔진 전체가 주고받는 자료형.

규칙 모듈은 `Violation` 만 만들어 돌려주면 되고, 그 밖의 것은 엔진이 다룬다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ConfigError(Exception):
    """규칙 파일이 잘못되었을 때. 종료코드 2 로 이어진다.

    문서가 규칙을 어긴 것과는 다른 사건이다. 문서를 올린 팀원은 규칙 파일을 고칠
    권한도 지식도 없으므로 둘을 섞으면 안 된다.
    """


@dataclass(frozen=True)
class Violation:
    """규칙 하나를 어긴 사실 하나."""

    rule: str
    expected: Any
    actual: Any
    message: str = ""

    def to_json(self) -> dict:
        return {
            "rule": self.rule,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
        }


@dataclass(frozen=True)
class Rule:
    """평면으로 펼쳐진 규칙 하나.

    로더가 규칙 파일과 템플릿을 읽어 이 모양으로 만들어 둔다. `params` 에는 템플릿에서
    뽑아낸 기대값이 이미 박혀 있어서, 규칙 모듈도 엔진도 템플릿이라는 것이 있는 줄 모른다.
    """

    kind: str
    doc_type: str
    template: str
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DocType:
    """규칙 파일 하나가 기술하는 문서 유형 하나."""

    name: str
    jurisdiction: str
    template: str
    rules: tuple[Rule, ...]
    source: str
