"""바뀐 파일 목록을 받아 검사한다. GitHub Actions 워크플로가 부른다.

`doc-guard --auto` 를 그대로 쓰지 않고 한 겹 두는 이유는, Actions 가 넘기는 목록을
먼저 걸러야 하기 때문이다. 존재하지 않는 경로를 엔진에 넘기면 리더가 오류를 내는데
그것은 규칙 파일이 깨진 것과 구분되지 않는다.

**검사할 수 없는 상태를 통과로 답하지 않는다.** 목록에 이름이 있는데 그 경로가 실제
파일이 아니면 무언가 어긋난 것이다. 지워진 파일은 워크플로가 `--diff-filter=d` 로 이미
빼고 넘기므로 정상 상황이 아니다. 실제로 이 자리에서 한 번 당했다. git 이 한글 경로를
따옴표와 8진수로 감싸 내놓는 바람에 모든 경로가 깨졌는데, 그때 이 스크립트가 말없이
"검사 대상 없음" 으로 넘겨 위반 문서가 있는 PR 이 초록불로 통과했다.

부르는 쪽이 둘이고, 규칙이 어디 있느냐가 달라 모드도 둘이다.

- **문서 저장소** — 회사 폴더 안에 `templates/` 와 `rules/` 와 문서가 함께 있다.
  인자 없이 부르면 `--auto` 로 문서에서 위로 올라가며 회사 폴더를 찾는다.
- **프로젝트 저장소** — 문서만 있고 규칙은 다른 저장소에 있다. 위로 올라가도 회사
  폴더가 없으므로 `--auto` 가 성립하지 않는다. `--rules` 로 규칙 폴더를, `--root` 로
  관할을 맞춰 볼 기준 경로를 받는다.

회사를 지정하지 않은 것은 "이 저장소 안에 회사 폴더가 있다" 는 뜻이다. 그래서 회사 폴더가
하나도 없으면 어떤 파일이 바뀌었든 검사할 방법이 없고, 그것은 프로젝트 저장소가 회사를
빠뜨린 경우다. 통과로 넘기면 검사를 받지 않은 문서가 "관할 밖" 을 달고 들어간다.

`--rules` 를 줄 때 `--root` 를 반드시 함께 받는다. 엔진의 기본 기준 경로는 "규칙 폴더의
한 단계 위" 인데, 프로젝트 저장소의 문서는 그 아래에 있지 않다. 그러면 상대경로 계산이
실패하고 절대경로로 떨어져 관할 glob 이 맞지 않게 되며, 그 문서는 위반도 오류도 아닌
"관할 밖" 으로 조용히 통과한다. 판단 실패가 관할 밖으로 위장되는 자리라 막아 둔다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from checker.cli import EXIT_CONFIG_ERROR, EXIT_PASS, main

EMPTY_REPORT = (
    '{"summary": {"scoped": 0, "passed": 0, "violations": 0, "out_of_scope": 0},'
    ' "files": []}'
)

USAGE = "사용법: check_changed.py <바뀐 파일 목록 파일> [--rules <규칙 폴더> --root <기준 경로>]"


def split_listing(text: str) -> tuple[list[str], list[str]]:
    """목록을 실제 파일과 그렇지 않은 것으로 가른다."""
    found, missing = [], []
    for line in text.splitlines():
        name = line.strip()
        if not name:
            continue
        (found if Path(name).is_file() else missing).append(name)
    return found, missing


def parse_args(
    args: list[str],
) -> tuple[tuple[str, str | None, str | None] | None, str | None]:
    """인자를 목록 파일과 규칙 위치로 가른다. 두 번째 값은 오류 사유다."""
    listing: str | None = None
    rules: str | None = None
    root: str | None = None
    index = 0
    while index < len(args):
        item = args[index]
        if item in ("--rules", "--root"):
            if index + 1 >= len(args):
                return None, f"{item} 에 값이 없습니다. {USAGE}"
            if item == "--rules":
                rules = args[index + 1]
            else:
                root = args[index + 1]
            index += 2
            continue
        if listing is not None:
            return None, f"알 수 없는 인자입니다: {item}. {USAGE}"
        listing = item
        index += 1
    if listing is None:
        return None, USAGE
    return (listing, rules, root), None


def config_error(message: str) -> int:
    """검사할 수 없는 상태를 알린다. 통과라고도 위반이라고도 답하지 않는다."""
    print(json.dumps({"status": "config_error", "message": message}, ensure_ascii=False))
    print(message, file=sys.stderr)
    return EXIT_CONFIG_ERROR


def rules_problem(rules: str, root: str | None) -> str | None:
    """규칙 위치가 검사에 쓸 수 있는 상태인지 본다. 쓸 수 있으면 None 이다."""
    if root is None:
        return (
            "--rules 를 줄 때는 --root 도 함께 주어야 합니다. 기준 경로가 없으면 관할을 "
            "규칙 폴더 기준으로 맞춰 보게 되어, 검사 대상이 하나도 잡히지 않은 채 "
            "통과합니다."
        )
    if not Path(rules).is_dir():
        return (
            f"규칙 폴더가 없습니다: {rules}. 문서 저장소에 그 회사 폴더가 있는지, "
            "회사 이름을 바르게 넘겼는지 확인하십시오."
        )
    if not Path(root).is_dir():
        return f"기준 경로가 없습니다: {root}."
    return None


def has_company_folder(root: Path, depth: int = 2) -> bool:
    """회사 폴더가 하나라도 있는지 본다.

    `templates/` 와 `rules/` 를 함께 둔 폴더가 회사 폴더다. 엔진이 문서에서 위로
    올라가며 찾는 것과 같은 표식을, 저장소 위에서 아래로 훑어 찾는다.
    """
    for level in range(depth + 1):
        for templates in root.glob("/".join(["*"] * level + ["templates"])):
            if templates.is_dir() and (templates.parent / "rules").is_dir():
                return True
    return False


def _force_utf8() -> None:
    """한글 메시지가 Windows 콘솔 코드페이지에서 깨지지 않게 한다."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main_entry(argv: list[str] | None = None) -> int:
    _force_utf8()
    args = sys.argv[1:] if argv is None else argv

    parsed, error = parse_args(args)
    if error is not None:
        return config_error(error)
    listing, rules, root = parsed

    if rules is not None:
        problem = rules_problem(rules, root)
        if problem is not None:
            return config_error(problem)
    elif root is not None:
        return config_error(f"--root 는 --rules 와 함께 주어야 합니다. {USAGE}")

    found, missing = split_listing(Path(listing).read_text(encoding="utf-8"))

    if missing:
        print(
            f"목록에 있으나 실제 파일이 아닌 경로 {len(missing)}건: "
            + ", ".join(missing[:5])
            + ("..." if len(missing) > 5 else ""),
            file=sys.stderr,
        )

    if missing and not found:
        # 전부 깨졌다. 통과라고 답하면 보호가 필요한 순간에 보호가 사라진다.
        return config_error(
            "바뀐 파일 목록의 경로가 하나도 실제 파일이 아닙니다. "
            "경로가 이스케이프되었거나 작업 디렉터리가 어긋났을 수 있습니다."
        )

    if not found:
        # 애초에 목록이 비어 있었다. 검사할 것이 없고 그 사실은 리포트가 싣는다.
        print(EMPTY_REPORT)
        return EXIT_PASS

    if rules is None:
        # 회사를 지정하지 않았다는 것은 "이 저장소 안에 회사 폴더가 있다" 는 뜻이다.
        # 회사 폴더가 하나도 없으면 어떤 파일이 바뀌었든 검사할 방법이 없다. 프로젝트
        # 저장소가 회사를 빠뜨린 경우가 여기로 온다. 통과로 넘기면 검사를 받지 않은
        # 문서가 "관할 밖" 을 달고 들어간다.
        if not has_company_folder(Path.cwd()):
            return config_error(
                "회사를 지정하지 않았는데 이 저장소 안에 회사 폴더가 없습니다. "
                "templates 와 rules 를 함께 둔 폴더를 찾지 못했습니다. 프로젝트 "
                "저장소라면 워크플로에 company 를 주어 문서 저장소의 기준을 "
                "가져오게 하십시오."
            )
        return main(["--auto", *found])
    return main(["--rules", rules, "--root", root, *found])


if __name__ == "__main__":
    raise SystemExit(main_entry())
