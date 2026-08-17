"""Configuration loading for Jarvis."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_CANDIDATES = (PROJECT_ROOT / ".env", Path.cwd() / ".env")
for _env_path in dict.fromkeys(_ENV_CANDIDATES):
    if _env_path.is_file():
        load_dotenv(dotenv_path=_env_path, override=False)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    anthropic_api_key: str = _env("ANTHROPIC_API_KEY")
    # GEMINI_API_KEY is the documented name; GOOGLE_API_KEY is supported as a
    # compatibility fallback used by Google tooling and existing deployments.
    gemini_api_key: str = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
    openweather_api_key: str = _env("OPENWEATHER_API_KEY")
    wake_word: str = _env("JARVIS_WAKE_WORD", "jarvis")
    model: str = _env("JARVIS_MODEL", "gemini-flash-latest")
    model_timeout_ms: int = int(_env("JARVIS_MODEL_TIMEOUT_MS", "20000"))
    tts_voice: str = _env("JARVIS_TTS_VOICE", "en-GB-RyanNeural")
    tts_rate: str = _env("JARVIS_TTS_RATE", "+0%")
    tts_pitch: str = _env("JARVIS_TTS_PITCH", "-2Hz")
    sample_rate: int = int(_env("JARVIS_SAMPLE_RATE", "16000"))
    stt_model: str = _env("JARVIS_STT_MODEL", "tiny.en")
    vad_silence_limit: float = float(_env("JARVIS_VAD_SILENCE_LIMIT", "1.0"))
    vad_no_speech_timeout: float = float(_env("JARVIS_VAD_NO_SPEECH_TIMEOUT", "2.0"))
    record_seconds: int = int(_env("JARVIS_RECORD_SECONDS", "11"))
    splash_duration_ms: int = int(_env("JARVIS_SPLASH_DURATION_MS", "3500"))
    db_path: str = _env("JARVIS_DB_PATH", "jarvis_history.sqlite3")


settings = Settings()
