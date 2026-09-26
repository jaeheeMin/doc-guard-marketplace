"""검사 리포트를 PR 코멘트용 마크다운으로 바꾼다.

사람이 읽는 화면이다. 위반한 규칙 이름만 나열하면 무엇을 어떻게 고쳐야 하는지 알 수
없으므로, 기대값과 실제값과 **쓸 템플릿 경로**를 함께 보여준다. 이 제품의 본질이
거절만 하는 것이 아니라 대신 무엇을 쓸지 알려주는 것이기 때문이다.

종료코드 1(문서 위반)과 그 밖의 모든 경우(설정 오류, 검사기 출력을 해석하지 못함,
예상치 못한 코드 — 통틀어 "검사 불능")는 받는 사람이 다르므로 글도 다르다. 문서를
올린 팀원은 규칙 파일을 고칠 권한도 지식도 없다. 자기 문서를 들여다보며 헤매게 두면
안 되고, 반대로 검사 불능을 조용히 통과로 뭉개도 안 된다(CLAUDE.md 원칙 7).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MARKER = "<!-- doc-guard -->"


def render(report: dict, code: int) -> str:
    out = [MARKER, "## doc-guard", ""]

    if code not in (0, 1):
        # 위반(1)이 아닌 모든 경우는 검사 불능이다 — 설정 오류(2)든, 검사기 출력을 아예
        # 해석하지 못한 경우든, 예상치 못한 종료코드든 전부 여기로 모은다. 받는 사람이
        # 위반과 다르다: 문서를 올린 팀원이 아니라 규칙·설정을 관리하는 담당자다.
        out += [
            "### ⚠️ 검사 불능",
            "",
            "```",
            str(report.get("message") or f"검사기가 예상치 못한 코드 {code} 로 끝났습니다.").strip(),
            "```",
            "",
            "**이것은 문서의 문제가 아닙니다.** 규칙 파일이나 설정을 관리하는 담당자가 고쳐야 합니다.",
        ]
        return "\n".join(out)

    summary = report.get("summary", {})
    scoped = summary.get("scoped", 0)
    violations = summary.get("violations", 0)
    skipped = summary.get("skipped", 0)
    skipped_files = [f for f in report.get("files", []) if f.get("status") == "skipped"]

    if scoped == 0:
        if skipped:
            # 관할 안에 자리표시·시스템 파일만 있었다. 대조할 문서는 없지만, 그것을
            # "관할 밖" 이라 하면 왜 아무것도 안 걸렸는지 알 수 없다.
            out += [f"검사할 문서는 없고, 건너뛴 파일 {skipped}건이 있습니다."]
            out += _render_skipped(skipped_files)
        else:
            out += ["검사 대상 문서가 없습니다. doc-guard 관할 밖의 변경입니다."]
        return "\n".join(out)

    if violations == 0:
        line = f"문서 {scoped}건을 검사했고 모두 템플릿을 따릅니다."
        if skipped:
            line += f" / 건너뛴 파일 {skipped}건"
        out += [line]
        out += _render_skipped(skipped_files)
        return "\n".join(out)

    out += [
        "### ❌ 템플릿 위반",
        "",
        f"문서 {scoped}건 중 **{violations}건**이 템플릿을 따르지 않습니다. **문서를 고쳐야 합니다.**",
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

    out += _render_skipped(skipped_files)
    out += ["---", "", "위 템플릿을 보고 문서를 고친 뒤 다시 올리십시오."]
    return "\n".join(out)


def _render_skipped(skipped_files: list[dict]) -> list[str]:
    """건너뛴 파일을 짧게 알린다.

    통과와 위반 코멘트 둘 다에서 부른다. 조용히 건너뛰면 "왜 이 파일은 검사 결과에
    안 보이지" 라는 의문이 남으므로, 위반이 없어도 이유와 함께 적어 둔다.
    """
    if not skipped_files:
        return []
    lines = ["", "### 건너뛴 파일", ""]
    for f in skipped_files:
        lines.append(f"- `{f.get('file')}` — {f.get('reason', '')}")
    return lines


def main() -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    if len(sys.argv) < 3:
        print("사용법: render_report.py <리포트 json> <종료코드>", file=sys.stderr)
        return 2

    report_path = Path(sys.argv[1])
    code = int(sys.argv[2])

    try:
        raw = report_path.read_text(encoding="utf-8")
    except OSError as exc:
        # 리포트 파일 자체를 못 읽었다. 검사를 통과한 것으로 보이면 안 되므로 검사
        # 불능으로 렌더링한다(#13).
        print(render({"message": f"{report_path} 를 읽지 못했습니다: {exc}"}, 2))
        return 0

    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        # 검사기 출력을 해석하지 못했다. 종료코드가 무엇이었든 이것도 검사 불능이다 —
        # 무엇을 검사했는지조차 알 수 없는 상태를 통과나 위반으로 뭉개면 안 된다.
        snippet = raw.strip()[:1000]
        print(render({"message": "검사기의 출력을 해석하지 못했습니다.\n\n" + snippet}, 2))
        return 0

    print(render(report, code))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
