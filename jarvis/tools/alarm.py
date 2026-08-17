from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from jarvis.memory import MemoryStore


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _parse_clock_time(text: str, tomorrow: bool = False) -> datetime:
    """Parse a local clock time and return it as a UTC-aware datetime."""
    now_local = _local_now()
    base = now_local + timedelta(days=1) if tomorrow else now_local
    cleaned = text.strip().lower().replace(".", "")
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", cleaned)
    if not match:
        raise ValueError(f"unrecognized time '{text}'")

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm = match.group(3)
    if minute > 59:
        raise ValueError(f"invalid minute in '{text}'")
    if ampm:
        if hour < 1 or hour > 12:
            raise ValueError(f"invalid 12-hour clock time '{text}'")
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
    elif hour > 23:
        raise ValueError(f"invalid 24-hour clock time '{text}'")

    candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now_local and not tomorrow:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def parse_scheduled_time(time_text: str) -> str:
    """Parse a spoken local time phrase into an ISO-8601 UTC timestamp."""
    raw = re.sub(r"^(at|for)\s+", "", time_text.strip().lower())
    now_utc = datetime.now(timezone.utc)

    in_match = re.fullmatch(r"in\s+(\d+)\s+(minute|minutes|min|hour|hours|hr|hrs)", raw)
    if in_match:
        value = int(in_match.group(1))
        unit = in_match.group(2)
        delta = timedelta(minutes=value) if unit.startswith("m") else timedelta(hours=value)
        return (now_utc + delta).isoformat()

    tomorrow_match = re.fullmatch(r"tomorrow(?:\s+at\s+(.+))?", raw)
    if tomorrow_match:
        time_part = tomorrow_match.group(1) or "9:00 am"
        return _parse_clock_time(time_part, tomorrow=True).isoformat()

    return _parse_clock_time(raw).isoformat()


# Backward-compatible private name for any existing callers.
def _parse_alarm_time(time_text: str) -> str:
    return parse_scheduled_time(time_text)


def format_scheduled_time(iso_time: str) -> str:
    """Format a stored UTC timestamp in the machine's local timezone."""
    local_time = datetime.fromisoformat(iso_time).astimezone()
    return local_time.strftime("%A, %B %-d at %-I:%M %p")


def set_alarm(text: str, time: str, memory: MemoryStore) -> str:
    """Persist an alarm and return only a verified success or failure result."""
    try:
        iso_time = parse_scheduled_time(time)
        alarm_id = memory.add_alarm(text=text, when=iso_time)
        return (
            f"TOOL_OK: Alarm #{alarm_id} was persisted and is scheduled for "
            f"{format_scheduled_time(iso_time)} ({iso_time}). Message: {text}"
        )
    except Exception as exc:
        return f"TOOL_ERROR: Alarm was not scheduled because {exc}."
