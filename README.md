# Jarvis

Jarvis is a local Python voice assistant inspired by Tony Stark's J.A.R.V.I.S. — *Just A Rather Very Intelligent System*. It runs continuously in the background, wakes up on hearing "Jarvis," and handles everything from web lookups to file management, hands-free.

Architecture:

```
Mic input -> Wake-word detection -> Speech-to-Text (VAD) -> LLM brain with tools -> Text-to-Speech -> Speaker output
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```
pip install -r requirements.txt
pip install python-docx pypdf
```

3. Create a `.env` file from `.env.example`.
4. Add your API keys and local settings.

## Environment

Required keys and settings:

* `GEMINI_API_KEY` for Gemini access
* `OPENWEATHER_API_KEY` for weather lookups
* `JARVIS_WAKE_WORD` — word Jarvis listens for while idle (default: `jarvis`)
* `JARVIS_MODEL`
* `JARVIS_MODEL_TIMEOUT_MS` — maximum time allowed for one model request before Jarvis returns to a recoverable listening state.
* `JARVIS_TTS_VOICE`
* `JARVIS_TTS_RATE`
* `JARVIS_TTS_PITCH`
* `JARVIS_SAMPLE_RATE`
* `JARVIS_STT_MODEL` — Whisper model used for local transcription; `tiny.en` is the low-latency default and can be changed to `base.en` for higher accuracy.
* `JARVIS_VAD_SILENCE_LIMIT` — seconds of silence after speech before recording stops.
* `JARVIS_VAD_NO_SPEECH_TIMEOUT` — maximum initial wait for speech before returning to the wake-word loop.
* `JARVIS_RECORD_SECONDS` — max length of a single command recording
* `JARVIS_SPLASH_DURATION_MS`
* `JARVIS_DB_PATH`

## Run

```
python -m jarvis.main
```

## How It Listens

Jarvis runs a continuous loop with two listening modes:

* **Idle / wake-word mode** — short 4-second bursts, checking for "Jarvis" (or close mishearings like "jarves," "charvis," and natural variants like "hey Jarvis," "ok Jarvis"). Fuzzy matching handles imperfect transcriptions so you don't need to say the word with perfect clarity.
* **Command mode** — once woken, Jarvis replies "Yes, sir?" and listens for your actual request using Voice Activity Detection: it starts recording when it hears speech, and stops automatically after ~2 seconds of silence, up to a `JARVIS_RECORD_SECONDS` hard ceiling.

A single persistent microphone stream is kept open for the lifetime of the app, rather than reopening the mic for every recording — this avoids flaky hangs that can occur from rapid stream open/close cycles on macOS. The VAD reads short 40 ms chunks, ends quickly after silence, and publishes microphone intensity through a coalescing background writer so HUD telemetry never blocks audio capture.

If Jarvis asks a follow-up/clarifying question (e.g. disambiguating between two similarly named files), it skips the wake-word requirement for your next reply — you can just answer directly.

## Supported Tools

* `get_weather(location)`
* `web_search(query)`
* `open_application(app_name)`
* `play_media(service, query)`
* `media_control(action)`
* `set_reminder(text, time)`
* `set_alarm(text, time)`
* `get_time()`
* `get_system_info(ram, cpu temp, battery, disk)`
* `power_control(action, confirm)`
* `open_website(url)`
* `play_youtube(query)`
* `find_file(name)`
* `describe_file(name)`
* `open_file(name)`
* `remember_fact(key, value)`

## Power Control

Jarvis can request shutdown or restart on macOS, but only with an explicit confirmation token and administrator authorization.

* `power_control("shutdown", "confirm")`
* `power_control("restart", "confirm")`

If the confirmation token is anything other than `confirm`, Jarvis refuses the request. If macOS rejects the request, Jarvis reports the failure instead of pretending the action succeeded.

## Media Playback

Jarvis can search and start playback on macOS using:

* `play_media("apple_music", "song name")`
* `play_media("spotify", "song name")`
* `media_control("play")`
* `media_control("pause")`
* `media_control("next")`
* `media_control("previous")`

Apple Music works best for local library items. Spotify uses the app's search URI to look up the track or album.

## Browser & YouTube

Jarvis can open any website by name or URL, and play YouTube videos directly:

* `open_website("github.com")` — opens the site in your default browser.
* `play_youtube("song or video name")` — finds the top matching video and opens it directly at the watch page (not just a search results list), so it starts playing right away.

## File Access

Jarvis can locate, describe, and open files by name — scoped only to `Documents`, `Desktop`, and `Downloads` for safety. It never searches system folders or your full home directory.

* `find_file("resume")` — lists matching files.
* `describe_file("resume")` — reads and summarizes the content. Supports plain text, code files, `.docx`, `.pdf`, and images (described via Gemini's vision capability).
* `open_file("resume")` — opens the file with its default macOS application.

**Ambiguity handling**: if multiple files match a name closely (e.g. `resume.docx` and `resume_draft.docx`), Jarvis asks which one you mean instead of guessing, and listens for your answer immediately without requiring the wake word again.

## Memory & Persistent Facts

Jarvis keeps two layers of memory, both stored in SQLite:

* **Rolling conversation history** — the last several exchanges, used for natural multi-turn context within a session.
* **Durable facts** — things like your name or preferences, stored permanently via `remember_fact` and re-injected into every conversation regardless of how much time or chat history has passed. Jarvis proactively calls this whenever you share something worth remembering long-term (e.g. "I'm Alex"), without needing you to say "remember" explicitly.

## Alarm

Jarvis can store alarms in SQLite and speak them when the scheduled time is reached.

* `set_alarm("Take medicine", "2026-08-06T21:00:00+00:00")`

Jarvis accepts either ISO-8601 timestamps in UTC or common phrases like:

* `in 30 minutes`
* `in 2 hours`
* `tomorrow at 7`
* `9 pm`

## Going Offline

If you say things like:

* `turn yourself off`
* `I don't need anything else`
* `stop listening`
* `bye Jarvis`

Jarvis will say goodbye, close its microphone stream cleanly, and stop its listening loop.

## Startup Animation

When Jarvis launches, it opens a blue animated splash screen inspired by the JARVIS HUD in your default browser and keeps it visible while Jarvis is running, reflecting live status (sleeping, listening, thinking, speaking). Splash updates run as non-blocking background calls, so they don't add latency to the main loop.

When you tell Jarvis to go offline, the splash shuts down with it.

## Speech Output

Jarvis strips Markdown formatting (asterisks, headers, bullets, links, code fences) from any text before speaking it, so LLM-generated responses read naturally aloud instead of pronouncing stray symbols. The system prompt also instructs the model to avoid Markdown in the first place.

## Notes

The STT module uses `faster-whisper` for offline transcription and captures microphone input with `sounddevice` through a single persistent stream. The brain layer runs on Gemini with full tool-calling support, and TTS uses `edge-tts` for natural-sounding speech. For faster delivery, the default TTS rate is `+0%`, which is the fastest valid "normal" rate value for `edge-tts`.

If you want a working default today, use `gemini-flash-latest` in `JARVIS_MODEL`. The `gemini-3.1-pro-preview` model exists, but it may be quota-limited depending on your account.

## Roadmap

This is an ongoing side project — planned upgrades include smarter multi-turn context handling, more tools, and a tighter local-first architecture.
