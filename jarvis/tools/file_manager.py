"""Safe file search, inspection, and opening tools."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SAFE_ROOTS = [Path.home() / "Documents", Path.home() / "Desktop", Path.home() / "Downloads"]
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json", ".py", ".js", ".html", ".css"}
DOCX_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic"}
MAX_RESULTS = 5
MAX_TEXT_CHARS = 4000


def _search_folders(name: str) -> list[Path]:
    """Case-insensitive search in safe roots only."""
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
        except OSError:
            logger.warning("Could not fully search %s", root, exc_info=True)
    matches.sort(key=lambda p: len(p.name))
    return matches[:MAX_RESULTS]


def _clarification_prompt(name: str, matches: list[Path], action: str) -> str:
    numbered = "; ".join(f"{i + 1}. {p.name} in {p.parent.name}" for i, p in enumerate(matches))
    return f"I found {len(matches)} files matching '{name}', sir — {numbered}. Which one would you like me to {action}?"


def _resolve_match(name: str, action: str) -> tuple[Path | None, str | None]:
    matches = _search_folders(name)
    if not matches:
        return None, f"No file matching '{name}' was found in Documents, Desktop, or Downloads."
    if len(matches) == 1:
        return matches[0], None
    exact = [p for p in matches if p.stem.lower() == name.strip().lower()]
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
