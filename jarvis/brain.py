"""LLM brain and tool-calling orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from google import genai
from google.genai.errors import ClientError
from google.genai import types


logger = logging.getLogger(__name__)


@dataclass
class BrainResponse:
    """Structured response from the LLM layer."""

    text: str
    tool_calls: list[dict[str, Any]]


class Brain:
    """Gemini-backed brain with basic tool-calling support and J.A.R.V.I.S. persona."""

    def __init__(self, model_name: str, api_key: str, tools: dict[str, Callable[..., str]]) -> None:
        self.model_name = model_name
        self.tools = tools
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key) if api_key else None

    def describe_image(self, path: Path) -> str:
        """Describe the content of an image file using the vision-capable model."""
        if self.client is None:
            return "I can't analyze images right now, sir — no API key is configured."
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".heic": "image/heic",
        }
        mime_type = mime_map.get(path.suffix.lower(), "image/jpeg")
        image_bytes = path.read_bytes()
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                "Describe what's in this image in two or three concise sentences, "
                "suitable for being read aloud by a voice assistant.",
            ],
        )
        return self._extract_text(response) or "I couldn't make out anything specific in that image, sir."

    def _tool_definitions(self) -> list[types.Tool]:
        specs: dict[str, dict[str, Any]] = {
            "get_weather": {
                "description": "Fetch current weather for a location.",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
            "web_search": {
                "description": "Search the web and summarize the top result.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            "open_application": {
                "description": "Open a desktop application by name.",
                "parameters": {
                    "type": "object",
                    "properties": {"app_name": {"type": "string"}},
                    "required": ["app_name"],
                },
            },
            "set_reminder": {
                "description": "Store a reminder in SQLite.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "time": {"type": "string"},
                    },
                    "required": ["text", "time"],
                },
            },
            "set_alarm": {
                "description": "Store an alarm in SQLite that will speak at the set time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "time": {"type": "string"},
                    },
                    "required": ["text", "time"],
                },
            },
            "get_time": {
                "description": "Return the current local time.",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_system_info": {
                "description": "Return diagnostic info about computer's CPU temp, RAM, battery, and disk.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["all", "cpu", "ram", "battery", "disk"],
                            "description": "Category of system information requested.",
                        }
                    },
                },
            },
            "power_control": {
                "description": "Shut down or restart the computer only after explicit confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["shutdown", "restart"],
                        },
                        "confirm": {
                            "type": "string",
                            "description": "Must be exactly confirm.",
                        },
                    },
                    "required": ["action", "confirm"],
                },
            },
            "play_media": {
                "description": "Play a song or album on Apple Music or Spotify.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "enum": ["apple_music", "spotify"],
                        },
                        "query": {
                            "type": "string",
                            "description": "Song, album, or artist name to search for.",
                        },
                    },
                    "required": ["service", "query"],
                },
            },
            "media_control": {
                "description": "Control media playback with play, pause, next, or previous.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["play", "pause", "next", "previous"],
                        }
                    },
                    "required": ["action"],
                },
            },
            "open_website": {
                "description": "Open a website in the default browser.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The website URL or domain to open, e.g. 'github.com'.",
                        }
                    },
                    "required": ["url"],
                },
            },
            "play_youtube": {
                "description": "Search for and play a video on YouTube in the default browser.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for and play on YouTube.",
                        }
                    },
                    "required": ["query"],
                },
            },
            "find_file": {
                "description": "Find files by name in the user's Documents, Desktop, and Downloads folders.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The file name or part of the file name to search for.",
                        }
                    },
                    "required": ["name"],
                },
            },
            "describe_file": {
                "description": (
                    "Find a file by name and describe or summarize its content. "
                    "Works for text files, Word docs, PDFs, and images."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The file name or part of the file name to look up and describe.",
                        }
                    },
                    "required": ["name"],
                },
            },
            "open_file": {
                "description": "Find a file by name and open it with its default application.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The file name or part of the file name to open.",
                        }
                    },
                    "required": ["name"],
                },
            },
            "remember_fact": {
                "description": (
                    "Store a durable fact about the user for future conversations, such as their name, "
                    "preferences, or other personal details they share. Call this whenever the user tells "
                    "you something worth remembering long-term (e.g. 'my name is Alex', "
                    "'I prefer metric units', 'my dog's name is Max')."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "A short label for the fact, e.g. 'name', 'favorite_team', 'dog_name'.",
                        },
                        "value": {
                            "type": "string",
                            "description": "The fact itself, e.g. 'Alex', 'Real Madrid', 'Max'.",
                        },
                    },
                    "required": ["key", "value"],
                },
            },
        }

        declarations: list[types.FunctionDeclaration] = []
        for name in self.tools:
            spec = specs.get(name, {"description": f"Call the {name} tool.", "parameters": {"type": "object", "properties": {}}})
            declarations.append(
                types.FunctionDeclaration(
                    name=name,
                    description=spec["description"],
                    parameters=spec["parameters"],
                )
            )
        return [types.Tool(function_declarations=declarations)] if declarations else []

    def _messages_to_contents(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        contents: list[dict[str, Any]] = []
        for message in messages:
            role = "model" if message["role"] == "assistant" else message["role"]
            contents.append({"role": role, "parts": [{"text": message["content"]}]})
        return contents

    @staticmethod
    def _extract_text_from_candidate(candidate: Any) -> str:
        parts = getattr(candidate.content, "parts", []) or []
        texts: list[str] = []
        for part in parts:
            text = getattr(part, "text", None)
            if text:
                texts.append(text)
        return "\n".join(texts).strip()

    @staticmethod
    def _extract_text(response: Any) -> str:
        for candidate in getattr(response, "candidates", []) or []:
            text = Brain._extract_text_from_candidate(candidate)
            if text:
                return text
        return ""

    @staticmethod
    def _extract_function_calls(response: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for candidate in getattr(response, "candidates", []) or []:
            for part in getattr(candidate.content, "parts", []) or []:
                call = getattr(part, "function_call", None)
                if call:
                    calls.append({"name": call.name, "args": dict(call.args or {})})
        return calls

    def _run_tool(self, name: str, args: dict[str, Any]) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return f"Tool {name} is not available."
        try:
            return str(tool(**args))
        except TypeError:
            return str(tool(*args.values()))
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("Tool %s failed", name)
            return f"Tool {name} failed: {exc}"

    @staticmethod
    def _tool_result_message(name: str, result: str) -> dict[str, str]:
        return {
            "role": "user",
            "content": f"Tool result for {name}: {result}",
        }

    def generate(self, messages: list[dict[str, str]], facts: dict[str, str] | None = None) -> BrainResponse:
        """Generate a response and run any requested tools.

        `facts` are durable, persisted user details (e.g. name) that should be
        known on every turn, independent of how much rolling chat history is
        included in `messages`.
        """
        if self.client is None:
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return BrainResponse(text=f"Gemini API key is missing. I heard: {last_user}", tool_calls=[])

        tool_results: list[dict[str, Any]] = []
        working_messages = list(messages)

        system_prompt = (
            "You are J.A.R.V.I.S., which stands for Just A Rather Very Intelligent System — "
            "Tony Stark's witty, intelligent, and polite AI assistant. "
            "Always address the user as 'sir' when appropriate. "
            "Provide concise, clear, and direct answers optimized for spoken text-to-speech output. "
            "Never use markdown formatting such as asterisks, bullet points, headers, or backticks — "
            "respond in plain spoken sentences only. "
            "This persona is a character you're playing — never assume the real user is Tony Stark "
            "or has any specific identity unless they've told you directly."
        )

        if facts:
            facts_lines = "; ".join(f"{key}: {value}" for key, value in facts.items())
            system_prompt += (
                f" Known facts about the user, remembered from past conversations: {facts_lines}. "
                "Use these naturally when relevant, without over-mentioning them."
            )

        system_prompt += (
            " Whenever the user shares something durable and worth remembering long-term — their name, "
            "preferences, or similar personal details — call the remember_fact tool immediately, even if "
            "they didn't explicitly say 'remember'. For example, if they say 'I'm Alex' or 'my name is Alex', "
            "call remember_fact with key='name' and value='Alex' right away, then continue the conversation "
            "naturally."
        )

        for _ in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=self._messages_to_contents(working_messages),
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=self._tool_definitions(),
                        temperature=0.4,
                    ),
                )
            except ClientError as exc:
                message = str(exc)
                if "429" in message or "Too Many Requests" in message:
                    return BrainResponse(
                        text="Gemini is busy right now, sir. I’ll keep running locally and try again shortly.",
                        tool_calls=[],
                    )
                raise
            tool_calls = self._extract_function_calls(response)
            if not tool_calls:
                return BrainResponse(text=self._extract_text(response) or "I’m here, sir.", tool_calls=tool_results)

            working_messages.append(
                {
                    "role": "assistant",
                    "content": self._extract_text(response) or "Calling requested tools.",
                }
            )
            for call in tool_calls:
                result = self._run_tool(call["name"], call.get("args", {}))
                tool_results.append({"name": call["name"], "result": result, "args": call.get("args", {})})
                working_messages.append(self._tool_result_message(call["name"], result))

        return BrainResponse(text="I completed the requested tools, sir.", tool_calls=tool_results)