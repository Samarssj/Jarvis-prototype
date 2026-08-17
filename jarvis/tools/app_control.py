"""Application and media control tools."""

from __future__ import annotations

import platform
import subprocess
from typing import Literal
from urllib.parse import quote_plus


def open_application(app_name: str) -> str:
    """Open a desktop application and report whether the launch request was spawned."""
    app_name = app_name.strip()
    if not app_name:
        return "TOOL_ERROR: An application name is required."

    system = platform.system().lower()
    try:
        if system == "darwin":
            subprocess.Popen(["open", "-a", app_name])
        elif system == "windows":
            subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=True)
        else:
            subprocess.Popen([app_name])
        return f"TOOL_OK: Launch request for {app_name} was accepted by the operating system."
    except (OSError, subprocess.SubprocessError) as exc:
        return f"TOOL_ERROR: Could not launch {app_name}: {exc}."


def power_control(action: Literal["shutdown", "restart"], confirm: str) -> str:
    """Shut down or restart the computer after explicit confirmation."""
    if action not in {"shutdown", "restart"}:
        return f"TOOL_ERROR: Unsupported power action '{action}'."
    if confirm.strip().lower() != "confirm":
        return f"TOOL_ERROR: Refused {action}; the explicit confirmation token is missing."

    system = platform.system().lower()
    if system != "darwin":
        return f"TOOL_ERROR: {action.title()} is only implemented for macOS right now."

    shell_command = "shutdown -h now" if action == "shutdown" else "shutdown -r now"
    command = [
        "/usr/bin/osascript",
        "-e",
        f'do shell script "{shell_command}" with administrator privileges',
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        if result.returncode == 0:
            return f"TOOL_OK: The {action} request was submitted to macOS."
        details = stderr or stdout or f"exit code {result.returncode}"
        return f"TOOL_ERROR: macOS rejected the {action} request: {details}."
    except (OSError, subprocess.SubprocessError) as exc:
        return f"TOOL_ERROR: Failed to request {action}: {exc}."


def _escape_applescript_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def play_media(service: Literal["apple_music", "spotify"], query: str) -> str:
    """Play a track or album in Apple Music or Spotify on macOS."""
    if service not in {"apple_music", "spotify"}:
        return f"TOOL_ERROR: Unsupported media service '{service}'."
    if platform.system().lower() != "darwin":
        return "TOOL_ERROR: Media playback is currently implemented for macOS only."

    query = query.strip()
    if not query:
        return "TOOL_ERROR: Please provide a song or album name."
    safe_query = _escape_applescript_text(query)

    try:
        if service == "spotify":
            pause_music_script = 'if application "Music" is running then tell application "Music" to pause'
            pause_result = subprocess.run(
                ["osascript", "-e", pause_music_script],
                capture_output=True,
                text=True,
                check=False,
            )
            if pause_result.returncode != 0:
                details = (pause_result.stderr or pause_result.stdout or "unknown AppleScript error").strip()
                return f"TOOL_ERROR: Could not pause Apple Music before starting Spotify: {details}."

            subprocess.Popen(["open", "-a", "Spotify"])
            spotify_script = f'''
            tell application "Spotify"
                activate
                delay 1.0
                try
                    play track "spotify:search:{quote_plus(query)}"
                on error
                    delay 0.8
                    play track "spotify:search:{quote_plus(query)}"
                end try
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", spotify_script],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                details = (result.stderr or result.stdout or "unknown AppleScript error").strip()
                return f"TOOL_ERROR: Spotify could not start '{query}': {details}."
            return f"TOOL_OK: Spotify accepted the request to play '{query}'."

        pause_spotify_script = 'if application "Spotify" is running then tell application "Spotify" to pause'
        pause_result = subprocess.run(
            ["osascript", "-e", pause_spotify_script],
            capture_output=True,
            text=True,
            check=False,
        )
        if pause_result.returncode != 0:
            details = (pause_result.stderr or pause_result.stdout or "unknown AppleScript error").strip()
            return f"TOOL_ERROR: Could not pause Spotify before starting Apple Music: {details}."

        subprocess.Popen(["open", "-a", "Music"])
        applescript = f'''
        tell application "Music"
            activate
            delay 0.5
            try
                set searchResults to (every track of library playlist 1 whose name contains "{safe_query}" or artist contains "{safe_query}")
                if (count of searchResults) > 0 then
                    play item 1 of searchResults
                    return "library"
                end if
            end try
            open location "music://music.apple.com/search?term={quote_plus(query)}"
            return "search"
        end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout or "unknown AppleScript error").strip()
            return f"TOOL_ERROR: Apple Music could not start '{query}': {details}."
        mode = (result.stdout or "").strip().lower()
        if mode == "library":
            return f"TOOL_OK: Apple Music started '{query}' from the library."
        if mode == "search":
            return f"TOOL_OK: Apple Music opened a search for '{query}'."
        return f"TOOL_ERROR: Apple Music returned no verified playback state for '{query}'."
    except (OSError, subprocess.SubprocessError) as exc:
        return f"TOOL_ERROR: Failed to play media: {exc}."


def media_control(action: Literal["play", "pause", "next", "previous"]) -> str:
    """Control playback dynamically in Spotify or Apple Music on macOS."""
    if action not in {"play", "pause", "next", "previous"}:
        return f"TOOL_ERROR: Unsupported media action '{action}'."
    if platform.system().lower() != "darwin":
        return "TOOL_ERROR: Media controls are currently implemented for macOS only."

    action_map_spotify = {
        "play": 'tell application "Spotify" to play',
        "pause": 'tell application "Spotify" to pause',
        "next": 'tell application "Spotify" to next track',
        "previous": 'tell application "Spotify" to previous track',
    }
    action_map_music = {
        "play": 'tell application "Music" to play',
        "pause": 'tell application "Music" to pause',
        "next": 'tell application "Music" to next track',
        "previous": 'tell application "Music" to previous track',
    }

    applescript = f'''
    tell application "System Events"
        set spotifyRunning to (name of processes contains "Spotify")
        set musicRunning to (name of processes contains "Music")
    end tell

    if spotifyRunning then
        tell application "Spotify"
            try
                set playerState to player state as string
                if playerState is "playing" or not musicRunning then
                    {action_map_spotify[action]}
                    return "Spotify media {action} sent."
                end if
            end try
        end tell
    end if

    if musicRunning then
        tell application "Music"
            try
                {action_map_music[action]}
                return "Apple Music media {action} sent."
            end try
        end tell
    end if

    return "No active media player (Spotify or Apple Music) found."
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0:
            return f"TOOL_ERROR: Media {action} failed: {output or f'exit code {result.returncode}'}."
        if not output or output.startswith("No active media player"):
            return f"TOOL_ERROR: Media {action} was not sent because no active supported player was found."
        return f"TOOL_OK: {output}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"TOOL_ERROR: Failed to send media {action}: {exc}."
