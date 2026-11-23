# AI-written

"""Step 2: map weather -> mood with Gemini, ready to feed RecipeAPI.

Setup:
    pip install requests
    export GEMINI_API_KEY="your-key"   # from https://aistudio.google.com/apikey

Run the checks (no network or API key needed, everything is mocked):
    python weather_mood.py
"""
import json
import os
from unittest.mock import MagicMock, patch

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Verify the current model name at https://ai.google.dev/gemini-api/docs/models
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

MOODS = ["warming", "cooling", "comforting", "refreshing", "light", "hearty"]

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

# Every key get_current_weather() must return, even when Open-Meteo omits data.
WEATHER_KEYS = [
    "temperature_f", "feels_like_f", "humidity_pct", "precipitation_in",
    "cloud_cover_pct", "wind_mph", "is_day", "weather_code",
    "condition", "temp_band", "summary", "ui_label",
]


# ---------------------------------------------------------------------------
# Weather (Open-Meteo), hardened so all keys always exist
# ---------------------------------------------------------------------------
def temperature_band(temp_f):
    if temp_f is None:
        return None
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
    """Fetch current weather. Always returns every key in WEATHER_KEYS
    (value is None when Open-Meteo didn't supply it)."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join([
            "temperature_2m", "apparent_temperature", "relative_humidity_2m",
            "precipitation", "weather_code", "cloud_cover", "wind_speed_10m", "is_day",
        ]),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    resp.raise_for_status()
    cur = resp.json().get("current") or {}

    code = cur.get("weather_code")
    condition = WMO_CODES.get(code) if code is not None else None
    temp = cur.get("temperature_2m")
    feels = cur.get("apparent_temperature")
    band = temperature_band(feels if feels is not None else temp)

    parts = [p for p in (band, condition) if p]
    is_day = cur.get("is_day")

    return {
        "temperature_f": temp,
        "feels_like_f": feels,
        "humidity_pct": cur.get("relative_humidity_2m"),
        "precipitation_in": cur.get("precipitation"),
        "cloud_cover_pct": cur.get("cloud_cover"),
        "wind_mph": cur.get("wind_speed_10m"),
        "is_day": bool(is_day) if is_day is not None else None,
        "weather_code": code,
        "condition": condition,
        "temp_band": band,
        "summary": " and ".join(parts) if parts else "unknown weather",
        "ui_label": f"{condition} day" if condition else "day",
    }


# ---------------------------------------------------------------------------
# Prompt builder: skips any field that is None
# ---------------------------------------------------------------------------
def build_mood_prompt(weather: dict) -> str:
    """Build the text prompt. Lines for missing (None) values are left out."""
    lines = []

    def add(label, value, fmt="{}"):
        if value is not None:
            lines.append(f"- {label}: {fmt.format(value)}")

    add("Conditions", weather.get("summary"))
    add("Temperature", weather.get("temperature_f"), "{}°F")
    add("Feels like", weather.get("feels_like_f"), "{}°F")
    add("Humidity", weather.get("humidity_pct"), "{}%")
    add("Wind", weather.get("wind_mph"), "{} mph")
    add("Cloud cover", weather.get("cloud_cover_pct"), "{}%")
    add("Precipitation", weather.get("precipitation_in"), "{} in")
    if weather.get("is_day") is not None:
        lines.append(f"- Time of day: {'daytime' if weather['is_day'] else 'nighttime'}")

    return (
        "Here is the current weather for the user's location:\n"
        + "\n".join(lines)
        + "\n\nPick the single mood of meal that best fits this weather, "
        "and give 3 to 5 short search keywords (dishes, ingredients, or "
        "cuisines) a recipe API could use."
    )


# ---------------------------------------------------------------------------
# Gemini call (the actual step 2 request)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You match weather to meals. Respond only with JSON that follows the schema. "
    "Cold or snowy weather suggests warming or hearty meals; hot weather suggests "
    "cooling, refreshing, or light meals; rainy or gloomy weather suggests "
    "comforting meals."
)

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "mood": {"type": "STRING", "format": "enum", "enum": MOODS},
        "keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "reason": {"type": "STRING"},
    },
    "required": ["mood", "keywords", "reason"],
}


def map_weather_to_mood(weather: dict) -> dict:
    """POST to Gemini and return {"mood", "keywords", "reason"}."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set the GEMINI_API_KEY environment variable.")

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": build_mood_prompt(weather)}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    resp = requests.post(
        GEMINI_URL,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()

    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    result = json.loads(text)
    if result.get("mood") not in MOODS:
        raise ValueError(f"Unexpected mood from Gemini: {result.get('mood')!r}")
    return result


def get_recipe_mood(weather: dict) -> dict:
    """Step 2 entry point. Pass the output of get_current_weather()."""
    return map_weather_to_mood(weather)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def check_missing_keys():
    """Weather function returns every key, even when Open-Meteo omits fields."""
    scenarios = {
        "full": {"current": {
            "temperature_2m": 41.0, "apparent_temperature": 37.0,
            "relative_humidity_2m": 80, "precipitation": 0.0, "weather_code": 3,
            "cloud_cover": 100, "wind_speed_10m": 6.0, "is_day": 1}},
        "partial": {"current": {"temperature_2m": 28.0, "wind_speed_10m": 12.0}},
        "empty current": {"current": {}},
        "no current block": {},
    }
    ok = True
    for name, body in scenarios.items():
        fake = MagicMock()
        fake.raise_for_status.return_value = None
        fake.json.return_value = body
        with patch("requests.get", return_value=fake):
            result = get_current_weather(37.83191, -122.21592)
        missing = [k for k in WEATHER_KEYS if k not in result]
        passed = not missing
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'} missing keys [{name}]: {missing or 'none missing'}")
    return ok


def check_none_values():
    """Prompt builder skips humidity=None but keeps the other lines."""
    weather = {
        "temperature_f": 28, "feels_like_f": 19, "humidity_pct": None,
        "precipitation_in": 0.1, "cloud_cover_pct": 90, "wind_mph": 12,
        "is_day": True, "weather_code": 73, "condition": "snowy",
        "temp_band": "freezing", "summary": "freezing and snowy",
        "ui_label": "snowy day",
    }
    prompt = build_mood_prompt(weather)
    print("\n--- generated prompt ---\n" + prompt + "\n------------------------")

    results = {
        'no "None" anywhere': "None" not in prompt,
        "no humidity line": "humidity" not in prompt.lower(),
        "has temperature line": "Temperature: 28°F" in prompt,
        "has wind line": "Wind: 12 mph" in prompt,
    }
    for name, passed in results.items():
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    return all(results.values())


if __name__ == "__main__":
    a = check_missing_keys()
    b = check_none_values()
    print("\nALL CHECKS PASSED" if a and b else "\nSOME CHECKS FAILED")
    # Live usage once your key is set:
    #   w = get_current_weather(37.83191, -122.21592)
    #   print(get_recipe_mood(w))

"""
PASS no "None" anywhere
PASS no humidity line
PASS has temperature line
PASS has wind line
"""