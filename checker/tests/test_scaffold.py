"""`/scaffold` 가 부르는 `scaffold.py` 를 검증한다.

`scaffold.py` 는 `checker` 패키지 밖, `plugins/harness/skills/scaffold/` 에
산다 — 플러그인 훅과 마찬가지로 엔진과는 별도로 설치되는 자리이기 때문이다.
그래서 평범한 `import` 대신 파일 경로로 직접 불러온다.

여기서 만든 구조가 검사 엔진과 실제로 맞물리는지까지 함께 확인한다. 구조만
맞고 검사기가 그 구조를 읽지 못하면 스캐폴딩은 겉모습만 흉내 낸 것이다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from checker.cli import EXIT_CONFIG_ERROR, EXIT_PASS, EXIT_VIOLATION, main

SCAFFOLD_PY = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "harness"
    / "skills"
    / "scaffold"
    / "scaffold.py"
)


def _load_scaffold_module():
    spec = importlib.util.spec_from_file_location("doc_guard_scaffold", SCAFFOLD_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


scaffold_mod = _load_scaffold_module()
scaffold = scaffold_mod.scaffold

EXPECTED_FILES = {
    "CLAUDE.md",
    "docs/ssot/PRD.md",
    "templates/README.md",
    "templates/harness/audit-change.md",
    "templates/harness/audit-ledger.md",
    "rules/README.md",
    "rules/ssot.yaml",
    "rules/audit-changes.yaml",
    "rules/audit-ledger.yaml",
    "conventions/README.md",
    "audit/README.md",
    "audit/changes/.gitkeep",
    "audit/ledger/.gitkeep",
    "env/README.md",
    ".github/workflows/doc-guard.yml",
}


def test_예상하는_파일을_모두_만들고_치환한다(tmp_path: Path):
    result = scaffold(tmp_path, "블루워드", "테스트프로젝트", False)

    assert set(result["created"]) == EXPECTED_FILES
    assert result["skipped"] == []
    assert result["dry_run"] is False

    # dot-github 는 실제로 만들 때 .github 로 바뀐다.
    assert (tmp_path / ".github" / "workflows" / "doc-guard.yml").is_file()
    assert not (tmp_path / "dot-github").exists()

    for rel in EXPECTED_FILES:
        path = tmp_path / rel
        assert path.is_file(), f"{rel} 이 만들어지지 않았다"
        text = path.read_text(encoding="utf-8")
        assert "{{" not in text, f"{rel} 에 치환되지 않은 자리표시자가 남아 있다"

    claude_md = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "블루워드 테스트프로젝트" in claude_md
    prd = (tmp_path / "docs" / "ssot" / "PRD.md").read_text(encoding="utf-8")
    assert "테스트프로젝트 PRD" in prd


def test_두번째_실행은_아무것도_만들지_않고_기존_파일을_보존한다(tmp_path: Path):
    first = scaffold(tmp_path, "고객사A", "프로젝트A", False)
    assert first["created"]

    # 사람이 이미 손댄 것처럼 하나를 고쳐 둔다.
    claude_md = tmp_path / "CLAUDE.md"
    edited = "# 사람이 직접 고친 내용\n"
    claude_md.write_text(edited, encoding="utf-8")

    second = scaffold(tmp_path, "고객사B", "프로젝트B", False)

    assert second["created"] == []
    assert set(second["skipped"]) == EXPECTED_FILES
    # 덮어쓰지 않았어야 한다.
    assert claude_md.read_text(encoding="utf-8") == edited


def test_dry_run은_아무것도_만들지_않는다(tmp_path: Path):
    result = scaffold(tmp_path, "고객사", "프로젝트", True)

    assert set(result["created"]) == EXPECTED_FILES
    assert result["dry_run"] is True
    # 폴더 자체가 생기지 않아야 한다.
    assert list(tmp_path.iterdir()) == []


# --- 검사 엔진과의 통합 -----------------------------------------------------

def _run_auto(capsys, *paths: Path) -> tuple[int, dict]:
    import json

    code = main(["--auto", *[str(p) for p in paths]])
    return code, json.loads(capsys.readouterr().out)


def test_스캐폴딩한_구조를_검사기가_그대로_읽는다(tmp_path: Path, capsys):
    scaffold(tmp_path, "고객사", "프로젝트", False)
    prd = tmp_path / "docs" / "ssot" / "PRD.md"

    code, out = _run_auto(capsys, prd)
    assert code == EXIT_PASS
    assert out["summary"]["scoped"] == 1
    assert out["summary"]["passed"] == 1
    assert out["summary"]["violations"] == 0

    # 이름을 바꾼 버전은 rules/ssot.yaml 의 filename 규칙을 어긴다.
    prd_v2 = prd.parent / "PRD_v2.md"
    prd_v2.write_text(prd.read_text(encoding="utf-8"), encoding="utf-8")

    code, out = _run_auto(capsys, prd_v2)
    assert code == EXIT_VIOLATION
    assert out["summary"]["violations"] == 1
    assert out["files"][0]["violations"][0]["rule"] == "filename"

    # audit/README.md 처럼 어떤 관할에도 안 걸리는 파일은 관할 밖으로 조용히
    # 지나가야 한다. 죽지 않는다.
    audit_readme = tmp_path / "audit" / "README.md"
    code, out = _run_auto(capsys, audit_readme)
    assert code == EXIT_PASS
    assert out["summary"]["out_of_scope"] == 1
    assert out["summary"]["scoped"] == 0
