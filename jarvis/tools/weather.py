from __future__ import annotations

import os

import requests


def get_weather(location: str) -> str:
    """Fetch current weather and report only validated API results."""
    location = location.strip()
    if not location:
        return "TOOL_ERROR: A location is required for weather."
    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    if not api_key:
        return "TOOL_ERROR: Weather API key is not configured."

    try:
        geo_response = requests.get(
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": location, "limit": 1, "appid": api_key},
            timeout=10,
        )
        geo_response.raise_for_status()
        geo = geo_response.json()
        if not isinstance(geo, list) or not geo:
            return f"TOOL_ERROR: Could not find a weather location for '{location}'."
        lat, lon = geo[0]["lat"], geo[0]["lon"]

        weather_response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
            timeout=10,
        )
        weather_response.raise_for_status()
        data = weather_response.json()
        name = data["name"]
        description = data["weather"][0]["description"]
        temperature = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        return f"TOOL_OK: {name}: {description}, {temperature}°C, feels like {feels_like}°C."
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        return f"TOOL_ERROR: Weather lookup failed for '{location}' because {exc}."
