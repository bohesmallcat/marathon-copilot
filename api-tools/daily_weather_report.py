#!/usr/bin/env python3
"""
Daily Marathon Weather Report Generator

Fetches weather for Shanghai and Wuxi, evaluates impact on runners,
and generates a Markdown report.

Usage:
    python3 daily_weather_report.py              # Generate and save to file
    python3 daily_weather_report.py --stdout      # Print to stdout only
"""

import os
import sys
import datetime
import argparse
from pathlib import Path

# Shared modules
from weather_client import fetch_weather, parse_weather_simple as parse_weather
from env_tax import calc_env_tax_simple as calc_env_tax, assess_conditions

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent

def load_env():
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env()

# Race calendar (example data — replace with your own races)
RACES = [
    {
        "name": "上海半程马拉松",
        "name_en": "Shanghai Half Marathon",
        "date": datetime.date(2026, 3, 15),
        "start_time": "07:00",
        "city": "Shanghai",
        "city_cn": "上海",
        "distance": "半马 21.1km",
        "course_notes": "浦东平坦赛道，12-18km 滨江开阔段有侧风",
        "runners": [
            {
                "name": "Runner_A",
                "goal": "sub-1:20",
                "pace": "3'47\"/km",
                "tpace_reserve": "12\"/km",
                "finish_est": "08:20",
                "risk": "伤病恢复中（伤病风险 >> 环境风险）",
            },
            {
                "name": "Runner_B",
                "goal": "sub-1:35",
                "pace": "4'30\"/km",
                "tpace_reserve": "20\"/km",
                "finish_est": "08:35",
                "risk": "训练量偏低（后程衰减风险 >> 环境风险）",
            },
        ],
    },
    {
        "name": "无锡马拉松",
        "name_en": "Wuxi Marathon",
        "date": datetime.date(2026, 3, 22),
        "start_time": "07:30",
        "city": "Wuxi",
        "city_cn": "无锡",
        "distance": "全马 42.195km",
        "course_notes": "太湖湖滨极平赛道，全程累计爬升仅30-50m，中国第一PB赛道",
        "runners": [
            {
                "name": "Runner_A",
                "goal": "sub-2:40",
                "pace": "3'47\"/km",
                "tpace_reserve": "16\"/km",
                "finish_est": "10:10",
                "risk": "赛间恢复时间短 + 伤病",
            },
        ],
    },
]

# Runner impact thresholds (from exercise physiology)
OPTIMAL_TEMP_LOW = 5
OPTIMAL_TEMP_HIGH = 15
HUMIDITY_DRIFT_THRESHOLD = 70
WIND_PENALTY_PER_MPH = 0.5  # seconds/km per mph headwind
CROSSWIND_COEFF = 0.5


# ---------------------------------------------------------------------------
# Report generation (uses shared fetch_weather, parse_weather, calc_env_tax)
# ---------------------------------------------------------------------------
def generate_report(today):
    """Generate the daily weather report."""
    cities = {
        "Shanghai": fetch_weather("Shanghai"),
        "Wuxi": fetch_weather("Wuxi"),
    }
    weather = {city: parse_weather(data) for city, data in cities.items()}

    lines = []
    lines.append(f"# 马拉松天气日报 Marathon Weather Daily")
    lines.append(f"**日期:** {today.strftime('%Y-%m-%d')} (北京时间)")
    lines.append(f"**数据源:** wttr.in (基于多家气象数据聚合)")
    lines.append("")

    # Upcoming races
    upcoming = [r for r in RACES if r["date"] >= today]
    if not upcoming:
        lines.append("> 所有赛事已结束，不再生成天气日报。")
        return "\n".join(lines), False

    for race in upcoming:
        days_to_race = (race["date"] - today).days
        city = race["city"]
        w = weather[city]
        is_full = "42" in race["distance"]

        lines.append(f"---")
        lines.append(f"## {race['name']} ({race['name_en']})")
        lines.append(f"**比赛日期:** {race['date'].strftime('%Y-%m-%d')} {race['start_time']} | "
                      f"**倒计时:** {days_to_race} 天 | **距离:** {race['distance']}")
        lines.append(f"**赛道:** {race['course_notes']}")
        lines.append("")

        # Current conditions
        cur = w["current"]
        lines.append(f"### 当前天气 ({race['city_cn']})")
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"| :--- | :--- |")
        lines.append(f"| 天气 | {cur['desc']} |")
        lines.append(f"| 气温 | {cur['temp_c']}°C (体感 {cur['feels_like_c']}°C) |")
        lines.append(f"| 湿度 | {cur['humidity']}% |")
        lines.append(f"| 气压 | {cur['pressure_hpa']} hPa |")
        lines.append(f"| 风力 | {cur['wind_kmh']} km/h ({cur['wind_mph']} mph) {cur['wind_dir']} |")
        lines.append("")

        # Forecast
        lines.append(f"### 未来天气预报")
        lines.append(f"| 日期 | 天气 | 温度 | 早间温度 | 午前温度 | 湿度 | 风速 | 降水概率 | 气压 |")
        lines.append(f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for fc in w["forecasts"]:
            race_marker = " **[比赛日]**" if fc["date"] == race["date"].strftime("%Y-%m-%d") else ""
            lines.append(
                f"| {fc['date']}{race_marker} | {fc['desc']} | "
                f"{fc['min_temp']}~{fc['max_temp']}°C | {fc['morning_avg_temp']}°C | "
                f"{fc['late_morning_temp']}°C | {fc['morning_humidity']}% | "
                f"{fc['morning_wind_kmh']}km/h | {fc['rain_chance']}% | {fc['pressure']}hPa |"
            )
        lines.append("")

        # Race day analysis (use closest forecast or current)
        race_date_str = race["date"].strftime("%Y-%m-%d")
        race_fc = None
        for fc in w["forecasts"]:
            if fc["date"] == race_date_str:
                race_fc = fc
                break
        if race_fc is None and w["forecasts"]:
            race_fc = w["forecasts"][-1]
            lines.append(f"> 注意: 比赛日 ({race_date_str}) 超出当前预报范围，以下分析基于最近可用预报 ({race_fc['date']})，仅供参考。")
            lines.append("")

        if race_fc:
            env_tax = calc_env_tax(race_fc, is_full=is_full)
            condition_rating = assess_conditions(race_fc)

            lines.append(f"### 环境影响评估")
            lines.append(f"**环境条件评级:** {condition_rating}")
            lines.append("")
            lines.append(f"| 环境税分项 | 预估损耗 | 说明 |")
            lines.append(f"| :--- | :--- | :--- |")

            wind_note = f"侧逆风段约{6 if not is_full else 15}km, {race_fc['morning_wind_mph']}mph"
            lines.append(f"| 风力损耗 | +{env_tax['wind']}\" | {wind_note} |")

            hum_note = f"湿度{race_fc['morning_humidity']}%"
            if race_fc['morning_humidity'] < HUMIDITY_DRIFT_THRESHOLD:
                hum_note += f", 低于{HUMIDITY_DRIFT_THRESHOLD}%心率漂移阈值"
            else:
                hum_note += f", 超过{HUMIDITY_DRIFT_THRESHOLD}%心率漂移阈值"
            lines.append(f"| 湿度心率漂移 | +{env_tax['humidity']}\" | {hum_note} |")

            temp_note = f"午前{race_fc['late_morning_temp']}°C"
            if race_fc['late_morning_temp'] > OPTIMAL_TEMP_HIGH:
                temp_note += f", 超最佳区间({OPTIMAL_TEMP_LOW}-{OPTIMAL_TEMP_HIGH}°C)上限{race_fc['late_morning_temp']-OPTIMAL_TEMP_HIGH}°C"
            else:
                temp_note += f", 在最佳区间({OPTIMAL_TEMP_LOW}-{OPTIMAL_TEMP_HIGH}°C)内"
            lines.append(f"| 温度税 | +{env_tax['temperature']}\" | {temp_note} |")
            lines.append(f"| 折返损耗 | +{env_tax['turnaround']}\" | 赛道折返点 |")
            lines.append(f"| **综合环境税** | **≈ {env_tax['total']}\"** | |")
            lines.append("")

            # Per-runner impact
            lines.append(f"### 跑者影响")
            for runner in race["runners"]:
                lines.append(f"#### {runner['name']}")
                lines.append(f"| 指标 | 数值 |")
                lines.append(f"| :--- | :--- |")
                lines.append(f"| 目标 | {runner['goal']} ({runner['pace']}) |")
                lines.append(f"| 预计完赛 | {runner['finish_est']} |")
                lines.append(f"| 环境税 | ≈ {env_tax['total']}\" |")
                lines.append(f"| T-Pace速度储备 | {runner['tpace_reserve']} |")

                # Calculate tax per km
                total_km = 42.195 if is_full else 21.0975
                tax_per_km = round(env_tax['total'] / total_km, 1)
                lines.append(f"| 环境税均摊 | ≈ {tax_per_km}\"/km |")
                lines.append(f"| 核心风险 | {runner['risk']} |")
                lines.append("")

        # Key reminders
        lines.append(f"### 关注要点")
        reminders = []
        if race_fc:
            if race_fc["late_morning_temp"] > OPTIMAL_TEMP_HIGH:
                reminders.append(f"午前温度 {race_fc['late_morning_temp']}°C 超出最佳竞赛区间，后半程注意补水散热")
            if race_fc["rain_chance"] > 30:
                reminders.append(f"降水概率 {race_fc['rain_chance']}%，备好轻薄防雨装备和备用袜子")
            if race_fc["morning_wind_kmh"] > 15:
                reminders.append(f"早间风速 {race_fc['morning_wind_kmh']}km/h，开阔路段守心率不追速")
            if race_fc["morning_humidity"] > 65:
                reminders.append(f"湿度 {race_fc['morning_humidity']}%偏高，注意心率漂移")
            if race_fc["late_morning_temp"] <= OPTIMAL_TEMP_HIGH and race_fc["rain_chance"] <= 20:
                reminders.append("天气条件有利于PB，按计划执行")

        if days_to_race <= 1:
            reminders.append("**比赛日/赛前最后一天！起跑前2h再次确认天气**")
        elif days_to_race <= 3:
            reminders.append(f"距比赛 {days_to_race} 天，预报准确度较高，关注风向和降水概率变化")
        else:
            reminders.append(f"距比赛 {days_to_race} 天，预报仍可能变化，持续关注")

        for r in reminders:
            lines.append(f"- {r}")
        lines.append("")

    lines.append("---")
    lines.append(f"> 本报告由 AI 自动生成于 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} CST。"
                 f"天气数据来自 wttr.in，仅供参考。")

    return "\n".join(lines), True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Daily Marathon Weather Report")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout only")
    args = parser.parse_args()

    today = datetime.date.today()
    print(f"[INFO] Generating weather report for {today}...")

    try:
        report, has_races = generate_report(today)
    except Exception as e:
        print(f"[ERROR] Failed to generate report: {e}")
        sys.exit(1)

    if not has_races:
        print("[INFO] All races are over. No report generated.")
        return

    if args.stdout:
        print("\n" + report)
        return

    # Save to file
    output_dir = SCRIPT_DIR / "reports"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"weather_report_{today.strftime('%m%d')}.md"
    output_file.write_text(report, encoding="utf-8")
    print(f"[OK] Report saved to {output_file}")


if __name__ == "__main__":
    main()
