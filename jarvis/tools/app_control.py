"""Application and media control tools."""

from __future__ import annotations

import platform
import subprocess
from typing import Literal
from urllib.parse import quote_plus


def open_application(app_name: str) -> str:
    """Open a desktop application by name."""
    system = platform.system().lower()
    if system == "darwin":
        subprocess.Popen(["open", "-a", app_name])
    elif system == "windows":
        subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=True)
    else:
        subprocess.Popen([app_name])
    return f"Launching {app_name}"


def power_control(action: Literal["shutdown", "restart"], confirm: str) -> str:
    """Shut down or restart the computer after explicit confirmation."""
    if confirm.strip().lower() != "confirm":
        return f"Refused {action}: missing confirmation token."

    system = platform.system().lower()
    if system != "darwin":
        return f"{action.title()} is only implemented for macOS right now."

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
            return f"The {action} request was submitted to macOS."
        details = stderr or stdout or f"exit code {result.returncode}"
        return f"macOS rejected the {action} request: {details}"
    except Exception as exc:
        return f"Failed to request {action}: {exc}"


def play_media(service: Literal["apple_music", "spotify"], query: str) -> str:
    """Play a track or album in Apple Music or Spotify on macOS."""
    if platform.system().lower() != "darwin":
        return "Media playback is currently implemented for macOS only."

    query = query.strip()
    if not query:
        return "Please provide a song or album name."

    try:
        if service == "spotify":
            # 1. Pause Apple Music if running to prevent overlapping audio
            pause_music_script = 'if application "Music" is running then tell application "Music" to pause'
            subprocess.run(["osascript", "-e", pause_music_script], capture_output=True, check=False)

            # 2. Launch Spotify app
            subprocess.Popen(["open", "-a", "Spotify"])
            
            # 3. Play search track directly via Spotify AppleScript URI
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
            subprocess.run(["osascript", "-e", spotify_script], capture_output=True, text=True, check=False)
            return f"Playing '{query}' on Spotify, sir."

        # Apple Music
        pause_spotify_script = 'if application "Spotify" is running then tell application "Spotify" to pause'
        subprocess.run(["osascript", "-e", pause_spotify_script], capture_output=True, check=False)

        subprocess.Popen(["open", "-a", "Music"])
        applescript = f'''
        tell application "Music"
            activate
            delay 0.5
            try
                set searchResults to (every track of library playlist 1 whose name contains "{query}" or artist contains "{query}")
                if (count of searchResults) > 0 then
                    play item 1 of searchResults
                    return "Playing '{query}' from your Apple Music library, sir."
                end if
            end try
            open location "music://music.apple.com/search?term={quote_plus(query)}"
            return "Searching and playing '{query}' on Apple Music, sir."
        end tell
        '''
        result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, check=False)
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode == 0 and output:
            return output
        return output or f"Playing '{query}' on Apple Music, sir."
    except Exception as exc:
        return f"Failed to play media: {exc}"


def media_control(action: Literal["play", "pause", "next", "previous"]) -> str:
    """Control playback dynamically in Spotify or Apple Music on macOS."""
    if platform.system().lower() != "darwin":
        return "Media controls are currently implemented for macOS only."

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
        result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, check=False)
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode == 0 and output:
            return output
        return f"Media {action} command executed."
    except Exception as exc:
        return f"Failed to send media {action}: {exc}"
