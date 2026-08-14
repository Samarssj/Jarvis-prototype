"""Local speech-to-text using faster-whisper with Voice Activity Detection (VAD)."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
import wave
from pathlib import Path

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

    def __init__(self, model_size: str = "base", sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        # Single CPU thread avoids macOS OpenMP thread locks
        self.model = WhisperModel(model_size, device="cpu", compute_type="float32", cpu_threads=1)

        self._stream_lock = threading.Lock()
        self.stream: sd.InputStream | None = None
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
                    logger.info("Microphone stream closed")

    def _ensure_stream(self) -> None:
        """Re-open the stream if it's missing or was closed unexpectedly."""
        if self.stream is None:
            self._open_stream()

    def record_audio_vad(
        self,
        max_seconds: float = 12.0,
        silence_limit: float = 2.1,
        energy_threshold: float = 0.025,
    ) -> Path:
        """Record audio dynamically with Voice Activity Detection (VAD).

        Stops automatically when silence is detected post-speech. Reads from
        the persistent stream rather than opening a new one each call.
        """
        chunk_duration = 0.05  # 50ms chunk
        chunk_size = int(self.sample_rate * chunk_duration)
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

                    if not has_speech_started:
                        if rms > energy_threshold:
                            has_speech_started = True
                            logger.info("Speech detected (RMS: %.4f)! Recording...", rms)
                        elif (time.time() - start_time) > 4.0:
                            logger.info("No speech detected after 4s.")
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
                return self.record_audio_fixed(seconds=int(max_seconds))

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

    def transcribe_file(self, audio_path: Path) -> str:
        """Transcribe an existing wav file with single-threaded greedy decoding."""
        logger.info("Transcribing audio file...")
        segments, _info = self.model.transcribe(str(audio_path), language="en", beam_size=1)
        text = "".join(segment.text for segment in segments).strip()
        logger.info("Transcription result: %s", text)
        return text

    def listen_and_transcribe(self, seconds: int = 11) -> str:
        """Record audio and return the transcribed text."""
        wav_path = self.record_audio(seconds=seconds)
        try:
            return self.transcribe_file(wav_path)
        finally:
            wav_path.unlink(missing_ok=True)