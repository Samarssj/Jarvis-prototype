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

    def __init__(
        self,
        model_name: str,
        api_key: str,
        tools: dict[str, Callable[..., str]],
        timeout_ms: int = 20000,
        fallback_model_name: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.fallback_model_name = fallback_model_name
        self.tools = tools
        self.api_key = api_key
        self.timeout_ms = timeout_ms
        self.client = (
            genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))
            if api_key
            else None
        )

    def _candidate_models(self) -> list[str]:
        models = [self.model_name]
        if self.fallback_model_name and self.fallback_model_name not in models:
            models.append(self.fallback_model_name)
        return models

    def _generate_content(self, *, contents: list[dict[str, Any]], system_prompt: str, tools: list[types.Tool]) -> Any:
        """Try the configured primary model first, then a fallback model on overload or availability errors."""
        assert self.client is not None
        last_error: Exception | None = None
        for model_name in self._candidate_models():
            try:
                return self.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=tools,
                        temperature=0.4,
                    ),
                )
            except ClientError as exc:
                message = str(exc)
                last_error = exc
                if "429" in message or "Too Many Requests" in message or "404" in message or "not found" in message.lower():
                    logger.warning("Gemini model %s unavailable or overloaded; trying fallback if available.", model_name)
                    continue
                raise
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if any(token in message for token in ("429", "too many requests", "rate", "quota", "unavailable", "not found")):
                    logger.warning("Gemini model %s failed (%s); trying fallback if available.", model_name, exc)
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("No Gemini models are configured.")

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
        response = self._generate_content(
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                "Describe what's in this image in two or three concise sentences, "
                "suitable for being read aloud by a voice assistant.",
            ],
            system_prompt="",
            tools=[],
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
        content = getattr(candidate, "content", None)
        if not content: return ""
        parts = getattr(content, "parts", []) or []
        texts: list[str] = []
        for part in parts:
            text = getattr(part, "text", None)
            if text:
                texts.append(text)
        return "\n".join(texts).strip()

    @staticmethod
    def _extract_text(response: Any) -> str:
        text_parts = []
        # Support for Live API chunks (LiveServerMessage -> LiveServerContent -> ModelTurn)
        if getattr(response, "server_content", None) and getattr(response.server_content, "model_turn", None):
            for part in getattr(response.server_content.model_turn, "parts", []) or []:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
        
        # Standard REST API chunks
        for candidate in getattr(response, "candidates", []) or []:
            text = Brain._extract_text_from_candidate(candidate)
            if text:
                text_parts.append(text)
                
        return "\n".join(text_parts).strip()

    @staticmethod
    def _extract_function_calls(response: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        # Support for Live API function calls (LiveServerMessage -> LiveClientToolCall)
        if getattr(response, "tool_call", None):
            for call in getattr(response.tool_call, "function_calls", []) or []:
                if getattr(call, "name", None):
                    calls.append({"name": call.name, "args": dict(call.args or {})})
                    
        # Standard REST API chunks
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            if not content: continue
            for part in getattr(content, "parts", []) or []:
                call = getattr(part, "function_call", None)
                if call:
                    calls.append({"name": call.name, "args": dict(call.args or {})})
        return calls

    def _run_tool(self, name: str, args: dict[str, Any]) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return f"TOOL_ERROR: Tool {name} is not available."
        try:
            try:
                raw_result = tool(**args)
            except TypeError:
                # Preserve compatibility with legacy positional-only callables,
                # while still catching errors raised by the fallback invocation.
                raw_result = tool(*args.values())
            if raw_result is None:
                return f"TOOL_ERROR: Tool {name} returned no result."
            result = str(raw_result).strip()
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("Tool %s failed", name)
            return f"TOOL_ERROR: Tool {name} failed: {exc}"
        if result.startswith(("TOOL_OK:", "TOOL_ERROR:", "TOOL_RESULT:")):
            return result
        return f"TOOL_RESULT: {result}"

    @staticmethod
    def _tool_result_message(name: str, result: str) -> dict[str, str]:
        return {
            "role": "user",
            "content": f"Tool result for {name}: {result}",
        }

    @staticmethod
    def _grounded_tool_response(tool_results: list[dict[str, Any]]) -> str:
        """Return a safe spoken response based only on exact tool output."""
        if not tool_results:
            return "I don't have a tool result to report, sir."

        failures = [
            str(item["result"]).removeprefix("TOOL_ERROR:").strip()
            for item in tool_results
            if str(item["result"]).startswith("TOOL_ERROR:")
        ]
        if failures:
            return "I couldn't complete that, sir. " + " ".join(failures)

        confirmations = [
            str(item["result"]).removeprefix("TOOL_OK:").strip()
            for item in tool_results
            if str(item["result"]).startswith("TOOL_OK:")
        ]
        observations = [
            str(item["result"]).removeprefix("TOOL_RESULT:").strip()
            for item in tool_results
            if str(item["result"]).startswith("TOOL_RESULT:")
        ]
        parts: list[str] = []
        if confirmations:
            parts.append("Confirmed, sir. " + " ".join(confirmations))
        if observations:
            parts.append("Here is what I found, sir. " + " ".join(observations))
        return " ".join(parts) if parts else "The tool returned no grounded content, sir."

    def generate(self, messages: list[dict[str, str]], facts: dict[str, str] | None = None) -> BrainResponse:
        """Generate a response and run any requested tools.

        `facts` are durable, persisted user details (e.g. name) that should be
        known on every turn, independent of how much rolling chat history is
        included in `messages`.
        """
        if self.client is None:
            return BrainResponse(
                text=(
                    "Gemini API key is missing, sir. Add GEMINI_API_KEY to the .env file in this Jarvis project "
                    "and restart me. No command was executed."
                ),
                tool_calls=[],
            )

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
                "or has any specific identity unless they've told you directly. "
                "Tool grounding is mandatory: when a tool is called, base any claim about that action only on "
                "the exact tool result. A result beginning with TOOL_OK means it succeeded; TOOL_ERROR means it "
                "failed. Never say an alarm, reminder, file operation, application launch, or other tool action "
                "was completed when the tool result does not confirm it. If a tool fails, say so plainly."
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
                response = self._generate_content(
                    contents=self._messages_to_contents(working_messages),
                    system_prompt=system_prompt,
                    tools=self._tool_definitions(),
                )
            except ClientError as exc:
                message = str(exc)
                logger.warning("Gemini request failed: %s", message)
                return BrainResponse(
                    text=(
                        "Gemini is temporarily unavailable, sir. I could not safely run that request. "
                        "Local file commands remain available."
                    ),
                    tool_calls=tool_results,
                )
            except Exception as exc:
                # google-genai raises ServerError/APIError variants for 5xx
                # responses; keep the voice loop alive and never claim a tool ran.
                logger.warning("Gemini provider error: %s", exc)
                return BrainResponse(
                    text=(
                        "Gemini is temporarily unavailable, sir. I could not safely run that request. "
                        "Local file commands remain available."
                    ),
                    tool_calls=tool_results,
                )
            tool_calls = self._extract_function_calls(response)
            if not tool_calls:
                text = self._extract_text(response)
                if text:
                    return BrainResponse(text=text, tool_calls=tool_results)
                fallback = self._grounded_tool_response(tool_results) if tool_results else "I’m here, sir."
                return BrainResponse(text=fallback, tool_calls=tool_results)

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

            # Every tool action is acknowledged directly from its verified result.
            # This prevents a second model turn from embellishing a success or
            # hiding a failure, while non-tool turns still use the model normally.
            return BrainResponse(text=self._grounded_tool_response(tool_results), tool_calls=tool_results)

    def _generate_content_stream(self, *, contents: list[dict[str, Any]], system_prompt: str, tools: list[types.Tool]) -> Any:
        assert self.client is not None
        last_error: Exception | None = None
        for model_name in self._candidate_models():
            try:
                stream = self.client.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=tools,
                        temperature=0.4,
                    ),
                )
                stream_iter = iter(stream)
                try:
                    first_chunk = next(stream_iter)
                except StopIteration:
                    return
                
                yield first_chunk
                yield from stream_iter
                return
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if any(token in message for token in ("429", "too many requests", "rate", "quota", "unavailable", "not found", "policy", "1008", "1007")):
                    logger.warning("Gemini model %s failed; trying fallback.", model_name)
                    continue
                raise
        
        if last_error is not None:
            raise last_error
        raise RuntimeError("No Gemini models are configured.")

    def generate_stream(self, messages: list[dict[str, str]], facts: dict[str, str] | None = None):
        """Yield generated sentences as they arrive, returning a final BrainResponse when done."""
        if self.client is None:
            yield "Gemini API key is missing, sir. Add GEMINI_API_KEY to the .env file in this Jarvis project and restart me."
            return BrainResponse(text="Gemini API key is missing.", tool_calls=[])

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
            "or has any specific identity unless they've told you directly. "
            "Tool grounding is mandatory: when a tool is called, base any claim about that action only on "
            "the exact tool result. A result beginning with TOOL_OK means it succeeded; TOOL_ERROR means it "
            "failed. Never say an action was completed when the tool result does not confirm it."
        )
        if facts:
            facts_lines = "; ".join(f"{key}: {value}" for key, value in facts.items())
            system_prompt += f" Known facts about the user: {facts_lines}."
        system_prompt += " Whenever the user shares something durable, call remember_fact immediately."

        import re

        for _ in range(3):
            try:
                stream = self._generate_content_stream(
                    contents=self._messages_to_contents(working_messages),
                    system_prompt=system_prompt,
                    tools=self._tool_definitions(),
                )
            except Exception as exc:
                logger.warning("Gemini streaming error: %s", exc)
                msg = "Gemini is temporarily unavailable, sir."
                yield msg
                return BrainResponse(text=msg, tool_calls=tool_results)

            text_buffer = ""
            full_text = ""
            tool_calls = []

            try:
                for chunk in stream:
                    calls = self._extract_function_calls(chunk)
                    if calls:
                        tool_calls.extend(calls)
                    
                    text = self._extract_text(chunk)
                    if text:
                        text_buffer += text
                        full_text += text
                        # Split into sentences based on punctuation followed by space
                        while True:
                            match = re.search(r'(?<=[.!?])\s+', text_buffer)
                            if match:
                                boundary = match.end()
                                sentence = text_buffer[:boundary].strip()
                                if sentence:
                                    yield sentence
                                text_buffer = text_buffer[boundary:]
                            else:
                                break
            except Exception as exc:
                logger.warning("Gemini streaming iteration error: %s", exc)
                if not full_text:
                    msg = "Gemini is temporarily unavailable, sir."
                    yield msg
                    return BrainResponse(text=msg, tool_calls=tool_results)
                # If we already yielded some text, just break and return what we have
                pass

            if text_buffer.strip():
                yield text_buffer.strip()

            if not tool_calls:
                if not full_text and tool_results:
                    fallback = self._grounded_tool_response(tool_results)
                    yield fallback
                    return BrainResponse(text=fallback, tool_calls=tool_results)
                return BrainResponse(text=full_text, tool_calls=tool_results)

            working_messages.append({"role": "assistant", "content": full_text or "Calling requested tools."})
            for call in tool_calls:
                result = self._run_tool(call["name"], call.get("args", {}))
                tool_results.append({"name": call["name"], "result": result, "args": call.get("args", {})})
                working_messages.append(self._tool_result_message(call["name"], result))

            # Return grounded tool response directly without second stream loop
            final_text = self._grounded_tool_response(tool_results)
            yield final_text
            return BrainResponse(text=final_text, tool_calls=tool_results)

        fallback = self._grounded_tool_response(tool_results)
        yield fallback
        return BrainResponse(text=fallback, tool_calls=tool_results)
