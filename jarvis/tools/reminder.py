from __future__ import annotations

from jarvis.memory import MemoryStore
from jarvis.tools.alarm import format_scheduled_time, parse_scheduled_time


def set_reminder(text: str, time: str, memory: MemoryStore) -> str:
    """Persist a reminder and return only a verified success or failure result."""
    try:
        iso_time = parse_scheduled_time(time)
        reminder_id = memory.add_reminder(text=text, when=iso_time)
        return (
            f"TOOL_OK: Reminder #{reminder_id} was persisted for "
            f"{format_scheduled_time(iso_time)} ({iso_time}). Message: {text}"
        )
    except Exception as exc:
        return f"TOOL_ERROR: Reminder was not saved because {exc}."
