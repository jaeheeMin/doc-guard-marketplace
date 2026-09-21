"""바뀐 파일 목록을 받아 검사한다. GitHub Actions 워크플로가 부른다.

`doc-guard --auto` 를 그대로 쓰지 않고 한 겹 두는 이유는, Actions 가 넘기는 목록에
삭제된 파일이나 검사 대상이 아닌 것이 섞여 들어오기 때문이다. 존재하지 않는 경로를
엔진에 넘기면 리더가 오류를 내는데, 그것은 설정 오류와 구분되지 않는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

from checker.cli import EXIT_PASS, EXIT_VIOLATION, main


def main_entry() -> int:
    if len(sys.argv) < 2:
        print("사용법: check_changed.py <바뀐 파일 목록 파일>", file=sys.stderr)
        return 2

    listing = Path(sys.argv[1])
    paths = []
    for line in listing.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name:
            continue
        p = Path(name)
        # 지워졌거나 디렉터리인 것은 검사할 수 없다.
        if p.is_file():
            paths.append(str(p))

    if not paths:
        # 검사할 것이 없다. 종료코드는 0 이고, 그 사실은 리포트가 싣는다.
        print('{"summary": {"scoped": 0, "passed": 0, "violations": 0, "out_of_scope": 0},'
              ' "files": []}')
        return EXIT_PASS

    return main(["--auto", *paths])


if __name__ == "__main__":
    raise SystemExit(main_entry())
