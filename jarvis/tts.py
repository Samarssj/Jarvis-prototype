"""Text-to-speech output using edge-tts."""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
import subprocess
import sys
import time
from pathlib import Path

import edge_tts
from playsound import playsound


logger = logging.getLogger(__name__)


def clean_for_speech(text: str) -> str:
    """Strip Markdown and other formatting artifacts so TTS reads plain words only."""
    # Remove bold/italic markers (**text**, *text*, __text__, _text_)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    # Remove markdown headers (#, ##, ###...)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Remove bullet/list markers at line starts (-, *, +)
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    # Remove markdown links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove inline code / code fences (`code`, ```code```)
    text = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", text)
    # Remove any leftover stray asterisks, underscores, tildes, backticks, pipes
    text = re.sub(r"[*_~`|]", "", text)
    # Collapse extra whitespace left behind
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class TextToSpeech:
    """Convert text to spoken audio."""

    def __init__(self, voice: str = "en-GB-RyanNeural", rate: str = "-10%", pitch: str = "-2Hz") -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def _speak_async(self, text: str, output_path: Path) -> None:
        communicate = edge_tts.Communicate(text=text, voice=self.voice, rate=self.rate, pitch=self.pitch)
        await communicate.save(str(output_path))

    def speak(self, text: str) -> Path:
        """Synthesize text to a temporary audio file."""
        text = clean_for_speech(text)
        with tempfile.NamedTemporaryFile(suffix=".mp3", prefix="jarvis_", delete=False) as tmp:
            output_path = Path(tmp.name)
        asyncio.run(self._speak_async(text, output_path))
        return output_path

    def play(self, audio_path: Path) -> None:
        """Play a synthesized audio file and clean it up."""
        try:
            if sys.platform == "darwin":
                subprocess.run(["afplay", "-v", "2.0", str(audio_path)], check=False)
            else:
                playsound(str(audio_path))
        finally:
            audio_path.unlink(missing_ok=True)

    def speak_and_play(self, text: str) -> None:
        """Convenience helper to synthesize, play, and pause briefly."""
        audio = self.speak(text)
        self.play(audio)
        time.sleep(0.1)