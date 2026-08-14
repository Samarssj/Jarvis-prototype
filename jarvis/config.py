"""Configuration loading for Jarvis."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv(override=True)


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    wake_word: str = os.getenv("JARVIS_WAKE_WORD", "jarvis")
    model: str = os.getenv("JARVIS_MODEL", "gemini-flash-latest")
    tts_voice: str = os.getenv("JARVIS_TTS_VOICE", "en-GB-RyanNeural")
    tts_rate: str = os.getenv("JARVIS_TTS_RATE", "+0%")
    tts_pitch: str = os.getenv("JARVIS_TTS_PITCH", "-2Hz")
    sample_rate: int = int(os.getenv("JARVIS_SAMPLE_RATE", "16000"))
    record_seconds: int = int(os.getenv("JARVIS_RECORD_SECONDS", "11"))
    splash_duration_ms: int = int(os.getenv("JARVIS_SPLASH_DURATION_MS", "3500"))
    db_path: str = os.getenv("JARVIS_DB_PATH", "jarvis_history.sqlite3")


settings = Settings()
