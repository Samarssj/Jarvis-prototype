"""Local speech-to-text using faster-whisper with Voice Activity Detection (VAD)."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
import wave
from pathlib import Path

from jarvis.splash import set_audio_level

# Prevent OpenMP thread deadlocks on macOS CPU with background threads
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["CTRANSLATE2_INTER_THREADS"] = "1"

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class SpeechToText:
    """Record from microphone with dynamic VAD and transcribe speech offline.

    Keeps a single persistent InputStream open for the lifetime of the object,
    instead of opening/closing a new stream on every recording. Repeatedly
    opening and closing streams (e.g. every few seconds while idle, waiting
    for a wake word) can trigger flaky hangs in PortAudio/CoreAudio on macOS.
    """

    def __init__(
        self,
        model_size: str = "tiny.en",
        sample_rate: int = 16000,
        silence_limit: float = 1.0,
        no_speech_timeout: float = 2.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.silence_limit = silence_limit
        self.no_speech_timeout = no_speech_timeout
        # Single CPU thread avoids macOS OpenMP thread locks
        self.model = WhisperModel(model_size, device="cpu", compute_type="float32", cpu_threads=1)

        self._stream_lock = threading.Lock()
        self.stream: sd.InputStream | None = None
        self._last_audio_publish = 0.0
        self._smoothed_audio_level = 0.0
        self._open_stream()

    def _open_stream(self) -> None:
        """Open and start the persistent input stream."""
        self.stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32")
        self.stream.start()
        logger.info("Microphone stream opened")

    def close(self) -> None:
        """Stop and close the persistent stream. Call once, on app shutdown."""
        with self._stream_lock:
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    logger.exception("Error closing microphone stream")
                finally:
                    self.stream = None
                    try:
                        set_audio_level(0.0)
                    except Exception:
                        logger.debug("Unable to reset microphone level on close", exc_info=True)
                    logger.info("Microphone stream closed")

    def _ensure_stream(self) -> None:
        """Re-open the stream if it's missing or was closed unexpectedly."""
        if self.stream is None:
            self._open_stream()

    def _publish_audio_level(self, rms: float) -> None:
        """Send a smoothed, normalized microphone level to the local HUD."""
        now = time.monotonic()
        if now - self._last_audio_publish < 0.08:
            return
        # Speech energy is typically concentrated below 0.2 RMS; compress the
        # range so quiet speech still produces visible motion without clipping.
        normalized = min(1.0, max(0.0, rms / 0.20))
        self._smoothed_audio_level = self._smoothed_audio_level * 0.55 + normalized * 0.45
        self._last_audio_publish = now
        try:
            set_audio_level(self._smoothed_audio_level)
        except Exception:
            logger.debug("Unable to publish microphone level", exc_info=True)

    def record_audio_vad(
        self,
        max_seconds: float = 12.0,
        silence_limit: float | None = None,
        energy_threshold: float = 0.025,
        no_speech_timeout: float | None = None,
    ) -> Path:
        """Record audio dynamically with Voice Activity Detection (VAD).

        Stops automatically when silence is detected post-speech. Reads from
        the persistent stream rather than opening a new one each call.
        """
        chunk_duration = 0.04  # 40ms chunk for responsive VAD
        chunk_size = int(self.sample_rate * chunk_duration)
        silence_limit = self.silence_limit if silence_limit is None else silence_limit
        no_speech_timeout = self.no_speech_timeout if no_speech_timeout is None else no_speech_timeout
        frames: list[np.ndarray] = []

        has_speech_started = False
        silence_start_time = None
        start_time = time.time()

        logger.info("VAD recording started (listening for speech)...")

        with self._stream_lock:
            try:
                self._ensure_stream()
                while True:
                    chunk, overflowed = self.stream.read(chunk_size)
                    if overflowed:
                        logger.debug("Audio stream overflowed")

                    flat_chunk = chunk.flatten()
                    frames.append(flat_chunk)

                    rms = float(np.sqrt(np.mean(flat_chunk ** 2)))
                    self._publish_audio_level(rms)

                    if not has_speech_started:
                        if rms > energy_threshold:
                            has_speech_started = True
                            logger.info("Speech detected (RMS: %.4f)! Recording...", rms)
                        elif (time.time() - start_time) > no_speech_timeout:
                            logger.info("No speech detected after %.1fs.", no_speech_timeout)
                            break
                    else:
                        if rms < energy_threshold:
                            if silence_start_time is None:
                                silence_start_time = time.time()
                            elif (time.time() - silence_start_time) >= silence_limit:
                                logger.info("Silence limit reached (%.1fs). Stopping recording.", silence_limit)
                                break
                        else:
                            silence_start_time = None

                    if (time.time() - start_time) >= max_seconds:
                        logger.info("Max recording duration (%.1fs) reached.", max_seconds)
                        break
            except Exception as exc:
                logger.warning("Stream read error, falling back to standard rec: %s", exc)
                # Stream may be in a bad state — drop it so it gets reopened next time.
                try:
                    if self.stream is not None:
                        self.stream.stop()
                        self.stream.close()
                except Exception:
                    pass
                self.stream = None
                try:
                    set_audio_level(0.0)
                except Exception:
                    logger.debug("Unable to reset microphone level after stream error", exc_info=True)
                return self.record_audio_fixed(seconds=int(max_seconds))

        try:
            set_audio_level(0.0)
        except Exception:
            logger.debug("Unable to reset microphone level", exc_info=True)

        if frames:
            audio_data = np.concatenate(frames, axis=0)
        else:
            audio_data = np.zeros((chunk_size,), dtype=np.float32)

        pcm = np.clip(audio_data, -1.0, 1.0)
        int16 = (pcm * 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", prefix="jarvis_", delete=False) as tmp:
            wav_path = Path(tmp.name)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(int16.tobytes())

        return wav_path

    def record_audio_fixed(self, seconds: int = 11) -> Path:
        """Fixed-duration fallback recording using a standalone one-off stream.

        Used only when the persistent stream has failed and needs a fresh
        one-off recording outside the normal VAD path.
        """
        logger.info("Recording %s seconds of fixed audio", seconds)
        audio = sd.rec(
            int(seconds * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        rms = float(np.sqrt(np.mean(audio.squeeze() ** 2)))
        self._publish_audio_level(rms)
        pcm = np.clip(audio.squeeze(), -1.0, 1.0)
        int16 = (pcm * 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", prefix="jarvis_", delete=False) as tmp:
            wav_path = Path(tmp.name)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(int16.tobytes())
        return wav_path

    def record_audio(self, seconds: int = 11) -> Path:
        return self.record_audio_vad(max_seconds=float(seconds))

    def transcribe_file(self, audio_path: Path, initial_prompt: str | None = None) -> str:
        """Transcribe an existing wav file with single-threaded greedy decoding."""
        logger.info("Transcribing audio file...")
        options = {
            "language": "en",
            "beam_size": 1,
            "condition_on_previous_text": False,
            "vad_filter": True,
        }
        if initial_prompt:
            options["initial_prompt"] = initial_prompt
        segments, _info = self.model.transcribe(str(audio_path), **options)
        text = "".join(segment.text for segment in segments).strip()
        logger.info("Transcription result: %s", text)
        return text

    def listen_and_transcribe(
        self,
        seconds: int = 11,
        silence_limit: float | None = None,
        no_speech_timeout: float | None = None,
        initial_prompt: str | None = None,
    ) -> str:
        """Record audio and return the transcribed text with stage timing logs."""
        started = time.perf_counter()
        wav_path = self.record_audio_vad(
            max_seconds=float(seconds),
            silence_limit=silence_limit,
            no_speech_timeout=no_speech_timeout,
        )
        recorded_ms = (time.perf_counter() - started) * 1000
        try:
            transcribe_started = time.perf_counter()
            text = self.transcribe_file(wav_path, initial_prompt=initial_prompt)
            transcribed_ms = (time.perf_counter() - transcribe_started) * 1000
            logger.info("Voice pipeline timing: capture=%.0fms transcription=%.0fms", recorded_ms, transcribed_ms)
            return text
        finally:
            wav_path.unlink(missing_ok=True)