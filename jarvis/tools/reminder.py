"""Reminder tool."""

from __future__ import annotations

from jarvis.memory import MemoryStore


def set_reminder(text: str, time: str, memory: MemoryStore) -> str:
    """Store a reminder."""
    memory.add_reminder(text=text, when=time)
    return f"Reminder saved: {text} at {time}"
