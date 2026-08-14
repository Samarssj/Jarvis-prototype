"""Web search tool."""

from __future__ import annotations

import html
import re
from urllib.parse import quote_plus

import requests


def web_search(query: str) -> str:
    """Search the web and summarize the top DuckDuckGo result."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        return f"Web search failed with HTTP {response.status_code}."

    match = re.search(
        r'<a[^>]*class="result__a"[^>]*href="(?P<link>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?result__snippet">(?P<snippet>.*?)</a>',
        response.text,
        re.S,
    )
    if not match:
        return f"No results found for '{query}'."

    title = html.unescape(re.sub("<.*?>", "", match.group("title"))).strip()
    snippet = html.unescape(re.sub("<.*?>", "", match.group("snippet"))).strip()
    link = html.unescape(match.group("link")).strip()
    return f"{title}: {snippet} ({link})"
