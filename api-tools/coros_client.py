#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
COROS Training Hub API Client.

Fetches activity data and training schedules from COROS Training Hub.
Supports both China (trainingcn.coros.com) and International (training.coros.com) endpoints.

Authentication:
  - Option A: Email/password login (auto-generates token)
  - Option B: Token from browser DevTools (CPL-coros-token cookie)

Usage:
  # List recent activities
  python coros_client.py --token <TOKEN> activities

  # List activities with email/password
  python coros_client.py --email <EMAIL> --password <PWD> activities --size 10

  # Fetch training schedule
  python coros_client.py --token <TOKEN> schedule --start 20260401 --end 20260412

  # Weekly training summary (last 7 days)
  python coros_client.py --token <TOKEN> weekly

  # Export raw JSON data
  python coros_client.py --token <TOKEN> activities --json

Getting token from browser:
  1. Open https://trainingcn.coros.com and log in
  2. F12 → Application → Cookies → copy value of `CPL-coros-token`
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta

try:
    import requests
    import urllib3
except ImportError:
    print("requests library required: pip install requests", file=sys.stderr)
    print("Or run with: uv run coros_client.py", file=sys.stderr)
    sys.exit(1)

# Suppress InsecureRequestWarning when SSL verify is disabled (corporate proxy)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ── API Configuration ──────────────────────────────────────────────

# China endpoints (trainingcn.coros.com)
CN_BASE_URL = "https://teamcnapi.coros.com"
# International endpoints (training.coros.com)
INTL_BASE_URL = "https://teamapi.coros.com"

ENDPOINTS = {
    "login":              "/account/login",
    "activities":         "/activity/query",
    "activity_detail":    "/activity/detail/query",
    "activity_download":  "/activity/detail/download",
    "schedule":           "/training/schedule/query",
    "dashboard":          "/dashboard/query",
    "dashboard_detail":   "/dashboard/detail/query",
    "analyse":            "/analyse/query",
    "program_calculate":  "/training/program/calculate",
    "program_add":        "/training/program/add",
    "program_query":      "/training/program/query",
    "exercise_query":     "/training/exercise/query",
}

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://trainingcn.coros.com",
    "Referer": "https://trainingcn.coros.com/",
}

REQUEST_TIMEOUT = 30


# ── Sport Type Mapping ─────────────────────────────────────────────

SPORT_TYPE_MAP = {
    (100, 8): "跑步",
    (100, 6): "跑步",
    (100, 15): "越野跑",
    (100, 31): "健走",
    (101, 0): "室内跑",
    (102, 15): "越野跑",
    (104, 0): "徒步",
    (200, 0): "骑行",
    (201, 0): "室内骑行",
    (400, 0): "有氧运动",
    (900, 31): "健走",
    (900, 0): "健走",
}

# Running workout segment templates (verified by openclaw-coros-coach)
# Used when creating structured running workouts via /training/program/add
RUNNING_TEMPLATES = {
    "warmup": {
        "name": "T1120",
        "originId": "425895398452936705",
        "exerciseType": 1,
        "overview": "sid_run_warm_up_dist",
    },
    "main": {
        "name": "T3001",
        "originId": "426109589008859136",
        "exerciseType": 2,
        "overview": "sid_run_training",
    },
    "cooldown": {
        "name": "T1122",
        "originId": "425895456971866112",
        "exerciseType": 3,
        "overview": "sid_run_cool_down_dist",
    },
}

# Sort number increment for segment ordering (2^24)
SORT_NO_INCREMENT = 16777216

# Default source image URL for workouts
DEFAULT_SOURCE_URL = (
    "https://d31oxp44ddzkyk.cloudfront.net/source/source_default"
    "/0/2fbd46e17bc54bc5873415c9fa767bdc.jpg"
)


# ── Helper Functions ───────────────────────────────────────────────

def format_pace(seconds_per_km: float) -> str:
    """Convert sec/km to min:sec/km string."""
    if not seconds_per_km or seconds_per_km <= 0:
        return "--:--"
    mins = int(seconds_per_km // 60)
    secs = int(seconds_per_km % 60)
    return f"{mins}'{secs:02d}\""


def format_duration(seconds: int | float) -> str:
    """Convert seconds to H:MM:SS or MM:SS string."""
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_distance(meters: float) -> str:
    """Convert meters to km with 2 decimal places."""
    if meters is None:
        return "0.00"
    return f"{meters / 1000:.2f}"


def format_date(date_int: int, start_time: int = None) -> str:
    """Convert YYYYMMDD int or Unix timestamp to readable date."""
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    if start_time:
        try:
            dt = datetime.fromtimestamp(int(start_time))
            return f"{dt.year}-{dt.month:02d}-{dt.day:02d} {weekdays[dt.weekday()]}"
        except (ValueError, OSError):
            pass
    s = str(date_int)
    try:
        dt = datetime(int(s[:4]), int(s[4:6]), int(s[6:8]))
        return f"{s[:4]}-{s[4:6]}-{s[6:8]} {weekdays[dt.weekday()]}"
    except (IndexError, ValueError):
        return str(date_int)


def get_sport_name(sport_type: int, mode: int) -> str:
    """Return sport type name in Chinese."""
    return SPORT_TYPE_MAP.get((sport_type, mode),
           SPORT_TYPE_MAP.get((sport_type, 0), "其他"))


# ── COROS API Client ───────────────────────────────────────────────

class CorosClient:
    """COROS Training Hub API client."""

    def __init__(self, region: str = "cn"):
        """Initialize client.

        Args:
            region: 'cn' for China, 'intl' for International.
        """
        self.base_url = CN_BASE_URL if region == "cn" else INTL_BASE_URL
        self.access_token: str | None = None
        self.user_id: str | None = None

        if region == "cn":
            self.headers = {**BASE_HEADERS}
        else:
            self.headers = {
                **BASE_HEADERS,
                "Origin": "https://training.coros.com",
                "Referer": "https://training.coros.com/",
            }

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}{ENDPOINTS[endpoint]}"

    def _auth_headers(self) -> dict:
        if not self.access_token:
            raise RuntimeError("Not authenticated. Call login() or set_token() first.")
        return {**self.headers, "accesstoken": self.access_token}

    def _write_headers(self) -> dict:
        """Headers for write operations (includes yfheader with userId)."""
        h = self._auth_headers()
        if self.user_id:
            h["yfheader"] = json.dumps({"userId": str(self.user_id)})
        return h

    # ── Authentication ─────────────────────────────────────────────

    def set_token(self, token: str) -> None:
        """Set access token directly (from browser DevTools)."""
        self.access_token = token

    def set_user_id(self, user_id: str) -> None:
        """Set user ID explicitly (needed for write operations)."""
        self.user_id = user_id

    def login(self, account: str, password: str) -> dict:
        """Login with email/phone and password.

        Args:
            account: Email address or phone number.
            password: Account password (will be MD5 hashed before sending).

        Returns:
            Login response data including accessToken and userId.
        """
        request_data = {
            "account": account,
            "accountType": 2,
            "pwd": hashlib.md5(password.encode()).hexdigest(),
        }
        resp = requests.post(
            self._url("login"),
            json=request_data,
            headers=self.headers,
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("result") != "0000":
            raise RuntimeError(f"Login failed: {result.get('message', result)}")

        data = result["data"]
        self.access_token = data["accessToken"]
        self.user_id = data.get("userId")
        return data

    # ── Activities ─────────────────────────────────────────────────

    def get_activities(self, size: int = 20, page: int = 1,
                       mode_list: str = "") -> dict:
        """Fetch activity list.

        Args:
            size: Number of records per page.
            page: Page number (1 = most recent).
            mode_list: Comma-separated sport type filter (empty = all).

        Returns:
            Raw API response dict.
        """
        params = {
            "size": size,
            "pageNumber": page,
            "modeList": mode_list,
        }
        resp = requests.get(
            self._url("activities"),
            params=params,
            headers=self._auth_headers(),
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()

    def get_activity_detail(self, label_id: str, sport_type: int) -> dict:
        """Fetch detailed activity data (splits, HR series, etc).

        Args:
            label_id: Activity's unique label ID.
            sport_type: Sport type code.

        Returns:
            Raw API response dict with summary, lapList, frequencyList.
        """
        payload = {
            "labelId": label_id,
            "sportType": sport_type,
            "screenW": 944,
            "screenH": 1440,
        }
        resp = requests.post(
            self._url("activity_detail"),
            params=payload,
            headers=self._auth_headers(),
            timeout=60,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Training Schedule ──────────────────────────────────────────

    def get_schedule(self, start_date: str, end_date: str) -> dict:
        """Fetch training schedule / calendar.

        Args:
            start_date: Start date in YYYYMMDD format.
            end_date: End date in YYYYMMDD format.

        Returns:
            Raw API response dict with schedule entities and week stages.
        """
        params = {
            "startDate": start_date,
            "endDate": end_date,
            "supportRestExercise": 1,
        }
        resp = requests.get(
            self._url("schedule"),
            params=params,
            headers=self._auth_headers(),
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Health & Recovery Data ─────────────────────────────────────

    def get_health_summary(self) -> dict:
        """Fetch health summary including HRV, recovery, resting HR.

        Calls /dashboard/query and extracts health-relevant fields
        from summaryInfo.

        Returns:
            Dict with keys: sleep_hrv, recovery, resting_hr, training_scores.
        """
        resp = requests.get(
            self._url("dashboard"),
            headers=self._auth_headers(),
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("result") != "0000":
            raise RuntimeError(f"API error: {result.get('message', result)}")

        info = result.get("data", {}).get("summaryInfo", {})

        # Extract sleep HRV data
        hrv_raw = info.get("sleepHrvData", {})
        hrv_list = []
        for item in hrv_raw.get("sleepHrvList", []):
            hrv_list.append({
                "date": item.get("happenDay"),
                "avg_hrv": item.get("avgSleepHrv", 0),
                "baseline": item.get("sleepHrvBase", 0),
                "sd": item.get("sleepHrvSd", 0),
            })

        sleep_hrv = {
            "baseline": hrv_raw.get("lastSleepHrvBase", 0),
            "sd": hrv_raw.get("lastSleepHrvSd", 0),
            "daily": hrv_list,
        }

        # Recovery info
        recovery = {
            "recovery_pct": info.get("recoveryPct", 0),
            "recovery_state": info.get("recoveryState", 0),
            "full_recovery_hours": info.get("fullRecoveryHours", 0),
        }

        # Training performance scores
        training_scores = {
            "aerobic_endurance": info.get("aerobicEnduranceScore", 0),
            "anaerobic_capacity": info.get("anaerobicCapacityScore", 0),
            "anaerobic_endurance": info.get("anaerobicEnduranceScore", 0),
            "lactate_threshold": info.get("lactateThresholdCapacityScore", 0),
            "stamina_level": info.get("staminaLevel", 0),
        }

        return {
            "sleep_hrv": sleep_hrv,
            "recovery": recovery,
            "resting_hr": info.get("rhr", 0),
            "training_scores": training_scores,
        }

    def get_training_load_detail(self, days: int = 14) -> dict:
        """Fetch daily training load metrics (ATI/CTI/TIB/fatigue).

        Calls /analyse/query and extracts daily training load detail
        from dayList.

        Args:
            days: Number of recent days to return (default 14).

        Returns:
            Dict with keys: daily_metrics (list), summary.
        """
        resp = requests.get(
            self._url("analyse"),
            headers=self._auth_headers(),
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("result") != "0000":
            raise RuntimeError(f"API error: {result.get('message', result)}")

        day_list = result.get("data", {}).get("dayList", [])

        # Take the last N days
        recent = day_list[-days:] if len(day_list) > days else day_list

        daily_metrics = []
        for d in recent:
            daily_metrics.append({
                "date": d.get("happenDay"),
                "training_load": d.get("trainingLoad", 0),
                "t7d": d.get("t7d", 0),
                "t28d": d.get("t28d", 0),
                "ati": d.get("ati", 0),       # Acute Training Index
                "cti": d.get("cti", 0),       # Chronic Training Index
                "tib": d.get("tib", 0),       # Training Intensity Balance
                "fatigue_rate": d.get("tiredRateNew", 0),
                "fatigue_state": d.get("tiredRateStateNew", 0),
                "recommended_tl_min": d.get("recomendTlMin", 0),
                "recommended_tl_max": d.get("recomendTlMax", 0),
            })

        # Compute summary from latest entry
        latest = daily_metrics[-1] if daily_metrics else {}
        summary = {
            "current_t7d": latest.get("t7d", 0),
            "current_t28d": latest.get("t28d", 0),
            "current_ati": latest.get("ati", 0),
            "current_cti": latest.get("cti", 0),
            "current_tib": latest.get("tib", 0),
            "current_fatigue_rate": latest.get("fatigue_rate", 0),
            "current_fatigue_state": latest.get("fatigue_state", 0),
        }

        return {
            "daily_metrics": daily_metrics,
            "summary": summary,
        }

    # ── Weekly Summary ─────────────────────────────────────────────

    def get_weekly_activities(self, weeks_ago: int = 0,
                              size: int = 50) -> list[dict]:
        """Fetch activities for a specific week.

        Args:
            weeks_ago: 0 = current week, 1 = last week, etc.
            size: Max activities to fetch (should cover a full week).

        Returns:
            List of activity dicts that fall within the target week.
        """
        today = datetime.now()
        # Monday of the target week
        target_monday = today - timedelta(days=today.weekday() + 7 * weeks_ago)
        target_monday = target_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        target_sunday = target_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

        result = self.get_activities(size=size, page=1)
        if result.get("result") != "0000":
            raise RuntimeError(f"API error: {result.get('message', result)}")

        data_list = result.get("data", {}).get("dataList", [])
        week_activities = []

        for a in data_list:
            start_time = a.get("startTime")
            if start_time:
                try:
                    dt = datetime.fromtimestamp(int(start_time))
                    if target_monday <= dt <= target_sunday:
                        week_activities.append(a)
                except (ValueError, OSError):
                    continue
        return week_activities

    def generate_weekly_summary(self, weeks_ago: int = 0) -> dict:
        """Generate a structured weekly training summary.

        Args:
            weeks_ago: 0 = current week, 1 = last week.

        Returns:
            Dict with weekly stats and per-activity breakdown.
        """
        activities = self.get_weekly_activities(weeks_ago=weeks_ago)

        today = datetime.now()
        target_monday = today - timedelta(days=today.weekday() + 7 * weeks_ago)
        target_sunday = target_monday + timedelta(days=6)

        summary = {
            "week_start": target_monday.strftime("%Y-%m-%d"),
            "week_end": target_sunday.strftime("%Y-%m-%d"),
            "total_activities": 0,
            "total_distance_km": 0.0,
            "total_duration_sec": 0,
            "total_training_load": 0,
            "run_count": 0,
            "run_distance_km": 0.0,
            "run_duration_sec": 0,
            "activities": [],
        }

        for a in activities:
            sport_type = a.get("sportType", 0)
            mode = a.get("mode", 0)
            distance_m = float(a.get("distance") or 0)
            total_time = int(a.get("totalTime") or 0)
            training_load = int(a.get("trainingLoad") or 0)

            activity_info = {
                "name": a.get("name", "Unknown"),
                "date": format_date(a.get("date"), a.get("startTime")),
                "type": get_sport_name(sport_type, mode),
                "distance_km": round(distance_m / 1000, 2),
                "duration": format_duration(total_time),
                "duration_sec": total_time,
                "pace": format_pace(a.get("avgSpeed", 0)),
                "avg_hr": a.get("avgHr", 0),
                "max_hr": a.get("maxHr", 0),
                "avg_cadence": a.get("avgCadence", 0),
                "training_load": training_load,
                "ascent": a.get("ascent", 0),
                "calories_kcal": (a.get("calorie") or 0) // 1000,
            }
            summary["activities"].append(activity_info)
            summary["total_activities"] += 1
            summary["total_distance_km"] += activity_info["distance_km"]
            summary["total_duration_sec"] += total_time
            summary["total_training_load"] += training_load

            # Count runs specifically (sportType 100=outdoor run, 101=indoor run)
            if sport_type in (100, 101):
                summary["run_count"] += 1
                summary["run_distance_km"] += activity_info["distance_km"]
                summary["run_duration_sec"] += total_time

        summary["total_distance_km"] = round(summary["total_distance_km"], 2)
        summary["run_distance_km"] = round(summary["run_distance_km"], 2)
        summary["total_duration_str"] = format_duration(summary["total_duration_sec"])
        summary["run_duration_str"] = format_duration(summary["run_duration_sec"])

        return summary

    # ── Workout Creation (Write API) ───────────────────────────────

    @staticmethod
    def build_running_segment(
        template_key: str,
        distance_km: float,
        pace_sec: int,
        pace_max_sec: int | None = None,
        sort_index: int = 1,
        display_name: str | None = None,
        user_id: int = 0,
    ) -> dict:
        """Build a single running workout segment payload.

        Args:
            template_key: 'warmup', 'main', or 'cooldown'.
            distance_km: Segment distance in km.
            pace_sec: Target pace in seconds/km (e.g. 330 = 5'30"/km).
            pace_max_sec: Max pace (slower end). Defaults to pace_sec + 10.
            sort_index: 1-based position index for ordering.
            display_name: Override segment display name (e.g. '快跑', '慢跑').
            user_id: COROS user ID (numeric). 0 for default.

        Returns:
            Dict ready for the exercises[] array in workout payload.
        """
        tpl = RUNNING_TEMPLATES[template_key]
        if pace_max_sec is None:
            pace_max_sec = pace_sec + 10

        segment = {
            "exerciseType": tpl["exerciseType"],
            "name": tpl["name"],
            "originId": tpl["originId"],
            "overview": tpl["overview"],
            "sportType": 1,
            "equipment": [1],
            "part": [0],
            "hrType": 3,
            "intensityType": 3,
            "intensityCustom": 0,
            "intensityDisplayUnit": 1,
            "intensityMultiplier": 0,
            "intensityPercent": 0,
            "intensityPercentExtend": 0,
            "intensityValue": pace_sec,
            "intensityValueExtend": pace_max_sec,
            "isIntensityPercent": False,
            "isDefaultAdd": 0,
            "isGroup": False,
            "targetType": 5,
            "targetValue": int(distance_km * 100000),
            "restType": 3,
            "restValue": 0,
            "sets": 1,
            "sortNo": sort_index * SORT_NO_INCREMENT,
            "groupId": "0",
            "access": 0,
            "sourceId": "0",
            "subType": 0,
            "userId": user_id,
            "createTimestamp": int(datetime.now().timestamp()),
            "defaultOrder": sort_index,
        }
        if display_name:
            segment["nameText"] = display_name
        return segment

    @staticmethod
    def build_running_workout_payload(
        name: str,
        overview: str,
        segments: list[dict],
        user_id: str = "0",
    ) -> dict:
        """Assemble a complete running workout payload.

        Args:
            name: Workout name (e.g. 'E跑-轻松跑 10km').
            overview: Short description.
            segments: List of segment dicts from build_running_segment().
            user_id: COROS user ID string.

        Returns:
            Complete payload dict for /training/program/add.
        """
        total_distance_cm = sum(s.get("targetValue", 0) for s in segments)
        total_sets = len(segments)

        return {
            "sportType": 1,
            "name": name,
            "overview": overview,
            "access": 1,
            "type": 0,
            "subType": 65535,
            "status": 1,
            "deleted": 0,
            "simple": False,
            "pbVersion": 2,
            "userId": user_id,
            "authorId": user_id,
            "sourceId": "425868142590476288",
            "sourceUrl": DEFAULT_SOURCE_URL,
            "distanceDisplayUnit": 1,
            "unit": 0,
            "version": 0,
            "poolLength": 2500,
            "poolLengthId": 1,
            "poolLengthUnit": 2,
            "isTargetTypeConsistent": 1,
            "targetType": 5,
            "targetValue": total_distance_cm,
            "duration": 0,
            "totalSets": total_sets,
            "sets": total_sets,
            "exerciseNum": total_sets,
            "exercises": segments,
            "headPic": "",
            "id": "0",
            "idInPlan": "0",
            "nickname": "",
            "originEssence": 0,
            "essence": 0,
            "estimatedType": 0,
            "estimatedValue": 0,
            "profile": "",
            "referExercise": {
                "intensityType": 1,
                "hrType": 0,
                "valueType": 1,
            },
            "sex": 0,
            "shareUrl": "",
            "star": 0,
            "thirdPartyId": 0,
            "trainingLoad": 0,
            "videoCoverUrl": "",
            "videoUrl": "",
            "fastIntensityTypeName": "pace",
            "poolLengthId": 1,
            "poolLengthUnit": 2,
            "createTimestamp": 0,
            "distance": 0,
        }

    def calculate_program(self, payload: dict) -> dict:
        """Calculate workout metrics (duration, training load).

        Calls /training/program/calculate before saving.

        Args:
            payload: Complete workout payload.

        Returns:
            Dict with duration, totalSets, trainingLoad.
        """
        resp = requests.post(
            self._url("program_calculate"),
            json=payload,
            headers=self._write_headers(),
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("result") != "0000":
            raise RuntimeError(
                f"Calculate failed: {result.get('message', result)}")
        return result.get("data", {})

    def add_program(self, payload: dict) -> dict:
        """Save workout to COROS Training Hub.

        Calls /training/program/add. The workout will sync to the watch.

        Args:
            payload: Complete workout payload (with calculated metrics applied).

        Returns:
            API response data (includes program ID on success).
        """
        resp = requests.post(
            self._url("program_add"),
            json=payload,
            headers=self._write_headers(),
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("result") != "0000":
            raise RuntimeError(
                f"Add program failed: {result.get('message', result)}")
        return result.get("data", result)

    def create_running_workout(
        self,
        name: str,
        overview: str,
        segments: list[dict],
    ) -> dict:
        """Create a running workout: calculate metrics then save.

        Args:
            name: Workout name.
            overview: Short description.
            segments: Segment dicts from build_running_segment().

        Returns:
            Dict with program_id, duration, training_load, total_sets.
        """
        user_id = str(self.user_id or "0")
        payload = self.build_running_workout_payload(
            name, overview, segments, user_id=user_id,
        )

        calculated = self.calculate_program(payload)
        payload["duration"] = calculated.get("duration", 0)
        payload["totalSets"] = calculated.get("totalSets", len(segments))
        payload["trainingLoad"] = calculated.get("trainingLoad", 0)
        payload["sets"] = payload["totalSets"]
        payload["distance"] = "0"

        program_id = self.add_program(payload)

        return {
            "program_id": program_id,
            "name": name,
            "duration": calculated.get("duration", 0),
            "training_load": calculated.get("trainingLoad", 0),
            "total_sets": calculated.get("totalSets", len(segments)),
        }

    def query_programs(
        self,
        name: str = "",
        sport_type: int = 0,
        limit: int = 10,
    ) -> dict:
        """Query existing workout programs.

        Args:
            name: Filter by name (empty = all).
            sport_type: 0=all, 1=running, 4=strength.
            limit: Max results.

        Returns:
            Raw API response data.
        """
        body = {
            "name": name,
            "supportRestExercise": 1,
            "startNo": 0,
            "limitSize": limit,
            "sportType": sport_type,
        }
        resp = requests.post(
            self._url("program_query"),
            json=body,
            headers=self._write_headers(),
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("result") != "0000":
            raise RuntimeError(
                f"Query programs failed: {result.get('message', result)}")
        return result.get("data", {})


# ── CLI Formatters ─────────────────────────────────────────────────

def print_activity(a: dict) -> None:
    """Print a single activity record."""
    sport_type = a.get("sportType", 100)
    mode = a.get("mode", 0)
    print(f"  名称: {a.get('name', 'Unknown')}")
    print(f"  日期: {format_date(a.get('date'), a.get('startTime'))}")
    print(f"  类型: {get_sport_name(sport_type, mode)}")
    print(f"  距离: {format_distance(float(a.get('distance') or 0))} km")
    print(f"  时长: {format_duration(a.get('totalTime', 0))}")
    print(f"  配速: {format_pace(a.get('avgSpeed', 0))} /km")
    if a.get("avgHr"):
        print(f"  平均心率: {a['avgHr']} bpm")
    if a.get("maxHr"):
        print(f"  最大心率: {a['maxHr']} bpm")
    if a.get("avgCadence"):
        print(f"  平均步频: {a['avgCadence']} spm")
    print(f"  训练负荷: {a.get('trainingLoad', 0)}")
    if a.get("ascent"):
        print(f"  累计爬升: {a['ascent']} m")
    if a.get("calorie"):
        print(f"  消耗热量: {a['calorie'] // 1000:,} kcal")
    print()


def print_weekly_summary(summary: dict) -> None:
    """Print weekly training summary."""
    print(f"\n{'='*50}")
    print(f"  周训练报告: {summary['week_start']} ~ {summary['week_end']}")
    print(f"{'='*50}")
    print(f"  总活动数: {summary['total_activities']} 次")
    print(f"  总距离:   {summary['total_distance_km']} km")
    print(f"  总时长:   {summary['total_duration_str']}")
    print(f"  总训练负荷: {summary['total_training_load']}")
    print(f"  ---")
    print(f"  跑步次数: {summary['run_count']} 次")
    print(f"  跑步距离: {summary['run_distance_km']} km")
    print(f"  跑步时长: {summary['run_duration_str']}")
    print(f"{'='*50}")

    if summary["activities"]:
        print(f"\n  活动明细:")
        print(f"  {'─'*46}")
        for i, act in enumerate(summary["activities"], 1):
            print(f"  [{i}] {act['date']} | {act['type']}")
            print(f"      {act['distance_km']} km | {act['duration']} | "
                  f"{act['pace']}/km | HR {act['avg_hr']}bpm | "
                  f"负荷 {act['training_load']}")
        print()


# ── CLI Entry Point ────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="COROS Training Hub — 训练数据获取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    # Auth options
    auth_group = parser.add_argument_group("认证方式 (二选一)")
    auth_group.add_argument(
        "--token", help="COROS accessToken (从浏览器 DevTools 获取)"
    )
    auth_group.add_argument("--email", help="COROS 账号邮箱/手机号")
    auth_group.add_argument("--password", help="COROS 账号密码")

    # Region
    parser.add_argument(
        "--region", choices=["cn", "intl"], default="cn",
        help="API 区域: cn=中国, intl=国际 (默认: cn)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="输出原始 JSON 格式"
    )

    # Subcommands
    sub = parser.add_subparsers(dest="command", help="子命令")

    # activities
    act = sub.add_parser("activities", help="查询活动记录")
    act.add_argument("--size", type=int, default=20, help="每页记录数 (默认: 20)")
    act.add_argument("--page", type=int, default=1, help="页码 (默认: 1)")

    # schedule
    sch = sub.add_parser("schedule", help="查询训练计划")
    sch.add_argument("--start", required=True, help="开始日期 (YYYYMMDD)")
    sch.add_argument("--end", required=True, help="结束日期 (YYYYMMDD)")

    # weekly
    wk = sub.add_parser("weekly", help="周训练汇总")
    wk.add_argument(
        "--weeks-ago", type=int, default=1,
        help="几周前 (0=本周, 1=上周, 默认: 1)"
    )

    # health
    sub.add_parser("health", help="健康数据 (HRV/恢复/训练负荷)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Build client
    client = CorosClient(region=args.region)

    # Authenticate
    if args.token:
        client.set_token(args.token)
    elif args.email and args.password:
        try:
            client.login(args.email, args.password)
            print("登录成功!", file=sys.stderr)
        except Exception as e:
            print(f"登录失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("错误: 需要 --token 或 --email + --password", file=sys.stderr)
        sys.exit(1)

    # Execute command
    if args.command == "activities":
        result = client.get_activities(size=args.size, page=args.page)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result.get("result") != "0000":
                print(f"API 错误: {result.get('message', result)}", file=sys.stderr)
                sys.exit(1)
            data = result.get("data", {})
            data_list = data.get("dataList", [])
            total = data.get("count", 0)
            print(f"\n共 {total} 条活动记录, 第 {args.page} 页:\n")
            for a in data_list:
                print_activity(a)

    elif args.command == "schedule":
        result = client.get_schedule(args.start, args.end)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result.get("result") != "0000":
                print(f"API 错误: {result.get('message', result)}", file=sys.stderr)
                sys.exit(1)
            data = result.get("data", {})
            entities = data.get("entityList", [])
            print(f"\n训练计划 ({args.start} ~ {args.end}):\n")
            for entity in entities:
                day = entity.get("happenDay", "")
                status = "✅" if entity.get("executeStatus") == 1 else "⬜"
                print(f"  {format_date(day)} {status}")
                if entity.get("exerciseBarChart"):
                    for ex in entity["exerciseBarChart"]:
                        print(f"    {ex.get('name', '?')}")
                print()

    elif args.command == "weekly":
        summary = client.generate_weekly_summary(weeks_ago=args.weeks_ago)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print_weekly_summary(summary)

    elif args.command == "health":
        health = client.get_health_summary()
        load = client.get_training_load_detail(days=7)
        if args.json:
            print(json.dumps({"health": health, "training_load": load},
                             ensure_ascii=False, indent=2))
        else:
            print(f"\n{'='*50}")
            print(f"  健康与恢复状态")
            print(f"{'='*50}")
            print(f"  安静心率:    {health['resting_hr']} bpm")
            rec = health['recovery']
            state_map = {1: "低", 2: "中低", 3: "中", 4: "完全恢复"}
            print(f"  恢复百分比:  {rec['recovery_pct']}%")
            print(f"  恢复状态:    {state_map.get(rec['recovery_state'], rec['recovery_state'])}")
            print(f"  完全恢复需:  {rec['full_recovery_hours']}h")
            print(f"\n  --- Sleep HRV ---")
            hrv = health['sleep_hrv']
            print(f"  HRV 基线:    {hrv['baseline']} ms")
            print(f"  HRV 标准差:  {hrv['sd']}")
            for d in hrv['daily']:
                ds = str(d['date'])
                dd = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"
                delta = d['avg_hrv'] - d['baseline']
                sign = "+" if delta >= 0 else ""
                print(f"    {dd}: HRV={d['avg_hrv']} ({sign}{delta})")
            print(f"\n  --- 训练负荷趋势 (近7天) ---")
            s = load['summary']
            print(f"  7天累计负荷:  {s['current_t7d']}")
            print(f"  28天累计负荷: {s['current_t28d']}")
            print(f"  ATI(急性):    {s['current_ati']}")
            print(f"  CTI(慢性):    {s['current_cti']}")
            print(f"  TIB(平衡):    {s['current_tib']}")
            fs_map = {1: "过度训练", 2: "恢复中", 3: "正常", 4: "减训练"}
            print(f"  疲劳度:       {s['current_fatigue_rate']:.1f} "
                  f"({fs_map.get(s['current_fatigue_state'], '?')})")
            print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
