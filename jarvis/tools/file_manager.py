"""Safe file search, inspection, and opening tools."""

from __future__ import annotations

import difflib
import logging
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)

SAFE_ROOTS = [Path.home() / "Documents", Path.home() / "Desktop", Path.home() / "Downloads"]
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json", ".py", ".js", ".html", ".css"}
DOCX_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic"}
MAX_RESULTS = 5
MAX_TEXT_CHARS = 4000

# Common suffixes are removed from the primary comparison form so a request for
# "Samar ATS Resume" can match both Samar_ATS_Resume.pdf.pdf and
# Samar_ATS_Resume.pdf-3.pdf. The full filename remains a secondary form, so a
# request that explicitly includes an extension still works.
KNOWN_FILE_EXTENSIONS = {
    ".csv",
    ".css",
    ".doc",
    ".docx",
    ".gif",
    ".heic",
    ".html",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".log",
    ".md",
    ".pdf",
    ".png",
    ".py",
    ".txt",
    ".webp",
}
_FILENAME_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_VOWELS = re.compile(r"[aeiouy]+")


def _normalize_filename_text(value: str) -> str:
    """Normalize punctuation, separators, accents, and case for filename input."""
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return _FILENAME_NON_ALNUM.sub(" ", ascii_value.casefold()).strip()


def _filename_tokens(value: str) -> list[str]:
    normalized = _normalize_filename_text(value)
    return normalized.split() if normalized else []


def _phonetic_token_key(token: str) -> str:
    """Create a conservative speech-oriented key for one filename token.

    Speech recognition often changes vowels and duplicates consonants. Collapsing
    repeated letters and vowel runs makes variants such as "summer" and
    "samar" comparable, while the matcher still requires multiple surrounding
    tokens or a strong overall filename score before accepting a result.
    """
    collapsed = re.sub(r"(.)\1+", r"\1", token)
    return _VOWELS.sub("a", collapsed)


def _token_similarity(query_token: str, candidate_token: str) -> float:
    if query_token == candidate_token:
        return 1.0
    if (
        len(re.sub(r"[aeiouy]", "", query_token)) >= 2
        and _phonetic_token_key(query_token) == _phonetic_token_key(candidate_token)
    ):
        return 0.94
    return difflib.SequenceMatcher(None, query_token, candidate_token).ratio()


def _strip_known_extensions(filename: str) -> str:
    """Return a filename with one or more known extensions removed."""
    value = filename
    while Path(value).suffix.casefold() in KNOWN_FILE_EXTENSIONS:
        value = Path(value).stem
    return value


def _candidate_name_forms(path: Path) -> tuple[str, ...]:
    """Return comparison forms that cover base names, suffixes, and full names."""
    base = _strip_known_extensions(path.name)
    forms = (base, path.stem, path.name)
    return tuple(dict.fromkeys(_normalize_filename_text(form) for form in forms if form))


def _name_similarity(query: str, candidate: str) -> float:
    """Score literal and speech-recognition-friendly similarity from 0.0 to 1.0."""
    query_normalized = _normalize_filename_text(query)
    candidate_normalized = _normalize_filename_text(candidate)
    if not query_normalized or not candidate_normalized:
        return 0.0
    if query_normalized in candidate_normalized:
        return 1.0

    query_compact = query_normalized.replace(" ", "")
    candidate_compact = candidate_normalized.replace(" ", "")
    compact_score = difflib.SequenceMatcher(None, query_compact, candidate_compact).ratio()

    query_tokens = query_normalized.split()
    candidate_tokens = candidate_normalized.split()
    token_scores = [
        max(_token_similarity(query_token, candidate_token) for candidate_token in candidate_tokens)
        for query_token in query_tokens
    ]
    token_coverage = sum(token_scores) / len(token_scores)
    if len(query_tokens) == 1:
        # A single spoken token may stand for one token in a longer filename;
        # do not penalize it merely because the filename has other words.
        return max(compact_score, token_coverage)

    order_score = difflib.SequenceMatcher(
        None, " ".join(query_tokens), " ".join(candidate_tokens)
    ).ratio()
    return max(compact_score, token_coverage * 0.75 + order_score * 0.25)


def _minimum_match_score(query: str) -> float:
    """Use a stricter threshold for one-word fuzzy requests."""
    return 0.86 if len(_filename_tokens(query)) == 1 else 0.80


def _search_folders(name: str) -> list[Path]:
    """Search safe roots using literal, separator-insensitive, and fuzzy matching."""
    query = _normalize_filename_text(name)
    if not query:
        return []

    scored_matches: list[tuple[float, Path]] = []
    minimum_score = _minimum_match_score(query)
    for root in SAFE_ROOTS:
        if not root.exists():
            continue
        try:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                score = max(
                    (_name_similarity(query, form) for form in _candidate_name_forms(path)),
                    default=0.0,
                )
                if score >= minimum_score:
                    scored_matches.append((score, path))
        except OSError:
            logger.warning("Could not fully search %s", root, exc_info=True)

    scored_matches.sort(key=lambda item: (-item[0], len(item[1].name), item[1].name.casefold()))
    return [path for _, path in scored_matches[:MAX_RESULTS]]


def _clarification_prompt(name: str, matches: list[Path], action: str) -> str:
    numbered = "; ".join(f"{i + 1}. {p.name} in {p.parent.name}" for i, p in enumerate(matches))
    return f"I found {len(matches)} files matching '{name}', sir — {numbered}. Which one would you like me to {action}?"


def _resolve_match(name: str, action: str) -> tuple[Path | None, str | None]:
    matches = _search_folders(name)
    if not matches:
        return None, f"No file matching '{name}' was found in Documents, Desktop, or Downloads."
    if len(matches) == 1:
        return matches[0], None
    query = _normalize_filename_text(name)
    exact = [
        p
        for p in matches
        if any(_normalize_filename_text(form) == query for form in _candidate_name_forms(p))
    ]
    if len(exact) == 1:
        return exact[0], None
    return None, _clarification_prompt(name, matches, action)


def find_file(name: str) -> str:
    """Find files by name in Documents, Desktop, and Downloads."""
    if not name or not name.strip():
        return "TOOL_ERROR: A file name is required."
    matches = _search_folders(name)
    if not matches:
        return f"TOOL_ERROR: No file matching '{name}' was found in Documents, Desktop, or Downloads."
    if len(matches) == 1:
        return f"TOOL_OK: Found one match: {matches[0].name} in {matches[0].parent}."
    listing = "; ".join(f"{p.name} in {p.parent.name}" for p in matches)
    return f"TOOL_OK: Found {len(matches)} matching files: {listing}."


def _read_text_file(path: Path) -> str:
    try:
        text = path.read_text(errors="ignore").strip()
    except OSError as exc:
        return f"TOOL_ERROR: Could not read {path.name}: {exc}."
    if not text:
        return f"TOOL_RESULT: {path.name} appears to be empty."
    return f"TOOL_RESULT: {text[:MAX_TEXT_CHARS]}"


def _read_docx_file(path: Path) -> str:
    try:
        import docx
    except ImportError:
        return "TOOL_ERROR: Word-document support is not installed."
    try:
        document = docx.Document(str(path))
        text = "\n".join(p.text for p in document.paragraphs if p.text.strip()).strip()
    except Exception as exc:
        return f"TOOL_ERROR: Could not read {path.name}: {exc}."
    if not text:
        return f"TOOL_RESULT: {path.name} appears to be empty."
    return f"TOOL_RESULT: {text[:MAX_TEXT_CHARS]}"


def _read_pdf_file(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "TOOL_ERROR: PDF support is not installed."
    try:
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:10]).strip()
    except Exception as exc:
        return f"TOOL_ERROR: Could not read {path.name}: {exc}."
    if not text:
        return f"TOOL_ERROR: {path.name} has no extractable text; it may be a scanned document."
    return f"TOOL_RESULT: {text[:MAX_TEXT_CHARS]}"


def _describe_image(path: Path, brain_describe_fn) -> str:
    if brain_describe_fn is None:
        return "TOOL_ERROR: Image understanding is not configured."
    try:
        description = brain_describe_fn(path)
    except Exception as exc:
        logger.exception("Failed to describe image")
        return f"TOOL_ERROR: Could not analyze {path.name}: {exc}."
    if not description or not str(description).strip():
        return f"TOOL_ERROR: Image analysis returned no description for {path.name}."
    return f"TOOL_RESULT: {description}"


def describe_file(name: str, brain_describe_fn=None) -> str:
    """Find a file and return grounded content or an explicit failure."""
    if not name or not name.strip():
        return "TOOL_ERROR: A file name is required."
    path, message = _resolve_match(name, action="describe")
    if path is None:
        return f"TOOL_ERROR: {message}"

    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        content = _describe_image(path, brain_describe_fn)
    elif ext in TEXT_EXTENSIONS:
        content = _read_text_file(path)
    elif ext in DOCX_EXTENSIONS:
        content = _read_docx_file(path)
    elif ext in PDF_EXTENSIONS:
        content = _read_pdf_file(path)
    else:
        return f"TOOL_ERROR: I found {path.name}, but cannot read file type '{ext or 'unknown'}'."

    if content.startswith("TOOL_ERROR:"):
        return content
    return f"TOOL_OK: {path.name}: {content.split(': ', 1)[1] if ': ' in content else content}"


def open_file(name: str) -> str:
    """Find a file and open it with its default application."""
    if not name or not name.strip():
        return "TOOL_ERROR: A file name is required."
    path, message = _resolve_match(name, action="open")
    if path is None:
        return f"TOOL_ERROR: {message}"

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=True)
        elif sys.platform.startswith("win"):
            import os
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
        logger.info("Opened file: %s", path)
        return f"TOOL_OK: Open request for {path.name} was accepted by the operating system."
    except (OSError, subprocess.SubprocessError) as exc:
        logger.exception("Failed to open file")
        return f"TOOL_ERROR: I couldn't open {path.name}: {exc}."
