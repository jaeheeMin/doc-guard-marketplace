"""회사 폴더 찾기와 --auto 모드.

훅과 GitHub Actions 가 둘 다 이 판단을 하므로 한 벌만 두고 양쪽이 쓴다.
"""
from __future__ import annotations

from pathlib import Path

from checker.locate import find_company_root, group_by_company


def _company(base: Path, name: str) -> Path:
    root = base / name
    (root / "templates").mkdir(parents=True)
    (root / "rules").mkdir()
    (root / "docs").mkdir()
    return root


def test_templates_와_rules_를_함께_가진_폴더를_찾는다(tmp_path):
    root = _company(tmp_path, "hanbit")
    doc = root / "docs" / "가" / "나.md"
    doc.parent.mkdir(parents=True)
    doc.touch()
    assert find_company_root(doc) == root.resolve()


def test_둘_중_하나만_있으면_회사_폴더가_아니다(tmp_path):
    """templates 만 있고 rules 가 없으면 대조는 되지만 강제할 규칙이 없다."""
    half = tmp_path / "반쪽"
    (half / "templates").mkdir(parents=True)
    doc = half / "문서.md"
    doc.touch()
    assert find_company_root(doc) is None


def test_회사_폴더_밖이면_없다(tmp_path):
    doc = tmp_path / "README.md"
    doc.touch()
    assert find_company_root(doc) is None


def test_가장_가까운_회사_폴더를_고른다(tmp_path):
    """저장소 루트에도 templates/rules 가 있고 회사 폴더에도 있으면 가까운 쪽이다."""
    outer = _company(tmp_path, "바깥")
    inner = _company(outer, "안쪽")
    doc = inner / "docs" / "문서.md"
    doc.touch()
    assert find_company_root(doc) == inner.resolve()


def test_회사별로_묶는다(tmp_path):
    a = _company(tmp_path, "가회사")
    b = _company(tmp_path, "나회사")
    da, db = a / "docs" / "1.md", b / "docs" / "2.md"
    orphan = tmp_path / "README.md"
    for f in (da, db, orphan):
        f.touch()

    grouped, orphans = group_by_company([da, db, orphan])
    assert set(grouped) == {a.resolve(), b.resolve()}
    assert grouped[a.resolve()] == [da]
    assert orphans == [orphan]
