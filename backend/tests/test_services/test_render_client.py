"""Render-service client tests.

The Playwright service is not available in unit tests, so these cover the two
properties that matter for correctness there: the client FAILS OPEN, and it
fails open *fast* (a dead service must not burn the full render budget on every
pipeline call).
"""

import time

import pytest

from app.services import dom_extractor


def test_timeout_splits_connect_from_render():
    """Connect is short, render is long.

    A 45s connect budget meant every overflow check against a down service cost
    45s; in a suite with dozens of such calls that is minutes of dead time.
    """
    assert dom_extractor.TIMEOUT.connect == dom_extractor.CONNECT_TIMEOUT
    assert dom_extractor.CONNECT_TIMEOUT < 5.0
    # The render budget is deliberately still generous.
    assert dom_extractor.TIMEOUT.read >= 30.0
    assert dom_extractor.TIMEOUT.write >= 30.0


def test_renderer_url_comes_from_settings():
    """No hardcoded Docker hostname — the URL is configuration.

    Asserts the *invariant* (whatever Settings says is what we call) rather than
    a literal, so it stays valid regardless of the URL a test injects.
    """
    from app.config import get_settings

    assert dom_extractor._renderer_url() == get_settings().renderer_url
    # The old module-level fallback is gone: nothing can silently ignore config.
    assert not hasattr(dom_extractor, "PLAYWRIGHT_SERVICE_URL")


async def test_detect_overflow_fails_open_fast():
    """An unreachable service yields no issues, quickly."""
    start = time.monotonic()
    issues = await dom_extractor.detect_overflow("<html><body>hi</body></html>", 1080, 1080)
    elapsed = time.monotonic() - start
    assert issues == []
    # Generous bound: the point is it is ~instant, not the 45s render budget.
    assert elapsed < 10.0, f"took {elapsed:.1f}s — should fail open fast"


async def test_render_to_png_returns_none_when_unreachable():
    assert await dom_extractor.render_to_png("<html></html>", 100, 100) is None


async def test_extract_dom_returns_none_when_unreachable():
    assert await dom_extractor.extract_dom_tree("<html></html>", 100, 100) is None


@pytest.mark.parametrize("corrupt", ["", "not json", '{"no": "dom"}'])
async def test_detect_overflow_tolerates_bad_responses(monkeypatch, corrupt):
    """A malformed payload from the service is not a crash."""

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            if corrupt == "not json":
                raise ValueError("not json")
            import json

            return json.loads(corrupt) if corrupt else {}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *a, **kw):
            return FakeResponse()

    monkeypatch.setattr(dom_extractor.httpx, "AsyncClient", FakeClient)
    assert await dom_extractor.detect_overflow("<html></html>", 1080, 1080) == []
