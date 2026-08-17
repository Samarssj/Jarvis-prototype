"""Time tool."""

from __future__ import annotations

from datetime import datetime


def get_time() -> str:
    """Return current local time as a verified tool result."""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"TOOL_OK: Local time is {current_time}."
    except Exception as exc:
        return f"TOOL_ERROR: Could not read local time: {exc}."
