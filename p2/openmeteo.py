# AI-written

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
ZIP_URL = "https://api.zippopotam.us/us/{zip_code}"  # free, no API key

# WMO weather codes used by Open-Meteo
WMO_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy",
    51: "drizzly", 53: "drizzly", 55: "drizzly",
    56: "freezing drizzle", 57: "freezing drizzle",
    61: "rainy", 63: "rainy", 65: "heavy rain",
    66: "freezing rain", 67: "freezing rain",
    71: "snowy", 73: "snowy", 75: "heavy snow", 77: "snowy",
    80: "rainy", 81: "rainy", 82: "heavy rain",
    85: "snowy", 86: "heavy snow",
    95: "stormy", 96: "stormy", 99: "stormy",
}


def zip_to_coordinates(zip_code: str) -> tuple[float, float]:
    """Convert a US ZIP code to (latitude, longitude)."""
    resp = requests.get(ZIP_URL.format(zip_code=zip_code), timeout=10)
    if resp.status_code == 404:
        raise ValueError(f"Unknown ZIP code: {zip_code}")
    resp.raise_for_status()
    place = resp.json()["places"][0]
    return float(place["latitude"]), float(place["longitude"])


def temperature_band(temp_f: float) -> str:
    if temp_f <= 32:
        return "freezing"
    if temp_f <= 50:
        return "cold"
    if temp_f <= 68:
        return "mild"
    if temp_f <= 85:
        return "warm"
    return "hot"


def get_current_weather(latitude: float, longitude: float) -> dict:
    """Fetch current weather from Open-Meteo, in US units."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "precipitation",
            "weather_code",
            "cloud_cover",
            "wind_speed_10m",
            "is_day",
        ]),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    resp.raise_for_status()
    cur = resp.json()["current"]

    condition = WMO_CODES.get(cur["weather_code"], "unknown")
    band = temperature_band(cur["apparent_temperature"])

    return {
        "temperature_f": cur["temperature_2m"],
        "feels_like_f": cur["apparent_temperature"],
        "humidity_pct": cur["relative_humidity_2m"],
        "precipitation_in": cur["precipitation"],
        "cloud_cover_pct": cur["cloud_cover"],
        "wind_mph": cur["wind_speed_10m"],
        "is_day": bool(cur["is_day"]),
        "weather_code": cur["weather_code"],
        "condition": condition,                      # e.g. "overcast"
        "temp_band": band,                           # e.g. "cold"
        "summary": f"{band} and {condition}",        # feed this to your LLM / UI
        "ui_label": f"{condition} day",              # "Here are your recipes for today's ..."
    }


def get_weather_for_zip(zip_code: str) -> dict:
    """Step 1 of the flow: ZIP -> coordinates -> weather."""
    lat, lon = zip_to_coordinates(zip_code)
    return get_current_weather(lat, lon)


if __name__ == "__main__":
    # Check 1: Oakland, CA (looking for cloudy)
    oakland = get_current_weather(37.83191, -122.21592)
    print("Oakland:", oakland["summary"], "| cloud cover:", oakland["cloud_cover_pct"], "%")

    # Check 2: Seattle, WA (looking for 40-45°F)
    seattle = get_current_weather(47.6615, -122.2811)
    print("Seattle:", seattle["summary"], "|", seattle["temperature_f"], "°F")

    # Full flow with a ZIP code
    print("94611:", get_weather_for_zip("94611")["summary"])

"""
Oakland: cold and clear | cloud cover: 0 %
Seattle: cold and overcast | 42.8 °F
94611: cold and clear
"""
