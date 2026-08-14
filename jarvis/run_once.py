"""One-shot Jarvis demo without the continuous microphone loop."""

from __future__ import annotations

import argparse
import logging

from jarvis.brain import Brain
from jarvis.config import settings
from jarvis.memory import MemoryStore
from jarvis.tts import TextToSpeech
from jarvis.tools.alarm import set_alarm
from jarvis.tools.app_control import open_application
from jarvis.tools.app_control import play_media
from jarvis.tools.app_control import media_control
from jarvis.tools.app_control import power_control
from jarvis.tools.reminder import set_reminder
from jarvis.tools.time_tool import get_time
from jarvis.tools.weather import get_weather
from jarvis.tools.web_search import web_search


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def build_brain(memory: MemoryStore) -> Brain:
    return Brain(
        model_name=settings.model,
        api_key=settings.gemini_api_key,
        tools={
            "get_weather": get_weather,
            "web_search": web_search,
            "open_application": open_application,
            "play_media": play_media,
            "media_control": media_control,
            "power_control": power_control,
            "set_reminder": lambda text, time: set_reminder(text, time, memory),
            "set_alarm": lambda text, time: set_alarm(text, time, memory),
            "get_time": get_time,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Jarvis once with a text prompt.")
    parser.add_argument("prompt", help="Text prompt to send to Jarvis")
    parser.add_argument("--speak", action="store_true", help="Speak the response with TTS")
    args = parser.parse_args()

    memory = MemoryStore(settings.db_path)
    brain = build_brain(memory)
    tts = TextToSpeech(voice=settings.tts_voice, rate=settings.tts_rate, pitch=settings.tts_pitch)

    memory.add_message("user", args.prompt)
    response = brain.generate(memory.get_recent_messages())
    memory.add_message("assistant", response.text)
    print(response.text)
    logger.info("Jarvis response: %s", response.text)

    if args.speak:
        tts.speak_and_play(response.text)


if __name__ == "__main__":
    main()
