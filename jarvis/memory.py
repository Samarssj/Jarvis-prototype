"""SQLite conversation, reminder, alarm, and durable user-fact storage."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MemoryStore:
    """Persist conversation turns, reminders, alarms, and durable user facts in SQLite."""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return self._connection

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
                )
                conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    time TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    delivered_at TEXT
                )
                """
                )
                reminder_columns = {row[1] for row in conn.execute("PRAGMA table_info(reminders)").fetchall()}
                if "delivered" not in reminder_columns:
                    conn.execute("ALTER TABLE reminders ADD COLUMN delivered INTEGER NOT NULL DEFAULT 0")
                if "delivered_at" not in reminder_columns:
                    conn.execute("ALTER TABLE reminders ADD COLUMN delivered_at TEXT")
                conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alarms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    time TEXT NOT NULL,
                    triggered INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    triggered_at TEXT
                )
                """
                )
                conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_facts (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
                )

    def add_message(self, role: str, content: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                "INSERT INTO conversations(role, content, created_at) VALUES (?, ?, ?)",
                (role, content, datetime.now(timezone.utc).isoformat()),
                )

    def get_recent_messages(self, limit: int = 12) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def add_reminder(self, text: str, when: str) -> int:
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                "INSERT INTO reminders(text, time, delivered, created_at) VALUES (?, ?, 0, ?)",
                (text, when, datetime.now(timezone.utc).isoformat()),
                )
                return int(cursor.lastrowid)

    def list_reminders(self) -> list[dict[str, str]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT text, time FROM reminders ORDER BY id DESC"
                ).fetchall()
        return [{"text": text, "time": when} for text, when in rows]

    def add_alarm(self, text: str, when: str) -> int:
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                "INSERT INTO alarms(text, time, triggered, created_at) VALUES (?, ?, 0, ?)",
                (text, when, datetime.now(timezone.utc).isoformat()),
                )
                return int(cursor.lastrowid)

    def get_due_reminders(self, now_iso: str) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, text, time
                    FROM reminders
                    WHERE delivered = 0 AND time <= ?
                    ORDER BY time ASC
                    """,
                    (now_iso,),
                ).fetchall()
        return [{"id": reminder_id, "text": text, "time": when} for reminder_id, text, when in rows]

    def mark_reminder_delivered(self, reminder_id: int) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE reminders
                    SET delivered = 1, delivered_at = ?
                    WHERE id = ?
                    """,
                    (datetime.now(timezone.utc).isoformat(), reminder_id),
                )

    def get_due_alarms(self, now_iso: str) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, text, time
                    FROM alarms
                    WHERE triggered = 0 AND time <= ?
                    ORDER BY time ASC
                    """,
                    (now_iso,),
                ).fetchall()
        return [{"id": alarm_id, "text": text, "time": when} for alarm_id, text, when in rows]

    def mark_alarm_triggered(self, alarm_id: int) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                """
                UPDATE alarms
                SET triggered = 1, triggered_at = ?
                WHERE id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), alarm_id),
                )

    def set_fact(self, key: str, value: str) -> None:
        """Store or update a durable fact about the user (e.g. name, preferences)."""
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO user_facts(key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (key.strip().lower(), value.strip(), datetime.now(timezone.utc).isoformat()),
                )

    def get_fact(self, key: str) -> str | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT value FROM user_facts WHERE key = ?",
                    (key.strip().lower(),),
                ).fetchone()
        return row[0] if row else None

    def get_all_facts(self) -> dict[str, str]:
        """Return all stored durable facts, e.g. {'name': 'Alex', 'favorite_team': 'Real Madrid'}."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT key, value FROM user_facts ORDER BY key ASC").fetchall()
        return {key: value for key, value in rows}

    def delete_fact(self, key: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM user_facts WHERE key = ?", (key.strip().lower(),))