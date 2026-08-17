"""Native macOS Calendar and Reminders integrations for Jarvis scheduling."""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone


class NativeScheduleError(RuntimeError):
    """Raised when a native macOS scheduling operation cannot be verified."""


@dataclass(frozen=True)
class NativeScheduleResult:
    """Identifiers returned by native scheduling applications."""

    calendar_event_id: str | None = None
    reminder_id: str | None = None


CALENDAR_NAME = os.getenv("JARVIS_NATIVE_CALENDAR", "Jarvis")
REMINDERS_LIST_NAME = os.getenv("JARVIS_NATIVE_REMINDERS_LIST", "Jarvis")


def _epoch_seconds(iso_time: str) -> str:
    try:
        target = datetime.fromisoformat(iso_time)
    except ValueError as exc:
        raise NativeScheduleError(f"invalid scheduled timestamp: {iso_time}") from exc
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return f"{target.timestamp():.6f}"


def _run_osascript(script: str, *arguments: str) -> str:
    if platform.system().lower() != "darwin":
        raise NativeScheduleError("native macOS scheduling is only available on macOS")
    command = ["/usr/bin/osascript", "-e", script, "--", *arguments]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise NativeScheduleError(f"could not run macOS automation: {exc}") from exc
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        details = stderr or stdout or f"osascript exit code {result.returncode}"
        permission_hint = (
            " Grant Terminal or the Python host access in System Settings > Privacy & Security > Automation "
            "if macOS denied Calendar or Reminders control."
        )
        raise NativeScheduleError(f"macOS automation failed: {details}.{permission_hint}")
    if not stdout:
        raise NativeScheduleError("macOS automation returned no native identifier")
    return stdout.splitlines()[-1].strip()


_COMMON_DATE_PREFIX = """
on run argv
    if (count of argv) < 2 then error "missing scheduling arguments"
    set itemText to item 1 of argv
    set epochSeconds to (item 2 of argv) as real
    set epochDate to current date
    set year of epochDate to 1970
    set month of epochDate to January
    set day of epochDate to 1
    set time of epochDate to 0
    set targetDate to epochDate + epochSeconds
"""


_CALENDAR_ALARM_SCRIPT = _COMMON_DATE_PREFIX + """
    if (count of argv) < 3 then error "missing calendar name"
    set targetCalendarName to item 3 of argv
    tell application "Calendar"
        if not (exists calendar targetCalendarName) then
            make new calendar with properties {name:targetCalendarName}
        end if
        tell calendar targetCalendarName
            set newEvent to make new event with properties {summary:("Jarvis Alarm: " & itemText), start date:targetDate, end date:(targetDate + 60)}
            tell newEvent
                make new sound alarm at end of sound alarms with properties {trigger interval:0, sound name:"Sosumi"}
            end tell
            set nativeId to uid of newEvent
        end tell
        reload calendars
        return nativeId
    end tell
end run
"""


_CALENDAR_REMINDER_SCRIPT = _COMMON_DATE_PREFIX + """
    if (count of argv) < 3 then error "missing calendar name"
    set targetCalendarName to item 3 of argv
    tell application "Calendar"
        if not (exists calendar targetCalendarName) then
            make new calendar with properties {name:targetCalendarName}
        end if
        tell calendar targetCalendarName
            set newEvent to make new event with properties {summary:("Jarvis Reminder: " & itemText), start date:targetDate, end date:(targetDate + 60)}
            tell newEvent
                make new display alarm at end of display alarms with properties {trigger interval:0}
            end tell
            set nativeId to uid of newEvent
        end tell
        reload calendars
        return nativeId
    end tell
end run
"""


_REMINDERS_SCRIPT = _COMMON_DATE_PREFIX + """
    if (count of argv) < 3 then error "missing reminders list name"
    set targetListName to item 3 of argv
    tell application "Reminders"
        if not (exists list targetListName) then
            make new list with properties {name:targetListName}
        end if
        tell list targetListName
            set newReminder to make new reminder with properties {name:itemText, remind me date:targetDate}
            return id of newReminder
        end tell
    end tell
end run
"""


def create_native_alarm(text: str, iso_time: str) -> NativeScheduleResult:
    """Create a Calendar event with a native sound alarm at the scheduled time."""
    text = text.strip()
    if not text:
        raise NativeScheduleError("alarm text cannot be empty")
    native_id = _run_osascript(_CALENDAR_ALARM_SCRIPT, text, _epoch_seconds(iso_time), CALENDAR_NAME)
    return NativeScheduleResult(calendar_event_id=native_id)


def create_native_reminder(text: str, iso_time: str) -> NativeScheduleResult:
    """Create both a Calendar alert and a Reminders item for a scheduled reminder."""
    text = text.strip()
    if not text:
        raise NativeScheduleError("reminder text cannot be empty")
    epoch = _epoch_seconds(iso_time)
    calendar_id = _run_osascript(_CALENDAR_REMINDER_SCRIPT, text, epoch, CALENDAR_NAME)
    try:
        reminder_id = _run_osascript(_REMINDERS_SCRIPT, text, epoch, REMINDERS_LIST_NAME)
    except NativeScheduleError as exc:
        raise NativeScheduleError(
            f"Calendar reminder was created with native ID {calendar_id}, but Reminders item creation failed: {exc}"
        ) from exc
    return NativeScheduleResult(calendar_event_id=calendar_id, reminder_id=reminder_id)
