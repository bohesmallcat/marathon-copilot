"""
weather_client.py — Shared weather fetching and parsing for Marathon Copilot.

Consolidates wttr.in API calls with retry logic and consistent parsing.

Used by:
  - generate_daily_briefing.py (race-day weather briefing)
  - daily_weather_report.py (multi-race weather report)
  - training-weekly skill (7-day training scheduling weather)
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


# ---------------------------------------------------------------------------
# Parse — 7-day training scheduling weather
# ---------------------------------------------------------------------------

def parse_for_training_schedule(data):
    """Extract 7-day weather for weekly training scheduling decisions.

    Unlike race-day parsing (focused on morning race hours), this provides
    full-day conditions relevant to flexible training scheduling:
    - Morning window (06:00-09:00): for early runners
    - Afternoon window (15:00-18:00): for after-work runners
    - Overall daily rating for training suitability

    Returns:
        list of dicts (up to 3 days from wttr.in free tier), each with:
            date, weekday, condition,
            temp_morning, temp_afternoon, temp_min, temp_max,
            humidity_morning, humidity_afternoon,
            wind_kmh, wind_dir,
            rain_chance_morning, rain_chance_afternoon, rain_chance_max,
            uv,
            run_rating (优/良/中/差),
            run_rating_score (0-100),
            best_window ("morning" / "afternoon" / "either" / "avoid"),
            notes (list of advisory strings)
    """
    days = []
    for day_data in data.get("weather", []):
        hourly = day_data["hourly"]

        # Time windows
        morning = [h for h in hourly if int(h["time"]) in (600, 900)]
        afternoon = [h for h in hourly if int(h["time"]) in (1500, 1800)]
        all_hours = hourly

        # Morning conditions
        if morning:
            temp_m = _avg_int(morning, "tempC")
            hum_m = _avg_int(morning, "humidity")
            rain_m = max(int(h.get("chanceofrain", 0)) for h in morning)
        else:
            temp_m = int(day_data["mintempC"])
            hum_m = 50
            rain_m = 0

        # Afternoon conditions
        if afternoon:
            temp_a = _avg_int(afternoon, "tempC")
            hum_a = _avg_int(afternoon, "humidity")
            rain_a = max(int(h.get("chanceofrain", 0)) for h in afternoon)
        else:
            temp_a = int(day_data["maxtempC"])
            hum_a = 50
            rain_a = 0

        rain_max = max(int(h.get("chanceofrain", 0)) for h in all_hours) if all_hours else 0
        uv = max(int(h.get("uvIndex", 0)) for h in all_hours) if all_hours else 0
        wind_kmh = _avg_int(morning or all_hours[:4], "windspeedKmph")
        wind_dir = (morning or all_hours[:1] or [{"winddir16Point": "N"}])[0]["winddir16Point"]
        desc = (morning[0]["weatherDesc"][0]["value"] if morning
                else all_hours[3]["weatherDesc"][0]["value"] if len(all_hours) > 3
                else "N/A")

        # Compute run suitability rating
        score, notes = _compute_run_rating(
            temp_m, temp_a, hum_m, hum_a, rain_m, rain_a, rain_max, wind_kmh, uv,
        )
        best_window = _pick_best_window(temp_m, temp_a, rain_m, rain_a, wind_kmh)

        if score >= 85:
            rating = "优"
        elif score >= 65:
            rating = "良"
        elif score >= 45:
            rating = "中"
        else:
            rating = "差"

        days.append({
            "date": day_data["date"],
            "condition": desc,
            "temp_morning": temp_m,
            "temp_afternoon": temp_a,
            "temp_min": int(day_data["mintempC"]),
            "temp_max": int(day_data["maxtempC"]),
            "humidity_morning": hum_m,
            "humidity_afternoon": hum_a,
            "wind_kmh": wind_kmh,
            "wind_dir": wind_dir,
            "rain_chance_morning": rain_m,
            "rain_chance_afternoon": rain_a,
            "rain_chance_max": rain_max,
            "uv": uv,
            "run_rating": rating,
            "run_rating_score": score,
            "best_window": best_window,
            "notes": notes,
        })

    return days


def _avg_int(hours, key):
    """Average of an integer field across hourly entries."""
    vals = [int(h[key]) for h in hours]
    return round(sum(vals) / len(vals)) if vals else 0


def _compute_run_rating(temp_m, temp_a, hum_m, hum_a, rain_m, rain_a, rain_max, wind_kmh, uv):
    """Score 0-100 for overall training suitability + advisory notes."""
    score = 100
    notes = []

    # Temperature scoring (best: 5-15°C morning)
    best_temp = temp_m
    if best_temp > 28:
        score -= 30
        notes.append("高温警告：建议室内或清晨训练")
    elif best_temp > 22:
        score -= 15
        notes.append("偏热：降低强度，注意补水")
    elif best_temp > 15:
        score -= 5
    elif best_temp < -5:
        score -= 25
        notes.append("严寒：考虑室内替代训练")
    elif best_temp < 0:
        score -= 10
        notes.append("低温：注意保暖，延长热身")

    # Rain scoring
    if rain_max >= 80:
        score -= 25
        notes.append("大概率降雨：建议调整训练日")
    elif rain_max >= 50:
        score -= 10
        notes.append("有降雨风险：备好替代方案")

    # Humidity scoring
    avg_hum = (hum_m + hum_a) / 2
    if avg_hum > 85:
        score -= 15
        notes.append("高湿度：心率易漂移，降低配速目标")
    elif avg_hum > 75:
        score -= 5

    # Wind scoring
    if wind_kmh > 40:
        score -= 20
        notes.append("强风：不适合间歇训练，建议避风路线")
    elif wind_kmh > 25:
        score -= 5

    # UV scoring
    if uv >= 8:
        score -= 10
        notes.append("紫外线极强：戴帽+防晒，避开 10:00-14:00")
    elif uv >= 6:
        score -= 5
        notes.append("紫外线较强：注意防晒")

    return max(score, 0), notes


def _pick_best_window(temp_m, temp_a, rain_m, rain_a, wind_kmh):
    """Recommend best time window for running."""
    m_ok = rain_m < 50 and 0 <= temp_m <= 25
    a_ok = rain_a < 50 and 0 <= temp_a <= 25

    if not m_ok and not a_ok:
        return "avoid"
    if m_ok and a_ok:
        # Prefer cooler window
        if abs(temp_m - 10) <= abs(temp_a - 10):
            return "either"  # morning slightly better but both fine
        return "either"
    if m_ok:
        return "morning"
    return "afternoon"
