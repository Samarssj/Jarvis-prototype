"""Alarm tool."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from jarvis.memory import MemoryStore


def _parse_alarm_time(time_text: str) -> str:
    """Parse a spoken time phrase into an ISO-8601 UTC timestamp."""
    raw = time_text.strip().lower()
    now = datetime.now(timezone.utc)

    in_match = re.match(r"in (\d+) (minute|minutes|hour|hours)", raw)
    if in_match:
        value = int(in_match.group(1))
        unit = in_match.group(2)
        delta = timedelta(minutes=value) if "minute" in unit else timedelta(hours=value)
        return (now + delta).isoformat()

    tomorrow_match = re.match(r"tomorrow(?: at (.+))?$", raw)
    if tomorrow_match:
        time_part = tomorrow_match.group(1) or "9:00 am"
        target = _parse_clock_time(time_part, tomorrow=True)
        return target.isoformat()

    return _parse_clock_time(raw).isoformat()


def _parse_clock_time(text: str, tomorrow: bool = False) -> datetime:
    """Parse a clock time like '9 pm' or '07:30' into UTC today/tomorrow."""
    now = datetime.now(timezone.utc)
    base = now + timedelta(days=1) if tomorrow else now
    cleaned = text.strip().lower().replace(".", "")
    match = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", cleaned)
    if not match:
        return base + timedelta(minutes=30)

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm = match.group(3)
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now and not tomorrow:
        candidate += timedelta(days=1)
    return candidate


def set_alarm(text: str, time: str, memory: MemoryStore) -> str:
    """Store an alarm that will fire later."""
    iso_time = _parse_alarm_time(time)
    memory.add_alarm(text=text, when=iso_time)
    return f"Alarm set for {iso_time}: {text}"
