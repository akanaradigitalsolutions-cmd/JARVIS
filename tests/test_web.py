from jarvis.skills.web import fetch_url, html_to_text


def test_html_to_text_strips_tags_and_script_style():
    html = """
    <html><head><style>body { color: red; }</style></head>
    <body>
        <script>console.log('nope')</script>
        <h1>Welcome</h1>
        <p>Hello <b>world</b>.</p>
    </body></html>
    """
    text = html_to_text(html)
    assert "Welcome" in text
    assert "Hello" in text
    assert "world" in text
    assert "console.log" not in text
    assert "color: red" not in text


def test_fetch_url_rejects_non_http_schemes():
    result = fetch_url("file:///etc/passwd")
    assert "error" in result


def test_fetch_url_rejects_ftp_scheme():
    result = fetch_url("ftp://example.com/file.txt")
    assert "error" in result
