"""Browser control: open websites and play YouTube content."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


def _open_url(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    elif sys.platform.startswith("win"):
        os.startfile(url)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", url], check=False)


def open_website(url: str) -> str:
    """Open a website in the default browser. Accepts a bare domain or full URL."""
    url = url.strip()
    if not url:
        return "No URL provided, sir."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        _open_url(url)
        logger.info("Opened website: %s", url)
        return f"Opening {url}, sir."
    except Exception as exc:
        logger.exception("Failed to open website")
        return f"I couldn't open that site, sir: {exc}"


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
    except Exception:
        logger.exception("Failed to fetch YouTube search results")
        return None

    match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
    return match.group(1) if match else None


def play_youtube(query: str) -> str:
    """Search YouTube and open the top matching video directly, so it plays right away."""
    query = query.strip()
    if not query:
        return "What would you like me to play, sir?"

    video_id = _find_first_video_id(query)
    if video_id:
        watch_url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
        try:
            _open_url(watch_url)
            logger.info("Opened YouTube video: %s (%s)", query, video_id)
            return f"Playing '{query}' on YouTube, sir."
        except Exception as exc:
            logger.exception("Failed to open YouTube video")
            return f"I couldn't open that video, sir: {exc}"

    # Fallback: couldn't extract a video ID, just open the search page instead.
    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    try:
        _open_url(search_url)
        logger.info("Opened YouTube search (fallback): %s", query)
        return f"I couldn't find a direct match, sir, so I've pulled up the search results for '{query}'."
    except Exception as exc:
        logger.exception("Failed to open YouTube")
        return f"I couldn't open YouTube, sir: {exc}"