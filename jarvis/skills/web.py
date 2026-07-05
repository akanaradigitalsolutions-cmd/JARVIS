"""Minimal web-page fetching: lets Jarvis pull the visible text of a public
URL so it can summarize or analyze real sites, without giving it general
shell/network tool access (Bash/WebFetch/WebSearch stay disallowed — see
jarvis/core/llm.py). Uses only the standard library (urllib + html.parser)
since stripping tags from a page is simple enough not to need a dependency.
"""

from __future__ import annotations

import urllib.request
from html.parser import HTMLParser
from urllib.error import URLError

from jarvis.skills.base import skill

_MAX_DOWNLOAD_BYTES = 2_000_000  # 2 MB cap, plenty for a page's HTML
_TIMEOUT_SECONDS = 15
_USER_AGENT = "Mozilla/5.0 (compatible; JarvisAssistant/1.0; personal use)"

_SKIP_TAGS = {"script", "style", "noscript", "head", "svg", "template"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            stripped = data.strip()
            if stripped:
                self.chunks.append(stripped)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "\n".join(parser.chunks)


@skill(
    name="fetch_url",
    description=(
        "Fetch a public web page over HTTP(S) and return its visible text content "
        "(HTML tags stripped), so it can be summarized, analyzed, or turned into a "
        "report/presentation. Use this whenever the user gives a URL or asks about a "
        "website's content. Only http/https URLs are supported."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The full URL to fetch, e.g. https://example.com"},
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters of extracted text to return (default 8000).",
            },
        },
        "required": ["url"],
    },
)
def fetch_url(url: str, max_chars: int = 8000) -> dict:
    if not url.lower().startswith(("http://", "https://")):
        return {"error": "Only http:// and https:// URLs are supported."}

    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310 - user-directed fetch
            raw = response.read(_MAX_DOWNLOAD_BYTES)
            content_type = response.headers.get_content_type()
            charset = response.headers.get_content_charset() or "utf-8"
    except (URLError, ValueError, TimeoutError) as exc:
        return {"error": f"Couldn't fetch '{url}': {exc}"}

    if content_type and "html" not in content_type and "text" not in content_type:
        return {"error": f"'{url}' returned unsupported content type: {content_type}"}

    text = html_to_text(raw.decode(charset, errors="replace"))
    truncated = len(text) > max_chars
    return {"url": url, "content_type": content_type, "text": text[:max_chars], "truncated": truncated}
