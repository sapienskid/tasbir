"""HTML sanitizer tests."""


from app.services.sanitizer import sanitize_html


def test_strict_removes_script_tags():
    out = sanitize_html("<p>hi</p><script>alert(1)</script>", mode="strict")
    assert "script" not in out
    assert "<p>hi</p>" in out


def test_strict_removes_iframe_and_object():
    html = "<div><iframe src='https://evil'></iframe><object data='x'></object></div>"
    out = sanitize_html(html, mode="strict")
    assert "iframe" not in out
    assert "object" not in out


def test_strict_strips_event_handlers():
    out = sanitize_html('<button onclick="alert(1)">x</button>', mode="strict")
    assert "onclick" not in out


def test_strict_strips_javascript_urls():
    out = sanitize_html('<a href="javascript:alert(1)">x</a>', mode="strict")
    assert "javascript:" not in out


def test_strict_strips_link_tags():
    out = sanitize_html("<head><link href='https://evil/x' rel='stylesheet'></head>", mode="strict")
    assert "<link" not in out


def test_strict_keeps_body_after_void_drops():
    # Dropped VOID tags (<meta>/<link>) must not swallow the rest of the doc.
    html = (
        "<!DOCTYPE html><html><head>"
        '<meta charset="UTF-8"><meta name="viewport">'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/x">'
        "<title>t</title></head>"
        "<body><div>KEEP ME</div></body></html>"
    )
    out = sanitize_html(html, mode="strict")
    assert "<body" in out
    assert "KEEP ME" in out
    assert "<link" not in out


def test_strict_keeps_style_block():
    html = "<style>.a{color:red}</style><div>ok</div>"
    out = sanitize_html(html, mode="strict")
    assert "<style>" in out
    assert ".a{color:red}" in out


def test_strict_scrubs_css_javascript_url():
    out = sanitize_html("<style>.a{background:url(javascript:alert(1))}</style>", mode="strict")
    assert "javascript:" not in out


def test_preserve_system_keeps_trusted_cdn_script():
    html = '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>'
    out = sanitize_html(html, mode="preserve_system")
    assert "cdn.jsdelivr.net" in out


def test_preserve_system_drops_arbitrary_script():
    out = sanitize_html('<script src="https://evil.example/x.js"></script>', mode="preserve_system")
    assert "evil.example" not in out


def test_preserve_system_drops_inline_script():
    out = sanitize_html("<script>alert(1)</script>", mode="preserve_system")
    assert "script" not in out


def test_preserve_system_keeps_font_link():
    html = '<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">'
    out = sanitize_html(html, mode="preserve_system")
    assert "fonts.googleapis.com" in out


def test_malformed_input_is_neutralized():
    out = sanitize_html("<script>alert(1)</script", mode="strict")
    assert "script" not in out


def test_empty_html_returns_empty():
    assert sanitize_html("", mode="strict") == ""
