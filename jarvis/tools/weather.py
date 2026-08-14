"""Weather tool."""

from __future__ import annotations

import os
from typing import Any

import requests


def get_weather(location: str) -> str:
    """Fetch current weather via OpenWeatherMap."""
    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    if not api_key:
        return "Weather API key is not configured."

    geo = requests.get(
        "https://api.openweathermap.org/geo/1.0/direct",
        params={"q": location, "limit": 1, "appid": api_key},
        timeout=15,
    ).json()
    if not geo:
        return f"Could not find location: {location}"
    lat, lon = geo[0]["lat"], geo[0]["lon"]
    data = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
        timeout=15,
    ).json()
    return (
        f"{data['name']}: {data['weather'][0]['description']}, "
        f"{data['main']['temp']}°C, feels like {data['main']['feels_like']}°C"
    )
