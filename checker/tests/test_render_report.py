"""PR 코멘트 렌더링을 단언한다.

위반과 검사 불능은 받는 사람이 다르므로(#13) 제목부터 갈려야 한다. 위반은 문서를
올린 팀원이 고치고, 검사 불능은 규칙·설정을 관리하는 담당자가 고친다. 이 구분이
무너지면 엉뚱한 사람이 헤매게 된다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from render_report import render  # noqa: E402


def _report(scoped: int, violations: int, files: list[dict] | None = None) -> dict:
    return {
        "summary": {
            "scoped": scoped,
            "passed": scoped - violations,
            "violations": violations,
            "out_of_scope": 0,
        },
        "files": files or [],
    }


def test_위반은_템플릿_위반_제목이다():
    report = _report(
        1,
        1,
        [
            {
                "file": "docs/제안서/제안서최종.md",
                "type": "제안서",
                "template": "templates/제안서.md",
                "status": "violation",
                "violations": [
                    {"rule": "filename", "expected": "20260101_x_제안서.md",
                     "actual": "제안서최종.md", "message": "파일 이름이 규칙과 다릅니다"}
                ],
            }
        ],
    )
    text = render(report, 1)
    assert "❌ 템플릿 위반" in text
    assert "문서를 고쳐야 합니다" in text
    assert "검사 불능" not in text
    assert "제안서최종.md" in text


def test_통과에는_위반_제목이_없다():
    text = render(_report(2, 0), 0)
    assert "❌" not in text
    assert "⚠️" not in text
    assert "모두 템플릿을 따릅니다" in text


def test_설정오류는_검사불능_제목이고_문서_문제가_아니라고_말한다():
    text = render({"message": "규칙.yaml 이 깨졌습니다"}, 2)
    assert "⚠️ 검사 불능" in text
    assert "문서의 문제가 아닙니다" in text
    assert "규칙.yaml 이 깨졌습니다" in text
    assert "❌ 템플릿 위반" not in text


def test_예상치_못한_코드도_검사불능이다():
    text = render({}, 7)
    assert "⚠️ 검사 불능" in text
    assert "문서의 문제가 아닙니다" in text


def test_리포트가_비어있어도_검사불능이지_통과가_아니다():
    """summary 가 없는 이상한 리포트를 통과로 읽으면 안 된다."""
    text = render({}, 2)
    assert "⚠️ 검사 불능" in text
    assert "모두 템플릿을 따릅니다" not in text


def test_리포트_json이_깨지면_main이_검사불능으로_렌더링한다(tmp_path, capsys):
    from render_report import main

    report_path = tmp_path / "report.json"
    report_path.write_text("이것은 JSON 이 아니다 {{{", encoding="utf-8")

    argv = ["render_report.py", str(report_path), "0"]
    old_argv = sys.argv
    sys.argv = argv
    try:
        assert main() == 0
    finally:
        sys.argv = old_argv

    out = capsys.readouterr().out
    assert "⚠️ 검사 불능" in out
    assert "해석하지 못했습니다" in out


def test_리포트_파일이_없으면_main이_검사불능으로_렌더링한다(tmp_path, capsys):
    from render_report import main

    missing = tmp_path / "없다.json"
    argv = ["render_report.py", str(missing), "0"]
    old_argv = sys.argv
    sys.argv = argv
    try:
        assert main() == 0
    finally:
        sys.argv = old_argv

    out = capsys.readouterr().out
    assert "⚠️ 검사 불능" in out
    assert str(missing) in out
