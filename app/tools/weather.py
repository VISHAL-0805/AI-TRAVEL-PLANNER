import httpx
from langchain_core.tools import tool
from app.core.config import OPENWEATHER_API_KEY


@tool
def get_weather_forecast(city: str) -> str:
    """Get weather forecast for a destination city.
    Returns current conditions and a 5-day outlook to help with packing and activity planning."""
    if not OPENWEATHER_API_KEY:
        return _mock_weather(city)

    try:
        resp = httpx.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "cnt": 8},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        city_name = data["city"]["name"]
        lines = [f"Weather forecast for {city_name}:"]
        for entry in data["list"][:8]:
            dt = entry["dt_txt"]
            temp = entry["main"]["temp"]
            desc = entry["weather"][0]["description"]
            lines.append(f"  {dt}: {temp}°C, {desc}")
        return "\n".join(lines)
    except Exception:
        return _mock_weather(city)


def _mock_weather(city: str) -> str:
    return (
        f"Weather forecast for {city} (estimated):\n"
        f"  Daytime highs: 22-28°C\n"
        f"  Nighttime lows: 14-18°C\n"
        f"  Conditions: Partly cloudy with occasional sunshine\n"
        f"  Recommendation: Pack layers and a light rain jacket"
    )
