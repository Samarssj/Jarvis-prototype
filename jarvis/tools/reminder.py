from __future__ import annotations

from jarvis.memory import MemoryStore
from jarvis.tools.alarm import format_scheduled_time, parse_scheduled_time
from jarvis.tools.native_schedule import NativeScheduleError, create_native_reminder


def set_reminder(text: str, time: str, memory: MemoryStore) -> str:
    """Persist a reminder and create native macOS Calendar and Reminders entries."""
    text = text.strip()
    if not text:
        return "TOOL_ERROR: Reminder text cannot be empty."
    try:
        iso_time = parse_scheduled_time(time)
        reminder_id = memory.add_reminder(text=text, when=iso_time)
        try:
            native = create_native_reminder(text, iso_time)
        except NativeScheduleError as exc:
            return (
                f"TOOL_ERROR: Reminder #{reminder_id} was saved locally, but the native macOS Calendar/Reminders entries "
                f"were not fully created: {exc}."
            )
        if not native.calendar_event_id or not native.reminder_id:
            return f"TOOL_ERROR: Reminder #{reminder_id} was saved locally, but macOS returned incomplete native identifiers."
        memory.attach_native_reminder(reminder_id, native.calendar_event_id, native.reminder_id)
        return (
            f"TOOL_OK: Reminder #{reminder_id} was created in macOS Calendar and Reminders and persisted locally. "
            f"Calendar ID {native.calendar_event_id}; Reminders ID {native.reminder_id}. Scheduled for "
            f"{format_scheduled_time(iso_time)} ({iso_time}). Message: {text}"
        )
    except Exception as exc:
        return f"TOOL_ERROR: Reminder was not saved because {exc}."
