"""설치된 플러그인 레이아웃에서 훅이 실제로 동작하는지 확인한다.

`test_shims.py` 는 이 저장소 안에서 훅 스크립트를 직접 부른다. 그것만으로는 #12 가
잡은 결함 — 마켓플레이스로 설치된 캐시에는 `plugins/doc-guard/` 만 들어가고
`checker/` 나 `pyproject.toml` 은 따라오지 않는다 — 를 재현하지 못한다. 저장소
안에서 돌리면 옛 코드도 `sys.path` 트릭으로 `checker` 를 찾아버려 통과해 버린다.

그래서 여기서는 `plugins/doc-guard/` 를 저장소 **바깥** 임시 폴더로 복사해 설치본을
흉내 내고, 그 전제(엔진이 따라오지 않았다)를 스스로 확인한 뒤 그 복사본의 훅을
서브프로세스로 부른다.

엔진은 실제로 GitHub 에서 받지 않는다. `DOC_GUARD_ENGINE` 을 이 워크트리로 지정해
`uvx` 가 로컬 소스로 설치하게 한다 — 네트워크 없이 빠르고, uv 캐시도 그대로 쓴다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SRC = ENGINE_ROOT / "plugins" / "doc-guard"

pytestmark = pytest.mark.skipif(
    shutil.which("uv") is None, reason="uv 가 없으면 엔진을 받아 실행할 수 없다"
)

PROPOSAL_RULES = """템플릿: ../templates/제안서.md
관할: "docs/제안서/**"

규칙:
  - 종류: required_sections
"""

PROPOSAL_TEMPLATE = "# 제안서\n\n## 개요\n\n## 일정\n"

BROKEN_RULES = "이것은: [부서진, yaml\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture(scope="module")
def installed_hook(tmp_path_factory) -> Path:
    """`plugins/doc-guard/` 를 저장소 밖으로 복사해 설치본을 흉내 낸다."""
    dest_parent = tmp_path_factory.mktemp("doc-guard-installed")
    dest = dest_parent / "doc-guard"
    shutil.copytree(PLUGIN_SRC, dest)

    # 설치본의 전제를 스스로 확인한다 — 엔진(checker)도 pyproject.toml 도 따라오지
    # 않았다. 이것이 어긋나면 이 테스트는 옛 결함을 재현하지 못하고 통과해 버린다.
    assert not (dest / "checker").exists()
    assert not (dest_parent / "pyproject.toml").exists()
    assert not (dest_parent.parent / "pyproject.toml").exists()

    return dest / "hooks" / "pre_write_guard.py"


@pytest.fixture()
def company(tmp_path) -> Path:
    """`templates/` 와 `rules/` 와 `docs/` 를 든 가짜 고객사 폴더."""
    root = tmp_path / "회사"
    _write(root / "templates" / "제안서.md", PROPOSAL_TEMPLATE)
    _write(root / "rules" / "제안서.yaml", PROPOSAL_RULES)
    (root / "docs" / "제안서").mkdir(parents=True)
    return root


def run_hook(hook: Path, payload: dict, engine: str) -> tuple[int, dict | None]:
    env = {**os.environ, "DOC_GUARD_ENGINE": engine}
    done = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=180,
    )
    if not done.stdout.strip():
        return done.returncode, None
    return done.returncode, json.loads(done.stdout)


def decision(out: dict | None) -> str | None:
    if out is None:
        return None
    return out["hookSpecificOutput"]["permissionDecision"]


def _write_payload(path: Path, content: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": content}}


def test_설치본에서도_위반_문서를_막는다(installed_hook, company):
    target = company / "docs" / "제안서" / "위반.md"
    code, out = run_hook(
        installed_hook, _write_payload(target, "# 제안서\n\n## 개요\n"), str(ENGINE_ROOT)
    )
    assert decision(out) == "deny"
    assert "일정" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_설치본에서도_규칙에_맞는_문서는_통과시킨다(installed_hook, company):
    target = company / "docs" / "제안서" / "통과.md"
    code, out = run_hook(
        installed_hook, _write_payload(target, PROPOSAL_TEMPLATE), str(ENGINE_ROOT)
    )
    assert code == 0 and out is None


def test_회사_폴더_밖의_파일은_관할_밖이라_통과시킨다(installed_hook, tmp_path):
    outside = tmp_path / "아무데나.md"
    code, out = run_hook(installed_hook, _write_payload(outside, "아무거나"), str(ENGINE_ROOT))
    assert code == 0 and out is None


def test_텍스트가_아닌_확장자는_관여하지_않는다(installed_hook, company):
    target = company / "docs" / "제안서" / "파일.docx"
    code, out = run_hook(installed_hook, _write_payload(target, "아무거나"), str(ENGINE_ROOT))
    assert code == 0 and out is None


def test_엔진을_받을_수_없으면_통과가_아니라_거절한다(installed_hook, company, tmp_path):
    """CLAUDE.md 원칙 7: '검사를 못 했다' 를 '통과' 로 뭉개지 않는다."""
    target = company / "docs" / "제안서" / "아무.md"
    missing_engine = str(tmp_path / "존재하지-않는-경로")
    code, out = run_hook(installed_hook, _write_payload(target, "아무거나"), missing_engine)
    assert decision(out) == "deny"
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert "확인되지 않는 상태로 통과시키지 않습니다" in reason


def test_규칙_설정_오류면_거절하고_담당자에게_알리라고_한다(installed_hook, tmp_path):
    root = tmp_path / "회사2"
    _write(root / "templates" / "제안서.md", PROPOSAL_TEMPLATE)
    _write(root / "rules" / "제안서.yaml", BROKEN_RULES)
    (root / "docs" / "제안서").mkdir(parents=True)
    target = root / "docs" / "제안서" / "아무.md"

    code, out = run_hook(installed_hook, _write_payload(target, "아무거나"), str(ENGINE_ROOT))
    assert decision(out) == "deny"
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert "문서의 문제가 아닙니다" in reason

def test_입력을_해석하지_못하면_통과시키지_않는다(installed_hook):
    # 입력을 못 읽으면 소관인지조차 모른다. 모른다는 것을 통과로 바꾸지 않는다(원칙 7).
    done = subprocess.run(
        [sys.executable, str(installed_hook)],
        input='{"tool_name": "Write", 깨진', capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )
    assert done.returncode == 0
    assert decision(json.loads(done.stdout)) == "deny"
