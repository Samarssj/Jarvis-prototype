"""Jarvis entry point."""

from __future__ import annotations

import os

# Set OpenMP thread limit prior to importing multithreaded libraries
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["CTRANSLATE2_INTER_THREADS"] = "1"

import difflib
import logging
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from jarvis.brain import Brain
from jarvis.config import settings
from jarvis.memory import MemoryStore
from jarvis.splash import get_running_port, set_state
from jarvis.stt import SpeechToText
from jarvis.tools.alarm import set_alarm
from jarvis.tools.app_control import media_control, open_application, play_media, power_control
from jarvis.tools.browser import open_website, play_youtube
from jarvis.tools.file_manager import describe_file, find_file, open_file
from jarvis.tools.reminder import set_reminder
from jarvis.tools.system_info import get_system_info
from jarvis.tools.time_tool import get_time
from jarvis.tools.weather import get_weather
from jarvis.tools.web_search import web_search
from jarvis.tts import TextToSpeech

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
SPLASH_PORT = None

# Common mishearings / natural variations of the wake word are matched too.
WAKE_WORD_ALIASES = ["jarvis", "hey jarvis", "ok jarvis", "okay jarvis", "yo jarvis"]


def get_greeting() -> str:
    """Return a time-aware Jarvis greeting."""
    hour = datetime.now().hour
    if hour < 3:
        return "Burning the midnight oil, sir? Jarvis is online — systems standing by, whenever you're ready."
    if hour < 12:
        return "Rise and shine, sir. Jarvis is online — all systems ready, right on schedule."
    if hour < 17:
        return "Good afternoon, sir. Jarvis is online — standing by, as always."
    return "Evening, sir. Jarvis is online — let's make tonight interesting."


def wants_suit_assembly(user_text: str) -> bool:
    """Fuzzy-match Mark 50 / Iron Man suit intent without requiring a command phrase."""
    normalized = re.sub(r"[^a-z0-9\s]", "", user_text.lower())
    normalized = re.sub(r"\b(fifty|fivty|fiifty)\s*(zero|0)\b", "50", normalized)
    tokens = normalized.split()

    def close_to(token: str, candidates: tuple[str, ...], threshold: float = 0.78) -> bool:
        return any(difflib.SequenceMatcher(None, token, candidate).ratio() >= threshold for candidate in candidates)

    has_mark = any(close_to(token, ("mark", "mk")) for token in tokens)
    has_50 = "50" in tokens or any(token in {"fiftyzero", "fivtyzero"} for token in tokens)
    has_suit = any(close_to(token, ("suit", "suite", "armor", "armour", "assembly")) for token in tokens)
    has_iron_theme = any(close_to(token, ("iron", "ironman", "stark", "reactor")) for token in tokens)
    return (has_mark and has_50) or (has_iron_theme and has_suit)


def should_exit(user_text: str) -> bool:
    """Detect whether the user wants Jarvis to stop listening."""
    normalized = user_text.lower()
    phrases = [
        "turn yourself off",
        "switch yourself off",
        "shut yourself down",
        "stop listening",
        "i don't need anything else",
        "i do not need anything else",
        "that's all",
        "thats all",
        "goodbye jarvis",
        "bye jarvis",
        "sleep jarvis",
        "turn off jarvis",
    ]
    return any(phrase in normalized for phrase in phrases)


def _is_wake_word_match(text: str, wake_word: str, threshold: float = 0.75) -> bool:
    """Flexible match: exact/substring match, common aliases, or close fuzzy match
    for mishearings (e.g. 'jarves', 'charvis', 'jarviss')."""
    normalized = re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()
    wake_word = wake_word.lower().strip()

    if not normalized:
        return False

    # 1) Direct substring match (covers "jarvis", "hey jarvis", etc. automatically)
    if wake_word in normalized:
        return True
    for alias in WAKE_WORD_ALIASES:
        if alias in normalized:
            return True

    # 2) Fuzzy match against each word in the transcription, to catch mishearings
    for word in normalized.split():
        ratio = difflib.SequenceMatcher(None, word, wake_word).ratio()
        if ratio >= threshold:
            return True

    return False


def wait_for_wake_word(stt: SpeechToText, wake_word: str) -> None:
    """Block until the wake word (or a close variant/mishearing) is heard."""
    wake_word = wake_word.lower().strip()
    logger.info("Sleeping — say '%s' to wake me up.", wake_word)
    while True:
        splash_update("SLEEPING", f"Say '{wake_word}' to wake me", "off")
        text = stt.listen_and_transcribe(seconds=4)  # short burst, cheap
        if not text:
            continue
        logger.info("Heard while sleeping: %s", text)
        if _is_wake_word_match(text, wake_word):
            logger.info("Wake word detected: %s", text)
            return


def alarm_worker(memory: MemoryStore, tts: TextToSpeech, stop_event: threading.Event, speech_lock: threading.Lock) -> None:
    """Poll for due alarms and reminders and announce only persisted due items."""
    while not stop_event.is_set():
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            for alarm in memory.get_due_alarms(now_iso):
                message = f"Alarm time, sir. {alarm['text']}"
                with speech_lock:
                    tts.speak_and_play(message)
                memory.mark_alarm_triggered(alarm["id"])
                memory.add_message("assistant", message)
                logger.info("Triggered persisted alarm #%s: %s", alarm["id"], alarm["text"])
            for reminder in memory.get_due_reminders(now_iso):
                message = f"Reminder, sir. {reminder['text']}"
                with speech_lock:
                    tts.speak_and_play(message)
                memory.mark_reminder_delivered(reminder["id"])
                memory.add_message("assistant", message)
                logger.info("Delivered persisted reminder #%s: %s", reminder["id"], reminder["text"])
        except Exception:
            logger.exception("Alarm/reminder worker error")
        stop_event.wait(5)


def splash_update(status: str, detail: str, mic: str) -> None:
    """Publish HUD state directly; the server reads the shared state file."""
    if get_running_port() is None:
        return
    try:
        set_state(status=status, detail=detail, mic=mic)
    except Exception:
        logger.exception("Failed to update splash")


def splash_set_animation(animation: str) -> None:
    """Trigger a visual HUD animation without blocking voice processing."""
    if get_running_port() is None:
        return
    try:
        set_state(animation=animation)
        if animation == "mark50_assembly":
            threading.Timer(14.5, lambda: set_state(animation="none")).start()
    except Exception:
        logger.exception("Failed to update splash animation")


def splash_set_latency(latency_ms: int) -> None:
    """Publish the latest measured model response latency to the HUD."""
    if get_running_port() is None:
        return
    try:
        set_state(latency_ms=latency_ms)
    except Exception:
        logger.exception("Failed to update splash latency")


def stop_splash() -> None:
    """Tell the splash server to shut down and clear its port marker."""
    global SPLASH_PORT
    port = SPLASH_PORT or get_running_port()
    if port is None:
        return
    try:
        subprocess.run([sys.executable, "-m", "jarvis.splash", "--shutdown", str(port)], check=False, timeout=3)
    except subprocess.TimeoutExpired:
        logger.warning("Splash shutdown timed out; continuing main process shutdown")
    finally:
        SPLASH_PORT = None


def _awaits_clarification(response_text: str) -> bool:
    """Heuristic: if Jarvis's reply ends in a question, treat it as awaiting
    a direct follow-up answer, rather than requiring the wake word again."""
    return response_text.strip().endswith("?")


def main() -> None:
    splash_proc = subprocess.Popen([sys.executable, "-m", "jarvis.splash"])
    for _ in range(20):
        if get_running_port() is not None:
            break
        time.sleep(0.1)

    stt: SpeechToText | None = None
    try:
        memory = MemoryStore(settings.db_path)
        tts = TextToSpeech(voice=settings.tts_voice, rate=settings.tts_rate, pitch=settings.tts_pitch)

        if not settings.gemini_api_key:
            missing_key_message = (
                "Gemini API key is missing, sir. Add GEMINI_API_KEY to the .env file in this Jarvis project, "
                "then restart me. I have not opened the microphone or processed the command."
            )
            logger.error("Gemini API key is missing; refusing to start the voice loop")
            splash_update("CONFIGURATION ERROR", "Gemini API key missing", "off")
            tts.speak_and_play(missing_key_message)
            return

        stt = SpeechToText(
            model_size=settings.stt_model,
            sample_rate=settings.sample_rate,
            silence_limit=settings.vad_silence_limit,
            no_speech_timeout=settings.vad_no_speech_timeout,
        )
        speech_lock = threading.Lock()
        stop_event = threading.Event()

        def speak(text: str) -> None:
            with speech_lock:
                tts.speak_and_play(text)

        def remember_fact(key: str, value: str) -> str:
            key = key.strip()
            value = value.strip()
            if not key or not value:
                return "TOOL_ERROR: Both a fact key and value are required."
            try:
                memory.set_fact(key, value)
                return f"TOOL_OK: Remembered that {key.replace('_', ' ')} is {value}."
            except Exception as exc:
                return f"TOOL_ERROR: Could not remember that fact: {exc}."

        brain = Brain(
            model_name=settings.model,
            api_key=settings.gemini_api_key,
            timeout_ms=settings.model_timeout_ms,
            tools={
                "get_weather": get_weather,
                "web_search": web_search,
                "open_application": open_application,
                "play_media": play_media,
                "media_control": media_control,
                "power_control": power_control,
                "get_system_info": get_system_info,
                "set_reminder": lambda text, time: set_reminder(text, time, memory),
                "set_alarm": lambda text, time: set_alarm(text, time, memory),
                "get_time": get_time,
                "open_website": open_website,
                "play_youtube": play_youtube,
                "find_file": find_file,
                "open_file": open_file,
                "remember_fact": remember_fact,
                "describe_file": None,  # placeholder, replaced below once brain exists
            },
        )
        # describe_file needs brain.describe_image for image content — wire it now that brain exists.
        brain.tools["describe_file"] = lambda name: describe_file(name, brain.describe_image)

        logger.info("Jarvis started")
        threading.Thread(target=alarm_worker, args=(memory, tts, stop_event, speech_lock), daemon=True).start()
        splash_update("LISTENING", "Awaiting your command, sir", "on")
        speak(get_greeting())

        awaiting_clarification = False

        while True:
            try:
                if not awaiting_clarification:
                    wait_for_wake_word(stt, settings.wake_word)
                    splash_update("LISTENING", "Yes, sir?", "on")
                    speak("Yes, sir?")
                else:
                    # Jarvis just asked a question — go straight to listening,
                    # no wake word needed for this one follow-up.
                    splash_update("LISTENING", "Listening for your answer...", "on")

                user_text = stt.listen_and_transcribe(seconds=settings.record_seconds)
                splash_update("LISTENING", "Listening...", "on")
                if not user_text:
                    logger.info("No speech detected")
                    splash_update("LISTENING", "Awaiting your command, sir", "off")
                    # If we were waiting on a clarification and got silence, don't
                    # loop on it forever — fall back to requiring the wake word again.
                    awaiting_clarification = False
                    continue

                logger.info("User said: %s", user_text)
                if should_exit(user_text):
                    memory.add_message("user", user_text)
                    goodbye = "Very well, sir. Going offline."
                    memory.add_message("assistant", goodbye)
                    splash_update("SPEAKING", "Going offline", "off")
                    speak(goodbye)
                    logger.info("Jarvis going offline on user request")
                    stop_event.set()
                    break

                memory.add_message("user", user_text)
                splash_update("THINKING", f'"{user_text}"', "off")
                if wants_suit_assembly(user_text):
                    splash_set_animation("mark50_assembly")
                started = time.perf_counter()
                response = brain.generate(memory.get_recent_messages(), facts=memory.get_all_facts())
                splash_set_latency(max(1, round((time.perf_counter() - started) * 1000)))
                memory.add_message("assistant", response.text)
                splash_update("SPEAKING", response.text[:60] + "..." if len(response.text) > 60 else response.text, "off")
                speak(response.text)

                awaiting_clarification = _awaits_clarification(response.text)
                if awaiting_clarification:
                    logger.info("Awaiting clarification — skipping wake word on next turn.")
                else:
                    splash_update("LISTENING", "Awaiting your command, sir", "on")
                logger.info("Responded with: %s", response.text)
            except KeyboardInterrupt:
                logger.info("Shutting down")
                stop_event.set()
                break
            except Exception:
                logger.exception("Unexpected error in main loop")
                awaiting_clarification = False
                recovery = "I couldn't complete that request, sir. No action was confirmed."
                try:
                    splash_update("SPEAKING", recovery, "off")
                    speak(recovery)
                except Exception:
                    logger.exception("Could not speak main-loop recovery message")
                splash_update("LISTENING", "Awaiting your command, sir", "on")
    finally:
        if stt is not None:
            stt.close()
        splash_update("SHUTTING DOWN", "Closing interface", "off")
        stop_splash()
        if splash_proc.poll() is None:
            splash_proc.terminate()


if __name__ == "__main__":
    main()