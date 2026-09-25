"""바뀐 파일 목록을 거르는 부분.

실제 저장소에서 한 번 당한 자리다. git 이 한글 경로를 따옴표와 8진수로 감싸 내놓는
바람에 모든 경로가 깨졌는데, 그때 말없이 "검사 대상 없음" 으로 넘겨 위반 문서가 있는
PR 이 초록불로 통과했다. 지역 테스트가 이것을 놓친 이유는 `git diff` 를 거치지 않고
경로를 직접 만들었기 때문이다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_changed import (  # noqa: E402
    EXIT_CONFIG_ERROR,
    EXIT_PASS,
    has_company_folder,
    main_entry,
    parse_args,
    split_listing,
)

EXIT_VIOLATION = 1


def test_전부_깨진_목록은_통과로_답하지_않는다(tmp_path, capsys):
    """검사할 수 없는 상태를 통과라고 답하면 보호가 필요한 순간에 보호가 사라진다."""
    listing = tmp_path / "changed.txt"
    listing.write_text(
        '"sample/docs/\353\260\234\355\221\234/\353\247\250.pptx"\n',
        encoding="utf-8",
    )
    assert main_entry([str(listing)]) == EXIT_CONFIG_ERROR
    assert "실제 파일이 아닙니다" in capsys.readouterr().out


def test_목록이_비어_있으면_통과다(tmp_path, capsys):
    """검사할 것이 없는 것과 검사하지 못한 것은 다르다."""
    listing = tmp_path / "changed.txt"
    listing.write_text("\n  \n", encoding="utf-8")
    assert main_entry([str(listing)]) == EXIT_PASS
    assert '"scoped": 0' in capsys.readouterr().out


def test_있는_것과_없는_것을_가른다(tmp_path):
    real = tmp_path / "있다.md"
    real.write_text("# 제목\n", encoding="utf-8")
    found, missing = split_listing(f"{real}\n{tmp_path / '없다.md'}\n\n")
    assert found == [str(real)]
    assert missing == [str(tmp_path / "없다.md")]


@pytest.mark.skipif(not Path(".git").exists() and not Path("../.git").exists(),
                    reason="git 저장소가 아니다")
def test_git_이_한글_경로를_이스케이프하지_않게_한다(tmp_path):
    """워크플로가 쓰는 그 옵션이 실제로 효과가 있는지 git 에 직접 확인한다.

    이 테스트는 `git diff` 를 실제로 거친다. 경로를 손으로 만들면 이 버그를 놓친다.
    """
    repo = tmp_path / "저장소"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True,
                                    encoding="utf-8", check=True)
    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    (repo / "기준.md").write_text("처음\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "first")
    (repo / "한글 이름.md").write_text("내용\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "second")

    기본 = run("diff", "--name-only", "HEAD~1", "HEAD").stdout
    끈것 = subprocess.run(
        ["git", "-c", "core.quotepath=false", "diff", "--name-only", "HEAD~1", "HEAD"],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout

    assert "\\" in 기본, "git 이 한글 경로를 이스케이프하지 않는다면 이 검사는 무의미하다"
    assert 끈것.strip() == "한글 이름.md"
    # 그리고 이스케이프된 쪽은 실제 파일로 인식되지 않는다 — 이것이 버그의 본체였다
    found, missing = split_listing(기본)
    assert found == [] and missing


# ── 규칙이 다른 저장소에 있을 때 ──────────────────────────────────────────────
#
# 프로젝트 저장소에는 문서만 있고 규칙은 문서 저장소에 있다. 문서에서 위로 올라가도
# 회사 폴더가 없으므로 `--auto` 가 성립하지 않고, `--rules` 와 `--root` 를 받아야 한다.


def test_인자를_가른다():
    assert parse_args(["목록.txt", "--rules", "r", "--root", "t"]) == (
        ("목록.txt", "r", "t"),
        None,
    )
    assert parse_args(["목록.txt"]) == (("목록.txt", None, None), None)

    parsed, error = parse_args(["목록.txt", "--rules"])
    assert parsed is None and "값이 없습니다" in error

    parsed, error = parse_args(["목록.txt", "덤"])
    assert parsed is None and "알 수 없는 인자" in error


def test_규칙만_주고_기준_경로를_빠뜨리면_막는다(tmp_path, capsys):
    """기준 경로가 없으면 관할을 규칙 폴더 기준으로 맞춰 보게 된다.

    그러면 프로젝트 저장소의 문서가 하나도 잡히지 않은 채 통과한다. 위반도 오류도
    아닌 "관할 밖" 으로 위장되는 자리라 아예 막는다.
    """
    listing = tmp_path / "changed.txt"
    listing.write_text("아무거나.md\n", encoding="utf-8")
    assert main_entry([str(listing), "--rules", str(tmp_path)]) == EXIT_CONFIG_ERROR
    assert "--root" in capsys.readouterr().out


def test_기준_경로만_주면_막는다(tmp_path, capsys):
    listing = tmp_path / "changed.txt"
    listing.write_text("아무거나.md\n", encoding="utf-8")
    assert main_entry([str(listing), "--root", str(tmp_path)]) == EXIT_CONFIG_ERROR
    assert "--rules" in capsys.readouterr().out


def test_없는_규칙_폴더는_통과로_답하지_않는다(tmp_path, capsys):
    """회사 이름을 잘못 넘기면 여기로 온다. 조용히 넘기면 검사 없이 병합된다."""
    listing = tmp_path / "changed.txt"
    listing.write_text("아무거나.md\n", encoding="utf-8")
    code = main_entry(
        [str(listing), "--rules", str(tmp_path / "없는회사" / "rules"), "--root", str(tmp_path)]
    )
    assert code == EXIT_CONFIG_ERROR
    assert "규칙 폴더가 없습니다" in capsys.readouterr().out


def _프로젝트_저장소(tmp_path: Path, sample: Path, 이름: str) -> tuple[Path, Path]:
    """문서만 있고 규칙도 템플릿도 없는 저장소를 흉내 낸다."""
    저장소 = tmp_path / "프로젝트저장소"
    문서 = 저장소 / "docs" / "제안서" / 이름
    문서.parent.mkdir(parents=True, exist_ok=True)
    문서.write_bytes((sample / "docs" / "제안서" / 이름).read_bytes())
    목록 = tmp_path / "changed.txt"
    목록.write_text(f"{문서}\n", encoding="utf-8")
    return 목록, 저장소


def test_규칙이_다른_트리에_있어도_검사한다(tmp_path, sample, rules_dir, capsys):
    """관할은 --root 기준으로 맞춰 보고, 템플릿은 규칙 파일 옆에서 찾는다.

    두 기준이 서로 독립이라 문서와 규칙이 다른 저장소에 있어도 성립한다.
    """
    목록, 저장소 = _프로젝트_저장소(tmp_path, sample, "20260921_로그인_제안서.md")
    code = main_entry([str(목록), "--rules", str(rules_dir), "--root", str(저장소)])
    report = json.loads(capsys.readouterr().out)
    assert code == EXIT_PASS
    assert report["summary"]["scoped"] == 1
    assert report["summary"]["violations"] == 0


def test_규칙이_다른_트리에_있어도_위반을_잡는다(tmp_path, sample, rules_dir, capsys):
    """관할 밖으로 조용히 넘기지 않고 위반으로 답해야 한다."""
    목록, 저장소 = _프로젝트_저장소(tmp_path, sample, "제안서최종.md")
    code = main_entry([str(목록), "--rules", str(rules_dir), "--root", str(저장소)])
    report = json.loads(capsys.readouterr().out)
    assert code == EXIT_VIOLATION
    assert report["summary"]["violations"] == 1


def test_기준_경로를_잘못_주면_관할_밖으로_위장된다(tmp_path, sample, rules_dir, capsys):
    """왜 --root 를 강제하는지 보이는 회귀 테스트.

    기준을 엉뚱한 곳으로 주면 상대경로 계산이 실패해 절대경로로 떨어지고, 관할 glob 이
    맞지 않아 위반 문서가 "관할 밖" 으로 통과한다. 이 동작 자체가 남아 있다는 것을
    적어 두어, 위에서 막은 것이 실제 위험을 막고 있음을 보인다.
    """
    목록, _ = _프로젝트_저장소(tmp_path, sample, "제안서최종.md")
    엉뚱한_기준 = tmp_path / "엉뚱"
    엉뚱한_기준.mkdir()
    code = main_entry([str(목록), "--rules", str(rules_dir), "--root", str(엉뚱한_기준)])
    report = json.loads(capsys.readouterr().out)
    assert code == EXIT_PASS
    assert report["summary"]["out_of_scope"] == 1


# ── 회사를 빠뜨린 경우 ────────────────────────────────────────────────────────
#
# 회사를 주지 않는 것은 "이 저장소 안에 회사 폴더가 있다" 는 뜻이다. 문서 저장소는 그렇고
# 프로젝트 저장소는 그렇지 않다. 둘을 가를 단서가 회사 폴더의 유무다.


def test_회사_폴더를_찾는다(tmp_path):
    assert not has_company_folder(tmp_path)

    (tmp_path / "대한물산" / "templates").mkdir(parents=True)
    assert not has_company_folder(tmp_path), "templates 만으로는 회사 폴더가 아니다"

    (tmp_path / "대한물산" / "rules").mkdir()
    assert has_company_folder(tmp_path)


def test_회사도_회사_폴더도_없으면_통과로_답하지_않는다(tmp_path, monkeypatch, capsys):
    """프로젝트 저장소가 company 를 빠뜨리면 여기로 온다.

    회사 폴더가 없으면 어떤 파일이 바뀌었든 검사할 방법이 없다. 그것은 관할 밖이 아니라
    설정이 어긋난 것이다.
    """
    문서 = tmp_path / "docs" / "회의록" / "20260922_주간정기.md"
    문서.parent.mkdir(parents=True)
    문서.write_text("# 회의록\n", encoding="utf-8")
    (tmp_path / "changed.txt").write_text("docs/회의록/20260922_주간정기.md\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    assert main_entry(["changed.txt"]) == EXIT_CONFIG_ERROR
    assert "회사 폴더가 없습니다" in capsys.readouterr().out


def test_회사_폴더가_있으면_스스로_찾아_나선다(tmp_path, monkeypatch, capsys):
    """문서 저장소는 회사를 주지 않는다. 그 경로를 막지 않는다."""
    (tmp_path / "대한물산" / "templates").mkdir(parents=True)
    (tmp_path / "대한물산" / "rules").mkdir()
    (tmp_path / "README.md").write_text("# 안내\n", encoding="utf-8")
    (tmp_path / "changed.txt").write_text("README.md\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    code = main_entry(["changed.txt"])
    report = json.loads(capsys.readouterr().out)
    assert code == EXIT_PASS
    assert report["summary"]["out_of_scope"] == 1
