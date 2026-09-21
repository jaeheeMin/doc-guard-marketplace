"""규칙 종류마다 통과와 의도적 위반과 경계를 짝으로 확인한다.

통과만 확인하면 검사기가 아무것도 하지 않아도 초록불이 된다. 거절하는 능력은 거절당해야 할
문서를 넣어 봐야 증명된다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from checker.engine import OUT_OF_SCOPE, PASS, VIOLATION, check
from checker.loader import load


def run(rules_dir: Path, sample: Path, *names: str) -> dict:
    targets = [(sample / n, n.replace("\\", "/")) for n in names]
    return check(targets, load(rules_dir))


def statuses(report: dict) -> list[str]:
    return [f["status"] for f in report["files"]]


def rules_hit(report: dict) -> set[str]:
    return {v["rule"] for f in report["files"] for v in f["violations"]}


# --- filename -------------------------------------------------------------

def test_filename_통과(rules_dir, sample):
    r = run(rules_dir, sample, "docs/제안서/20260921_로그인_제안서.md")
    assert statuses(r) == [PASS]


def test_filename_위반(rules_dir, sample):
    r = run(rules_dir, sample, "docs/제안서/제안서최종.md")
    assert statuses(r) == [VIOLATION]
    assert "filename" in rules_hit(r)


# --- required_sections ----------------------------------------------------

def test_필수_절이_빠지면_위반(rules_dir, sample):
    r = run(rules_dir, sample, "docs/제안서/20260921_결제_제안서.md")
    assert statuses(r) == [VIOLATION]
    missing = [v for f in r["files"] for v in f["violations"] if v["rule"] == "required_sections"]
    assert [v["expected"] for v in missing] == ["일정"]


def test_선택_절은_빠져도_통과(rules_dir, sample):
    """경계 사례. 템플릿에 있지만 '선택_섹션' 으로 지정한 절은 없어도 된다."""
    r = run(rules_dir, sample, "docs/제안서/20260921_배송_제안서.md")
    assert statuses(r) == [PASS]


def test_문서_제목은_비교하지_않는다(rules_dir, sample):
    """1수준 제목은 문서 자신의 이름이라 템플릿과 다른 것이 정상이다."""
    r = run(rules_dir, sample, "docs/제안서/20260921_로그인_제안서.md")
    assert r["files"][0]["violations"] == []


# --- required_sheets / table_headers --------------------------------------

def test_엑셀_통과(rules_dir, sample):
    r = run(rules_dir, sample, "docs/개발사양서/통과.xlsx")
    assert statuses(r) == [PASS]


def test_시트가_없으면_위반(rules_dir, sample):
    r = run(rules_dir, sample, "docs/개발사양서/시트없음.xlsx")
    assert statuses(r) == [VIOLATION]
    assert "required_sheets" in rules_hit(r)


def test_헤더가_다르면_위반(rules_dir, sample):
    r = run(rules_dir, sample, "docs/개발사양서/헤더다름.xlsx")
    assert statuses(r) == [VIOLATION]
    assert "table_headers" in rules_hit(r)


def test_시트가_더_있는_것은_통과(rules_dir, sample):
    """경계 사례. 화면 레이아웃 시트처럼 프로그램마다 붙는 시트가 있어도 된다.

    실제 템플릿에서 빈 양식은 7시트, 채운 산출물은 10시트였다. 시트 집합이 같을 것을
    요구하면 정상 산출물이 전부 걸린다.
    """
    r = run(rules_dir, sample, "docs/개발사양서/시트추가.xlsx")
    assert statuses(r) == [PASS]


# --- slide_layouts --------------------------------------------------------

def test_공식_템플릿에서_시작한_자료는_통과(rules_dir, sample):
    r = run(rules_dir, sample, "docs/발표자료/통과.pptx")
    assert statuses(r) == [PASS]


def test_다른_템플릿에서_만든_자료는_위반(rules_dir, sample):
    r = run(rules_dir, sample, "docs/발표자료/다른템플릿.pptx")
    assert statuses(r) == [VIOLATION]
    assert "slide_layouts" in rules_hit(r)


def test_한_장짜리도_템플릿_안쪽이면_통과(rules_dir, sample):
    r = run(rules_dir, sample, "docs/발표자료/한장만.pptx")
    assert statuses(r) == [PASS]


# --- 관할 -----------------------------------------------------------------

def test_템플릿이_없는_파일은_검사하지_않는다(rules_dir, sample):
    """대조할 템플릿이 없으면 할 말이 없다. '통과' 라고 답하면 거짓말이다."""
    r = run(rules_dir, sample, "README.md")
    assert statuses(r) == [OUT_OF_SCOPE]
    assert r["files"][0]["type"] is None
    assert r["summary"]["scoped"] == 0


def test_통과해도_유형과_템플릿을_싣는다(rules_dir, sample):
    """문서를 올리는 사람은 위반을 알기 전에 '뭘 보고 쓰지' 부터 궁금하다."""
    r = run(rules_dir, sample, "docs/제안서/20260921_로그인_제안서.md")
    f = r["files"][0]
    assert f["type"] == "제안서"
    assert f["template"].endswith("제안서.md")
