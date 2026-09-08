from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--run-gpu", action="store_true", help="실제 GPU 테스트 실행")
    parser.addoption("--run-performance", action="store_true", help="장시간 성능 테스트 실행")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skips = {
        "gpu": not config.getoption("--run-gpu"),
        "performance": not config.getoption("--run-performance"),
    }
    for item in items:
        for marker, disabled in skips.items():
            if disabled and marker in item.keywords:
                item.add_marker(pytest.mark.skip(reason=f"--run-{marker} 옵션이 필요합니다"))


@pytest.fixture
def performance_artifact_dir(tmp_path: Path) -> Path:
    configured = os.environ.get("VIDEEP_PERFORMANCE_ARTIFACT_DIR")
    path = Path(configured) if configured else tmp_path / "performance"
    path.mkdir(parents=True, exist_ok=True)
    return path
