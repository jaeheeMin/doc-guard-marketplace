"""CLI 계약을 단언한다.

훅과 Actions 가 둘 다 이 계약만 붙들고 있으므로 계약이 곧 인터페이스다. 눈으로 확인하는
것으로는 안 되고 테스트가 지켜야 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from checker.cli import EXIT_CONFIG_ERROR, EXIT_PASS, EXIT_VIOLATION, main


def invoke(capsys, rules: Path, *paths: Path, root: Path | None = None) -> tuple[int, dict]:
    argv = ["--rules", str(rules)]
    if root is not None:
        argv += ["--root", str(root)]
    argv += [str(p) for p in paths]
    code = main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_통과는_0(capsys, rules_dir, sample):
    code, out = invoke(capsys, rules_dir, sample / "docs/제안서/20260921_로그인_제안서.md")
    assert code == EXIT_PASS
    assert out["summary"]["violations"] == 0


def test_위반은_1(capsys, rules_dir, sample):
    code, out = invoke(capsys, rules_dir, sample / "docs/제안서/제안서최종.md")
    assert code == EXIT_VIOLATION
    assert out["summary"]["violations"] == 1


def test_전부_관할_밖이어도_0(capsys, rules_dir, sample):
    """README 만 고친 PR 이 CI 를 깨뜨리면 안 된다.

    '검사한 것이 없다' 는 사실은 종료코드가 아니라 리포트의 scoped 가 싣는다.
    """
    code, out = invoke(capsys, rules_dir, sample / "README.md")
    assert code == EXIT_PASS
    assert out["summary"]["scoped"] == 0
    assert out["summary"]["out_of_scope"] == 1


def test_인자가_없어도_0(capsys, rules_dir):
    code, out = invoke(capsys, rules_dir)
    assert code == EXIT_PASS
    assert out["summary"] == {"scoped": 0, "passed": 0, "violations": 0, "out_of_scope": 0}


def test_리포트_모양(capsys, rules_dir, sample):
    _, out = invoke(capsys, rules_dir, sample / "docs/제안서/제안서최종.md")
    assert set(out) == {"summary", "files"}
    assert set(out["summary"]) == {"scoped", "passed", "violations", "out_of_scope"}
    f = out["files"][0]
    assert set(f) == {"file", "type", "template", "status", "violations"}
    assert set(f["violations"][0]) == {"rule", "expected", "actual", "message"}


def test_파일_하나든_폴더든_같은_결과(capsys, rules_dir, sample):
    """완료 조건 중 하나.

    규칙을 한 파일에 몰아 쓰든 유형마다 쪼개든 엔진이 강제하지 않는다. 이 선택은 규칙을
    쓰는 사람의 몫이어야 하므로, 양쪽이 같은 결과를 내는지 지켜야 한다.
    """
    target = sample / "docs/제안서/제안서최종.md"
    _, by_dir = invoke(capsys, rules_dir, target)
    _, by_file = invoke(capsys, rules_dir / "제안서.yaml", target)
    assert by_dir == by_file


def test_한_파일에_유형_여럿을_담아도_같다(capsys, tmp_path, rules_dir, sample):
    merged = tmp_path / "rules"
    merged.mkdir()
    import yaml

    types = {}
    for f in sorted(rules_dir.glob("*.yaml")):
        body = yaml.safe_load(f.read_text(encoding="utf-8"))
        body["템플릿"] = str((rules_dir / body["템플릿"]).resolve())
        types[f.stem] = body
    (merged / "전체.yaml").write_text(
        yaml.safe_dump({"유형들": types}, allow_unicode=True), encoding="utf-8"
    )

    target = sample / "docs/개발사양서/헤더다름.xlsx"
    _, split = invoke(capsys, rules_dir, target)
    _, single = invoke(capsys, merged, target, root=sample)
    assert [f["status"] for f in split["files"]] == [f["status"] for f in single["files"]]
    assert [v["rule"] for v in split["files"][0]["violations"]] == [
        v["rule"] for v in single["files"][0]["violations"]
    ]


# --- 설정 오류 -------------------------------------------------------------

def _rules(tmp_path: Path, body: str, template: str = "제안서.md") -> Path:
    d = tmp_path / "회사" / "rules"
    d.mkdir(parents=True)
    (tmp_path / "회사" / "templates").mkdir(exist_ok=True)
    (tmp_path / "회사" / "templates" / template).write_text("# 제목\n\n## 개요\n", encoding="utf-8")
    (d / "규칙.yaml").write_text(body, encoding="utf-8")
    return d


def test_모르는_규칙_종류는_설정오류(capsys, tmp_path):
    rules = _rules(tmp_path, "템플릿: ../templates/제안서.md\n관할: 'docs/**'\n규칙:\n  - 종류: 없는규칙\n")
    code, out = invoke(capsys, rules)
    assert code == EXIT_CONFIG_ERROR
    assert out["status"] == "config_error"
    assert "없는규칙" in out["message"]


def test_템플릿이_없으면_설정오류(capsys, tmp_path):
    rules = _rules(tmp_path, "템플릿: ../templates/없다.md\n관할: 'docs/**'\n규칙: []\n")
    code, out = invoke(capsys, rules)
    assert code == EXIT_CONFIG_ERROR
    assert "템플릿" in out["message"]


def test_관할이_겹치면_로드_시점에_설정오류(capsys, tmp_path):
    """값싸게 판정되는 겹침은 대상 파일과 무관하게 로드할 때 잡는다."""
    body = (
        "유형들:\n"
        "  가:\n    템플릿: ../templates/제안서.md\n    관할: 'docs/**'\n    규칙: []\n"
        "  나:\n    템플릿: ../templates/제안서.md\n    관할: 'docs/**'\n    규칙: []\n"
    )
    rules = _rules(tmp_path, body)
    code, out = invoke(capsys, rules)
    assert code == EXIT_CONFIG_ERROR
    assert "관할" in out["message"]


def test_실제_파일이_두_유형에_걸리면_설정오류(capsys, tmp_path):
    """로드 시점 정적 검사가 놓친 겹침은 검사 시점에 잡는다.

    추측해서 한쪽을 고르지 않는다. 이 제품의 출력은 '이 템플릿을 쓰세요' 라서, 조용히
    고른 것이 틀리면 사람을 엉뚱한 템플릿으로 안내한다.
    """
    body = (
        "유형들:\n"
        "  가:\n    템플릿: ../templates/제안서.md\n    관할: 'docs/**/*.md'\n    규칙: []\n"
        "  나:\n    템플릿: ../templates/제안서.md\n    관할: 'docs/보고/*.md'\n    규칙: []\n"
    )
    rules = _rules(tmp_path, body)
    doc = tmp_path / "회사" / "docs" / "보고" / "가.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# 가\n", encoding="utf-8")
    code, out = invoke(capsys, rules, doc)
    assert code == EXIT_CONFIG_ERROR
    assert "여러 유형" in out["message"]


def test_깨진_YAML_은_설정오류(capsys, tmp_path):
    rules = _rules(tmp_path, "템플릿: [\n관할: 'docs/**'\n")
    code, out = invoke(capsys, rules)
    assert code == EXIT_CONFIG_ERROR
