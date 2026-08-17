"""Robust wake-word matching for speech-recognition transcripts."""

from __future__ import annotations

import difflib
import re


DEFAULT_WAKE_ALIASES = (
    "jarvis",
    "hey jarvis",
    "ok jarvis",
    "okay jarvis",
    "yo jarvis",
    # Common faster-whisper variants observed in real transcripts.
    "javis",
    "javi",
    "jervis",
    "jarves",
    "jarviss",
    "hey javis",
    "hey javi",
    "job is",
    "major",
    "hey jud",
)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", text.casefold()).strip()


def _close(token: str, candidate: str, threshold: float = 0.74) -> bool:
    if token == candidate:
        return True
    if len(token) < 3 or len(candidate) < 3:
        return False
    return difflib.SequenceMatcher(None, token, candidate).ratio() >= threshold


def is_wake_word_match(
    text: str,
    wake_word: str = "jarvis",
    threshold: float = 0.74,
    aliases: tuple[str, ...] = DEFAULT_WAKE_ALIASES,
) -> bool:
    """Return whether a transcript contains the wake word or a close variant.

    Matching is intentionally limited to the configured wake word, known
    transcript variants, and short contiguous phrase windows. It does not use
    unrestricted fuzzy matching over the entire transcript, which would create
    false wake-ups from unrelated speech.
    """
    normalized = _normalize(text)
    configured = _normalize(wake_word)
    if not normalized or not configured:
        return False

    alias_texts = {_normalize(alias) for alias in aliases if _normalize(alias)}
    alias_texts.add(configured)
    # "major" is a useful observed one-word transcription of Jarvis, but it
    # must only match as the whole utterance (or an explicit hey-prefixed form).
    if normalized == "major" or normalized == "hey major":
        return True
    for alias in alias_texts - {"major"}:
        if re.search(rf"(?:^|\s){re.escape(alias)}(?:$|\s)", normalized):
            return True

    tokens = normalized.split()
    candidates = tuple(alias_texts - {"major"})
    for index in range(len(tokens)):
        for width in (1, 2, 3):
            window = tokens[index : index + width]
            if len(window) != width:
                continue
            phrase = " ".join(window)
            compact = "".join(window)
            for candidate in candidates:
                candidate_compact = candidate.replace(" ", "")
                if _close(phrase, candidate, threshold) or _close(compact, candidate_compact, threshold):
                    return True

    return False
