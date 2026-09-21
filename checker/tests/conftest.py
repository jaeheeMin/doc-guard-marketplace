from __future__ import annotations

from pathlib import Path

import pytest

from checker.tests import make_fixtures


@pytest.fixture(scope="session")
def sample(tmp_path_factory) -> Path:
    """실제 문서 저장소와 같은 모양의 가짜 고객사 폴더를 만들어 돌려준다."""
    make_fixtures.main()
    return make_fixtures.ROOT


@pytest.fixture(scope="session")
def rules_dir(sample: Path) -> Path:
    return sample / "rules"
