"""Web search tool."""

from __future__ import annotations

import html
import re
from urllib.parse import quote_plus

import requests


def web_search(query: str) -> str:
    """Search DuckDuckGo and return a verified top result or an explicit error."""
    query = query.strip()
    if not query:
        return "TOOL_ERROR: A search query is required."

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"TOOL_ERROR: Web search failed because {exc}."

    match = re.search(
        r'<a[^>]*class="result__a"[^>]*href="(?P<link>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?result__snippet">(?P<snippet>.*?)</a>',
        response.text,
        re.S,
    )
    if not match:
        return f"TOOL_ERROR: No web results found for '{query}'."

    title = html.unescape(re.sub(r"<.*?>", "", match.group("title"))).strip()
    snippet = html.unescape(re.sub(r"<.*?>", "", match.group("snippet"))).strip()
    link = html.unescape(match.group("link")).strip()
    if not title or not link:
        return f"TOOL_ERROR: The search response for '{query}' was incomplete."
    return f"TOOL_OK: {title}: {snippet} ({link})"
