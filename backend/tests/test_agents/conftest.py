"""Agent-node test fixtures — redirect file output away from the real data dir."""

import pytest


@pytest.fixture(autouse=True)
def _tmp_output_dir(tmp_path, monkeypatch):
    """Point the renderer at a throwaway dir so graph runs never write to
    data/output/ (the previous culprit was data/output/test-graph)."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "output_dir", str(tmp_path))
    return str(tmp_path)
