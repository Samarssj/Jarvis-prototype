# Jarvis

Jarvis is a local Python voice assistant inspired by Tony Stark style workflows. It is structured as a modular pipeline:

Mic input -> Speech-to-Text -> LLM brain with tools -> Text-to-Speech -> Speaker output

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file from `.env.example`.
4. Add your API keys and local settings.

## Environment

Required keys and settings:

- `GEMINI_API_KEY` for Gemini access
- `OPENWEATHER_API_KEY` for weather lookups
- `JARVIS_MODEL`
- `JARVIS_TTS_VOICE`
- `JARVIS_TTS_RATE`
- `JARVIS_TTS_PITCH`
- `JARVIS_SAMPLE_RATE`
- `JARVIS_RECORD_SECONDS`
- `JARVIS_SPLASH_DURATION_MS`
- `JARVIS_DB_PATH`

## Run

```bash
python -m jarvis.main
```

## Supported Tools

- `get_weather(location)`
- `web_search(query)`
- `open_application(app_name)`
- `play_media(service, query)`
- `media_control(action)`
- `set_reminder(text, time)`
- `set_alarm(text, time)`
- `get_time()`
- `get_system_info(ram, cpu temp, battery, disk)`
- `power_control(action, confirm)`
- `turn yourself off`
- `i don’t need anything else`
- `stop listening`

## Power Control

Jarvis can request shutdown or restart on macOS, but only with an explicit confirmation token and administrator authorization.

- `power_control("shutdown", "confirm")`
- `power_control("restart", "confirm")`

If the confirmation token is anything other than `confirm`, Jarvis refuses the request.
If macOS rejects the request, Jarvis now reports the failure instead of pretending the action succeeded.

## Media Playback

Jarvis can search and start playback on macOS using:

- `play_media("apple_music", "song name")`
- `play_media("spotify", "song name")`
- `media_control("play")`
- `media_control("pause")`
- `media_control("next")`
- `media_control("previous")`

Apple Music works best for local library items. Spotify uses the app's search URI to look up the track or album.

## Alarm

Jarvis can store alarms in SQLite and speak them when the scheduled time is reached.

- `set_alarm("Take medicine", "2026-08-06T21:00:00+00:00")`

Jarvis accepts either ISO-8601 timestamps in UTC or common phrases like:

- `in 30 minutes`
- `in 2 hours`
- `tomorrow at 7`
- `9 pm`

## Going Offline

If you say things like:

- `turn yourself off`
- `I don't need anything else`
- `stop listening`
- `bye Jarvis`

Jarvis will say goodbye and stop its listening loop.

## Startup Animation

When Jarvis launches, it opens a blue animated splash screen inspired by the JARVIS HUD in your default browser and keeps it visible while Jarvis is running.

When you tell Jarvis to go offline, the splash shuts down with it.

## Notes

The STT module uses `faster-whisper` for offline transcription and captures microphone input with `sounddevice`.
The current brain and TTS layers are scaffolded and ready for Gemini and Edge TTS integration.
For a faster delivery, the default TTS rate is `+0%`, which is the fastest valid "normal" rate value for `edge-tts`.

If you want a working default today, use `gemini-flash-latest` in `JARVIS_MODEL`. The `gemini-3.1-pro-preview` model exists, but it may be quota-limited depending on your account.
