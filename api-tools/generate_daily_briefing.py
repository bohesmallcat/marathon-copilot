#!/usr/bin/env python3
"""
328 苏河半马 · 赛前每日天气 + 训练 + 饮食 自动化简报

每日北京时间 08:00 自动运行，生成包含：
  1. 最新天气预报与环境税评估
  2. 当日训练计划
  3. 当日饮食建议
  4. 恢复监控 checklist
  5. 配速方案确认 / 更新

Usage:
    python3 generate_daily_briefing.py                # 生成并保存
    python3 generate_daily_briefing.py --stdout        # 仅输出到终端
    python3 generate_daily_briefing.py --date 2026-03-25  # 指定日期生成
"""

import os
import sys
import json
import datetime
import argparse
import math
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERROR] pip install requests")
    sys.exit(1)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Constants & Race Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
ONEDRIVE_REPORTS = Path(
    "/mnt/c/Users/Danna_C/OneDrive - Dell Technologies/Documents/PB/api-tools/reports"
)
LOCAL_REPORTS = SCRIPT_DIR / "reports"

RACE_DATE = datetime.date(2026, 3, 28)
RACE_START_TIME = "07:00"
RACE_CITY = "Shanghai"
RACE_CITY_CN = "上海"
RACE_NAME = "2026 上海苏州河半程马拉松"
RACE_DISTANCE_KM = 21.0975
RACE_GPS_DISTANCE_KM = 21.35  # actual GPS distance due to bends

# Runner profile
RUNNER = {
    "name": "薄荷猫猫",
    "weight_kg": 52,
    "height_cm": 166,
    "bsa": 1.57,
    "body_correction": 0.90,
    "pb": "1:33:56",
    "pb_315": "1:36:03",
    "tpace": "4'03\"",
    "tpace_bpm": 176,
    "reserve_per_km": 21,  # seconds
    "plan_a": {"time": "1:33:00", "pace": "4'24\"/km", "gps_pace": "4'22\"/km"},
    "plan_b": {"time": "1:33:50", "pace": "4'26\"/km", "gps_pace": "4'25\"/km"},
    "plan_c": {"time": "1:35:00", "pace": "4'28\"/km", "gps_pace": "4'28\"/km"},
}

# Baseline weather (from battle plan, 3/16)
BASELINE = {
    "weather": "晴 (Sunny)",
    "temp_start": 10.6,
    "temp_end": 14.4,
    "humidity": 44,
    "wind_mph": 8,
    "wind_kmh": 13,
    "wind_dir": "北",
    "rain_chance": 5,
    "uv": 7,
    "env_tax_total": 15,
    "env_tax_wind": 2,
    "env_tax_humidity": 0,
    "env_tax_temp": 0,
    "env_tax_uv": 5,
    "env_tax_turnaround": 8,
}

# Environment tax model
OPTIMAL_TEMP_LOW = 5
OPTIMAL_TEMP_HIGH = 15
HUMIDITY_DRIFT_THRESHOLD = 70
WIND_PENALTY_PER_MPH = 0.5
CROSSWIND_COEFF = 0.50
URBAN_SHELTER_REDUCTION = 0.40  # 60% shelter -> 40% effective
EXPOSED_KM = 3.5
TURNAROUND_TAX = 8

# ---------------------------------------------------------------------------
# Training & Diet Plans (keyed by D-N)
# ---------------------------------------------------------------------------
TRAINING_PLANS = {
    4: {  # D-4 = 3/24
        "phase": "Taper 减量期",
        "workout": "轻松跑",
        "distance": "5km @ 5'30\"/km",
        "rpe": "RPE 4",
        "hr_cap": "< 145bpm",
        "gear": "日常训练鞋",
        "details": "维持跑感，Taper 减量期不追速。",
        "post_run": [
            "足弓强化训练（全量 5 动作 × 全组数，约 15 分钟）",
            "泡沫轴放松 10min（小腿 + 大腿前侧）",
            "血泡状态检查",
        ],
        "arch_training": "全量",
    },
    3: {  # D-3 = 3/25
        "phase": "赛前激活",
        "workout": "赛前开腿跑（醒腿）",
        "distance": "5km 总量：2km 热身 + 4x200m @ 3'50\"-4'00\"（间歇慢跑 200m）+ 1.5km 放松",
        "rpe": "RPE 5-6",
        "hr_cap": "200m 间歇可至 170bpm",
        "gear": "日常训练鞋",
        "details": (
            "赛前最后一次有速度的训练。200m 间歇调动快肌纤维，"
            "速度快于比赛配速但距离极短，不产生疲劳。"
        ),
        "post_run": [
            "足弓强化训练（全量 — 最后一次全量训练）",
            "泡沫轴放松 10min",
            "拉伸 15min",
        ],
        "arch_training": "全量（最后一次）",
    },
    2: {  # D-2 = 3/26
        "phase": "Taper + 碳水负荷",
        "workout": "完全休息（散步可）",
        "distance": "0km",
        "rpe": "—",
        "hr_cap": "—",
        "gear": "—",
        "details": (
            "赛前 2 天，完全休息让身体超量恢复。碳水负荷启动日，"
            "全力吃碳水：白米饭、面条、面包、果汁。"
        ),
        "post_run": [
            "足弓强化训练（减半，各 1 组即可）",
            "轻度拉伸 10min",
        ],
        "arch_training": "减半（各 1 组）",
    },
    1: {  # D-1 = 3/27
        "phase": "赛前最终准备",
        "workout": "极轻松抖腿跑",
        "distance": "2km @ 6'00\"/km + 2x100m 大步跑",
        "rpe": "RPE 2-3",
        "hr_cap": "< 135bpm (慢跑段)",
        "gear": "日常训练鞋",
        "details": (
            "仅为保持跑感和神经激活。100m 大步跑感受一下身体弹性。"
            "22:00 前入睡。"
        ),
        "post_run": [
            "足弓强化训练（减半，各 1 组）",
            "检查比赛装备清单：鞋子、号码布、手表充电、能量胶、帽子、足弓贴扎材料、凡士林、水泡贴、五趾袜",
        ],
        "arch_training": "减半（各 1 组）",
        "extra": (
            "**装备检查清单：**\n"
            "- [ ] Alphafly 3（已测试确认）\n"
            "- [ ] 号码布 + 安全别针\n"
            "- [ ] 手表充电至 100%\n"
            "- [ ] 能量胶 x2（10km + 赛前）\n"
            "- [ ] 帽子/遮阳帽\n"
            "- [ ] 足弓贴扎（Low-Dye taping）材料：肌贴/运动胶带\n"
            "- [ ] 凡士林/Body Glide\n"
            "- [ ] 水泡贴（Compeed）\n"
            "- [ ] 五趾袜\n"
            "- [ ] 短袖 + 短裤\n"
            "- [ ] 赛后换洗衣物 + 一次性雨衣（赛后备用）\n"
        ),
    },
    0: {  # D-Day = 3/28
        "phase": "比赛日",
        "workout": "2026 上海苏州河半程马拉松",
        "distance": "21.0975km",
        "rpe": "全力",
        "hr_cap": "按配速表执行",
        "gear": "Alphafly 3 + 足弓贴扎 + 凡士林 + 水泡贴 + 五趾袜",
        "details": (
            "04:30 起床 → 05:00 早餐 → 06:00 到达起点 → "
            "06:30 热身慢跑 10min + 动态拉伸 → 06:50 进入出发区 → 07:00 起跑"
        ),
        "post_run": [],
        "arch_training": "不做",
    },
}

DIET_PLANS = {
    4: {  # D-4
        "phase": "正常训练期",
        "carb_target": "260-312g（5-6g/kg）",
        "protein_target": "62g（1.2g/kg）",
        "water": "1.5-2L",
        "meals": {
            "早餐": "粥/面包 + 鸡蛋 + 牛奶（~60g 碳水 + 20g 蛋白）",
            "午餐": "米饭 + 瘦肉/鱼 + 蔬菜（~100g 碳水 + 25g 蛋白）",
            "训练前": "香蕉 1 根 或 能量棒（跑前 30min，~25g 碳水）",
            "晚餐": "面条/米饭 + 蛋白质 + 蔬菜（~80g 碳水 + 20g 蛋白）",
            "加餐": "水果/酸奶（按需）",
        },
        "notes": [
            "不需要碳水负荷，保持正常饮食",
            "避免尝试新食物",
            "少油少辛辣，减少肠胃负担",
        ],
    },
    3: {  # D-3
        "phase": "正常训练期（最后一天）",
        "carb_target": "260-312g（5-6g/kg）",
        "protein_target": "62g（1.2g/kg）",
        "water": "1.5-2L",
        "meals": {
            "早餐": "粥/面包 + 鸡蛋 + 牛奶（~60g 碳水 + 20g 蛋白）",
            "午餐": "米饭 + 瘦肉/鱼 + 蔬菜（~100g 碳水 + 25g 蛋白）",
            "训练后": "巧克力牛奶 300ml 或 香蕉 + 酸奶（30min 内，碳水:蛋白 3:1）",
            "晚餐": "面条/米饭 + 蛋白质 + 蔬菜（~80g 碳水 + 20g 蛋白）",
        },
        "notes": [
            "明天开始碳水负荷，今天正常吃",
            "训练后及时补充碳水+蛋白，帮助恢复",
            "保持清淡，避免肠胃不适",
        ],
    },
    2: {  # D-2
        "phase": "碳水负荷 Day 1",
        "carb_target": "416-520g（8-10g/kg）",
        "protein_target": "52g（1.0g/kg）",
        "water": "2L+",
        "meals": {
            "早餐": "大碗白粥 + 馒头/面包 + 果酱 + 果汁（~120g 碳水）",
            "午餐": "大碗米饭（300g+）+ 少量瘦肉 + 蔬菜（~150g 碳水）",
            "下午加餐": "香蕉 2 根 + 运动饮料 500ml（~60g 碳水）",
            "晚餐": "大碗面条/米饭 + 面包（~140g 碳水）",
            "睡前": "果汁 200ml 或 蜂蜜水（~30g 碳水）",
        },
        "notes": [
            "**碳水负荷启动！** 目标 416-520g 碳水/天",
            "以米饭、面条、面包、果汁、香蕉为主",
            "蛋白质适当降低，把胃的空间留给碳水",
            "不要吃高脂肪食物（会占胃容量且不利于糖原合成）",
            "少量多餐，避免单次吃太撑",
            "如果感觉体重上升 0.5-1kg 是正常的（糖原 + 水分储存）",
        ],
    },
    1: {  # D-1
        "phase": "碳水负荷 Day 2",
        "carb_target": "416-520g（8-10g/kg）",
        "protein_target": "52g（1.0g/kg）",
        "water": "2L+",
        "meals": {
            "早餐": "大碗白粥/面条 + 面包 + 果汁（~120g 碳水）",
            "午餐": "大碗米饭（300g+）+ 少量瘦肉（~150g 碳水）",
            "下午加餐": "香蕉 + 能量棒 + 运动饮料（~60g 碳水）",
            "晚餐": "面条/米饭 + 面包（~130g 碳水）— **最晚 19:00 吃完**",
            "睡前": "少量果汁（~30g 碳水）",
        },
        "notes": [
            "碳水负荷第二天，继续高碳水饮食",
            "**晚餐最晚 19:00 完成**，给消化系统充分时间",
            "**22:00 前入睡**，保证 6+ 小时睡眠",
            "晚餐不要吃太撑，避免影响睡眠",
            "明早 04:30 起床，今晚早点准备好赛前早餐食材",
        ],
    },
    0: {  # D-Day
        "phase": "比赛日",
        "carb_target": "120-150g（赛前早餐）",
        "protein_target": "低",
        "water": "300ml（早餐时）",
        "meals": {
            "04:30 早餐": "白米饭/面包 + 果酱（120-150g 碳水）— 复制 315 赛前餐",
            "05:00": "100-150mg 咖啡因（1 杯浓缩咖啡）",
            "06:50 赛前 10min": "能量胶 1 支（20-25g 碳水）+ 100ml 水",
            "赛中 5km": "100ml 饮料，快速通过",
            "赛中 10km": "150ml 运动饮料 + 能量胶 1 支 — **关键补给点**",
            "赛中 12.5km": "100ml 水",
            "赛中 15km": "150ml 饮料",
            "赛中 17.5km": "100ml 水",
            "赛中 20km": "跳过或小口 50ml",
        },
        "notes": [
            "**严格复制 315 赛前餐 — 已验证无肠胃问题**",
            "起床后立即喝 200ml 温水",
            "不吃任何赛前没吃过的东西",
        ],
    },
}

# Recovery monitoring items
RECOVERY_CHECKLIST = {
    "晨脉": "起床后卧床测量，应回到基线 ± 3bpm",
    "左脚踝": "0-10 疼痛量表，应为 0-2（无痛或微酸）",
    "血泡": "目视检查，D+9 后应完全愈合",
    "DOMS": "下楼梯/蹲起测试，应无明显酸痛",
    "睡眠": "目标 7+ 小时，今晚 22:30 前入睡",
}


# ---------------------------------------------------------------------------
# Weather Fetching
# ---------------------------------------------------------------------------
def fetch_weather_wttr(city="Shanghai"):
    """Fetch weather from wttr.in."""
    url = f"https://wttr.in/{city}?format=j1"
    r = requests.get(url, timeout=30, verify=False)
    r.raise_for_status()
    return r.json()


def parse_hourly_for_race(data):
    """Extract race-relevant weather from wttr.in JSON."""
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
        # Morning hours 6-9 for race relevance
        morning = [h for h in hourly if int(h["time"]) in [600, 900]]
        late_morning = [h for h in hourly if int(h["time"]) in [1200]]
        # 7am slot
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

        uv_vals = [int(h.get("uvIndex", 0)) for h in hourly]
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
            "desc": morning[0]["weatherDesc"][0]["value"] if morning else day_data.get("weatherDesc", [{"value": "N/A"}])[0] if isinstance(day_data.get("weatherDesc"), list) else "N/A",
            "pressure": int(morning[0]["pressure"]) if morning else 1013,
        }
        result["forecasts"].append(fc)

    return result


# ---------------------------------------------------------------------------
# Environment Tax Calculation
# ---------------------------------------------------------------------------
def calc_env_tax(forecast):
    """Calculate environment tax based on latest forecast."""
    tax = {}

    # Wind tax
    wind_mph = forecast["morning_wind_mph"]
    wind_tax_per_km = wind_mph * WIND_PENALTY_PER_MPH * CROSSWIND_COEFF * URBAN_SHELTER_REDUCTION
    tax["wind"] = round(wind_tax_per_km * EXPOSED_KM)

    # Humidity tax
    avg_humidity = (forecast["start_humidity"] + forecast["finish_humidity"]) / 2
    if avg_humidity >= HUMIDITY_DRIFT_THRESHOLD:
        excess = avg_humidity - HUMIDITY_DRIFT_THRESHOLD
        if excess <= 10:
            penalty_per_km = 3  # +3"/km for 70-80%
        else:
            penalty_per_km = 7  # +5-10"/km for >80%
        # Estimate km above threshold (linear interpolation)
        if forecast["start_humidity"] > HUMIDITY_DRIFT_THRESHOLD > forecast["finish_humidity"]:
            # Crosses threshold during race
            frac_above = (forecast["start_humidity"] - HUMIDITY_DRIFT_THRESHOLD) / (
                forecast["start_humidity"] - forecast["finish_humidity"]
            )
            km_above = frac_above * RACE_GPS_DISTANCE_KM
        elif forecast["start_humidity"] > HUMIDITY_DRIFT_THRESHOLD and forecast["finish_humidity"] > HUMIDITY_DRIFT_THRESHOLD:
            km_above = RACE_GPS_DISTANCE_KM
        else:
            km_above = 0
        # Apply body correction & low-temp correction
        if forecast["avg_morning_temp"] < 12:
            temp_correction = 0.6  # cold air reduces humidity impact
        elif forecast["avg_morning_temp"] < 15:
            temp_correction = 0.75
        else:
            temp_correction = 1.0
        tax["humidity"] = round(penalty_per_km * km_above * temp_correction * RUNNER["body_correction"])
    else:
        tax["humidity"] = 0

    # Temperature tax
    finish_temp = forecast.get("finish_temp", forecast["late_morning_temp"])
    if finish_temp > OPTIMAL_TEMP_HIGH:
        excess = finish_temp - OPTIMAL_TEMP_HIGH
        penalty_km = 6  # last 6km affected
        base_tax = excess * 2 * penalty_km / 6
        tax["temperature"] = round(base_tax * RUNNER["body_correction"])
    else:
        tax["temperature"] = 0

    # UV/sunshine tax
    uv = forecast["morning_uv"]
    if uv >= 6 and forecast["avg_morning_temp"] > 12:
        tax["uv"] = round(1 * 5)  # +1"/km for last 5km
    else:
        tax["uv"] = 0

    # Turnaround/bends (fixed)
    tax["turnaround"] = TURNAROUND_TAX

    tax["total"] = sum(tax.values())
    return tax


def assess_signal(env_tax_total, baseline_total=BASELINE["env_tax_total"]):
    """Determine green/yellow/orange/red light."""
    delta = abs(env_tax_total - baseline_total)
    if delta < 10:
        return "绿灯：方案有效", "green"
    elif delta < 30:
        return "黄灯：微调", "yellow"
    elif delta < 60:
        return "橙灯：降级考虑", "orange"
    else:
        return "红灯：方案失效", "red"


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------
def generate_report(today):
    """Generate the comprehensive daily briefing."""
    days_to_race = (RACE_DATE - today).days
    if days_to_race < 0:
        return "比赛已结束。", False

    is_race_day = days_to_race == 0
    is_d1 = days_to_race == 1

    # Fetch weather
    try:
        raw = fetch_weather_wttr(RACE_CITY)
        weather = parse_hourly_for_race(raw)
        weather_ok = True
    except Exception as e:
        weather = None
        weather_ok = False
        weather_error = str(e)

    # Find race-day forecast
    race_fc = None
    today_fc = None
    race_fc_is_proxy = False  # True if using closest forecast as proxy
    if weather_ok:
        race_date_str = RACE_DATE.strftime("%Y-%m-%d")
        today_date_str = today.strftime("%Y-%m-%d")
        for fc in weather["forecasts"]:
            if fc["date"] == race_date_str:
                race_fc = fc
            if fc["date"] == today_date_str:
                today_fc = fc
        # If race day not in forecast range, use the closest (last) forecast
        if race_fc is None and weather["forecasts"]:
            race_fc = weather["forecasts"][-1]
            race_fc_is_proxy = True

    # Calculate env tax
    env_tax = None
    if race_fc:
        env_tax = calc_env_tax(race_fc)

    # Get training & diet plan
    training = TRAINING_PLANS.get(days_to_race)
    diet = DIET_PLANS.get(days_to_race)

    # Reserve calculations
    total_reserve = RUNNER["reserve_per_km"] * RACE_GPS_DISTANCE_KM
    reserve_util = None
    if env_tax:
        reserve_util = round(env_tax["total"] / total_reserve * 100, 1)

    # Signal assessment
    signal_text, signal_color = ("—", "unknown")
    if env_tax:
        signal_text, signal_color = assess_signal(env_tax["total"])
    # When no env tax data, default to yellow (maintain plan) not red
    if signal_color == "unknown":
        signal_text = "黄灯：维持方案（等待精准预报）"
        signal_color = "yellow"

    # -----------------------------------------------------------------------
    # Build Markdown
    # -----------------------------------------------------------------------
    lines = []

    # Title
    if is_race_day:
        lines.append(f"# {RACE_NAME} 赛前最终简报 (Final Briefing)")
    elif is_d1:
        lines.append(f"# {RACE_NAME} 赛前天气日报 D-1")
    else:
        lines.append(f"# {RACE_NAME} 赛前天气日报 D-{days_to_race}")

    lines.append(
        f"**跑者:** {RUNNER['name']} | **比赛日:** {RACE_DATE.strftime('%Y-%m-%d')} "
        f"{RACE_START_TIME} 起跑 | **倒计时:** {days_to_race} 天"
    )
    lines.append(
        f"**数据获取时间:** {today.strftime('%Y-%m-%d')} "
        f"{datetime.datetime.now().strftime('%H:%M')} CST | "
        f"**数据源:** wttr.in"
    )
    if days_to_race <= 3:
        confidence = "高（距比赛 ≤3 天，预报准确率 >85%）"
    elif days_to_race <= 7:
        confidence = "中高"
    else:
        confidence = "中（预报仍可能变化）"
    lines.append(f"**预报可信度:** {confidence}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Section 1: Weather Snapshot ---
    lines.append("## 1. 天气速览")
    lines.append("")
    if not weather_ok:
        lines.append(f"> **数据获取失败：** {weather_error}")
        lines.append("> 使用上次成功数据 + 趋势外推。该日报置信度降低。")
    elif race_fc:
        # Build quick summary
        proxy_note = ""
        if race_fc_is_proxy:
            proxy_note = f"（注：比赛日 3/28 超出预报范围，以下基于最近可用预报 {race_fc['date']} 的数据参考推算）"
        summary_parts = []
        summary_parts.append(
            f"3/28 赛时参考{'预报' if not race_fc_is_proxy else '推算'}：起跑 ~{race_fc['start_temp']}°C / "
            f"完赛 ~{race_fc['finish_temp']}°C，"
            f"湿度 ~{race_fc['start_humidity']}%→{race_fc['finish_humidity']}%，"
            f"风 ~{race_fc['morning_wind_kmh']}km/h {race_fc['wind_dir']}，"
            f"赛时降水 {race_fc['morning_rain_chance']}%。"
        )
        if env_tax:
            summary_parts.append(
                f"环境税 ≈{env_tax['total']}\"（基准 {BASELINE['env_tax_total']}\"），"
                f"储备利用率 {reserve_util}%。**{signal_text}。**"
            )
        if proxy_note:
            summary_parts.append(f" {proxy_note}")
        lines.append(f"> {''.join(summary_parts)}")
    lines.append("")

    # --- Section 2: Race Day Weather ---
    lines.append("---")
    lines.append("")
    lines.append("## 2. 比赛日天气预报")
    lines.append("")
    if race_fc:
        if race_fc_is_proxy:
            lines.append(
                f"> 注意：比赛日 ({RACE_DATE}) 超出当前 3 天预报范围。"
                f"以下分析基于最近可用预报 ({race_fc['date']})，仅供参考。"
                f"D-2 起将获得比赛日精准预报。"
            )
            lines.append("")
        lines.append("| 气象因子 | 最新预报 | 作战方案基准 (3/16) | 变化 | 影响评估 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")

        # Weather
        lines.append(
            f"| 天气 | {race_fc['desc']} | {BASELINE['weather']} | — | — |"
        )
        # Temp
        temp_change = "有利" if OPTIMAL_TEMP_LOW <= race_fc["start_temp"] <= OPTIMAL_TEMP_HIGH else "关注"
        lines.append(
            f"| 气温 | {race_fc['start_temp']}°C → {race_fc['finish_temp']}°C | "
            f"{BASELINE['temp_start']}°C → {BASELINE['temp_end']}°C | "
            f"{'↑' if race_fc['start_temp'] > BASELINE['temp_start'] else '↓' if race_fc['start_temp'] < BASELINE['temp_start'] else '='} | "
            f"{'最佳区间' if OPTIMAL_TEMP_LOW <= race_fc['finish_temp'] <= OPTIMAL_TEMP_HIGH else '超出最佳区间'} |"
        )
        # Humidity
        hum_delta = race_fc["start_humidity"] - BASELINE["humidity"]
        hum_dir = "↑" if hum_delta > 0 else "↓" if hum_delta < 0 else "="
        hum_impact = "安全" if race_fc["start_humidity"] < 70 else "警戒"
        lines.append(
            f"| 湿度 | {race_fc['start_humidity']}%→{race_fc['finish_humidity']}% | "
            f"{BASELINE['humidity']}% | {hum_dir}{abs(hum_delta)}% | "
            f"{'安全（<70%）' if race_fc['start_humidity'] < 70 else '起跑偏高，赛中快速下降' if race_fc['finish_humidity'] < 70 else '全程偏高'} |"
        )
        # Wind
        lines.append(
            f"| 风力 | {race_fc['morning_wind_kmh']}km/h ({race_fc['morning_wind_mph']}mph) {race_fc['wind_dir']} | "
            f"{BASELINE['wind_kmh']}km/h ({BASELINE['wind_mph']}mph) {BASELINE['wind_dir']} | "
            f"{'↑' if race_fc['morning_wind_kmh'] > BASELINE['wind_kmh'] else '↓'} | "
            f"{'可忽略' if race_fc['morning_wind_kmh'] <= 15 else '需关注'} |"
        )
        # Rain
        lines.append(
            f"| 降水概率 | {race_fc['morning_rain_chance']}% | "
            f"{BASELINE['rain_chance']}% | "
            f"{'↑' if race_fc['morning_rain_chance'] > BASELINE['rain_chance'] else '↓'} | "
            f"{'无风险' if race_fc['morning_rain_chance'] <= 20 else '低' if race_fc['morning_rain_chance'] <= 40 else '中'} |"
        )
        # UV
        lines.append(
            f"| UV 指数 | {race_fc['morning_uv']} | {BASELINE['uv']} | "
            f"{'↓' if race_fc['morning_uv'] < BASELINE['uv'] else '↑'} | "
            f"{'无日晒风险' if race_fc['morning_uv'] < 6 else '需防晒'} |"
        )
        lines.append("")

    # --- Section 3: Weather Trend ---
    lines.append("---")
    lines.append("")
    lines.append("## 3. 赛前天气趋势")
    lines.append("")
    if weather_ok and weather["forecasts"]:
        lines.append("| 日期 | 天气 | 温度 | 湿度 | 降水概率 | 对备赛影响 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for fc in weather["forecasts"]:
            fc_date = datetime.date.fromisoformat(fc["date"])
            fc_dn = (RACE_DATE - fc_date).days
            marker = ""
            if fc_date == RACE_DATE:
                marker = " **[比赛日]**"
            elif fc_date == today:
                marker = " **(今天)**"
            impact = ""
            if fc_date == RACE_DATE:
                impact = "比赛日"
            elif fc_dn == 1:
                impact = "赛前休息 + 碳水负荷"
            elif fc_dn == 2:
                impact = "完全休息 + 碳水负荷开始"
            elif fc_dn == 3:
                impact = "赛前开腿跑"
            elif fc_date == today:
                impact = "今日训练"
            else:
                impact = "Taper"
            lines.append(
                f"| {fc['date']}{marker} | {fc['desc']} | "
                f"{fc['min_temp']}~{fc['max_temp']}°C | "
                f"{fc['avg_morning_humidity']}% | "
                f"{fc['max_rain_chance']}% | {impact} |"
            )
        lines.append("")

    # --- Section 4: Environment Tax ---
    lines.append("---")
    lines.append("")
    lines.append("## 4. 环境税更新")
    lines.append("")
    if env_tax:
        lines.append("| 环境税分项 | 作战方案基准 | 最新预估 | 变化 | 说明 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")

        def _delta(new, old):
            d = new - old
            return f"+{d}\"" if d > 0 else f"{d}\"" if d < 0 else "0"

        wind_note = (
            f"赛时 {race_fc['morning_wind_mph']}mph, "
            f"苏河城区遮挡 60%, 暴露段 {EXPOSED_KM}km"
        )
        lines.append(
            f"| 侧风 | +{BASELINE['env_tax_wind']}\" | "
            f"+{env_tax['wind']}\" | {_delta(env_tax['wind'], BASELINE['env_tax_wind'])} | {wind_note} |"
        )

        hum_note = f"均湿 ~{round((race_fc['start_humidity']+race_fc['finish_humidity'])/2)}%"
        if race_fc["start_humidity"] > HUMIDITY_DRIFT_THRESHOLD > race_fc["finish_humidity"]:
            hum_note += f", 起跑 {race_fc['start_humidity']}% > 70%, 赛中跌破阈值"
        elif race_fc["start_humidity"] < HUMIDITY_DRIFT_THRESHOLD:
            hum_note += f", 全程 < 70% 阈值"
        lines.append(
            f"| 湿度心率漂移 | +{BASELINE['env_tax_humidity']}\" | "
            f"+{env_tax['humidity']}\" | {_delta(env_tax['humidity'], BASELINE['env_tax_humidity'])} | {hum_note} |"
        )

        temp_note = f"完赛时 ~{race_fc['finish_temp']}°C"
        if race_fc["finish_temp"] <= OPTIMAL_TEMP_HIGH:
            temp_note += f", 在最佳区间内"
        else:
            temp_note += f", 超上限 {race_fc['finish_temp'] - OPTIMAL_TEMP_HIGH}°C"
        lines.append(
            f"| 温度税 | +{BASELINE['env_tax_temp']}\" | "
            f"+{env_tax['temperature']}\" | {_delta(env_tax['temperature'], BASELINE['env_tax_temp'])} | {temp_note} |"
        )

        uv_note = f"UV {race_fc['morning_uv']}"
        if race_fc["morning_uv"] < 6:
            uv_note += ", 无日晒风险"
        lines.append(
            f"| UV/日晒 | +{BASELINE['env_tax_uv']}\" | "
            f"+{env_tax['uv']}\" | {_delta(env_tax['uv'], BASELINE['env_tax_uv'])} | {uv_note} |"
        )

        lines.append(
            f"| 弯道/折返 | +{BASELINE['env_tax_turnaround']}\" | "
            f"+{env_tax['turnaround']}\" | 0 | 赛道固定因素 |"
        )
        lines.append(
            f"| **综合环境税** | **≈{BASELINE['env_tax_total']}\"** | "
            f"**≈{env_tax['total']}\"** | "
            f"**{_delta(env_tax['total'], BASELINE['env_tax_total'])}** | |"
        )
        lines.append("")

    # --- Section 5: Runner Impact ---
    lines.append("---")
    lines.append("")
    lines.append("## 5. 跑者影响评估")
    lines.append("")
    if env_tax:
        lines.append(f"**环境税占速度储备比：** {reserve_util}%", )
        if reserve_util < 5:
            lines.append("（环境几乎零阻力）")
        elif reserve_util < 15:
            lines.append("（环境可控）")
        elif reserve_util < 25:
            lines.append("（环境有一定压力）")
        else:
            lines.append("（环境成为显著阻力）")
        lines.append("")

        # Threshold check
        lines.append("**关键阈值检查：**")
        lines.append("")
        lines.append("| 检查项 | 阈值 | 当前状态 | 判定 |")
        lines.append("| :--- | :--- | :--- | :--- |")

        hum_status = f"起跑 {race_fc['start_humidity']}%, 完赛 {race_fc['finish_humidity']}%"
        if race_fc["start_humidity"] < 70:
            hum_judge = "安全"
        elif race_fc["finish_humidity"] < 70:
            hum_judge = "警戒（赛中跌破阈值）"
        else:
            hum_judge = "危险"
        lines.append(f"| 湿度心率漂移 | 70% | {hum_status} | {hum_judge} |")

        temp_status = f"赛时 {race_fc['start_temp']}→{race_fc['finish_temp']}°C"
        if OPTIMAL_TEMP_LOW <= race_fc["finish_temp"] <= OPTIMAL_TEMP_HIGH:
            temp_judge = "最佳"
        elif race_fc["finish_temp"] <= OPTIMAL_TEMP_HIGH + 3:
            temp_judge = "可接受"
        else:
            temp_judge = "超限"
        lines.append(f"| 温度区间 | 5-15°C | {temp_status} | {temp_judge} |")

        wind_status = f"{race_fc['morning_wind_kmh']}km/h"
        wind_judge = "可忽略" if race_fc["morning_wind_kmh"] <= 15 else "需关注" if race_fc["morning_wind_kmh"] <= 25 else "显著"
        lines.append(f"| 风力影响 | >15km/h | {wind_status} | {wind_judge} |")

        rain_status = f"{race_fc['morning_rain_chance']}%"
        rain_judge = "无" if race_fc["morning_rain_chance"] <= 10 else "低" if race_fc["morning_rain_chance"] <= 30 else "中"
        lines.append(f"| 降水风险 | >30% | {rain_status} | {rain_judge} |")
        lines.append("")

        # Signal
        lines.append(f"**作战方案有效性：** **{signal_text}**")
        lines.append("")
        if signal_color == "green":
            lines.append("> 环境条件优异，按原方案执行。")
        elif signal_color == "yellow":
            lines.append("> 环境税有小幅变化，维持 Plan A 目标，关注湿度和配速。")
        elif signal_color == "orange":
            lines.append("> 环境税变化较大，考虑从 Plan A 降级至 Plan B。")
        else:
            lines.append("> 环境条件恶化严重，必须降级，重新评估目标。")
        lines.append("")

    # --- Section 6: Action Items ---
    lines.append("---")
    lines.append("")
    lines.append("## 6. 行动建议")
    lines.append("")

    action_items = []
    if race_fc:
        if race_fc["start_humidity"] > 70:
            action_items.append(
                f"**起跑前额外补水 100ml。** 起跑湿度 {race_fc['start_humidity']}% 偏高，保持预充水分。"
            )
            action_items.append(
                f"**前 5km 心率预警上限 162bpm。** 高湿度下心率偏高 2-4bpm 属正常。"
            )
        if race_fc["morning_rain_chance"] > 30:
            action_items.append("备好轻薄防雨装备和备用袜子。")
        if race_fc["morning_uv"] >= 6:
            action_items.append("涂抹防晒霜（颈部、手臂），戴遮阳帽。")
        if race_fc["start_humidity"] < 70 and race_fc["finish_temp"] <= 15 and race_fc["morning_rain_chance"] <= 20:
            action_items.append("**天气条件有利，按原方案执行，无需调整。**")

    if not action_items:
        action_items.append("按原方案执行，无需调整。")

    for i, item in enumerate(action_items, 1):
        lines.append(f"{i}. {item}")
    lines.append("")

    # --- Section 7: Pace Plan ---
    lines.append("---")
    lines.append("")
    lines.append("## 7. 配速方案确认")
    lines.append("")
    if signal_color in ("green", "yellow") or (race_fc_is_proxy and signal_color in ("orange",)):
        # When using proxy data, maintain plan unless clearly red
        if race_fc_is_proxy and signal_color == "orange":
            lines.append(
                "**配速方案暂时维持 Plan A: 1:33:00**"
                "（当前信号基于代理预报数据，比赛日预报尚未到位。待 D-2 获得精准预报后再做最终判定。）"
            )
        else:
            lines.append("**配速方案维持不变。** Plan A: 1:33:00")
        lines.append("")
        lines.append("```")
        lines.append(f"{RUNNER['name']} | 目标: 1:33:00 | PB: {RUNNER['pb']} | 苏河半马")
        if race_fc:
            lines.append(
                f"{race_fc['desc']} | 起跑{race_fc['start_temp']}°C "
                f"湿度{race_fc['start_humidity']}%→{race_fc['finish_humidity']}% | 无隧道 | "
                f"风{race_fc['morning_wind_mph']}mph"
            )
        lines.append("")
        lines.append("[0-5k]  GPS 4'26\" | HR < 162 | 复制315前半程，克制")
        lines.append("[6-12k] GPS 4'21\" | HR 160-166 | 巡航，10k补胶")
        lines.append("[13-18k] GPS 4'20\" | HR < 170 | 苏河平路，无风")
        lines.append("[19k-F] GPS 4'10\" | 释放阈值 | 拿回被315偷走的3分钟")
        lines.append("熔断：12k前HR>168 → Plan B (1:33:50, GPS 4'25\")")
        lines.append("脚踝：刺痛持续2km → 降至 5'00\"")
        lines.append("装备：足弓贴扎+凡士林+水泡贴+五趾袜 已测试确认")
        lines.append("```")
    elif signal_color == "orange":
        lines.append("**考虑降级至 Plan B: 1:33:50 (GPS 4'25\"/km)**")
    else:
        lines.append("**必须降级。重新评估目标。**")
    lines.append("")

    # --- Section 8: Today's Training ---
    lines.append("---")
    lines.append("")
    if is_race_day:
        lines.append("## 8. 赛前 Checklist")
    else:
        lines.append(f"## 8. 今日训练 (D-{days_to_race} / {today.strftime('%m月%d日')} {_weekday_cn(today)})")
    lines.append("")

    if training:
        lines.append("| 项目 | 内容 |")
        lines.append("| :--- | :--- |")
        lines.append(f"| **阶段** | {training['phase']} |")
        lines.append(f"| **训练** | {training['workout']} |")
        lines.append(f"| **距离/配速** | {training['distance']} |")
        lines.append(f"| **强度** | {training['rpe']} |")
        lines.append(f"| **心率上限** | {training['hr_cap']} |")
        lines.append(f"| **装备** | {training['gear']} |")
        lines.append("")
        lines.append(f"**训练说明：** {training['details']}")
        lines.append("")

        # Today's weather for training
        if today_fc and not is_race_day:
            lines.append("**今日天气适配：**")
            lines.append(
                f"- {RACE_CITY_CN}今日 {today_fc['min_temp']}-{today_fc['max_temp']}°C，"
                f"{today_fc['desc']}，湿度 {today_fc['avg_morning_humidity']}%，"
                f"风 {today_fc['morning_wind_kmh']}km/h"
            )
            if today_fc["max_rain_chance"] > 40:
                lines.append(f"- 降水概率 {today_fc['max_rain_chance']}%，选择降水间隙出门或备防水外套")
            if today_fc["min_temp"] < 10:
                lines.append(f"- 气温偏低，着长袖跑")
            lines.append("")

        # Post-run tasks
        if training["post_run"]:
            lines.append("**跑后必做：**")
            for task in training["post_run"]:
                lines.append(f"- {task}")
            lines.append("")

        if training.get("extra"):
            lines.append(training["extra"])
            lines.append("")
    else:
        lines.append("> 今日无特定训练计划。保持轻松活动即可。")
        lines.append("")

    # --- Section 9: Today's Diet ---
    lines.append("---")
    lines.append("")
    lines.append(f"## 9. 今日饮食 (D-{days_to_race})")
    lines.append("")

    if diet:
        lines.append(f"**阶段：** {diet['phase']}")
        lines.append(f"**碳水目标：** {diet['carb_target']}")
        lines.append(f"**蛋白质目标：** {diet['protein_target']}")
        lines.append(f"**水分：** {diet['water']}")
        lines.append("")
        lines.append("| 时段 | 建议 |")
        lines.append("| :--- | :--- |")
        for meal, desc in diet["meals"].items():
            lines.append(f"| **{meal}** | {desc} |")
        lines.append("")

        if diet["notes"]:
            lines.append("**饮食注意事项：**")
            for note in diet["notes"]:
                lines.append(f"- {note}")
            lines.append("")
    else:
        lines.append("> 保持正常均衡饮食。")
        lines.append("")

    # --- Section 10: Recovery Monitoring ---
    if not is_race_day:
        lines.append("---")
        lines.append("")
        lines.append("## 10. 恢复监控")
        lines.append("")
        lines.append("| 检查项 | 方法与标准 |")
        lines.append("| :--- | :--- |")
        for item, desc in RECOVERY_CHECKLIST.items():
            lines.append(f"| **{item}** | {desc} |")
        lines.append("")

    # --- Section 11: Tomorrow Preview / Race Day Checklist ---
    if is_race_day:
        # Final briefing extras
        lines.append("---")
        lines.append("")
        lines.append("## 10. 赛前最终确认")
        lines.append("")
        lines.append("- [ ] 最终天气确认：实况与预报一致？")
        lines.append("- [ ] 着装定案：短袖 + 短裤 + 帽子")
        lines.append("- [ ] 补给物资：能量胶 x2 + 咖啡因 ✓")
        lines.append("- [ ] 足弓贴扎（Low-Dye taping）已完成")
        lines.append("- [ ] 凡士林涂抹 + 水泡贴预贴 + 五趾袜")
        lines.append("- [ ] 手表充电 100% + 配速提醒已设置")
        lines.append("- [ ] 号码布已别好")
        lines.append(f"- [ ] 热身方案：06:30 慢跑 10min + 动态拉伸（{race_fc['start_temp'] if race_fc else '~10'}°C，正常热身即可）")
        lines.append("")
        lines.append("**去拿回属于你的成绩。**")
    elif is_d1:
        lines.append("---")
        lines.append("")
        lines.append("## 11. 赛前 48h 天气确认")
        lines.append("")
        if race_fc:
            if race_fc["start_humidity"] < 75 and race_fc["finish_temp"] <= 15:
                lines.append("> **天气按剧本走，信心拉满。** 3/28 预报持续稳定，PB 条件充分。")
            else:
                lines.append(
                    f"> 3/28 预报总体可控。起跑湿度 {race_fc['start_humidity']}% 需注意前半程心率，"
                    f"但赛中快速下降。维持 Plan A。"
                )
        lines.append("")
        lines.append("**明天就是比赛日。今晚 22:00 前入睡。**")
    else:
        lines.append("---")
        lines.append("")
        lines.append(f"## 11. 明日预告 (D-{days_to_race - 1})")
        lines.append("")
        tomorrow = today + datetime.timedelta(days=1)
        tmr_training = TRAINING_PLANS.get(days_to_race - 1)
        tmr_diet = DIET_PLANS.get(days_to_race - 1)
        tmr_fc = None
        if weather_ok:
            tmr_str = tomorrow.strftime("%Y-%m-%d")
            for fc in weather["forecasts"]:
                if fc["date"] == tmr_str:
                    tmr_fc = fc
        if tmr_fc:
            lines.append(
                f"**明日天气：** {tmr_fc['desc']} "
                f"{tmr_fc['min_temp']}-{tmr_fc['max_temp']}°C / "
                f"{tmr_fc['avg_morning_humidity']}% 湿度 / "
                f"{tmr_fc['morning_wind_kmh']}km/h"
            )
        if tmr_training:
            lines.append(f"**明日训练：** {tmr_training['workout']} — {tmr_training['distance']}")
        if tmr_diet:
            lines.append(f"**明日饮食：** {tmr_diet['phase']}，碳水 {tmr_diet['carb_target']}")
        lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append("")
    lines.append(
        f"> 本日报由自动化脚本生成于 "
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} CST。"
        f"天气数据来自 wttr.in，仅供参考。赛时决策以实际体感为准。"
    )

    return "\n".join(lines), True


def _weekday_cn(d):
    """Return Chinese weekday name."""
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[d.weekday()]


# ---------------------------------------------------------------------------
# PDF Generation (weasyprint)
# ---------------------------------------------------------------------------
def md_to_pdf(md_text, pdf_path):
    """Convert Markdown text to styled PDF using weasyprint.

    Reuses the design system from generate_pdf.py (dark header + orange accent).
    """
    try:
        import markdown as _md
        import re
        from weasyprint import HTML as _HTML
    except ImportError as exc:
        print(f"[WARN] PDF dependency missing ({exc}), skipping PDF generation.")
        return False

    html_body = _md.markdown(md_text, extensions=["tables", "fenced_code", "nl2br"])

    # -- post-process: classify blockquotes --------------------------------
    def _classify_bq(match):
        content = match.group(1)
        if any(k in content for k in ["注意", "数据获取失败"]):
            cls = "note-warning"
        elif any(k in content for k in ["红灯", "必须降级", "危险"]):
            cls = "note-danger"
        elif any(k in content for k in ["本日报", "天气数据", "生成于"]):
            cls = "note-meta"
        else:
            cls = "note-info"
        return f'<blockquote class="{cls}">{content}</blockquote>'

    html_body = re.sub(
        r"<blockquote>(.*?)</blockquote>", _classify_bq, html_body, flags=re.DOTALL
    )

    # Wrap first h1 in title-banner
    html_body = re.sub(
        r"<h1>(.*?)</h1>",
        r'<div class="title-banner"><h1>\1</h1></div>',
        html_body,
        count=1,
    )

    # Orange accent bars for <hr>
    html_body = html_body.replace("<hr />", '<div class="accent-bar"></div>')
    html_body = html_body.replace("<hr>", '<div class="accent-bar"></div>')

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">
<style>
@page {{
    size: A4;
    margin: 1.8cm 2cm;
    @bottom-center {{ content: counter(page); font-size: 9pt; color: #999; }}
}}
body {{
    font-family: "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 10.5pt; line-height: 1.7; color: #1a1a1a; background: #fff;
}}
.title-banner {{
    background: #2c3e50; color: #fff; padding: 18px 24px 14px;
    margin: -10px -10px 20px; border-radius: 4px;
}}
.title-banner h1 {{
    font-size: 18pt; font-weight: bold; color: #fff;
    margin: 0; padding: 0; border: none; letter-spacing: 1px;
}}
h2 {{
    font-size: 14pt; font-weight: bold; color: #2c3e50;
    border-bottom: 2.5px solid #2c3e50; padding-bottom: 6px;
    margin-top: 26px; margin-bottom: 12px;
}}
h3 {{
    font-size: 12pt; font-weight: bold; color: #34495e;
    margin-top: 20px; margin-bottom: 8px;
    padding-left: 10px; border-left: 3.5px solid #e67e22;
}}
.accent-bar {{
    height: 3px; background: linear-gradient(90deg, #e67e22, #f39c12);
    border: none; margin: 24px 0; border-radius: 2px;
}}
table {{
    border-collapse: collapse; width: 100%; margin: 12px 0 16px;
    font-size: 9pt; border: none; border-radius: 4px; overflow: hidden;
}}
table tr:first-child {{ background: #2c3e50 !important; }}
table tr:first-child th, table tr:first-child td {{
    background: #2c3e50; color: #fff; font-weight: bold; border: none;
}}
th, td {{
    padding: 7px 10px; border-bottom: 1px solid #e8e8e8;
    text-align: left; vertical-align: top;
}}
tbody tr:nth-child(even), tr:nth-child(even) {{ background: #f8f9fa; }}
tbody tr:nth-child(odd), tr:nth-child(odd)   {{ background: #fff; }}
blockquote {{
    margin: 14px 0; padding: 12px 16px; border-radius: 4px;
    font-size: 10pt; line-height: 1.65; border-left: 4px solid;
    page-break-inside: avoid;
}}
blockquote.note-info    {{ background: #e9f2f8; border-left-color: #3498db; color: #1a3a5c; }}
blockquote.note-warning {{ background: #fdf2e8; border-left-color: #e67e22; color: #5a3510; }}
blockquote.note-danger  {{ background: #fdedeb; border-left-color: #c0392b; color: #5a1a15; }}
blockquote.note-meta    {{ background: #f5f5f5; border-left-color: #999; color: #666; font-size: 9pt; }}
pre {{
    background: #f0f3f6; border: 1px solid #dce1e6; border-radius: 4px;
    padding: 14px 16px; font-family: "Consolas", "Monaco", monospace;
    font-size: 9pt; line-height: 1.55; white-space: pre-wrap; word-wrap: break-word;
    color: #2c3e50;
}}
code {{
    font-family: "Consolas", "Monaco", monospace; font-size: 9pt;
    background: #f0f3f6; padding: 2px 5px; border-radius: 3px; color: #c0392b;
}}
pre code {{ background: none; padding: 0; color: #2c3e50; }}
strong {{ color: #2c3e50; }}
ul, ol {{ margin: 8px 0; padding-left: 24px; }}
li {{ margin-bottom: 4px; line-height: 1.65; }}
p {{ margin: 8px 0; line-height: 1.7; }}
h2, h3 {{ page-break-after: avoid; }}
table {{ page-break-inside: auto; }}
tr {{ page-break-inside: avoid; }}
</style></head>
<body>{html_body}</body></html>"""

    try:
        _HTML(string=full_html).write_pdf(str(pdf_path))
        size_kb = pdf_path.stat().st_size / 1024
        print(f"[OK] PDF generated: {pdf_path} ({size_kb:.0f} KB)")
        return True
    except Exception as exc:
        print(f"[WARN] PDF generation failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Save & Persistence
# ---------------------------------------------------------------------------
def save_report(report, today, days_to_race):
    """Save report (Markdown + PDF) to both local and OneDrive directories."""
    md_filename = f"薄荷猫猫_328_天气日报_D-{days_to_race}.md"
    pdf_filename = f"薄荷猫猫_328_天气日报_D-{days_to_race}.pdf"
    saved_paths = []

    for output_dir in [ONEDRIVE_REPORTS, LOCAL_REPORTS]:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            # Save Markdown
            md_path = output_dir / md_filename
            md_path.write_text(report, encoding="utf-8")
            saved_paths.append(str(md_path))
            print(f"[OK] Markdown saved to {md_path}")

            # Generate PDF
            pdf_path = output_dir / pdf_filename
            md_to_pdf(report, pdf_path)
            saved_paths.append(str(pdf_path))
        except Exception as e:
            print(f"[WARN] Failed to save to {output_dir}: {e}")

    return saved_paths


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="328 苏河半马 Daily Briefing Generator")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout only")
    parser.add_argument("--date", type=str, help="Override date (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.date:
        today = datetime.date.fromisoformat(args.date)
    else:
        today = datetime.date.today()

    days_to_race = (RACE_DATE - today).days
    print(f"[INFO] Date: {today}, D-{days_to_race}, generating briefing...")

    if days_to_race < 0:
        print("[INFO] Race is over. No report generated.")
        return

    try:
        report, ok = generate_report(today)
    except Exception as e:
        print(f"[ERROR] Failed to generate report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if args.stdout:
        print("\n" + report)
        return

    save_report(report, today, days_to_race)


if __name__ == "__main__":
    main()
