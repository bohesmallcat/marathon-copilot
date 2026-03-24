"""
env_tax.py — Single authoritative environment tax calculation.

Consolidates the environment tax model from generate_daily_briefing.py and
daily_weather_report.py into one reusable module.

Used by: generate_daily_briefing.py, daily_weather_report.py, daily_weather_email.py.
"""


def calc_env_tax(forecast, *, model, runner=None, is_full=False, distance_km=21.0975):
    """Calculate environment tax based on forecast + model parameters.

    Args:
        forecast: dict with weather data (keys depend on format, see below).
        model: dict of env tax model parameters from race_config.yaml['env_tax_model'].
        runner: dict with runner profile (body_correction, etc). None = no body correction.
        is_full: True for full marathon, False for half.
        distance_km: GPS distance for the race.

    Forecast dict must contain at minimum:
        morning_wind_mph (or morning_wind_kmh)
        start_humidity, finish_humidity (or morning_humidity)
        finish_temp (or late_morning_temp)
        avg_morning_temp (optional, for low-temp correction)
        morning_uv (optional)

    Returns:
        dict with keys: wind, humidity, temperature, uv, turnaround, total
    """
    tax = {}

    # --- Unpack model params ---
    optimal_temp_high = model.get("optimal_temp_high", 15)
    humidity_threshold = model.get("humidity_drift_threshold", 70)
    wind_penalty = model.get("wind_penalty_per_mph", 0.5)
    crosswind = model.get("crosswind_coeff", 0.50)
    shelter = model.get("urban_shelter_reduction", 1.0)  # 1.0 = no shelter
    exposed_km = model.get("exposed_km", 6 if not is_full else 15)
    turnaround = model.get("turnaround_tax", 8 if not is_full else 10)
    body_correction = runner["body_correction"] if runner and "body_correction" in runner else 1.0

    # --- Wind tax ---
    wind_mph = forecast.get("morning_wind_mph", 0)
    if not wind_mph and "morning_wind_kmh" in forecast:
        wind_mph = round(forecast["morning_wind_kmh"] * 0.621371)
    tax["wind"] = round(wind_mph * wind_penalty * crosswind * shelter * exposed_km)

    # --- Humidity tax ---
    # Prefer start/finish pair (generate_daily_briefing format) over single morning_humidity
    if "start_humidity" in forecast and "finish_humidity" in forecast:
        avg_humidity = (forecast["start_humidity"] + forecast["finish_humidity"]) / 2
        start_hum = forecast["start_humidity"]
        finish_hum = forecast["finish_humidity"]
    else:
        avg_humidity = forecast.get("morning_humidity", 50)
        start_hum = avg_humidity
        finish_hum = avg_humidity

    if avg_humidity >= humidity_threshold:
        excess = avg_humidity - humidity_threshold
        penalty_per_km = 3 if excess <= 10 else 7  # +3"/km for 70-80%, +7"/km for >80%

        # Estimate km above threshold
        if start_hum > humidity_threshold > finish_hum:
            frac_above = (start_hum - humidity_threshold) / max(start_hum - finish_hum, 1)
            km_above = frac_above * distance_km
        elif start_hum > humidity_threshold and finish_hum > humidity_threshold:
            km_above = distance_km
        else:
            km_above = 0

        # Low-temp correction (cold air reduces humidity impact)
        avg_temp = forecast.get("avg_morning_temp", 15)
        if avg_temp < 12:
            temp_correction = 0.6
        elif avg_temp < 15:
            temp_correction = 0.75
        else:
            temp_correction = 1.0

        tax["humidity"] = round(penalty_per_km * km_above * temp_correction * body_correction)
    else:
        tax["humidity"] = 0

    # --- Temperature tax ---
    finish_temp = forecast.get("finish_temp", forecast.get("late_morning_temp", 15))
    if finish_temp > optimal_temp_high:
        excess = finish_temp - optimal_temp_high
        penalty_km = 6 if not is_full else 20
        base_tax = excess * 2 * penalty_km / 6
        tax["temperature"] = round(base_tax * body_correction)
    else:
        tax["temperature"] = 0

    # --- UV/sunshine tax ---
    uv = forecast.get("morning_uv", 0)
    avg_temp = forecast.get("avg_morning_temp", 15)
    if uv >= 6 and avg_temp > 12:
        tax["uv"] = round(1 * 5)  # +1"/km for last 5km
    else:
        tax["uv"] = 0

    # --- Turnaround/bends (fixed) ---
    tax["turnaround"] = turnaround

    tax["total"] = sum(tax.values())
    return tax


def calc_env_tax_simple(forecast, is_full=False):
    """Simplified env tax for daily_weather_report.py / daily_weather_email.py.

    Uses the basic model without body correction, UV, or low-temp correction.
    Maintains backward compatibility with the original calc_env_tax logic.
    """
    tax = {}
    wind_mph = forecast.get("morning_wind_mph", 0)
    exposed_km = 15 if is_full else 6
    tax["wind"] = round(wind_mph * 0.5 * 0.5 * exposed_km)

    humidity = forecast.get("morning_humidity", 50)
    if humidity >= 70:
        dist = 42 if is_full else 21
        tax["humidity"] = round((humidity - 70) * 0.5 * dist)
    else:
        tax["humidity"] = 0

    late_temp = forecast.get("late_morning_temp", 15)
    if late_temp > 15:
        excess = late_temp - 15
        penalty_km = 20 if is_full else 6
        tax["temperature"] = round(excess * 2 * penalty_km / 6)
    else:
        tax["temperature"] = 0

    tax["turnaround"] = 10 if is_full else 8
    tax["total"] = sum(tax.values())
    return tax


def assess_signal(env_tax_total, baseline_total, thresholds=None):
    """Determine green/yellow/orange/red signal.

    Args:
        env_tax_total: Current calculated env tax.
        baseline_total: Baseline env tax from battle plan.
        thresholds: dict with green/yellow/orange keys. Defaults to standard.

    Returns:
        Tuple of (signal_text, signal_color).
    """
    if thresholds is None:
        thresholds = {"green": 10, "yellow": 30, "orange": 60}

    delta = abs(env_tax_total - baseline_total)
    if delta < thresholds["green"]:
        return "绿灯：方案有效", "green"
    elif delta < thresholds["yellow"]:
        return "黄灯：微调", "yellow"
    elif delta < thresholds["orange"]:
        return "橙灯：降级考虑", "orange"
    else:
        return "红灯：方案失效", "red"


def assess_conditions(forecast):
    """Rate overall conditions as a label (优/良/中/差).

    Uses the same scoring logic from daily_weather_report.py.
    """
    temp = forecast.get("late_morning_temp", forecast.get("finish_temp", 15))
    humidity = forecast.get("morning_humidity",
                            forecast.get("avg_morning_humidity", 50))
    rain = forecast.get("rain_chance", forecast.get("morning_rain_chance", 0))
    wind = forecast.get("morning_wind_kmh", 10)

    score = 100
    if temp > 15:
        score -= (temp - 15) * 5
    if temp < 5:
        score -= (5 - temp) * 3
    if humidity > 60:
        score -= (humidity - 60) * 1
    if humidity > 70:
        score -= 10
    if rain > 50:
        score -= 10
    if wind > 20:
        score -= 5

    if score >= 90:
        return "优 (Excellent)"
    elif score >= 75:
        return "良好偏优 (Good+)"
    elif score >= 65:
        return "良 (Good)"
    elif score >= 50:
        return "中 (Fair)"
    else:
        return "差 (Poor)"
