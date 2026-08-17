"""Browser and YouTube control tools."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


def _open_url(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=True)
    elif sys.platform.startswith("win"):
        os.startfile(url)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", url], check=True)


def _normalize_url(raw_url: str) -> str:
    url = raw_url.strip()
    if not url:
        raise ValueError("No URL provided")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only valid HTTP or HTTPS URLs are supported")
    return url


def open_website(url: str) -> str:
    """Open a validated website in the default browser."""
    try:
        normalized_url = _normalize_url(url)
        _open_url(normalized_url)
        logger.info("Opened website: %s", normalized_url)
        return f"TOOL_OK: Open request for {normalized_url} was accepted by the browser launcher."
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.exception("Failed to open website")
        return f"TOOL_ERROR: I couldn't open that site: {exc}."


def _find_first_video_id(query: str) -> str | None:
    """Fetch YouTube's search results page and extract the first video ID."""
    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    request = urllib.request.Request(
        search_url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except (OSError, urllib.error.URLError, ValueError):
        logger.exception("Failed to fetch YouTube search results")
        return None

    match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
    return match.group(1) if match else None


def play_youtube(query: str) -> str:
    """Search YouTube and open the top matching video or a verified search page."""
    query = query.strip()
    if not query:
        return "TOOL_ERROR: What would you like me to play on YouTube?"

    video_id = _find_first_video_id(query)
    if video_id:
        watch_url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
        try:
            _open_url(watch_url)
            logger.info("Opened YouTube video: %s (%s)", query, video_id)
            return f"TOOL_OK: Opened the top YouTube result for '{query}'."
        except (OSError, subprocess.SubprocessError) as exc:
            logger.exception("Failed to open YouTube video")
            return f"TOOL_ERROR: I couldn't open that YouTube video: {exc}."

    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    try:
        _open_url(search_url)
        logger.info("Opened YouTube search fallback: %s", query)
        return f"TOOL_OK: No direct video ID was verified, so I opened YouTube search results for '{query}'."
    except (OSError, subprocess.SubprocessError) as exc:
        logger.exception("Failed to open YouTube search")
        return f"TOOL_ERROR: I couldn't open YouTube search: {exc}."
