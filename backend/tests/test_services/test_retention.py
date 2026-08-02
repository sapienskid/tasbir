"""Retention sweep tests — expired outputs removed, fresh ones kept."""

import os
import time


class _FakeResult:
    rowcount = 1


class _FakeSession:
    async def execute(self, stmt):
        return _FakeResult()

    async def commit(self):
        pass


class _FakePool:
    def __call__(self):
        return self

    async def __aenter__(self):
        return _FakeSession()

    async def __aexit__(self, *exc):
        return False


def test_sweep_removes_expired_keeps_fresh(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.tasks import retention

    settings = get_settings()
    monkeypatch.setattr(settings, "output_dir", str(tmp_path))
    monkeypatch.setattr(settings, "output_ttl_hours", 1)

    async def fake_factory():
        return _FakePool()

    monkeypatch.setattr(retention, "get_shared_session_factory", fake_factory)

    old = tmp_path / "old-task"
    old.mkdir()
    (old / "x.html").write_text("x")
    past = time.time() - 7200
    os.utime(old, (past, past))

    fresh = tmp_path / "fresh-task"
    fresh.mkdir()
    (fresh / "y.html").write_text("y")

    retention.sweep_expired()

    assert not old.exists()
    assert (fresh / "y.html").exists()
