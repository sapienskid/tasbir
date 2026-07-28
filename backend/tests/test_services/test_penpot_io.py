"""Tests for v3 services: Penpot I/O and DOM Extractor."""

import json
from pathlib import Path
from app.services.penpot_io import PenpotWriter, PenpotReader, PenpotShape, Fill, TextContent, DEFAULT_TOKEN_VALUES, inject_tokens_into_html


def test_penpot_writer_builds_zip(tmp_path: Path):
    writer = PenpotWriter(file_name="Test File")
    root_shape = PenpotShape(
        name="test-board",
        shape_type="frame",
        width=1080,
        height=1080,
        fills=[Fill(color="#0f172a")],
    )
    text_shape = PenpotShape(
        name="Headline",
        shape_type="text",
        width=500,
        height=50,
        text_content=TextContent(text="Hello Penpot", font_size=32),
    )
    root_shape.children.append(text_shape)
    
    writer.add_board("instagram-square", 1080, 1080, root_shape)
    zip_bytes = writer.build()
    
    assert len(zip_bytes) > 0
    test_file = tmp_path / "test.penpot"
    test_file.write_bytes(zip_bytes)
    
    # Read back with PenpotReader
    reader = PenpotReader(test_file)
    pages = reader.list_pages()
    assert "instagram-square" in pages


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
