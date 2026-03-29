"""
training_calculator.py — Marathon Copilot Core Algorithm Library (Python)

Single authoritative Python module for ALL marathon copilot calculations.
Ports every algorithm from cloudfunctions/common/utils.js and adds new
periodization / training-cycle algorithms.

Algorithms included:
  1. VDOT Calculator (Daniels Running Formula)
  2. Body Surface Area (BSA) & body-size correction
  3. Environmental Tax Calculator
  4. HRV Correction Coefficient
  5. PB Probability Calculator
  6. Pacing Plan Generator
  7. Training Periodization Model (NEW — not in utils.js)
  8. Weekly Training Template Generator (NEW — not in utils.js)
  9. Utility / formatting functions

Dependencies: Python standard library only (math, datetime, re).

Reference standard for examples: 65 kg / 170 cm generic runner ("Runner_A").
No real personal data is stored or used anywhere in this module.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

# ============================================================
# Constants
# ============================================================

REFERENCE_WEIGHT_KG = 65.0
REFERENCE_HEIGHT_CM = 170.0
REFERENCE_BSA_RATIO = 0.0270  # BSA / weight for 65 kg / 170 cm

HALF_MARATHON_KM = 21.0975
FULL_MARATHON_KM = 42.195

# Pace multipliers relative to marathon pace (Daniels-inspired)
PACE_MULTIPLIERS = {
    "easy": 1.25,
    "marathon": 1.00,
    "threshold": 0.91,
    "interval": 0.82,
    "repetition": 0.75,
}

# Training periodization defaults
MAX_WEEKLY_INCREASE_PCT = 0.10   # never increase > 10 % per week
RECOVERY_WEEK_INTERVAL = 4       # every 4th week is a recovery week
RECOVERY_WEEK_REDUCTION = 0.25   # reduce volume by 25 % on recovery weeks
TAPER_REDUCTIONS = [0.20, 0.40, 0.60]  # final 3 taper weeks


# ============================================================
# 1. VDOT Calculator (Daniels Running Formula)
# ============================================================

def calculate_vdot(distance_km: float, time_minutes: float) -> float:
    """Calculate VDOT from a race result using the Daniels Running Formula.

    Args:
        distance_km: Race distance in kilometres (e.g. 21.0975 for a half marathon).
        time_minutes: Finish time in decimal minutes (e.g. 93.0 for 1:33:00).

    Returns:
        VDOT value rounded to one decimal place.

    Example:
        >>> calculate_vdot(21.0975, 93.0)   # 1:33:00 half marathon
        46.5
    """
    velocity = distance_km / time_minutes * 1000  # metres per minute
    vo2 = -4.60 + 0.182258 * velocity + 0.000104 * velocity ** 2
    pct_vo2max = (
        0.8
        + 0.1894393 * math.exp(-0.012778 * time_minutes)
        + 0.2989558 * math.exp(-0.1932605 * time_minutes)
    )
    return round(vo2 / pct_vo2max, 1)


def predict_time_from_vdot(vdot: float, distance_km: float) -> float:
    """Predict race time (minutes) for a given VDOT and distance via binary search.

    Args:
        vdot: Runner's VDOT value.
        distance_km: Target race distance in kilometres.

    Returns:
        Predicted time in minutes, rounded to one decimal.

    Example:
        >>> predict_time_from_vdot(46.5, 21.0975)  # ~93 min
    """
    lo = distance_km * 2
    hi = distance_km * 10
    for _ in range(100):
        mid = (lo + hi) / 2
        if calculate_vdot(distance_km, mid) > vdot:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 1)


def get_training_paces(vdot: float) -> Dict[str, int]:
    """Derive training pace zones (seconds per km) from VDOT.

    Zones are computed as multiples of predicted marathon pace:
        Easy x1.25 | Marathon x1.00 | Threshold x0.91 | Interval x0.82 | Rep x0.75

    Args:
        vdot: Runner's VDOT value.

    Returns:
        Dict mapping zone name -> pace in seconds/km.

    Example:
        >>> get_training_paces(46.5)
        {'easy': 349, 'marathon': 279, 'threshold': 254, 'interval': 229, 'repetition': 209}
    """
    marathon_time_min = predict_time_from_vdot(vdot, FULL_MARATHON_KM)
    m_pace = marathon_time_min / FULL_MARATHON_KM * 60  # seconds per km
    return {zone: round(m_pace * mult) for zone, mult in PACE_MULTIPLIERS.items()}


# ============================================================
# 2. Body Surface Area (BSA) Calculator
# ============================================================

def calculate_bsa(height_cm: float, weight_kg: float) -> float:
    """Du Bois body-surface-area formula.

    BSA (m^2) = 0.007184 * height^0.725 * weight^0.425

    Args:
        height_cm: Height in centimetres.
        weight_kg: Weight in kilograms.

    Returns:
        BSA in m^2, rounded to 3 decimals.

    Example:
        >>> calculate_bsa(170, 65)  # reference Runner_A
    """
    return round(0.007184 * height_cm ** 0.725 * weight_kg ** 0.425, 3)


def get_body_size_correction(height_cm: float, weight_kg: float) -> Dict[str, float]:
    """Compute body-size correction factor relative to 65 kg / 170 cm reference.

    The correction is used to adjust environmental-tax penalties for body size.

    Returns:
        Dict with ``bsa``, ``bsa_ratio``, ``correction_factor``.

    Example:
        >>> get_body_size_correction(170, 65)
        {'bsa': 1.753, 'bsa_ratio': 0.027, 'correction_factor': 1.0}
    """
    bsa = calculate_bsa(height_cm, weight_kg)
    bsa_ratio = round(bsa / weight_kg, 4)
    correction_factor = round(REFERENCE_BSA_RATIO / bsa_ratio, 2)
    return {
        "bsa": bsa,
        "bsa_ratio": bsa_ratio,
        "correction_factor": correction_factor,
    }


# ============================================================
# 3. Environmental Tax Calculator
# ============================================================

def calculate_environmental_tax(
    *,
    wind_speed_mph: float = 0,
    crosswind_coeff: float = 0.6,
    exposed_km: float = 0,
    humidity: float = 50,
    total_distance_km: float = HALF_MARATHON_KM,
    late_temp: float = 15,
    penalty_km: float = 0,
    body_size_correction_factor: float = 1.0,
    turnaround_count: int = 0,
) -> Dict[str, Union[int, str]]:
    """Estimate time penalty (seconds) from environmental conditions.

    This is the *simple / legacy* model identical to utils.js
    ``calculateEnvironmentalTax``.  For the advanced model with UV / humidity-
    gradient logic, see ``env_tax.py:calc_env_tax()``.

    Args:
        wind_speed_mph: Head/cross-wind speed in mph.
        crosswind_coeff: 0-1 cross-wind exposure coefficient.
        exposed_km: Kilometres exposed to wind.
        humidity: Average humidity (%).
        total_distance_km: Race distance in km.
        late_temp: Late-race temperature in deg C.
        penalty_km: Kilometres affected by high temperature (default: distance/3).
        body_size_correction_factor: From ``get_body_size_correction``.
        turnaround_count: Number of U-turn / hairpin turnarounds.

    Returns:
        Dict with ``wind``, ``humidity``, ``temperature``, ``turnaround``,
        ``total`` (all ints, seconds), and a ``summary`` string.
    """
    wind_tax = wind_speed_mph * 0.5 * crosswind_coeff * exposed_km

    humidity_tax = (
        (humidity - 70) * 0.5 * total_distance_km if humidity > 70 else 0
    )

    if late_temp > 15:
        effective_penalty_km = penalty_km if penalty_km else total_distance_km / 3
        temperature_tax = (
            (late_temp - 15) * 2 * effective_penalty_km / 6
            * body_size_correction_factor
        )
    else:
        temperature_tax = 0

    turnaround_tax = turnaround_count * 4

    wind_r = round(wind_tax)
    humidity_r = round(humidity_tax)
    temperature_r = round(temperature_tax)
    turnaround_r = round(turnaround_tax)
    total = wind_r + humidity_r + temperature_r + turnaround_r

    summary = (
        f"\u98ce\u963b{wind_r}\" + \u6e7f\u5ea6{humidity_r}\" + "
        f"\u6e29\u5ea6{temperature_r}\" + \u6298\u8fd4{turnaround_r}\" = \u603b\u8ba1{total}\""
    )
    return {
        "wind": wind_r,
        "humidity": humidity_r,
        "temperature": temperature_r,
        "turnaround": turnaround_r,
        "total": total,
        "summary": summary,
    }


# ============================================================
# 4. HRV Correction Coefficient
# ============================================================

def calculate_hrv_correction(
    personal_baseline: float,
    seven_day_avg: float,
    seven_day_sd: float,
    seven_day_min: float,
    race_day_hrv: Optional[float] = None,
) -> Dict:
    """Three-dimension HRV assessment producing a multiplicative correction.

    Dimensions:
        1. Baseline deviation -- 7-day mean vs. personal baseline.
        2. Stability (CV) -- 7-day standard-deviation / mean.
        3. Race-day rebound -- race-morning HRV vs. 7-day minimum.

    Args:
        personal_baseline: Long-term average HRV (rMSSD).
        seven_day_avg: Mean HRV over the last 7 days.
        seven_day_sd: Standard deviation of HRV over the last 7 days.
        seven_day_min: Minimum HRV reading in the last 7 days.
        race_day_hrv: Morning-of-race HRV reading (optional).

    Returns:
        Dict with ``baseline_deviation``, ``stability_cv``,
        ``race_day_rebound``, ``factors`` (sub-dict), ``correction``,
        and ``assessment`` (Chinese text label).

    Example:
        >>> calculate_hrv_correction(60, 58, 5, 50, 65)
    """
    baseline_deviation = ((seven_day_avg - personal_baseline) / personal_baseline) * 100
    stability_cv = (seven_day_sd / seven_day_avg) * 100

    race_day_rebound_val: Optional[float] = None
    if race_day_hrv is not None and seven_day_min:
        race_day_rebound_val = ((race_day_hrv - seven_day_min) / seven_day_min) * 100

    # --- Factor look-ups (match utils.js exactly) ---
    if baseline_deviation > 5:
        f_baseline = 1.02
    elif baseline_deviation >= -3:
        f_baseline = 1.00
    elif baseline_deviation >= -10:
        f_baseline = 0.98
    else:
        f_baseline = 0.95

    if stability_cv < 10:
        f_stability = 1.02
    elif stability_cv <= 15:
        f_stability = 1.00
    else:
        f_stability = 0.97

    if race_day_rebound_val is None:
        f_rebound = 1.00
    elif race_day_rebound_val > 30:
        f_rebound = 1.01
    elif race_day_rebound_val >= 15:
        f_rebound = 1.00
    else:
        f_rebound = 0.98

    correction = round(f_baseline * f_stability * f_rebound, 3)

    if correction >= 1.02:
        assessment = "\u72b6\u6001\u6781\u4f73"
    elif correction >= 1.00:
        assessment = "\u72b6\u6001\u6b63\u5e38"
    elif correction >= 0.97:
        assessment = "\u72b6\u6001\u504f\u4f4e"
    else:
        assessment = "\u72b6\u6001\u8f83\u5dee\uff0c\u5efa\u8bae\u4fdd\u5b88\u76ee\u6807"

    return {
        "baseline_deviation": round(baseline_deviation, 1),
        "stability_cv": round(stability_cv, 1),
        "race_day_rebound": round(race_day_rebound_val, 1) if race_day_rebound_val is not None else None,
        "factors": {
            "baseline": f_baseline,
            "stability": f_stability,
            "rebound": f_rebound,
        },
        "correction": correction,
        "assessment": assessment,
    }


# ============================================================
# 5. PB Probability Calculator
# ============================================================

def calculate_pb_odds(
    current_vdot: float,
    target_vdot: float,
    weekly_km: float = 50,
    distance_km: float = HALF_MARATHON_KM,
    env_tax_seconds: float = 0,
    target_time_seconds: float = 0,
    hrv_correction: float = 1.0,
    injury_correction: float = 1.0,
    race_interval_days: int = 30,
) -> Dict:
    """Estimate probability (%) of achieving a PB / target time.

    Combines VDOT gap, training volume grade, environmental penalty,
    HRV status, injury status, and race-interval recovery.

    Args:
        current_vdot: Current estimated VDOT.
        target_vdot: VDOT required for the target time.
        weekly_km: Recent average weekly distance.
        distance_km: Race distance in km.
        env_tax_seconds: Estimated env-tax penalty (seconds).
        target_time_seconds: Target finish time (seconds).
        hrv_correction: HRV multiplicative factor (from ``calculate_hrv_correction``).
        injury_correction: Injury multiplicative factor (1.0 = healthy).
        race_interval_days: Days since last race.

    Returns:
        Dict with ``odds`` (int 5-95), ``confidence`` range string,
        ``assessment`` (Chinese), and ``factors`` breakdown.
    """
    vdot_gap = current_vdot - target_vdot

    # Base probability from VDOT gap
    if vdot_gap >= 2:
        base_probability = 0.90
    elif vdot_gap >= 1:
        base_probability = 0.85
    elif vdot_gap >= 0:
        base_probability = 0.78
    elif vdot_gap >= -0.5:
        base_probability = 0.70
    elif vdot_gap >= -1:
        base_probability = 0.60
    elif vdot_gap >= -2:
        base_probability = 0.45
    else:
        base_probability = 0.30

    # Training volume coefficient
    if distance_km == FULL_MARATHON_KM:
        min_weekly_km, opt_weekly_km = 60, 80
    else:
        min_weekly_km, opt_weekly_km = 40, 55

    if weekly_km >= opt_weekly_km:
        training_coeff, training_grade = 1.00, "A"
    elif weekly_km >= min_weekly_km:
        training_coeff, training_grade = 0.95, "B"
    elif weekly_km >= min_weekly_km * 0.75:
        training_coeff, training_grade = 0.90, "C"
    else:
        training_coeff, training_grade = 0.85, "D"

    # Environmental coefficient
    env_tax_pct = env_tax_seconds / target_time_seconds if target_time_seconds > 0 else 0
    env_coeff = 1 - env_tax_pct

    # Race-interval coefficient
    if race_interval_days >= 21:
        interval_coeff = 1.00
    elif race_interval_days >= 14:
        interval_coeff = 0.97
    elif race_interval_days >= 7:
        interval_coeff = 0.93
    else:
        interval_coeff = 0.88

    raw_odds = (
        base_probability
        * training_coeff
        * env_coeff
        * hrv_correction
        * injury_correction
        * interval_coeff
    )
    odds = round(min(max(raw_odds, 0.05), 0.95) * 100)

    if odds >= 80:
        assessment = "\u76ee\u6807\u975e\u5e38\u53ef\u884c\uff0c\u5efa\u8bae\u52c7\u6562\u51b2\u51fb"
    elif odds >= 65:
        assessment = "\u76ee\u6807\u5408\u7406\uff0c\u6709\u8f83\u5927\u628a\u63e1\u8fbe\u6210"
    elif odds >= 50:
        assessment = "\u76ee\u6807\u6709\u6311\u6218\u6027\uff0c\u9700\u8981\u826f\u597d\u7684\u6267\u884c"
    elif odds >= 35:
        assessment = "\u76ee\u6807\u504f\u6fc0\u8fdb\uff0c\u5efa\u8bae\u51c6\u5907\u4fdd\u5b88\u5907\u9009\u65b9\u6848"
    else:
        assessment = "\u76ee\u6807\u98ce\u9669\u8f83\u9ad8\uff0c\u5f3a\u70c8\u5efa\u8bae\u8c03\u6574\u76ee\u6807"

    return {
        "odds": odds,
        "confidence": f"{max(odds - 5, 5)}%-{min(odds + 5, 95)}%",
        "assessment": assessment,
        "factors": {
            "base_probability": round(base_probability * 100),
            "training_coeff": {
                "value": training_coeff,
                "grade": training_grade,
                "weekly_km": weekly_km,
            },
            "env_coeff": {
                "value": round(env_coeff, 3),
                "tax_seconds": env_tax_seconds,
                "tax_pct": round(env_tax_pct * 100, 2),
            },
            "hrv_correction": hrv_correction,
            "injury_correction": injury_correction,
            "interval_coeff": {
                "value": interval_coeff,
                "days": race_interval_days,
            },
        },
    }


# ============================================================
# 6. Pacing Plan Generator
# ============================================================

def _get_segment_name(km: int, distance_km: float) -> str:
    """Return Chinese segment label for a given km within a race."""
    pct = km / distance_km
    if pct <= 0.15:
        return "\u8d77\u6b65\u6bb5"
    if pct <= 0.50:
        return "\u5de1\u822a\u6bb5"
    if pct <= 0.75:
        return "\u7ef4\u6301\u6bb5"
    if pct <= 0.90:
        return "\u575a\u6301\u6bb5"
    return "\u51b2\u523a\u6bb5"


def generate_pacing_plan(
    target_time_seconds: float,
    distance_km: float = HALF_MARATHON_KM,
    strategy: str = "even",
    env_tax_seconds: float = 0,
) -> List[Dict]:
    """Generate a per-km pacing plan for race day.

    Strategies:
        * ``even``  -- mostly uniform, slightly quicker opening, gentle positive last 15 %.
        * ``negative`` -- conservative first half, faster second half.
        * ``conservative`` -- slightly slower throughout except the first 3 km.

    Args:
        target_time_seconds: Target finish time in seconds.
        distance_km: Race distance.
        strategy: One of ``even``, ``negative``, ``conservative``.
        env_tax_seconds: Environmental penalty (half is absorbed into pace budget).

    Returns:
        List of per-km dicts with ``km``, ``distance``, ``pace_seconds``,
        ``pace_display``, ``cum_time_seconds``, ``cum_time_display``, ``segment``.
    """
    total_km = math.ceil(distance_km)
    last_km_fraction = distance_km - math.floor(distance_km)
    adjusted_time = target_time_seconds - env_tax_seconds * 0.5
    avg_pace = adjusted_time / distance_km

    plan: List[Dict] = []
    for km in range(1, total_km + 1):
        is_last = km == total_km
        km_distance = last_km_fraction if (is_last and last_km_fraction > 0) else 1.0

        if strategy == "even":
            if km <= 2:
                pace_adjust = -2
            elif km > distance_km * 0.85:
                pace_adjust = 1
            else:
                pace_adjust = 0
        elif strategy == "negative":
            if km <= distance_km * 0.5:
                pace_adjust = 3
            elif km <= distance_km * 0.75:
                pace_adjust = 0
            else:
                pace_adjust = -3
        elif strategy == "conservative":
            pace_adjust = 2 if km > 3 else 0
        else:
            pace_adjust = 0

        pace_sec = round(avg_pace + pace_adjust)
        plan.append({
            "km": km,
            "distance": km_distance,
            "pace_seconds": pace_sec,
            "pace_display": format_pace(pace_sec),
            "cum_time_seconds": 0,
            "cum_time_display": "",
            "segment": _get_segment_name(km, distance_km),
        })

    cum = 0.0
    for item in plan:
        cum += item["pace_seconds"] * item["distance"]
        item["cum_time_seconds"] = round(cum)
        item["cum_time_display"] = format_time(round(cum))

    return plan


# ============================================================
# 7. Training Periodization Model  (NEW -- not in utils.js)
# ============================================================

# Phase definitions: (name_en, name_cn, week_range, easy%, tempo%, interval%, long_run%)
_FULL_PHASES = [
    ("Recovery",              "\u8d5b\u540e\u6062\u590d\u671f",   (1, 2),  90, 0,  0,  10),
    ("Base Building",         "\u6709\u6c27\u57fa\u7840\u671f",   (4, 6),  75, 5,  0,  20),
    ("Aerobic Development",   "\u6709\u6c27\u53d1\u5c55\u671f",   (4, 6),  65, 15, 5,  15),
    ("Marathon Specific",     "\u9a6c\u62c9\u677e\u4e13\u9879\u671f", (4, 6),  55, 15, 10, 20),
    ("Peak / Sharpening",     "\u5dc5\u5cf0\u51b2\u523a\u671f",   (2, 3),  60, 15, 15, 10),
    ("Taper",                 "\u8d5b\u524d\u51cf\u91cf\u671f",   (2, 3),  75, 10, 5,  10),
]
_HALF_PHASES = [
    ("Recovery",              "\u8d5b\u540e\u6062\u590d\u671f",   (1, 2),  90, 0,  0,  10),
    ("Base Building",         "\u6709\u6c27\u57fa\u7840\u671f",   (3, 4),  75, 5,  0,  20),
    ("Aerobic Development",   "\u6709\u6c27\u53d1\u5c55\u671f",   (3, 4),  65, 15, 5,  15),
    ("Race Specific",         "\u534a\u9a6c\u4e13\u9879\u671f",   (2, 3),  55, 15, 15, 15),
    ("Taper",                 "\u8d5b\u524d\u51cf\u91cf\u671f",   (1, 2),  75, 10, 5,  10),
]

# Key workout templates per phase (phase index -> list of workout descriptions)
_FULL_KEY_WORKOUTS: Dict[int, List[str]] = {
    0: ["\u8f7b\u677e\u8dd130-40min", "\u6563\u6b65+\u52a8\u6001\u62c9\u4f38"],
    1: ["\u8f7b\u677e\u8dd160-75min", "\u957f\u8dd190-120min (E pace)", "Strides 6x100m"],
    2: ["\u8282\u594f\u8dd1 20-30min (T pace)", "\u957f\u8dd1120-150min with \u6700\u540e20min MP", "\u8f7b\u677e\u8dd1+Strides"],
    3: ["MP\u957f\u8dd1 25-32km (\u542b12-20km@MP)", "\u8282\u594f\u8dd1 2x20min (T pace)", "\u95f4\u6b47 5x1000m (I pace)"],
    4: ["\u95f4\u6b47 6x1000m (I pace)", "MP\u8dd1 10-15km", "\u8282\u594f\u8dd1 30min (T pace)"],
    5: ["\u8f7b\u677e\u8dd140-50min", "\u77ed\u95f4\u6b47 4x400m", "\u8d5b\u524d\u6fc0\u6d3b\u8dd1 3km@MP"],
}
_HALF_KEY_WORKOUTS: Dict[int, List[str]] = {
    0: ["\u8f7b\u677e\u8dd130-40min", "\u6563\u6b65+\u52a8\u6001\u62c9\u4f38"],
    1: ["\u8f7b\u677e\u8dd150-60min", "\u957f\u8dd170-90min (E pace)", "Strides 6x100m"],
    2: ["\u8282\u594f\u8dd1 20min (T pace)", "\u957f\u8dd190-110min with \u6700\u540e15min HMP", "\u95f4\u6b47 4x1000m"],
    3: ["HMP\u957f\u8dd1 16-18km (\u542b8-12km@HMP)", "\u95f4\u6b47 5x1000m (I pace)", "\u8282\u594f\u8dd1 25min"],
    4: ["\u8f7b\u677e\u8dd135-45min", "\u77ed\u95f4\u6b47 3x400m", "\u8d5b\u524d\u6fc0\u6d3b\u8dd1 2km@HMP"],
}


def design_training_phases(
    target_race_date: str,
    current_date: str,
    current_vdot: float,
    target_vdot: float,
    current_weekly_km: float,
    is_full: bool = True,
) -> List[Dict]:
    """Design multi-phase training periodization from now until race day.

    The algorithm distributes available weeks across canonical phases,
    scaling each phase proportionally when total weeks differ from the
    template mid-point.

    Phases for full marathon (typical 16-33 weeks):
    - Phase 0: Recovery (if coming off a race) - 1-2 weeks
    - Phase 1: Base Building - 4-6 weeks, 80/20 easy/quality
    - Phase 2: Aerobic Development - 4-6 weeks, add tempo runs
    - Phase 3: Marathon Specific - 4-6 weeks, MP long runs
    - Phase 4: Peak/Sharpening - 2-3 weeks
    - Phase 5: Taper - 2-3 weeks

    For half marathon (typical 8-16 weeks):
    - Phase 0: Recovery - 1-2 weeks
    - Phase 1: Base Building - 3-4 weeks
    - Phase 2: Aerobic Development - 3-4 weeks
    - Phase 3: Race Specific - 2-3 weeks
    - Phase 4: Taper - 1-2 weeks

    Args:
        target_race_date: Race day ``"YYYY-MM-DD"``.
        current_date: Start date ``"YYYY-MM-DD"``.
        current_vdot: Runner's current VDOT.
        target_vdot: VDOT required for goal time.
        current_weekly_km: Recent average weekly km.
        is_full: ``True`` for full marathon, ``False`` for half marathon.

    Returns:
        List of phase dicts with:
        - phase_number, name, name_cn, weeks, start_date, end_date
        - weekly_km_range (min, max)
        - intensity_distribution (easy_pct, tempo_pct, interval_pct, long_run_pct)
        - key_workouts (list of workout templates)
        - vdot_target (expected VDOT at end of phase)

    Example:
        >>> design_training_phases("2025-11-02", "2025-03-10", 44.0, 46.5, 40, True)
    """
    race_dt = datetime.strptime(target_race_date, "%Y-%m-%d")
    start_dt = datetime.strptime(current_date, "%Y-%m-%d")
    total_weeks = max(int((race_dt - start_dt).days / 7), 4)

    template = _FULL_PHASES if is_full else _HALF_PHASES
    key_workouts_map = _FULL_KEY_WORKOUTS if is_full else _HALF_KEY_WORKOUTS

    # Sum of mid-point weeks for each phase
    mid_total = sum((lo + hi) / 2 for (_, _, (lo, hi), *_) in template)
    scale = total_weeks / mid_total

    # Allocate weeks per phase, respecting min/max
    allocated: List[int] = []
    for _, _, (lo, hi), *_ in template:
        raw = round(((lo + hi) / 2) * scale)
        allocated.append(max(lo, min(hi, raw)))

    # Adjust to hit exact total: trim or extend the largest flexible phase
    diff = total_weeks - sum(allocated)
    if diff != 0:
        # Prefer adjusting the longest phase (usually Base or Specific)
        adjustable = sorted(
            range(len(allocated)),
            key=lambda i: allocated[i],
            reverse=True,
        )
        for idx in adjustable:
            lo, hi = template[idx][2]
            room = hi - allocated[idx] if diff > 0 else allocated[idx] - lo
            change = min(abs(diff), room) * (1 if diff > 0 else -1)
            allocated[idx] += change
            diff -= change
            if diff == 0:
                break

    # If still not exact, force-add/remove from the biggest block
    if diff != 0:
        biggest = max(range(len(allocated)), key=lambda i: allocated[i])
        allocated[biggest] += diff

    # VDOT progression: linear interpolation across phases
    vdot_step = (target_vdot - current_vdot) / max(len(template) - 1, 1)

    # Peak weekly volume: scale up from current, cap at sensible max
    peak_km = min(current_weekly_km * 1.6, 130 if is_full else 90)

    cursor = start_dt
    phases: List[Dict] = []
    for i, (name_en, name_cn, _, easy, tempo, interval, long_run) in enumerate(template):
        weeks = allocated[i]
        phase_start = cursor
        phase_end = cursor + timedelta(weeks=weeks) - timedelta(days=1)
        cursor = phase_end + timedelta(days=1)

        # Volume range depends on phase position
        if i == 0:  # recovery
            km_min = current_weekly_km * 0.4
            km_max = current_weekly_km * 0.6
        elif i <= 2:  # base / aerobic
            km_min = current_weekly_km * (0.8 + 0.1 * i)
            km_max = min(current_weekly_km * (1.0 + 0.15 * i), peak_km)
        elif i == len(template) - 1:  # taper
            km_min = peak_km * 0.4
            km_max = peak_km * 0.7
        else:  # specific / peak
            km_min = peak_km * 0.85
            km_max = peak_km

        phase_vdot = round(current_vdot + vdot_step * i, 1)

        phases.append({
            "phase_number": i,
            "name": name_en,
            "name_cn": name_cn,
            "weeks": weeks,
            "start_date": phase_start.strftime("%Y-%m-%d"),
            "end_date": phase_end.strftime("%Y-%m-%d"),
            "weekly_km_range": {"min": round(km_min, 1), "max": round(km_max, 1)},
            "intensity_distribution": {
                "easy_pct": easy,
                "tempo_pct": tempo,
                "interval_pct": interval,
                "long_run_pct": long_run,
            },
            "key_workouts": key_workouts_map.get(i, []),
            "vdot_target": phase_vdot,
        })

    return phases


def calculate_weekly_volume_progression(
    start_km: float,
    peak_km: float,
    total_weeks: int,
    phases: List[Dict],
) -> List[Dict]:
    """Generate week-by-week target volume with periodization.

    Rules:
        * Never increase more than 10 % per week.
        * Every 4th week is a recovery week (volume drops ~25 %).
        * Peak volume occurs in the main specific phase.
        * Taper: last 3 weeks reduce by 20 % -> 40 % -> 60 %.

    Args:
        start_km: Starting weekly volume.
        peak_km: Target peak weekly volume.
        total_weeks: Total weeks in the plan.
        phases: Output of ``design_training_phases``.

    Returns:
        List of dicts per week: ``week_number``, ``target_km``,
        ``is_recovery_week``, ``phase_name``.

    Example:
        >>> calculate_weekly_volume_progression(40, 64, 33, phases)
    """
    result: List[Dict] = []

    # Build a week -> phase map
    week_phase: List[str] = []
    for p in phases:
        week_phase.extend([p["name"]] * p["weeks"])
    # Pad/trim to total_weeks
    while len(week_phase) < total_weeks:
        week_phase.append(week_phase[-1] if week_phase else "Base Building")
    week_phase = week_phase[:total_weeks]

    # Determine taper start week
    taper_start = total_weeks  # default: no taper
    for p in phases:
        if "taper" in p["name"].lower():
            running_weeks = 0
            for pp in phases:
                if pp is p:
                    break
                running_weeks += pp["weeks"]
            taper_start = running_weeks
            break

    # Target volume curve: ramp from start_km to peak_km at taper_start,
    # then apply taper reductions.
    ramp_weeks = max(taper_start, 1)
    prev_km = start_km

    for w in range(1, total_weeks + 1):
        phase_name = week_phase[w - 1] if w <= len(week_phase) else "Taper"
        is_recovery = (w % RECOVERY_WEEK_INTERVAL == 0) and w < taper_start

        if w <= taper_start:
            # Linear target on the ramp, capped by 10 % rule
            linear_target = start_km + (peak_km - start_km) * (w / ramp_weeks)
            max_allowed = prev_km * (1 + MAX_WEEKLY_INCREASE_PCT)
            target = min(linear_target, max_allowed)
            if is_recovery:
                target = prev_km * (1 - RECOVERY_WEEK_REDUCTION)
        else:
            # Taper phase
            weeks_into_taper = w - taper_start
            taper_idx = min(weeks_into_taper - 1, len(TAPER_REDUCTIONS) - 1)
            reduction = TAPER_REDUCTIONS[taper_idx]
            target = peak_km * (1 - reduction)
            is_recovery = False  # taper weeks are not tagged as "recovery"

        target = round(max(target, 10), 1)  # floor at 10 km
        result.append({
            "week_number": w,
            "target_km": target,
            "is_recovery_week": is_recovery,
            "phase_name": phase_name,
        })
        # For ramp calculation, keep track of non-recovery previous week
        if not is_recovery:
            prev_km = target

    return result


def generate_milestone_tests(
    phases: List[Dict],
    vdot: float,
) -> List[Dict]:
    """Generate milestone tests aligned with training phases.

    Tests:
        * End of Base Building: 5 km time trial.
        * End of Aerobic Development: 10 km time trial or tempo test.
        * End of Specific phase: half-marathon tune-up or 25-30 km MP long run.

    Args:
        phases: Output of ``design_training_phases``.
        vdot: Current VDOT for pace targets.

    Returns:
        List of test dicts with ``test_name``, ``target_week``,
        ``distance_km``, ``target_pace``, ``purpose``.
    """
    paces = get_training_paces(vdot)
    tests: List[Dict] = []
    running_week = 0

    for p in phases:
        end_week = running_week + p["weeks"]
        name_lower = p["name"].lower()

        if "base" in name_lower:
            tests.append({
                "test_name": "5km Time Trial",
                "test_name_cn": "5\u516c\u91cc\u6d4b\u8bd5\u8dd1",
                "target_week": end_week,
                "distance_km": 5.0,
                "target_pace": format_pace(paces["threshold"]),
                "purpose": "Assess base aerobic fitness after build phase.",
                "purpose_cn": "\u8bc4\u4f30\u6709\u6c27\u57fa\u7840\u671f\u540e\u7684\u57fa\u7840\u4f53\u80fd",
            })
        elif "aerobic" in name_lower or "development" in name_lower:
            tests.append({
                "test_name": "10km Time Trial / Tempo Test",
                "test_name_cn": "10\u516c\u91cc\u6d4b\u8bd5\u8dd1/\u8282\u594f\u8dd1\u6d4b\u8bd5",
                "target_week": end_week,
                "distance_km": 10.0,
                "target_pace": format_pace(paces["threshold"]),
                "purpose": "Assess aerobic development and lactate threshold.",
                "purpose_cn": "\u8bc4\u4f30\u6709\u6c27\u53d1\u5c55\u548c\u4e73\u9178\u9608\u503c\u6c34\u5e73",
            })
        elif "specific" in name_lower:
            tests.append({
                "test_name": "Half-Marathon Tune-up / Long MP Run",
                "test_name_cn": "\u534a\u9a6c\u8c03\u6574\u8d5b/\u957f\u8ddd\u79bbMP\u8dd1",
                "target_week": max(end_week - 1, running_week + 1),
                "distance_km": 21.0975,
                "target_pace": format_pace(paces["marathon"]),
                "purpose": "Validate marathon-specific fitness and race-day execution.",
                "purpose_cn": "\u9a8c\u8bc1\u9a6c\u62c9\u677e\u4e13\u9879\u4f53\u80fd\u53ca\u6bd4\u8d5b\u65e5\u6267\u884c\u529b",
            })

        running_week = end_week

    return tests


# ============================================================
# 8. Weekly Training Template Generator  (NEW -- not in utils.js)
# ============================================================

# Day-of-week labels (Monday = 0)
_DOW_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DOW_LABELS_CN = ["\u5468\u4e00", "\u5468\u4e8c", "\u5468\u4e09", "\u5468\u56db", "\u5468\u4e94", "\u5468\u516d", "\u5468\u65e5"]

# Strength session types
_STRENGTH_SESSIONS = {
    "core": "Core & stability (plank, dead bug, bird dog) 20-30min",
    "lower": "Lower body strength (squats, lunges, calf raises) 30min",
    "hip": "Hip & glute activation (clamshell, bridge, band walks) 20min",
}


def generate_week_template(
    phase: Dict,
    week_number: int,
    target_km: float,
    vdot: float,
    is_recovery_week: bool,
    runner_profile: Optional[Dict] = None,
) -> Dict:
    """Generate a 7-day training template for a given training week.

    The template allocates runs and rest days according to the phase
    intensity distribution.  Quality sessions are reduced on recovery weeks.

    Template structure:
    - 4-6 run days per week depending on phase
    - 1-2 quality sessions per week (tempo, intervals, MP long run)
    - 1 long run per week
    - 1-2 rest days
    - Optional: strength training days

    Args:
        phase: A single phase dict from ``design_training_phases``.
        week_number: The week number in the overall plan.
        target_km: Total volume target for this week.
        vdot: Current VDOT (for pace calculation).
        is_recovery_week: Whether this is a scheduled recovery/down week.
        runner_profile: Optional dict with ``runs_per_week`` (4-6, default 5),
            ``long_run_day`` (0-6, default 6 = Sunday).

    Returns:
        Dict with ``week_number``, ``phase_name``, ``total_km``,
        ``quality_sessions``, ``long_run``, ``strength_days``,
        and ``days`` (list of 7 day templates).

    Example:
        >>> phase = {"name": "Aerobic Development", "name_cn": "Aerobic Dev Phase",
        ...          "intensity_distribution": {"easy_pct": 65, "tempo_pct": 15,
        ...              "interval_pct": 5, "long_run_pct": 15}}
        >>> generate_week_template(phase, 8, 50, 46.5, False)
    """
    runs_per_week = 5
    long_run_day = 6  # Sunday
    if runner_profile:
        runs_per_week = runner_profile.get("runs_per_week", 5)
        long_run_day = runner_profile.get("long_run_day", 6)

    paces = get_training_paces(vdot)
    dist = phase["intensity_distribution"]

    # Allocate km by type
    long_run_km = round(target_km * dist["long_run_pct"] / 100, 1)
    tempo_km = round(target_km * dist["tempo_pct"] / 100, 1)
    interval_km = round(target_km * dist["interval_pct"] / 100, 1)
    easy_km = round(target_km - long_run_km - tempo_km - interval_km, 1)

    if is_recovery_week:
        tempo_km = round(tempo_km * 0.5, 1)
        interval_km = 0
        easy_km = round(target_km - long_run_km - tempo_km, 1)

    # Determine run days (exclude rest days)
    rest_days_count = 7 - runs_per_week
    # Default rest days: Monday and Friday (indices 0, 4) for 5-day weeks
    if rest_days_count == 2:
        rest_indices = {0, 4}
    elif rest_days_count == 3:
        rest_indices = {0, 3, 5}
    elif rest_days_count == 1:
        rest_indices = {0}
    else:
        rest_indices = set()

    # Move long_run_day out of rest
    rest_indices.discard(long_run_day)

    # Quality session days: Tuesday (1) and Thursday (3) by default
    quality_days = [d for d in [1, 3] if d not in rest_indices and d != long_run_day]

    # Build day templates
    easy_per_day = round(easy_km / max(runs_per_week - len(quality_days) - 1, 1), 1)
    days: List[Dict] = []

    quality_idx = 0
    for d in range(7):
        dow = _DOW_LABELS[d]
        dow_cn = _DOW_LABELS_CN[d]

        if d in rest_indices:
            days.append({
                "day": dow,
                "day_cn": dow_cn,
                "type": "rest",
                "type_cn": "\u4f11\u606f",
                "distance_km": 0,
                "pace_zone": None,
                "pace_display": None,
                "notes": "\u4f11\u606f\u6216\u4ea4\u53c9\u8bad\u7ec3",
                "strength": _STRENGTH_SESSIONS.get(
                    "core" if d == 0 else "hip", None
                ),
            })
        elif d == long_run_day:
            lr_type = "Long Run"
            lr_type_cn = "\u957f\u8ddd\u79bb\u8dd1"
            lr_pace = paces["easy"]
            lr_notes = "\u957f\u8ddd\u79bb\u8dd1\uff0cE\u914d\u901f"
            phase_lower = phase["name"].lower()
            if "specific" in phase_lower and not is_recovery_week:
                lr_notes = "\u957f\u8ddd\u79bb\u542bMP\u6bb5"
                lr_pace = paces["marathon"]
            days.append({
                "day": dow,
                "day_cn": dow_cn,
                "type": lr_type,
                "type_cn": lr_type_cn,
                "distance_km": long_run_km,
                "pace_zone": "easy" if "specific" not in phase["name"].lower() else "marathon",
                "pace_display": format_pace(lr_pace),
                "notes": lr_notes,
                "strength": None,
            })
        elif d in quality_days and quality_idx < len(quality_days):
            # First quality = tempo, second = intervals (if applicable)
            if quality_idx == 0 and tempo_km > 0:
                q_type = "Tempo"
                q_type_cn = "\u8282\u594f\u8dd1"
                q_km = tempo_km + easy_per_day * 0.5  # warm-up + cool-down
                q_pace = paces["threshold"]
                q_notes = f"\u70ed\u8eab + {tempo_km}km@T + \u653e\u677e\u8dd1"
            elif interval_km > 0:
                q_type = "Intervals"
                q_type_cn = "\u95f4\u6b47\u8dd1"
                q_km = interval_km + easy_per_day * 0.5
                q_pace = paces["interval"]
                q_notes = "\u70ed\u8eab + \u95f4\u6b47@I\u914d\u901f + \u653e\u677e\u8dd1"
            else:
                q_type = "Easy"
                q_type_cn = "\u8f7b\u677e\u8dd1"
                q_km = easy_per_day
                q_pace = paces["easy"]
                q_notes = "\u8f7b\u677e\u8dd1+\u52a0\u901f\u8dd1"

            days.append({
                "day": dow,
                "day_cn": dow_cn,
                "type": q_type,
                "type_cn": q_type_cn,
                "distance_km": round(q_km, 1),
                "pace_zone": "threshold" if "Tempo" in q_type else ("interval" if "Interval" in q_type else "easy"),
                "pace_display": format_pace(q_pace),
                "notes": q_notes,
                "strength": None,
            })
            quality_idx += 1
        else:
            days.append({
                "day": dow,
                "day_cn": dow_cn,
                "type": "Easy",
                "type_cn": "\u8f7b\u677e\u8dd1",
                "distance_km": easy_per_day,
                "pace_zone": "easy",
                "pace_display": format_pace(paces["easy"]),
                "notes": "\u8f7b\u677e\u8dd1",
                "strength": _STRENGTH_SESSIONS.get("lower", None) if d == 2 else None,
            })

    # Tally actual planned km
    actual_km = round(sum(d["distance_km"] for d in days), 1)

    # Count quality sessions
    quality_count = sum(1 for d in days if d["type"] in ("Tempo", "Intervals"))

    strength_days = [
        {"day": days[d]["day"], "session": days[d]["strength"]}
        for d in range(7) if days[d].get("strength")
    ]

    return {
        "week_number": week_number,
        "phase_name": phase["name"],
        "phase_name_cn": phase["name_cn"],
        "total_km": actual_km,
        "target_km": target_km,
        "is_recovery_week": is_recovery_week,
        "quality_sessions": quality_count,
        "long_run": {
            "distance_km": long_run_km,
            "type": days[long_run_day]["type"],
        },
        "strength_days": strength_days,
        "days": days,
    }


# ============================================================
# 9. Utility / Formatting Functions
# ============================================================

def format_pace(seconds: Union[int, float]) -> str:
    """Format a pace value (seconds per km) as M'SS".

    Example:
        >>> format_pace(275)
        "4'35\\""
    """
    seconds = int(round(seconds))
    m = seconds // 60
    s = seconds % 60
    return f"{m}'{s:02d}\""


def format_time(total_seconds: Union[int, float]) -> str:
    """Format total seconds as H:MM:SS or M:SS.

    Example:
        >>> format_time(5580)
        '1:33:00'
    """
    total_seconds = int(round(total_seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def parse_time_to_seconds(time_str: str) -> int:
    """Parse "H:MM:SS", "M:SS", or raw seconds string to integer seconds.

    Examples:
        >>> parse_time_to_seconds("1:33:00")
        5580
        >>> parse_time_to_seconds("33:00")
        1980
        >>> parse_time_to_seconds("5580")
        5580
    """
    if not time_str:
        return 0
    time_str = time_str.strip()
    if re.fullmatch(r"\d+", time_str):
        return int(time_str)
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def parse_pace_to_seconds(pace_str: str) -> int:
    """Parse pace string like "4'35\\"" or "4:35" to seconds.

    Examples:
        >>> parse_pace_to_seconds("4'35\\"")
        275
        >>> parse_pace_to_seconds("4:35")
        275
    """
    if not pace_str:
        return 0
    pace_str = pace_str.strip()
    if re.fullmatch(r"\d+", pace_str):
        return int(pace_str)
    m = re.search(r"(\d+)['':](\d+)", pace_str)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return 0


def get_distance_label(km: float) -> str:
    """Return a label for common race distances.

    Example:
        >>> get_distance_label(21.0975)
        'Half Marathon'
    """
    if abs(km - HALF_MARATHON_KM) < 0.5:
        return "\u534a\u7a0b\u9a6c\u62c9\u677e"
    if abs(km - FULL_MARATHON_KM) < 0.5:
        return "\u5168\u7a0b\u9a6c\u62c9\u677e"
    if abs(km - 10) < 0.5:
        return "10\u516c\u91cc"
    if abs(km - 5) < 0.5:
        return "5\u516c\u91cc"
    return f"{km}\u516c\u91cc"


# ============================================================
# Self-tests
# ============================================================

if __name__ == "__main__":
    import json

    SEP = "=" * 64

    def section(title: str) -> None:
        print(f"\n{SEP}\n  {title}\n{SEP}")

    # --- 1. VDOT ---
    section("1. VDOT Calculator")
    v = calculate_vdot(HALF_MARATHON_KM, 93.0)  # 1:33:00 half
    print(f"  VDOT for 1:33:00 half marathon: {v}")
    predicted = predict_time_from_vdot(v, HALF_MARATHON_KM)
    print(f"  Predicted half time from VDOT {v}: {predicted} min ({format_time(int(predicted * 60))})")
    predicted_full = predict_time_from_vdot(v, FULL_MARATHON_KM)
    print(f"  Predicted full time from VDOT {v}: {predicted_full} min ({format_time(int(predicted_full * 60))})")

    # --- 2. Training paces ---
    section("2. Training Paces (VDOT 46.5)")
    paces = get_training_paces(46.5)
    for zone, sec in paces.items():
        print(f"  {zone:>12s}: {format_pace(sec)}  ({sec} sec/km)")

    # --- 3. BSA ---
    section("3. Body Surface Area (65 kg / 170 cm reference)")
    bsa_info = get_body_size_correction(170, 65)
    print(f"  BSA = {bsa_info['bsa']} m^2")
    print(f"  BSA ratio = {bsa_info['bsa_ratio']}")
    print(f"  Correction factor = {bsa_info['correction_factor']}")

    # --- 4. Environmental Tax ---
    section("4. Environmental Tax (example conditions)")
    env = calculate_environmental_tax(
        wind_speed_mph=8, crosswind_coeff=0.5, exposed_km=6,
        humidity=75, total_distance_km=HALF_MARATHON_KM,
        late_temp=22, turnaround_count=2,
    )
    print(f"  {env['summary']}")

    # --- 5. HRV Correction ---
    section("5. HRV Correction (example values)")
    hrv = calculate_hrv_correction(60, 58, 5, 50, 65)
    print(f"  Correction: {hrv['correction']}  Assessment: {hrv['assessment']}")
    print(f"  Factors: {hrv['factors']}")

    # --- 6. PB Odds ---
    section("6. PB Probability (example)")
    pb = calculate_pb_odds(
        current_vdot=46.5, target_vdot=47.0,
        weekly_km=55, distance_km=HALF_MARATHON_KM,
        env_tax_seconds=45, target_time_seconds=5400,
        hrv_correction=1.0, race_interval_days=30,
    )
    print(f"  Odds: {pb['odds']}%  ({pb['confidence']})")
    print(f"  Assessment: {pb['assessment']}")

    # --- 7. Pacing Plan ---
    section("7. Pacing Plan (1:30:00 half, even strategy)")
    plan = generate_pacing_plan(5400, HALF_MARATHON_KM, "even")
    for row in plan[:5]:
        print(f"  km {row['km']:2d}  {row['pace_display']}  cum {row['cum_time_display']}  [{row['segment']}]")
    print(f"  ... ({len(plan)} km total)")

    # --- 8. Training Periodization (33-week full marathon) ---
    section("8. Training Periodization (33-week full marathon cycle)")
    phases = design_training_phases("2025-11-02", "2025-03-10", 44.0, 46.5, 40, True)
    for p in phases:
        print(
            f"  Phase {p['phase_number']}: {p['name_cn']} ({p['name']}) "
            f"-- {p['weeks']}w  [{p['start_date']} -> {p['end_date']}]  "
            f"VDOT {p['vdot_target']}  "
            f"Vol {p['weekly_km_range']['min']}-{p['weekly_km_range']['max']} km/w"
        )

    # --- 9. Weekly Volume Progression ---
    section("9. Weekly Volume Progression (first 12 of 33 weeks)")
    vol = calculate_weekly_volume_progression(40, 64, 33, phases)
    for w in vol[:12]:
        marker = " [R]" if w["is_recovery_week"] else ""
        print(f"  Week {w['week_number']:2d}: {w['target_km']:5.1f} km  ({w['phase_name']}){marker}")
    print(f"  ... ({len(vol)} weeks total, peak = {max(w['target_km'] for w in vol)} km)")

    # --- 10. Milestone Tests ---
    section("10. Milestone Tests")
    tests = generate_milestone_tests(phases, 44.0)
    for t in tests:
        print(
            f"  Week {t['target_week']:2d}: {t['test_name_cn']} ({t['test_name']}) "
            f"-- {t['distance_km']} km @ {t['target_pace']}"
        )

    # --- 11. Weekly Template ---
    section("11. Weekly Template (Phase 2, Week 8, 50 km)")
    phase2 = phases[2] if len(phases) > 2 else phases[-1]
    tmpl = generate_week_template(phase2, 8, 50, 46.5, False)
    print(f"  Phase: {tmpl['phase_name_cn']}  Total: {tmpl['total_km']} km  Quality: {tmpl['quality_sessions']}")
    for d in tmpl["days"]:
        strength_note = f"  + {d['strength'][:30]}..." if d.get("strength") else ""
        print(
            f"  {d['day_cn']} {d['day']:9s}  {d['type_cn']:6s}  "
            f"{d['distance_km']:5.1f} km  {d['pace_display'] or '---':>8s}{strength_note}"
        )

    # --- 12. Utility round-trip ---
    section("12. Utility Functions")
    print(f"  format_pace(275)     = {format_pace(275)}")
    print(f"  format_time(5580)    = {format_time(5580)}")
    print(f"  parse_time('1:33:00')= {parse_time_to_seconds('1:33:00')}")
    pace_result = parse_pace_to_seconds("4'35\"")
    print(f"  parse_pace(\"4'35\\\"\") = {pace_result}")
    print(f"  get_distance_label(21.0975) = {get_distance_label(21.0975)}")
    print(f"  get_distance_label(42.195)  = {get_distance_label(42.195)}")

    print(f"\n{SEP}\n  All self-tests completed successfully.\n{SEP}")
