"""File lookup, content description, and opening — scoped to safe user folders."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Only these folders are ever searched. Deliberately excludes system/root paths.
SAFE_ROOTS = [
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
]

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json", ".py", ".js", ".html", ".css"}
DOCX_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic"}

MAX_RESULTS = 5
MAX_TEXT_CHARS = 4000


def _search_folders(name: str) -> list[Path]:
    """Case-insensitive search for files whose name contains the query, in safe roots only."""
    name = name.strip().lower()
    matches: list[Path] = []
    for root in SAFE_ROOTS:
        if not root.exists():
            continue
        try:
            for path in root.rglob("*"):
                if path.is_file() and name in path.name.lower():
                    matches.append(path)
                    if len(matches) >= MAX_RESULTS * 3:
                        break
        except PermissionError:
            continue
    # Prefer closer/shorter matches first (more likely to be the intended file)
    matches.sort(key=lambda p: len(p.name))
    return matches[:MAX_RESULTS]


def _clarification_prompt(name: str, matches: list[Path], action: str) -> str:
    """Build a spoken question asking the user to pick between ambiguous matches."""
    numbered = "; ".join(f"{i + 1}. {p.name} in {p.parent.name}" for i, p in enumerate(matches))
    return (
        f"I found {len(matches)} files matching '{name}', sir — {numbered}. "
        f"Which one would you like me to {action}?"
    )


def _resolve_match(name: str, action: str) -> tuple[Path | None, str | None]:
    """Search for a file and decide whether it's safe to act on automatically.

    Returns (path, None) if there's a single confident match, ready to act on.
    Returns (None, clarification_text) if the user should be asked to disambiguate.
    Returns (None, not_found_text) if nothing matched.
    """
    matches = _search_folders(name)
    if not matches:
        return None, f"I couldn't find any file matching '{name}' in your Documents, Desktop, or Downloads, sir."

    if len(matches) == 1:
        return matches[0], None

    # Multiple matches: only auto-pick if one is a clearly exact/near-exact match
    # (e.g. searching "resume" and one file is literally "resume.docx").
    exact = [p for p in matches if p.stem.lower() == name.strip().lower()]
    if len(exact) == 1:
        return exact[0], None

    # Otherwise, genuinely ambiguous — ask instead of guessing.
    return None, _clarification_prompt(name, matches, action)


def find_file(name: str) -> str:
    """Find files by name in Documents, Desktop, and Downloads."""
    if not name or not name.strip():
        return "What's the file called, sir?"
    matches = _search_folders(name)
    if not matches:
        return f"I couldn't find any file matching '{name}' in your Documents, Desktop, or Downloads, sir."
    if len(matches) == 1:
        return f"Found one match, sir: {matches[0].name} in {matches[0].parent}."
    listing = "; ".join(f"{p.name} in {p.parent.name}" for p in matches)
    return f"I found {len(matches)} matches, sir: {listing}."


def _read_text_file(path: Path) -> str:
    try:
        text = path.read_text(errors="ignore")
    except Exception as exc:
        return f"I couldn't read that file, sir: {exc}"
    text = text.strip()
    if not text:
        return f"{path.name} appears to be empty, sir."
    snippet = text[:MAX_TEXT_CHARS]
    return snippet


def _read_docx_file(path: Path) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        return "I can't read Word documents right now, sir — the python-docx package isn't installed."
    try:
        document = docx.Document(str(path))
        text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    except Exception as exc:
        return f"I couldn't read that document, sir: {exc}"
    if not text.strip():
        return f"{path.name} appears to be empty, sir."
    return text[:MAX_TEXT_CHARS]


def _read_pdf_file(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "I can't read PDFs right now, sir — the pypdf package isn't installed."
    try:
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:10])
    except Exception as exc:
        return f"I couldn't read that PDF, sir: {exc}"
    if not text.strip():
        return f"{path.name} doesn't appear to contain extractable text, sir — it may be a scanned document."
    return text[:MAX_TEXT_CHARS]


def _describe_image(path: Path, brain_describe_fn) -> str:
    """Describe image content. Requires a describe function backed by a vision-capable model."""
    if brain_describe_fn is None:
        return f"{path.name} is an image, sir, but I don't currently have image understanding wired up."
    try:
        return brain_describe_fn(path)
    except Exception as exc:
        logger.exception("Failed to describe image")
        return f"I couldn't analyze that image, sir: {exc}"


def describe_file(name: str, brain_describe_fn=None) -> str:
    """Find a file by name and return a description/summary of its content.

    If multiple files match ambiguously, asks the user to clarify instead of guessing.
    """
    path, message = _resolve_match(name, action="describe")
    if path is None:
        return message  # either "not found" or a clarification question

    ext = path.suffix.lower()

    if ext in IMAGE_EXTENSIONS:
        description = _describe_image(path, brain_describe_fn)
        return f"{path.name}: {description}"
    if ext in TEXT_EXTENSIONS:
        content = _read_text_file(path)
        return f"Here's what's in {path.name}, sir: {content}"
    if ext in DOCX_EXTENSIONS:
        content = _read_docx_file(path)
        return f"Here's what's in {path.name}, sir: {content}"
    if ext in PDF_EXTENSIONS:
        content = _read_pdf_file(path)
        return f"Here's what's in {path.name}, sir: {content}"

    return f"I found {path.name}, sir, but I don't know how to read that file type ({ext})."


def open_file(name: str) -> str:
    """Find a file by name and open it with its default application.

    If multiple files match ambiguously, asks the user to clarify instead of guessing.
    """
    path, message = _resolve_match(name, action="open")
    if path is None:
        return message  # either "not found" or a clarification question

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif sys.platform.startswith("win"):
            import os
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
        logger.info("Opened file: %s", path)
        return f"Opening {path.name}, sir."
    except Exception as exc:
        logger.exception("Failed to open file")
        return f"I couldn't open that file, sir: {exc}"