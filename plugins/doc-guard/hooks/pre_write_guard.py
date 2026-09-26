"""문서를 저장하기 전에 검사하고, 템플릿을 벗어나면 거절한다.

검사 엔진은 판정만 한다. 거절은 여기서 한다. 엔진이 위반을 종료코드 1 로 알리고,
이 훅이 그것을 받아 Claude 의 쓰기를 막는다.

**왜 PreToolUse 인가.** 막을 수 있는 훅 시점은 여기뿐이다. PostToolUse 는 도구가
이미 실행된 뒤라 되돌릴 수 없다. 대신 이 시점에는 파일이 아직 디스크에 없거나 옛
내용이므로, 저장될 최종 모습을 훅이 직접 만들어 봐야 한다.

- `Write` 는 `tool_input.content` 에 최종 내용이 그대로 온다.
- `Edit` 은 바꿀 조각만 오므로, 디스크의 현재 내용을 읽어 치환을 적용해 본다.

**왜 Python 인가.** 엔진이 이미 Python 이라 새 의존성이 늘지 않고, `jq` 없이 동작하며,
Windows 에서 CRLF 와 한글 인코딩을 다루기 쉽다. 이 저장소의 bash 훅들이 그 둘 때문에
따로 손을 봐야 했다.

**왜 이 파일이 `checker` 를 import 하지 않는가.** 마켓플레이스로 설치된 플러그인
캐시에는 `plugins/doc-guard/` 만 들어가고 `checker/` 는 따라오지 않는다(#12). 예전에는
`sys.path` 에 저장소 루트를 얹어 `checker.locate` 를 가져다 썼는데, 설치본에는 그
루트 자체가 없어 `ModuleNotFoundError` 로 죽었고, Claude Code 는 이 훅의 0/2 가 아닌
종료코드를 "막지 않음" 으로 여겨 조용히 통과시켰다(CLAUDE.md 원칙 7 위반). 그래서 이
파일은 stdlib 만 쓰고, 검사 엔진 자체도 `uvx` 로 이 저장소의 GitHub 원격에서 매번
받아 온다 — 훅과 GitHub Actions 가 같은 엔진을 쓰게 하기 위해서다(이슈 #12 결정).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# 검사 엔진을 받아 오는 기본 위치. GitHub Actions 재사용 워크플로의 기본
# `engine-ref` (main) 와 맞춘다 — 두 관문이 같은 엔진을 쓰는 것이 이 구조의 전제다.
DEFAULT_ENGINE_SPEC = "git+https://github.com/jaeheeMin/blueward-harness@main"

# 엔진을 실행할 시간. uvx 가 처음 이 저장소를 받아 빌드하는 데 시간이 걸릴 수 있어
# 넉넉히 둔다. 이후에는 uv 캐시에 남아 빠르다. hooks.json 의 훅 타임아웃(120초)보다
# 짧게 두어, 타임아웃이 나더라도 이 스크립트가 먼저 붙잡아 deny 로 답할 여유를 남긴다.
ENGINE_TIMEOUT_SECONDS = 110

# 이 훅이 내용을 재조립할 수 있는 형식. docx·xlsx·pptx 는 바이너리라 Write/Edit 도구로
# 의미 있게 만들어지지 않으므로 손대지 않는다. 그쪽은 GitHub Actions 검사가 잡는다.
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".yaml", ".yml", ".json", ".csv"}

# 회사 폴더는 이 둘을 함께 가진 디렉터리다. `checker/locate.py` 의 `find_company_root`
# 와 같은 판단이다. 설치된 플러그인에는 엔진(checker 패키지)이 따라오지 않아 가져다
# 쓸 수 없으므로 여기 그대로 옮겨 적는다 — `checker/locate.py` 가 바뀌면 이쪽도 손으로
# 맞춰야 한다는 뜻이고, 그 대가는 알고 지는 것이다(#12 결정 사항).
COMPANY_MARKERS = ("templates", "rules")

ALLOW = 0  # 통과. 아무것도 출력하지 않으면 통과다.


def allow() -> None:
    sys.exit(ALLOW)


def deny(reason: str) -> None:
    """쓰기를 막고 사유를 사람과 Claude 에게 보여준다."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    # 출력 인코딩을 못 박는다. Windows 콘솔 기본값으로는 한글을 낼 수 없다.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.exit(0)


def find_company_root(path: Path) -> Path | None:
    """문서에서 위로 올라가며 회사 폴더를 찾는다. 없으면 None.

    `checker/locate.py` 의 같은 이름 함수를 그대로 옮긴 것이다. 위 COMPANY_MARKERS
    주석을 본다.
    """
    try:
        start = path.resolve()
    except OSError:
        start = path
    for parent in [start.parent, *start.parent.parents]:
        if all((parent / marker).is_dir() for marker in COMPANY_MARKERS):
            return parent
    return None


def engine_spec() -> str:
    """검사 엔진을 어디서 받을지 정한다.

    기본은 이 저장소의 main 브랜치이고, GitHub Actions 의 기본 `engine-ref` 와
    맞춘다. `DOC_GUARD_ENGINE` 환경변수를 두면 그것을 `uvx --from` 에 그대로
    넘긴다 — 개발과 테스트가 로컬 체크아웃 경로를 가리켜 네트워크 없이 빠르게
    돌리는 통로다.
    """
    return os.environ.get("DOC_GUARD_ENGINE") or DEFAULT_ENGINE_SPEC


def proposed_content(tool: str, tool_input: dict, path: Path) -> str | None:
    """저장되고 나면 파일이 어떤 모습일지 만들어 본다."""
    if tool == "Write":
        return tool_input.get("content") or ""

    # Edit: 디스크의 현재 내용에 치환을 적용해 최종 모습을 얻는다.
    old = tool_input.get("old_string")
    new = tool_input.get("new_string")
    if old is None or new is None:
        return None
    try:
        current = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # 읽을 수 없으면 최종 모습을 알 수 없다. 막지 않는다 — 검사 대상이 아닐
        # 가능성이 크고, 잘못 막으면 팀원이 손쓸 방법이 없다.
        return None
    if old not in current:
        # 치환이 실패할 상황이다. Claude 자신의 오류로 처리되게 둔다.
        return None
    return current.replace(old, new) if tool_input.get("replace_all") else current.replace(old, new, 1)


def format_violations(report: dict) -> str:
    lines = []
    for entry in report.get("files", []):
        if entry.get("status") != "violation":
            continue
        lines.append(f"[{entry.get('type')}] {entry.get('file')}")
        for v in entry.get("violations", []):
            lines.append(f"  - {v.get('message')}")
            expected, actual = v.get("expected"), v.get("actual")
            if expected not in (None, ""):
                lines.append(f"      기대: {expected}")
            if actual not in (None, ""):
                lines.append(f"      실제: {actual}")
        template = entry.get("template")
        if template:
            lines.append(f"  쓸 템플릿: {template}")
    return "\n".join(lines)


def _main() -> None:
    # Windows 콘솔의 기본 stdin 인코딩으로는 회사 폴더나 문서 이름에 든 한글 경로가
    # 깨질 수 있다(#14 의 일부). 여기서 못 박아 두면 적어도 이 훅이 받는 JSON 은
    # 안전하게 읽힌다.
    reconfigure_stdin = getattr(sys.stdin, "reconfigure", None)
    if reconfigure_stdin is not None:
        reconfigure_stdin(encoding="utf-8")

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        # 입력을 읽지 못하면 이 파일이 doc-guard 소관인지조차 알 수 없다. 모른다는 것을
        # 통과로 바꾸지 않는다(CLAUDE.md 원칙 7).
        deny(
            "doc-guard 훅이 Claude Code 가 넘긴 입력을 해석하지 못해 이 문서를 확인할 수 "
            "없었습니다.\n확인되지 않는 상태로 통과시키지 않습니다."
        )

    tool = payload.get("tool_name") or ""
    if tool not in ("Write", "Edit"):
        allow()

    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path")
    if not raw_path:
        allow()

    path = Path(raw_path)
    if path.suffix.lower() not in TEXT_SUFFIXES:
        allow()

    company = find_company_root(path)
    if company is None:
        allow()  # doc-guard 의 소관이 아니다

    content = proposed_content(tool, tool_input, path)
    if content is None:
        allow()

    try:
        relative = path.resolve().relative_to(company.resolve())
    except ValueError:
        allow()

    with tempfile.TemporaryDirectory(prefix="doc-guard-") as tmp:
        staged = Path(tmp) / relative
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(content, encoding="utf-8")

        # 규칙은 회사 폴더의 진짜 것을 쓰고(템플릿 경로가 거기서 풀린다), 관할을 맞춰 볼
        # 기준만 임시 폴더로 둔다. 그래야 파일명·위치 규칙이 원래 자리 기준으로 판정된다.
        #
        # 엔진 자체는 이 저장소에 있지 않고 uvx 로 GitHub 에서 받는다. 처음 받을 때는
        # 네트워크가 필요하고 시간이 걸리지만, uv 캐시에 남아 이후로는 빠르다.
        cmd = [
            "uvx", "--from", engine_spec(), "doc-guard",
            "--rules", str(company / "rules"),
            "--root", tmp,
            str(staged),
        ]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        try:
            done = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", env=env,
                timeout=ENGINE_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            # 여기까지 왔다는 것은 이 파일이 doc-guard 소관이라는 뜻이다. 검사할 수 없는
            # 상태로 통과시키면 정확히 필요한 순간에 보호가 사라진다.
            deny(
                "doc-guard 가 검사 엔진을 받거나 실행하지 못해 이 문서를 확인할 수 없었습니다.\n"
                f"사유: {exc}\n\n"
                "확인할 것: uv 가 설치되어 있는가, 엔진을 처음 받는 것이라면 네트워크가 "
                "되는가. 로컬에서 개발·테스트 중이라면 DOC_GUARD_ENGINE 환경변수로 엔진 "
                "경로를 지정할 수 있습니다.\n"
                "확인되지 않는 상태로 통과시키지 않습니다."
            )

    if done.returncode == 0:
        allow()

    try:
        report = json.loads(done.stdout)
    except json.JSONDecodeError:
        deny(
            "doc-guard 검사기의 출력을 해석하지 못했습니다.\n"
            f"{(done.stderr or done.stdout or '').strip()[:500]}\n\n"
            "확인되지 않는 상태로 통과시키지 않습니다."
        )

    if done.returncode == 2:
        # 설정 오류는 문서 위반과 받는 사람이 다르다. 문서를 쓰는 팀원은 규칙 파일을
        # 고칠 권한도 지식도 없으므로, 자기 문서를 들여다보며 헤매게 두면 안 된다.
        deny(
            "doc-guard 규칙 파일에 문제가 있어 검사할 수 없습니다.\n"
            f"{report.get('message', '')}\n\n"
            "이것은 문서의 문제가 아닙니다. 규칙 파일을 관리하는 담당자에게 알리십시오."
        )

    if done.returncode == 1:
        deny(
            "doc-guard: 이 문서가 템플릿을 따르지 않습니다.\n\n"
            + format_violations(report)
            + "\n\n위 템플릿을 보고 고친 뒤 다시 저장하십시오."
        )

    # 0, 1, 2 는 검사기가 약속한 종료코드다(checker/cli.py). 그 밖은 계약에 없으므로
    # 통과도 위반도 아니다 — 검사를 할 수 없었던 것으로 보고 막는다.
    deny(
        f"doc-guard 검사기가 알 수 없는 종료코드({done.returncode})로 끝나 이 문서를 "
        "확인할 수 없었습니다.\n"
        "확인되지 않는 상태로 통과시키지 않습니다."
    )


def main() -> None:
    """`_main` 을 감싸 무엇이 터지든 막는 쪽으로 떨어지게 한다.

    예전 결함은 `ModuleNotFoundError` 가 이 함수 바깥, import 시점에 나서 훅 전체가
    처리되지 않은 예외로 죽었고, Claude Code 는 0 도 2 도 아닌 그 종료코드를 "막지
    않음" 으로 여겨 조용히 통과시켰다(CLAUDE.md 원칙 7). 이제 이 파일은 stdlib 만
    import 하므로 그 경로 자체가 사라졌지만, 앞으로 또 다른 예상 못한 예외가 나더라도
    같은 실패로 되풀이되지 않도록 여기서 한 번 더 막는다. `allow()`/`deny()` 는
    `sys.exit` 로 끝나므로(`SystemExit` 는 `Exception` 이 아니다) 정상 종료 경로는
    이 처리에 걸리지 않는다.
    """
    try:
        _main()
    except Exception as exc:  # noqa: BLE001 - 의도적으로 전부 잡아 fail-closed 로 만든다
        deny(
            "doc-guard 훅에서 예상치 못한 오류가 나 이 문서를 확인할 수 없었습니다.\n"
            f"사유: {type(exc).__name__}: {exc}\n"
            "확인되지 않는 상태로 통과시키지 않습니다."
        )


if __name__ == "__main__":
    main()
