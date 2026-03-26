#!/usr/bin/env python3
"""
赛前每日天气 + 训练 + 饮食 自动化简报

每日北京时间 08:00 自动运行，生成包含：
  1. 最新天气预报与环境税评估
  2. 当日训练计划
  3. 当日饮食建议
  4. 恢复监控 checklist
  5. 配速方案确认 / 更新

Configuration is loaded from race_config.yaml (single source of truth).

Usage:
    python3 generate_daily_briefing.py                # 生成并保存
    python3 generate_daily_briefing.py --stdout        # 仅输出到终端
    python3 generate_daily_briefing.py --date 2026-03-25  # 指定日期生成
    python3 generate_daily_briefing.py --config other.yaml  # 使用其他配置文件
"""

import os
import sys
import json
import datetime
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Load race_config.yaml → module-level constants
# ---------------------------------------------------------------------------
try:
    import yaml
except ImportError:
    # Fallback: lightweight YAML-subset loader for simple key-value configs
    # Only needed if PyYAML is not installed
    yaml = None


def _load_config(config_path=None):
    """Load race_config.yaml and return the parsed dict."""
    if config_path is None:
        config_path = SCRIPT_DIR / "race_config.yaml"
    config_path = Path(config_path)
    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)
    text = config_path.read_text(encoding="utf-8")
    if yaml:
        return yaml.safe_load(text)
    # Minimal fallback: try json if someone converted it
    try:
        return json.loads(text)
    except Exception:
        print("[ERROR] pip install pyyaml  (needed to parse race_config.yaml)")
        sys.exit(1)


# Will be populated in main() after argparse, but provide defaults for import
CFG = None  # filled by _init_from_config()

# Module-level aliases — populated by _init_from_config()
RACE_DATE = None
RACE_START_TIME = None
RACE_CITY = None
RACE_CITY_CN = None
RACE_NAME = None
RACE_DISTANCE_KM = None
RACE_GPS_DISTANCE_KM = None
RUNNER = None
BASELINE = None
TRAINING_PLANS = None
DIET_PLANS = None
RECOVERY_CHECKLIST = None
ONEDRIVE_REPORTS = None
LOCAL_REPORTS = None


def _init_from_config(cfg):
    """Populate module-level constants from parsed config dict."""
    global CFG, RACE_DATE, RACE_START_TIME, RACE_CITY, RACE_CITY_CN, RACE_NAME
    global RACE_DISTANCE_KM, RACE_GPS_DISTANCE_KM, RUNNER, BASELINE
    global TRAINING_PLANS, DIET_PLANS, RECOVERY_CHECKLIST
    global ONEDRIVE_REPORTS, LOCAL_REPORTS

    CFG = cfg
    race = cfg["race"]
    RACE_DATE = datetime.date.fromisoformat(race["date"])
    RACE_START_TIME = race["start_time"]
    RACE_CITY = race["city"]
    RACE_CITY_CN = race["city_cn"]
    RACE_NAME = race["name"]
    RACE_DISTANCE_KM = race["distance_km"]
    RACE_GPS_DISTANCE_KM = race.get("gps_distance_km", RACE_DISTANCE_KM)

    runner_cfg = cfg["runner"]
    RUNNER = {
        "name": runner_cfg["name"],
        "weight_kg": runner_cfg["weight_kg"],
        "height_cm": runner_cfg["height_cm"],
        "bsa": runner_cfg["bsa"],
        "body_correction": runner_cfg["body_correction"],
        "pb": runner_cfg["pb"],
        "pb_315": runner_cfg.get("pb_315", ""),
        "tpace": runner_cfg["tpace"],
        "tpace_bpm": runner_cfg["tpace_bpm"],
        "reserve_per_km": runner_cfg["reserve_per_km"],
        "plan_a": runner_cfg["plans"]["a"],
        "plan_b": runner_cfg["plans"]["b"],
        "plan_c": runner_cfg["plans"]["c"],
    }

    bl = cfg["baseline"]
    BASELINE = {
        "weather": bl["weather"],
        "temp_start": bl["temp_start"],
        "temp_end": bl["temp_end"],
        "humidity": bl["humidity"],
        "wind_mph": bl["wind_mph"],
        "wind_kmh": bl["wind_kmh"],
        "wind_dir": bl["wind_dir"],
        "rain_chance": bl["rain_chance"],
        "uv": bl["uv"],
        "env_tax_total": bl["env_tax"]["total"],
        "env_tax_wind": bl["env_tax"]["wind"],
        "env_tax_humidity": bl["env_tax"]["humidity"],
        "env_tax_temp": bl["env_tax"]["temp"],
        "env_tax_uv": bl["env_tax"]["uv"],
        "env_tax_turnaround": bl["env_tax"]["turnaround"],
    }

    # Training & diet plans — config keys are integers (D-N days)
    TRAINING_PLANS = {int(k): v for k, v in cfg.get("training", {}).items()}
    DIET_PLANS = {int(k): v for k, v in cfg.get("diet", {}).items()}
    RECOVERY_CHECKLIST = cfg.get("recovery_checklist", {})

    # Output paths (env vars override config)
    paths = cfg.get("paths", {})
    ONEDRIVE_REPORTS = Path(
        os.environ.get("REPORTS_ONEDRIVE_DIR", paths.get("reports_onedrive", ""))
    ) if paths.get("reports_onedrive") or os.environ.get("REPORTS_ONEDRIVE_DIR") else None
    LOCAL_REPORTS = Path(
        os.environ.get("REPORTS_DIR", paths.get("reports_local", "./reports"))
    )
    if not LOCAL_REPORTS.is_absolute():
        LOCAL_REPORTS = SCRIPT_DIR / LOCAL_REPORTS

    _init_model_constants()


# ---------------------------------------------------------------------------
# Shared modules (weather, env_tax, pdf)
# ---------------------------------------------------------------------------
from weather_client import fetch_weather, parse_hourly_for_race   # noqa: E402
from env_tax import calc_env_tax as _calc_env_tax_core, assess_signal as _assess_signal_core  # noqa: E402


def _get_env_tax_model():
    """Return env tax model params from config."""
    return CFG["env_tax_model"]


def calc_env_tax(forecast):
    """Calculate environment tax using shared module + config."""
    return _calc_env_tax_core(
        forecast,
        model=_get_env_tax_model(),
        runner=RUNNER,
        is_full=CFG["race"].get("is_full", False),
        distance_km=RACE_GPS_DISTANCE_KM,
    )


def assess_signal(env_tax_total, baseline_total=None):
    """Determine green/yellow/orange/red light using config thresholds."""
    if baseline_total is None:
        baseline_total = BASELINE["env_tax_total"]
    thresholds = CFG.get("signal", {"green": 10, "yellow": 30, "orange": 60})
    return _assess_signal_core(env_tax_total, baseline_total, thresholds)


# Convenience accessor for env tax model params used in report text.
# These are populated by _init_from_config() alongside the other module-level vars.
OPTIMAL_TEMP_LOW = 5
OPTIMAL_TEMP_HIGH = 15
HUMIDITY_DRIFT_THRESHOLD = 70
EXPOSED_KM = 3.5


def _init_model_constants():
    """Populate model-constant aliases from config (called by _init_from_config)."""
    global OPTIMAL_TEMP_LOW, OPTIMAL_TEMP_HIGH, HUMIDITY_DRIFT_THRESHOLD, EXPOSED_KM
    m = CFG.get("env_tax_model", {})
    OPTIMAL_TEMP_LOW = m.get("optimal_temp_low", 5)
    OPTIMAL_TEMP_HIGH = m.get("optimal_temp_high", 15)
    HUMIDITY_DRIFT_THRESHOLD = m.get("humidity_drift_threshold", 70)
    EXPOSED_KM = m.get("exposed_km", 3.5)


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

    # Fetch weather (uses shared weather_client with retry)
    try:
        raw = fetch_weather(RACE_CITY)
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
    plan_a = RUNNER["plan_a"]
    plan_b = RUNNER["plan_b"]
    pace_table = CFG.get("pace_table", {})
    if signal_color in ("green", "yellow") or (race_fc_is_proxy and signal_color in ("orange",)):
        # When using proxy data, maintain plan unless clearly red
        if race_fc_is_proxy and signal_color == "orange":
            lines.append(
                f"**配速方案暂时维持 Plan A: {plan_a['time']}**"
                f"（当前信号基于代理预报数据，比赛日预报尚未到位。待 D-2 获得精准预报后再做最终判定。）"
            )
        else:
            lines.append(f"**配速方案维持不变。** Plan A: {plan_a['time']}")
        lines.append("")
        lines.append("```")
        lines.append(f"{RUNNER['name']} | 目标: {plan_a['time']} | PB: {RUNNER['pb']} | 苏河半马")
        if race_fc:
            lines.append(
                f"{race_fc['desc']} | 起跑{race_fc['start_temp']}°C "
                f"湿度{race_fc['start_humidity']}%→{race_fc['finish_humidity']}% | 无隧道 | "
                f"风{race_fc['morning_wind_mph']}mph"
            )
        lines.append("")
        for split in pace_table.get("splits", []):
            lines.append(split)
        for rule in pace_table.get("fuse_rules", []):
            lines.append(rule)
        lines.append("```")
    elif signal_color == "orange":
        lines.append(f"**考虑降级至 Plan B: {plan_b['time']} ({plan_b.get('gps_pace', plan_b['pace'])})**")
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
# PDF Generation — delegates to shared pdf_styles module
# ---------------------------------------------------------------------------
def md_to_pdf(md_text, pdf_path):
    """Convert Markdown text to styled PDF using shared design system."""
    from pdf_styles import md_to_pdf as _pdf
    return _pdf(md_text, pdf_path, title=RACE_NAME)


# ---------------------------------------------------------------------------
# Save & Persistence
# ---------------------------------------------------------------------------
def save_report(report, today, days_to_race):
    """Save report (Markdown + PDF) to both local and OneDrive directories."""
    runner_tag = RUNNER["name"]
    race_tag = RACE_DATE.strftime("%m%d")  # e.g. "0328"
    md_filename = f"{runner_tag}_{race_tag}_天气日报_D-{days_to_race}.md"
    pdf_filename = f"{runner_tag}_{race_tag}_天气日报_D-{days_to_race}.pdf"
    saved_paths = []

    output_dirs = [d for d in [ONEDRIVE_REPORTS, LOCAL_REPORTS] if d]
    for output_dir in output_dirs:
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
    parser = argparse.ArgumentParser(description="Pre-Race Daily Briefing Generator")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout only")
    parser.add_argument("--date", type=str, help="Override date (YYYY-MM-DD)")
    parser.add_argument("--config", type=str, help="Path to race_config.yaml")
    args = parser.parse_args()

    # Load configuration
    cfg = _load_config(args.config)
    _init_from_config(cfg)

    if args.date:
        today = datetime.date.fromisoformat(args.date)
    else:
        today = datetime.date.today()

    days_to_race = (RACE_DATE - today).days
    print(f"[INFO] {RACE_NAME}")
    print(f"[INFO] Runner: {RUNNER['name']}, Date: {today}, D-{days_to_race}")

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
