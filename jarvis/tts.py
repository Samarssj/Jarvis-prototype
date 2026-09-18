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
        """Convenience helper to synthesize and play speech without an extra delay."""
        started = time.perf_counter()
        audio = self.speak(text)
        synthesized_ms = (time.perf_counter() - started) * 1000
        playback_started = time.perf_counter()
        self.play(audio)
        logger.info("Speech timing: synthesis=%.0fms playback=%.0fms", synthesized_ms, (time.perf_counter() - playback_started) * 1000)


import queue
import threading

class TTSWorker:
    """Asynchronous worker for synthesizing and playing TTS chunks."""
    
    def __init__(self, tts: TextToSpeech):
        self.tts = tts
        self._text_queue = queue.Queue()
        self._audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._current_process = None
        
        self._synthesis_thread = threading.Thread(target=self._synthesize_worker, daemon=True)
        self._playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self._synthesis_thread.start()
        self._playback_thread.start()

    def enqueue_text(self, text: str):
        """Add a text chunk to be synthesized and played."""
        if text and text.strip():
            self._text_queue.put(text)

    def interrupt(self):
        """Interrupt current playback and clear queues without stopping threads."""
        if self._current_process:
            try:
                self._current_process.terminate()
            except Exception:
                pass
        
        while not self._text_queue.empty():
            try: 
                self._text_queue.get_nowait()
                self._text_queue.task_done()
            except queue.Empty: break
            
        while not self._audio_queue.empty():
            try: 
                self._audio_queue.get_nowait()
                self._audio_queue.task_done()
            except queue.Empty: break

    def stop(self):
        """Completely stop threads."""
        self.interrupt()
        self._stop_event.set()

    def wait_until_done(self):
        """Block until all queued text is synthesized and played."""
        self._text_queue.join()
        self._audio_queue.join()

    def _synthesize_worker(self):
        while not self._stop_event.is_set():
            try:
                text = self._text_queue.get(timeout=0.1)
                if not text.strip():
                    self._text_queue.task_done()
                    continue
                audio_path = self.tts.speak(text)
                self._audio_queue.put(audio_path)
                self._text_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS Synthesis error: {e}")
                self._text_queue.task_done()

    def _playback_worker(self):
        while not self._stop_event.is_set():
            try:
                audio_path = self._audio_queue.get(timeout=0.1)
                try:
                    if sys.platform == "darwin":
                        self._current_process = subprocess.Popen(["afplay", "-v", "2.0", str(audio_path)])
                        self._current_process.wait()
                        self._current_process = None
                    else:
                        self.tts.play(audio_path)
                finally:
                    audio_path.unlink(missing_ok=True)
                self._audio_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS Playback error: {e}")
                self._audio_queue.task_done()