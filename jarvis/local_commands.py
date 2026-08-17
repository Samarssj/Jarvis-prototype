"""Local command shortcuts that must not depend on a remote model."""

from __future__ import annotations

import re

from jarvis.tools.file_manager import find_file, open_file


def extract_file_command(user_text: str) -> tuple[str, str] | None:
    """Extract common open/find file commands from a speech transcript."""
    normalized = re.sub(r"\s+", " ", user_text.casefold()).strip()
    if not normalized:
        return None

    action_match = re.search(r"\b(open|find|locate|show)\b", normalized)
    if not action_match or not re.search(r"\b(file|document|resume)\b", normalized):
        return None

    action = "open" if action_match.group(1) in {"open", "show"} else "find"
    name_match = re.search(
        r"\b(?:named|called|name[d]? as|as|to)\s+(.+?)\s*[.!?]*$",
        normalized,
    )
    if name_match:
        name = name_match.group(1).strip()
    else:
        remainder = normalized[action_match.end() :]
        remainder = re.sub(r"^\s+(?:the\s+)?(?:file|document|resume)\b", "", remainder).strip()
        name = remainder.strip(" .,!?\")")

    if not name or name in {"the file", "a file", "it"}:
        return None
    return action, name


def run_file_command(action: str, name: str) -> str:
    """Execute a local file action and return a grounded spoken response."""
    result = open_file(name) if action == "open" else find_file(name)
    if result.startswith("TOOL_OK:"):
        return "Confirmed, sir. " + result.removeprefix("TOOL_OK:").strip()
    if result.startswith("TOOL_ERROR:"):
        return "I couldn't complete that, sir. " + result.removeprefix("TOOL_ERROR:").strip()
    return "Here is what I found, sir. " + result.removeprefix("TOOL_RESULT:").strip()
