"""바뀐 파일 목록을 받아 검사한다. GitHub Actions 워크플로가 부른다.

`doc-guard --auto` 를 그대로 쓰지 않고 한 겹 두는 이유는, Actions 가 넘기는 목록을
먼저 걸러야 하기 때문이다. 존재하지 않는 경로를 엔진에 넘기면 리더가 오류를 내는데
그것은 규칙 파일이 깨진 것과 구분되지 않는다.

**검사할 수 없는 상태를 통과로 답하지 않는다.** 목록에 이름이 있는데 그 경로가 실제
파일이 아니면 무언가 어긋난 것이다. 지워진 파일은 워크플로가 `--diff-filter=d` 로 이미
빼고 넘기므로 정상 상황이 아니다. 실제로 이 자리에서 한 번 당했다. git 이 한글 경로를
따옴표와 8진수로 감싸 내놓는 바람에 모든 경로가 깨졌는데, 그때 이 스크립트가 말없이
"검사 대상 없음" 으로 넘겨 위반 문서가 있는 PR 이 초록불로 통과했다.

같은 이유로 목록 파일 자체가 없는 것과 목록이 비어 있는 것도 구분한다. 목록이 비어
있으면 "바뀐 것이 없다" 는 뜻이라 통과(0)가 맞지만, 목록 파일을 읽지 못하면 무엇이
바뀌었는지조차 알아내지 못한 것이므로 검사 불능(2)이다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from checker.cli import EXIT_CONFIG_ERROR, EXIT_PASS, main

EMPTY_REPORT = (
    '{"summary": {"scoped": 0, "passed": 0, "violations": 0, "skipped": 0,'
    ' "out_of_scope": 0}, "files": []}'
)


def split_listing(text: str) -> tuple[list[str], list[str]]:
    """목록을 실제 파일과 그렇지 않은 것으로 가른다."""
    found, missing = [], []
    for line in text.splitlines():
        name = line.strip()
        if not name:
            continue
        (found if Path(name).is_file() else missing).append(name)
    return found, missing


def main_entry(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("사용법: check_changed.py <바뀐 파일 목록 파일>", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    listing_path = Path(args[0])
    try:
        listing_text = listing_path.read_text(encoding="utf-8")
    except OSError as exc:
        # 목록 파일 자체가 없다. 목록이 비어 있는 것과는 다르다 — 비어 있으면 "바뀐 것이
        # 없다" 지만, 파일이 없으면 무엇이 바뀌었는지조차 알아낼 수 없었다는 뜻이다.
        print(json.dumps({
            "status": "config_error",
            "message": f"바뀐 파일 목록 {listing_path} 를 읽지 못했습니다: {exc}",
        }, ensure_ascii=False))
        return EXIT_CONFIG_ERROR

    found, missing = split_listing(listing_text)

    if missing:
        print(
            f"목록에 있으나 실제 파일이 아닌 경로 {len(missing)}건: "
            + ", ".join(missing[:5])
            + ("..." if len(missing) > 5 else ""),
            file=sys.stderr,
        )

    if missing and not found:
        # 전부 깨졌다. 통과라고 답하면 보호가 필요한 순간에 보호가 사라진다.
        print(
            '{"status": "config_error", "message": '
            '"바뀐 파일 목록의 경로가 하나도 실제 파일이 아닙니다. '
            '경로가 이스케이프되었거나 작업 디렉터리가 어긋났을 수 있습니다."}'
        )
        return EXIT_CONFIG_ERROR

    if not found:
        # 애초에 목록이 비어 있었다. 검사할 것이 없고 그 사실은 리포트가 싣는다.
        print(EMPTY_REPORT)
        return EXIT_PASS

    return main(["--auto", *found])


if __name__ == "__main__":
    raise SystemExit(main_entry())
