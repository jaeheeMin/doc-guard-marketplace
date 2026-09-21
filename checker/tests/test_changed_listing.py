"""바뀐 파일 목록을 거르는 부분.

실제 저장소에서 한 번 당한 자리다. git 이 한글 경로를 따옴표와 8진수로 감싸 내놓는
바람에 모든 경로가 깨졌는데, 그때 말없이 "검사 대상 없음" 으로 넘겨 위반 문서가 있는
PR 이 초록불로 통과했다. 지역 테스트가 이것을 놓친 이유는 `git diff` 를 거치지 않고
경로를 직접 만들었기 때문이다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_changed import EXIT_CONFIG_ERROR, EXIT_PASS, main_entry, split_listing  # noqa: E402


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
