"""Tests for Penpot I/O: token reading and HTML injection."""

from pathlib import Path
from app.services.penpot_io import PenpotReader, DEFAULT_TOKEN_VALUES, inject_tokens_into_html


def test_penpot_reader_default_tokens(tmp_path: Path):
    non_existent = tmp_path / "non_existent.penpot"
    reader = PenpotReader(non_existent)
    tokens = reader.get_tokens()
    assert "--color-bg" in tokens
    assert tokens["--color-bg"] == "#0f172a"


def test_inject_tokens_into_html():
    html = "<html><head></head><body><h1>Hi</h1></body></html>"
    tokens = {"--color-bg": "#0f172a"}
    res = inject_tokens_into_html(html, tokens)
    assert "--color-bg: #0f172a;" in res
    assert "<style>" in res
