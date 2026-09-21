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
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# 이 훅이 내용을 재조립할 수 있는 형식. docx·xlsx·pptx 는 바이너리라 Write/Edit 도구로
# 의미 있게 만들어지지 않으므로 손대지 않는다. 그쪽은 GitHub Actions 검사가 잡는다.
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".yaml", ".yml", ".json", ".csv"}

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
    """문서가 속한 회사 폴더를 찾는다.

    회사 폴더는 `templates/` 와 `rules/` 를 함께 가진 디렉터리다. 문서에서 위로
    올라가며 찾는다. 찾지 못하면 doc-guard 의 소관이 아니므로 아무 말도 하지 않는다.

    이 판단에 엔진이 필요 없다는 점이 중요하다. 대부분의 쓰기는 여기서 끝나므로,
    파일을 고칠 때마다 검사기를 띄우지 않는다.
    """
    for parent in [path.parent, *path.parent.parents]:
        if (parent / "templates").is_dir() and (parent / "rules").is_dir():
            return parent
    return None


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


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        allow()  # 입력을 해석하지 못하면 관여하지 않는다

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

    engine = Path(__file__).resolve().parents[3]

    with tempfile.TemporaryDirectory(prefix="doc-guard-") as tmp:
        staged = Path(tmp) / relative
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(content, encoding="utf-8")

        # 규칙은 회사 폴더의 진짜 것을 쓰고(템플릿 경로가 거기서 풀린다), 관할을 맞춰 볼
        # 기준만 임시 폴더로 둔다. 그래야 파일명·위치 규칙이 원래 자리 기준으로 판정된다.
        cmd = [
            "uv", "run", "--project", str(engine), "doc-guard",
            "--rules", str(company / "rules"),
            "--root", tmp,
            str(staged),
        ]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        try:
            done = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", env=env, timeout=25
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            # 여기까지 왔다는 것은 이 파일이 doc-guard 소관이라는 뜻이다. 검사할 수 없는
            # 상태로 통과시키면 정확히 필요한 순간에 보호가 사라진다.
            deny(
                "doc-guard 가 검사기를 실행하지 못해 이 문서를 확인할 수 없었습니다.\n"
                f"사유: {exc}\n"
                "uv 가 설치되어 있는지 확인하십시오. 확인되지 않는 상태로 통과시키지 않습니다."
            )

    if done.returncode == 0:
        allow()

    try:
        report = json.loads(done.stdout)
    except json.JSONDecodeError:
        deny(
            "doc-guard 검사기의 출력을 해석하지 못했습니다.\n"
            f"{(done.stderr or done.stdout or '').strip()[:500]}"
        )

    if done.returncode == 2:
        # 설정 오류는 문서 위반과 받는 사람이 다르다. 문서를 쓰는 팀원은 규칙 파일을
        # 고칠 권한도 지식도 없으므로, 자기 문서를 들여다보며 헤매게 두면 안 된다.
        deny(
            "doc-guard 규칙 파일에 문제가 있어 검사할 수 없습니다.\n"
            f"{report.get('message', '')}\n\n"
            "이것은 문서의 문제가 아닙니다. 규칙 파일을 관리하는 담당자에게 알리십시오."
        )

    deny(
        "doc-guard: 이 문서가 템플릿을 따르지 않습니다.\n\n"
        + format_violations(report)
        + "\n\n위 템플릿을 보고 고친 뒤 다시 저장하십시오."
    )


if __name__ == "__main__":
    main()
