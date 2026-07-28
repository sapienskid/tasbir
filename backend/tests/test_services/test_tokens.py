"""Tests for design token loading and HTML injection."""

from pathlib import Path

from app.services.tokens import load_tokens, DEFAULT_TOKEN_VALUES, inject_tokens_into_html


def test_load_tokens_defaults(tmp_path: Path):
    tokens = load_tokens(tmp_path / "non_existent.yaml")
    assert "--color-bg" in tokens
    assert tokens["--color-bg"] == "#0f172a"


def test_load_tokens_from_file(tmp_path: Path):
    tf = tmp_path / "tokens.yaml"
    tf.write_text("--color-bg: '#ff0000'")
    tokens = load_tokens(tf)
    assert tokens["--color-bg"] == "#ff0000"


def test_inject_tokens_into_html():
    html = "<html><head></head><body><h1>Hi</h1></body></html>"
    tokens = {"--color-bg": "#0f172a"}
    res = inject_tokens_into_html(html, tokens)
    assert "--color-bg: #0f172a;" in res
    assert "<style>" in res
