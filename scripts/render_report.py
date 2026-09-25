"""검사 리포트를 PR 코멘트용 마크다운으로 바꾼다.

사람이 읽는 화면이다. 위반한 규칙 이름만 나열하면 무엇을 어떻게 고쳐야 하는지 알 수
없으므로, 기대값과 실제값과 **쓸 템플릿 경로**를 함께 보여준다. 이 제품의 본질이
거절만 하는 것이 아니라 대신 무엇을 쓸지 알려주는 것이기 때문이다.

종료코드 1(문서 위반)과 2(설정 오류)는 받는 사람이 다르므로 글도 다르다. 문서를 올린
팀원은 규칙 파일을 고칠 권한도 지식도 없다. 자기 문서를 들여다보며 헤매게 두면 안 된다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MARKER = "<!-- doc-guard -->"


def render(report: dict, code: int) -> str:
    out = [MARKER, "## doc-guard", ""]

    if code == 2:
        out += [
            "### 검사를 수행하지 못해 통과 여부를 판단하지 못했습니다",
            "",
            "```",
            str(report.get("message", "")).strip(),
            "```",
            "",
            "**이것은 문서의 문제가 아닙니다.** 규칙 파일이나 워크플로 설정을 관리하는"
            " 담당자에게 알리십시오. 통과한 것이 아니므로 이대로 병합하면 검사를 받지 않은"
            " 문서가 들어갑니다.",
        ]
        return "\n".join(out)

    summary = report.get("summary", {})
    scoped = summary.get("scoped", 0)
    violations = summary.get("violations", 0)

    if scoped == 0:
        out += ["검사 대상 문서가 없습니다. doc-guard 관할 밖의 변경입니다."]
        return "\n".join(out)

    if violations == 0:
        out += [f"문서 {scoped}건을 검사했고 모두 템플릿을 따릅니다."]
        return "\n".join(out)

    out += [
        f"문서 {scoped}건 중 **{violations}건**이 템플릿을 따르지 않습니다.",
        "",
    ]
    for entry in report.get("files", []):
        if entry.get("status") != "violation":
            continue
        out += [f"### `{entry.get('file')}`", "", f"유형: **{entry.get('type')}**", ""]
        for v in entry.get("violations", []):
            out.append(f"- {v.get('message')}")
            expected, actual = v.get("expected"), v.get("actual")
            if expected not in (None, ""):
                out.append(f"  - 기대: `{expected}`")
            if actual not in (None, ""):
                out.append(f"  - 실제: `{actual}`")
        template = entry.get("template")
        if template:
            out += ["", f"쓸 템플릿: `{template}`"]
        out.append("")

    out += ["---", "", "위 템플릿을 보고 고친 뒤 다시 올리십시오."]
    return "\n".join(out)


def main() -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    if len(sys.argv) < 3:
        print("사용법: render_report.py <리포트 json> <종료코드>", file=sys.stderr)
        return 2

    raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    code = int(sys.argv[2])
    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        print(MARKER)
        print("## doc-guard\n\n검사기의 출력을 해석하지 못했습니다.\n")
        print("```\n" + raw.strip()[:1000] + "\n```")
        return 0

    print(render(report, code))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
