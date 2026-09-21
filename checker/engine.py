"""평면 규칙을 돌려 위반을 모은다.

여기는 문서 유형도 템플릿도 모른다. 로더가 이미 유형 묶음을 펼치고 템플릿에서 기대값을
뽑아 두었으므로, 엔진이 하는 일은 '이 파일이 어느 관할에 드는가' 와 '거기 달린 규칙들을
돌린다' 둘뿐이다. 규칙 종류가 늘어도 이 파일은 바뀌지 않는다.
"""
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from checker import rules as rule_registry
from checker.model import ConfigError, DocType, Violation

OUT_OF_SCOPE = "out_of_scope"
PASS = "pass"
VIOLATION = "violation"


def _matches(relative: str, pattern: str) -> bool:
    """glob 하나를 경로에 맞춰 본다.

    구분자를 `/` 로 맞춘 뒤 본다. 훅은 Windows 에서, Actions 는 Linux 에서 도는데 같은
    규칙 파일이 양쪽에서 같게 동작해야 한다. `**` 는 fnmatch 가 `*` 와 구분하지 않으므로
    여러 단계를 건너뛰는 뜻으로 그대로 쓴다.
    """
    path = relative.replace("\\", "/")
    pattern = pattern.replace("\\", "/")
    if fnmatch(path, pattern):
        return True
    # `docs/**` 처럼 끝이 열린 꼴은 그 아래 전부를 뜻하게 한다.
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3].rstrip("/") + "/")
    return False


def resolve(relative: str, types: list[DocType]) -> DocType | None:
    """파일이 어느 문서 유형의 관할에 드는지 정한다.

    둘 이상에 걸리면 고르지 않고 설정 오류로 끊는다. 이 제품의 출력은 "이 템플릿을 쓰세요"
    라서, 조용히 한쪽을 고르면 틀렸을 때 사람을 엉뚱한 템플릿으로 안내한다. 아무 신호 없이
    틀린 답을 주느니 시끄럽게 실패하는 편이 낫다.
    """
    hits = [t for t in types if _matches(relative, t.jurisdiction)]
    if not hits:
        return None
    if len(hits) > 1:
        names = ", ".join(f"'{t.name}'({t.jurisdiction})" for t in hits)
        raise ConfigError(f"{relative} 이 여러 유형의 관할에 든다 — {names}")
    return hits[0]


def check_file(path: Path, relative: str, types: list[DocType]) -> dict:
    doc_type = resolve(relative, types)
    if doc_type is None:
        return {
            "file": relative,
            "type": None,
            "template": None,
            "status": OUT_OF_SCOPE,
            "violations": [],
        }

    violations: list[Violation] = []
    for r in doc_type.rules:
        fn = rule_registry.get(r.kind)
        params = dict(r.params)
        params["_relative"] = relative
        violations.extend(fn(path, params))

    return {
        "file": relative,
        "type": doc_type.name,
        # 위반이 없어도 유형과 템플릿을 싣는다. 문서를 올리는 사람은 위반을 알기 전에
        # "뭘 보고 쓰지" 부터 궁금하기 때문이다. 템플릿을 쓰지 않는 유형도 있으므로
        # (템플릿 자체를 검사하는 경우) 없으면 null 이다.
        "template": doc_type.template or None,
        "status": VIOLATION if violations else PASS,
        "violations": [v.to_json() for v in violations],
    }


def check(paths: list[tuple[Path, str]], types: list[DocType]) -> dict:
    files = [check_file(p, rel, types) for p, rel in paths]
    counted = [f for f in files if f["status"] != OUT_OF_SCOPE]
    return {
        "summary": {
            "scoped": len(counted),
            "passed": sum(1 for f in counted if f["status"] == PASS),
            "violations": sum(1 for f in counted if f["status"] == VIOLATION),
            "out_of_scope": len(files) - len(counted),
        },
        "files": files,
    }
