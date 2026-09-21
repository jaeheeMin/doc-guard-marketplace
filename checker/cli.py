"""엔진의 유일한 공개 인터페이스.

플러그인 훅과 GitHub Actions 가 둘 다 이 명령 하나를 부른다. 두 호출 지점이 이 계약만
붙들고 있으므로 계약이 곧 인터페이스다.

종료코드
    0  통과. 검사한 것이 하나도 없는 경우(전부 관할 밖)도 여기 든다. README 만 고친 PR 이
       CI 를 깨뜨리면 안 되기 때문이다. 구분은 종료코드가 아니라 리포트의 `scoped` 가 싣는다.
    1  문서 위반.
    2  설정 오류. 규칙 파일이 깨졌거나 관할이 겹친 경우.
    3 이상은 비워 둔다. 나중에 "검사한 것이 없으면 실패로 쳐라" 가 필요해지면 기본값을
    건드리지 않는 선택 플래그로 붙인다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from checker.engine import check
from checker.loader import load
from checker.model import ConfigError

EXIT_PASS = 0
EXIT_VIOLATION = 1
EXIT_CONFIG_ERROR = 2


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="doc-guard",
        description="문서가 고객사 템플릿을 따르는지 검사한다.",
    )
    parser.add_argument("paths", nargs="*", type=Path, help="검사할 문서")
    parser.add_argument(
        "--rules", required=True, type=Path, help="규칙 파일 하나 또는 규칙 폴더"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="관할 glob 을 맞춰 볼 기준 경로. 기본은 규칙 폴더의 한 단계 위(회사 폴더)",
    )
    args = parser.parse_args(argv)

    try:
        rules_path = args.rules.resolve()
        types = load(rules_path)
        # 관할 glob 은 회사 폴더를 기준으로 쓴다(`docs/제안서/**`). 규칙은 그 아래
        # `rules/` 에 있으므로 한 단계 위가 기준이 된다.
        rules_dir = rules_path if rules_path.is_dir() else rules_path.parent
        root = (args.root or rules_dir.parent).resolve()
        targets = [(p, _relative(p, root)) for p in args.paths]
        report = check(targets, types)
    except ConfigError as exc:
        json.dump(
            {"status": "config_error", "message": str(exc)},
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return EXIT_CONFIG_ERROR

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return EXIT_VIOLATION if report["summary"]["violations"] else EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
