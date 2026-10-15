"""Fetch current and hourly forecast weather for Mumbai from Open-Meteo."""
from datetime import datetime, timezone
import requests

URL = "https://api.open-meteo.com/v1/forecast"
MUMBAI = {"latitude": 19.0760, "longitude": 72.8777}

def fetch_weather():
    params = {
        **MUMBAI,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation,precipitation_probability,wind_speed_10m",
        "forecast_days": 2,
        "timezone": "Asia/Kolkata",
    }
    response = requests.get(URL, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    payload["_cityflow_fetched_at_utc"] = datetime.now(timezone.utc).isoformat()
    return payload
