"""Time tool."""

from __future__ import annotations

from datetime import datetime


def get_time() -> str:
    """Return current local time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
