"""
weather_client.py — Shared weather fetching and parsing for Marathon Copilot.

Consolidates wttr.in API calls with retry logic and consistent parsing.
Used by: generate_daily_briefing.py, daily_weather_report.py, daily_weather_email.py.
"""

import time
import urllib3

try:
    import requests
except ImportError:
    raise ImportError("pip install requests")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_weather(city="Shanghai", retries=3, backoff=2.0, timeout=30):
    """Fetch weather JSON from wttr.in with retry logic.

    Args:
        city: City name for wttr.in query.
        retries: Number of retry attempts (default 3).
        backoff: Base backoff seconds, doubled on each retry.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON dict from wttr.in.

    Raises:
        RuntimeError: If all retries fail.
    """
    url = f"https://wttr.in/{city}?format=j1"
    last_err = None
    wait = backoff
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=timeout, verify=False)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(f"[WARN] wttr.in attempt {attempt} failed: {e}. Retrying in {wait:.0f}s...")
                time.sleep(wait)
                wait *= 2
    raise RuntimeError(f"wttr.in failed after {retries} attempts: {last_err}")


# ---------------------------------------------------------------------------
# Parse — race-relevant hourly data
# ---------------------------------------------------------------------------

def parse_hourly_for_race(data):
    """Extract race-relevant weather from wttr.in JSON.

    Returns dict with:
        current: dict of current conditions
        forecasts: list of per-day dicts with morning averages, wind, humidity, etc.
    """
    current = data["current_condition"][0]
    result = {
        "current": {
            "temp_c": int(current["temp_C"]),
            "feels_like_c": int(current["FeelsLikeC"]),
            "humidity": int(current["humidity"]),
            "pressure_hpa": int(current["pressure"]),
            "wind_kmh": int(current["windspeedKmph"]),
            "wind_mph": round(int(current["windspeedKmph"]) * 0.621371),
            "wind_dir": current["winddir16Point"],
            "desc": current["weatherDesc"][0]["value"],
            "uv": int(current.get("uvIndex", 0)),
        },
        "forecasts": [],
    }

    for day_data in data.get("weather", []):
        hourly = day_data["hourly"]
        morning = [h for h in hourly if int(h["time"]) in [600, 900]]
        late_morning = [h for h in hourly if int(h["time"]) in [1200]]
        seven_am = [h for h in hourly if int(h["time"]) == 600]
        nine_am = [h for h in hourly if int(h["time"]) == 900]

        if morning:
            avg_temp = sum(int(h["tempC"]) for h in morning) / len(morning)
            avg_humidity = sum(int(h["humidity"]) for h in morning) / len(morning)
            avg_wind_kmh = sum(int(h["windspeedKmph"]) for h in morning) / len(morning)
        else:
            avg_temp = (int(day_data["mintempC"]) + int(day_data["maxtempC"])) / 2
            avg_humidity = 50
            avg_wind_kmh = 10

        start_temp = int(seven_am[0]["tempC"]) if seven_am else int(day_data["mintempC"])
        start_humidity = int(seven_am[0]["humidity"]) if seven_am else int(avg_humidity)
        finish_temp = int(nine_am[0]["tempC"]) if nine_am else int(day_data["maxtempC"])
        finish_humidity = int(nine_am[0]["humidity"]) if nine_am else int(avg_humidity)

        late_temp = int(late_morning[0]["tempC"]) if late_morning else int(day_data["maxtempC"])

        rain_chances = [int(h.get("chanceofrain", 0)) for h in hourly]
        morning_rain = max(int(h.get("chanceofrain", 0)) for h in morning) if morning else 0

        morning_uv = max(int(h.get("uvIndex", 0)) for h in morning) if morning else 0

        fc = {
            "date": day_data["date"],
            "min_temp": int(day_data["mintempC"]),
            "max_temp": int(day_data["maxtempC"]),
            "start_temp": start_temp,
            "finish_temp": finish_temp,
            "avg_morning_temp": round(avg_temp, 1),
            "late_morning_temp": late_temp,
            "start_humidity": start_humidity,
            "finish_humidity": finish_humidity,
            "avg_morning_humidity": round(avg_humidity),
            "morning_wind_kmh": round(avg_wind_kmh),
            "morning_wind_mph": round(avg_wind_kmh * 0.621371),
            "wind_dir": morning[0]["winddir16Point"] if morning else "N",
            "morning_rain_chance": morning_rain,
            "max_rain_chance": max(rain_chances) if rain_chances else 0,
            "morning_uv": morning_uv,
            "desc": (morning[0]["weatherDesc"][0]["value"]
                     if morning
                     else "N/A"),
            "pressure": int(morning[0]["pressure"]) if morning else 1013,
        }
        result["forecasts"].append(fc)

    return result


def parse_weather_simple(data):
    """Simpler parse — compatible with daily_weather_report.py / daily_weather_email.py.

    Returns same structure but uses integer division and slightly different field names
    to maintain backward compatibility.
    """
    current = data["current_condition"][0]
    result = {
        "current": {
            "temp_c": int(current["temp_C"]),
            "feels_like_c": int(current["FeelsLikeC"]),
            "humidity": int(current["humidity"]),
            "pressure_hpa": int(current["pressure"]),
            "wind_kmh": int(current["windspeedKmph"]),
            "wind_mph": round(int(current["windspeedKmph"]) * 0.621371),
            "wind_dir": current["winddir16Point"],
            "desc": current["weatherDesc"][0]["value"],
            "uv": current.get("uvIndex", "N/A"),
        },
        "forecasts": [],
    }

    for day in data.get("weather", []):
        hourly_data = day["hourly"]
        morning_hours = [h for h in hourly_data if int(h["time"]) in [600, 900]]
        late_morning = [h for h in hourly_data if int(h["time"]) in [1200]]

        if morning_hours:
            avg_temp = sum(int(h["tempC"]) for h in morning_hours) // len(morning_hours)
            avg_humidity = sum(int(h["humidity"]) for h in morning_hours) // len(morning_hours)
            avg_wind = sum(int(h["windspeedKmph"]) for h in morning_hours) // len(morning_hours)
        else:
            avg_temp = (int(day["mintempC"]) + int(day["maxtempC"])) // 2
            avg_humidity = 50
            avg_wind = 10

        late_temp = int(late_morning[0]["tempC"]) if late_morning else int(day["maxtempC"])

        forecast = {
            "date": day["date"],
            "min_temp": int(day["mintempC"]),
            "max_temp": int(day["maxtempC"]),
            "morning_avg_temp": avg_temp,
            "late_morning_temp": late_temp,
            "morning_humidity": avg_humidity,
            "morning_wind_kmh": avg_wind,
            "morning_wind_mph": round(avg_wind * 0.621371),
            "wind_dir": morning_hours[0]["winddir16Point"] if morning_hours else "N",
            "desc": hourly_data[3]["weatherDesc"][0]["value"] if len(hourly_data) > 3 else "N/A",
            "rain_chance": max(int(h.get("chanceofrain", 0)) for h in hourly_data),
            "pressure": int(hourly_data[3]["pressure"]) if len(hourly_data) > 3 else 1013,
        }
        result["forecasts"].append(forecast)

    return result


def extract_race_day_forecast(data, race_date):
    """Extract a single race-day forecast from parsed weather data.

    Compatible with daily_weather_email.py's extract_race_day_forecast.
    Uses parse_weather_simple format internally.

    Args:
        data: Raw wttr.in JSON (not parsed).
        race_date: datetime.date for the race.

    Returns:
        dict with morning/late-morning averages, or None if not in range.
    """
    race_date_str = race_date.strftime("%Y-%m-%d")
    for day in data.get("weather", []):
        if day["date"] == race_date_str:
            hourly = day["hourly"]
            morning = [h for h in hourly if int(h["time"]) in [600, 900]]
            noon = [h for h in hourly if int(h["time"]) in [1200]]

            if morning:
                avg_temp = sum(int(h["tempC"]) for h in morning) // len(morning)
                avg_hum = sum(int(h["humidity"]) for h in morning) // len(morning)
                avg_wind = sum(int(h["windspeedKmph"]) for h in morning) // len(morning)
            else:
                avg_temp = (int(day["mintempC"]) + int(day["maxtempC"])) // 2
                avg_hum = 50
                avg_wind = 10

            late_temp = int(noon[0]["tempC"]) if noon else int(day["maxtempC"])
            wind_dir = morning[0]["winddir16Point"] if morning else "N/A"

            return {
                "date": day["date"],
                "desc": hourly[3]["weatherDesc"][0]["value"] if len(hourly) > 3 else "N/A",
                "min_temp": int(day["mintempC"]),
                "max_temp": int(day["maxtempC"]),
                "morning_avg_temp": avg_temp,
                "late_morning_temp": late_temp,
                "morning_humidity": avg_hum,
                "morning_wind_kmh": avg_wind,
                "morning_wind_mph": round(avg_wind * 0.621371),
                "wind_dir": wind_dir,
                "rain_chance": max(int(h.get("chanceofrain", 0)) for h in hourly),
                "pressure": int(hourly[3]["pressure"]) if len(hourly) > 3 else 1013,
            }
    return None
