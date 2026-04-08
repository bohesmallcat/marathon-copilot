#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pyyaml"]
# ///
"""
generate_next_week_plan.py — COROS → 算法引擎 → training-weekly 自动化桥梁

端到端流程:
  1. 从 COROS 拉取上周实际训练数据
  2. 加载 runner_profile + training_cycle_config
  3. 用 training_calculator 计算下周训练框架（配速/跑量/阶段）
  4. 获取下周 7 天天气预报 + 适跑指数
  5. 生成结构化上下文，供 training-weekly skill (LLM) 生成完整周计划

Usage:
  # 完整流程：拉数据 + 生成 prompt（默认）
  python generate_next_week_plan.py --token <TOKEN>

  # 指定配置文件
  python generate_next_week_plan.py --token <TOKEN> \\
      --runner runner_profile_xxx.yaml \\
      --cycle training_cycle_config.yaml

  # 仅生成上周报告（不含下周计划）
  python generate_next_week_plan.py --token <TOKEN> --report-only

  # 输出 JSON（给其他脚本消费）
  python generate_next_week_plan.py --token <TOKEN> --json

  # 使用 .env 中的 COROS 凭据（无需 --token）
  python generate_next_week_plan.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from coros_client import CorosClient, format_pace, format_duration, get_sport_name
from coros_weekly_report import (
    analyze_weekly_data,
    format_markdown_report,
    format_llm_prompt_context,
    load_training_plan,
    classify_run,
)

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Optional: weather_client for 7-day forecast
try:
    from weather_client import fetch_weather, parse_for_training_schedule
    HAS_WEATHER = True
except ImportError:
    HAS_WEATHER = False

# Optional: training_calculator for algorithmic plan
try:
    from training_calculator import (
        calculate_vdot,
        get_training_paces,
        generate_week_template,
        design_training_phases,
        format_pace as tc_format_pace,
    )
    HAS_CALCULATOR = True
except ImportError:
    HAS_CALCULATOR = False


# ── Config Loaders ─────────────────────────────────────────────────

def load_env():
    """Load .env file if exists."""
    env_path = SCRIPT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def find_yaml_config(pattern: str) -> Path | None:
    """Find a YAML config file matching pattern in api-tools dir."""
    for p in SCRIPT_DIR.glob(pattern):
        if ".example" not in p.name:
            return p
    return None


def load_runner_profile(path: str | None = None) -> dict | None:
    """Load runner profile YAML."""
    if not HAS_YAML:
        return None
    if path:
        p = Path(path) if Path(path).is_absolute() else SCRIPT_DIR / path
    else:
        p = find_yaml_config("runner_profile_*.yaml")
    if p and p.exists():
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return None


def load_cycle_config(path: str | None = None) -> dict | None:
    """Load training cycle config YAML."""
    if not HAS_YAML:
        return None
    if path:
        p = Path(path) if Path(path).is_absolute() else SCRIPT_DIR / path
    else:
        p = find_yaml_config("training_cycle_config*.yaml")
        if not p:
            p = SCRIPT_DIR / "training_cycle_config.yaml"
    if p and p.exists():
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return None


# ── Resolve COROS Token ────────────────────────────────────────────

def resolve_token(args) -> str | None:
    """Resolve COROS token from args, env, or token manager."""
    if args.token:
        return args.token
    # Try .env
    load_env()
    token = os.environ.get("COROS_TOKEN")
    if token:
        return token
    # Try token manager cache
    try:
        from coros_token_manager import get_valid_token
        return get_valid_token()
    except (ImportError, Exception):
        pass
    return None


# ── Week Number Computation ────────────────────────────────────────

def compute_week_info(cycle_config: dict, target_date: datetime) -> dict:
    """Determine current week number, phase, and planned volume.

    Args:
        cycle_config: Full training_cycle_config dict.
        target_date: The Monday of the target week.

    Returns:
        Dict with week_number, phase info, planned_km, etc.
    """
    cycle = cycle_config.get("cycle", {})
    start_str = cycle.get("start_date", "")
    if not start_str:
        return {}

    cycle_start = datetime.strptime(str(start_str), "%Y-%m-%d")
    week_number = (target_date - cycle_start).days // 7 + 1

    if week_number < 1:
        return {"week_number": week_number, "status": "before_cycle"}

    total_weeks = cycle.get("total_weeks", 52)
    if week_number > total_weeks:
        return {"week_number": week_number, "status": "past_cycle"}

    # Walk phases to find current one
    phases = cycle_config.get("phases", [])
    accumulated = 0
    current_phase = None
    week_in_phase = 0
    is_recovery_week = False

    for phase in phases:
        pw = phase.get("weeks", 0)
        if accumulated < week_number <= accumulated + pw:
            current_phase = phase
            week_in_phase = week_number - accumulated
            break
        accumulated += pw

    if not current_phase:
        return {"week_number": week_number, "status": "no_phase_match"}

    # Recovery week check (every 4th week in phase, or explicitly in weekly_km)
    is_recovery_week = (week_in_phase % 4 == 0) and week_in_phase > 0

    # Get planned km
    weekly_km_list = current_phase.get("weekly_km", [])
    planned_km = (weekly_km_list[week_in_phase - 1]
                  if week_in_phase <= len(weekly_km_list) else None)

    # Next week info
    next_week_number = week_number + 1
    next_accumulated = 0
    next_phase = None
    next_week_in_phase = 0
    for phase in phases:
        pw = phase.get("weeks", 0)
        if next_accumulated < next_week_number <= next_accumulated + pw:
            next_phase = phase
            next_week_in_phase = next_week_number - next_accumulated
            break
        next_accumulated += pw

    next_planned_km = None
    next_is_recovery = False
    if next_phase:
        nwk = next_phase.get("weekly_km", [])
        next_planned_km = (nwk[next_week_in_phase - 1]
                           if next_week_in_phase <= len(nwk) else None)
        next_is_recovery = (next_week_in_phase % 4 == 0) and next_week_in_phase > 0

    return {
        "week_number": week_number,
        "status": "active",
        "phase_number": current_phase.get("number"),
        "phase_name": current_phase.get("name"),
        "phase_name_cn": current_phase.get("name_cn"),
        "week_in_phase": week_in_phase,
        "is_recovery_week": is_recovery_week,
        "planned_km": planned_km,
        "intensity": current_phase.get("intensity", {}),
        "hr_cap": current_phase.get("hr_cap"),
        "key_focus": current_phase.get("key_focus"),
        "key_workouts": current_phase.get("key_workouts", []),
        "next_week": {
            "week_number": next_week_number,
            "phase_number": next_phase.get("number") if next_phase else None,
            "phase_name": next_phase.get("name") if next_phase else None,
            "phase_name_cn": next_phase.get("name_cn") if next_phase else None,
            "week_in_phase": next_week_in_phase,
            "is_recovery_week": next_is_recovery,
            "planned_km": next_planned_km,
            "intensity": next_phase.get("intensity", {}) if next_phase else {},
            "hr_cap": next_phase.get("hr_cap") if next_phase else None,
            "key_focus": next_phase.get("key_focus") if next_phase else None,
            "key_workouts": next_phase.get("key_workouts", []) if next_phase else [],
        },
    }


# ── Training Paces from Profile ────────────────────────────────────

def compute_paces(runner_profile: dict | None, cycle_config: dict | None) -> dict:
    """Compute training paces from VDOT."""
    vdot = None
    if cycle_config:
        vdot = cycle_config.get("cycle", {}).get("vdot_start")
    if runner_profile:
        vdot_hist = runner_profile.get("vdot_history", {})
        vdot = vdot_hist.get("current_vdot") or vdot

    if not vdot or not HAS_CALCULATOR:
        return {}

    paces = get_training_paces(float(vdot))
    return {
        "vdot": float(vdot),
        "E_pace": tc_format_pace(paces["easy"]),
        "M_pace": tc_format_pace(paces["marathon"]),
        "T_pace": tc_format_pace(paces["threshold"]),
        "I_pace": tc_format_pace(paces["interval"]),
        "R_pace": tc_format_pace(paces["repetition"]),
        "paces_raw": paces,
    }


# ── Weather Forecast ───────────────────────────────────────────────

def get_weather_forecast(city: str) -> list[dict]:
    """Fetch 7-day weather forecast with run suitability scoring."""
    if not HAS_WEATHER:
        return []
    try:
        data = fetch_weather(city)
        return parse_for_training_schedule(data)
    except Exception as e:
        print(f"Warning: 天气获取失败: {e}", file=sys.stderr)
        return []


# ── Prompt Generator ───────────────────────────────────────────────

def generate_skill_prompt(
    coros_analysis: dict,
    week_info: dict,
    paces: dict,
    weather: list[dict],
    runner_profile: dict | None,
    cycle_config: dict | None,
) -> str:
    """Generate a comprehensive prompt for the training-weekly skill.

    This prompt contains all the structured data the LLM needs to
    generate a complete 7-day training plan.
    """
    lines = []
    now = datetime.now()
    next_monday = now + timedelta(days=(7 - now.weekday()))
    next_sunday = next_monday + timedelta(days=6)

    nw = week_info.get("next_week", {})

    lines.append(f"# 请生成下周训练计划")
    lines.append("")
    lines.append(f"目标周: {next_monday.strftime('%Y-%m-%d')} ~ "
                 f"{next_sunday.strftime('%Y-%m-%d')}")
    lines.append("")

    # ── Section 1: Training Cycle Context ──
    lines.append("## 1. 训练周期上下文")
    lines.append("")
    if nw and nw.get("phase_name_cn"):
        lines.append(f"- 周期第 {nw['week_number']} 周（阶段内第 {nw['week_in_phase']} 周）")
        lines.append(f"- 当前阶段: Phase {nw['phase_number']} — {nw['phase_name_cn']}")
        lines.append(f"- 阶段重点: {nw.get('key_focus', 'N/A')}")
        lines.append(f"- 是否恢复周: {'是' if nw.get('is_recovery_week') else '否'}")
        if nw.get("planned_km"):
            lines.append(f"- 计划跑量: {nw['planned_km']} km")
        intensity = nw.get("intensity", {})
        if intensity:
            parts = []
            for k, v in intensity.items():
                if v > 0:
                    name_map = {"easy": "轻松", "tempo": "节奏", "interval": "间歇", "long_run": "长距离"}
                    parts.append(f"{name_map.get(k, k)} {v}%")
            lines.append(f"- 强度分布: {' / '.join(parts)}")
        if nw.get("hr_cap"):
            lines.append(f"- 心率上限: {nw['hr_cap']} bpm")
        if nw.get("key_workouts"):
            lines.append(f"- 关键训练:")
            for kw in nw["key_workouts"]:
                lines.append(f"  - {kw}")
    else:
        lines.append("- 无训练周期配置，请根据上周数据自行判断强度。")
    lines.append("")

    # ── Section 2: Training Paces ──
    if paces:
        lines.append("## 2. 训练配速区间")
        lines.append("")
        lines.append(f"- VDOT: {paces['vdot']}")
        lines.append(f"- E-Pace (轻松跑): {paces['E_pace']}/km")
        lines.append(f"- M-Pace (马拉松配速): {paces['M_pace']}/km")
        lines.append(f"- T-Pace (乳酸阈值): {paces['T_pace']}/km")
        lines.append(f"- I-Pace (间歇): {paces['I_pace']}/km")
        lines.append(f"- R-Pace (重复跑): {paces['R_pace']}/km")
        lines.append("")

    # ── Section 3: Last Week COROS Data ──
    lines.append("## 3. 上周训练执行数据（COROS 手表实际记录）")
    lines.append("")
    lines.append(format_llm_prompt_context(coros_analysis))
    lines.append("")

    # ── Section 4: Plan vs Actual ──
    comp = coros_analysis.get("plan_comparison")
    if comp:
        lines.append("## 4. 上周计划 vs 实际")
        lines.append("")
        lines.append(f"- 计划跑量: {comp['planned_km']} km")
        lines.append(f"- 实际跑量: {comp['actual_km']} km")
        lines.append(f"- 偏差: {comp['deviation_km']:+.1f} km ({comp['deviation_pct']:+.1f}%)")
        lines.append(f"- 状态: {comp['status']}")
        lines.append("")

    # ── Section 5: Recovery Assessment ──
    lines.append("## 5. 恢复状态评估（基于 COROS 数据推断）")
    lines.append("")
    actual = coros_analysis.get("actual", {})
    training_load = actual.get("training_load", 0)
    if training_load > 500:
        lines.append("- 训练负荷: 偏高 (>500)，建议本周适当降量")
    elif training_load > 350:
        lines.append(f"- 训练负荷: 中等 ({training_load})，可正常推进")
    else:
        lines.append(f"- 训练负荷: 较低 ({training_load})，可适度增量")

    hr_summary = coros_analysis.get("hr_summary", {})
    lines.append(f"- 心率范围: {hr_summary.get('avg_hr_range', 'N/A')}")
    lines.append("")

    # ── Section 6: Runner Profile ──
    if runner_profile:
        lines.append("## 6. 跑者档案摘要")
        lines.append("")
        runner = runner_profile.get("runner", {})
        if runner:
            lines.append(f"- 体重: {runner.get('weight_kg', 'N/A')} kg")
            lines.append(f"- 最大心率: {runner.get('max_hr', 'N/A')} bpm")
            lines.append(f"- 乳酸阈心率: {runner.get('lactate_threshold_hr', 'N/A')} bpm")
            lines.append(f"- 安静心率: {runner.get('resting_hr', 'N/A')} bpm")
        # Training state
        ts = runner_profile.get("training_state", {})
        if ts:
            lines.append(f"- 近4周平均跑量: {ts.get('recent_4week_avg_km', 'N/A')} km/周")
            lines.append(f"- 训练年限: {ts.get('training_age_years', 'N/A')} 年")
        # Health
        health = runner_profile.get("health", {})
        injuries = health.get("current_injuries", [])
        if injuries:
            for inj in injuries:
                lines.append(f"- 伤病: {inj.get('area', '?')} "
                             f"(严重度 {inj.get('severity', '?')}/10)")
        # Menstrual cycle
        mc = runner_profile.get("menstrual_cycle", {})
        if mc.get("enabled"):
            lines.append(f"- 生理周期: 已启用 (周期长度 {mc.get('cycle_length', 28)} 天)")
            lines.append(f"- 上次经期: {mc.get('last_period_start', 'N/A')}")
        lines.append("")

    # ── Section 7: Weather Forecast ──
    if weather:
        lines.append("## 7. 下周天气预报")
        lines.append("")
        lines.append("| 日期 | 天气 | 温度 | 湿度 | 风速 | 降雨% | UV | 适跑 | 建议窗口 |")
        lines.append("|------|------|------|------|------|-------|----|----|----------|")
        for w in weather:
            lines.append(
                f"| {w['date']} | {w['condition']} | "
                f"{w['temp_min']}~{w['temp_max']}°C | "
                f"{w['humidity_morning']}% | "
                f"{w['wind_kmh']}km/h {w['wind_dir']} | "
                f"{w['rain_chance_max']}% | "
                f"{w['uv']} | "
                f"{w['run_rating']}({w['run_rating_score']}) | "
                f"{w['best_window']} |"
            )
        lines.append("")
        # Notes
        for w in weather:
            if w.get("notes"):
                lines.append(f"  {w['date']}: {'; '.join(w['notes'])}")
        lines.append("")

    # ── Instruction ──
    lines.append("---")
    lines.append("")
    lines.append("请根据以上数据，按照 training-weekly 技能的输出格式，"
                 "生成完整的下周训练计划（含每日训练处方、饮食方案、力量训练、恢复监控）。")
    lines.append("")

    return "\n".join(lines)


# ── Save Weekly Report ─────────────────────────────────────────────

def save_weekly_report(
    coros_analysis: dict,
    week_info: dict,
    runner_id: str,
    output_dir: Path,
) -> Path:
    """Save COROS weekly data as a report file that training-weekly skill can find.

    File naming: {runner_id}_W{N}_weekly_report.md
    """
    wn = week_info.get("week_number", 0)
    filename = f"{runner_id}_W{wn}_weekly_report.md"
    report_path = output_dir / filename

    report = format_markdown_report(coros_analysis)
    # Prepend metadata
    header = (
        f"---\n"
        f"runner: {runner_id}\n"
        f"week: {wn}\n"
        f"source: COROS Training Hub (自动生成)\n"
        f"generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"---\n\n"
    )
    report_path.write_text(header + report, encoding="utf-8")
    return report_path


# ── CLI ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="COROS → 训练计划自动化桥梁",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    auth = parser.add_argument_group("COROS 认证")
    auth.add_argument("--token", help="COROS accessToken")
    auth.add_argument("--email", help="COROS 账号")
    auth.add_argument("--password", help="COROS 密码")

    parser.add_argument("--region", choices=["cn", "intl"], default="cn")
    parser.add_argument("--runner", help="跑者档案 YAML 路径")
    parser.add_argument("--cycle", help="训练周期配置 YAML 路径")
    parser.add_argument("--city", default="Shanghai", help="天气查询城市 (默认: Shanghai)")
    parser.add_argument("--weeks-ago", type=int, default=1,
                        help="分析几周前的数据 (默认: 1=上周)")

    output = parser.add_argument_group("输出选项")
    output.add_argument("--json", action="store_true", help="输出 JSON")
    output.add_argument("--report-only", action="store_true",
                        help="仅生成上周报告，不含下周计划 prompt")
    output.add_argument("--save-report", action="store_true",
                        help="保存 weekly_report.md 到项目目录")
    output.add_argument("-o", "--output", help="保存输出到文件")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # ── Resolve token ──
    token = resolve_token(args)
    if not token:
        if args.email and args.password:
            client = CorosClient(region=args.region)
            client.login(args.email, args.password)
        else:
            print("错误: 需要 --token 或 --email + --password，"
                  "或在 .env 中设置 COROS_TOKEN", file=sys.stderr)
            sys.exit(1)
    else:
        client = CorosClient(region=args.region)
        client.set_token(token)

    # ── Load configs ──
    runner_profile = load_runner_profile(args.runner)
    cycle_config = load_cycle_config(args.cycle)

    # ── Pull COROS data ──
    print(f"正在从 COROS 拉取训练数据...", file=sys.stderr)
    summary = client.generate_weekly_summary(weeks_ago=args.weeks_ago)

    if summary["total_activities"] == 0:
        print("该周无训练记录。", file=sys.stderr)
        sys.exit(0)

    print(f"  获取到 {summary['total_activities']} 条活动, "
          f"跑步 {summary['run_distance_km']}km", file=sys.stderr)

    # ── Analyze ──
    plan_data = None
    if cycle_config:
        plan_data = load_training_plan(
            args.cycle or str(find_yaml_config("training_cycle_config*.yaml") or ""),
            summary["week_start"],
        )
    analysis = analyze_weekly_data(summary, plan_data)

    # ── Compute week info ──
    today = datetime.now()
    last_monday = today - timedelta(days=today.weekday() + 7 * args.weeks_ago)
    week_info = {}
    if cycle_config:
        week_info = compute_week_info(cycle_config, last_monday)

    # ── Compute paces ──
    paces = compute_paces(runner_profile, cycle_config)

    # ── Save weekly report if requested ──
    if args.save_report:
        runner_id = "runner"
        if runner_profile:
            runner_id = runner_profile.get("runner", {}).get("nickname", "runner")
        report_dir = SCRIPT_DIR / "reports"
        report_dir.mkdir(exist_ok=True)
        report_path = save_weekly_report(analysis, week_info, runner_id, report_dir)
        print(f"  周报已保存: {report_path}", file=sys.stderr)

    if args.report_only:
        # Just output the analysis
        if args.json:
            print(json.dumps(analysis, ensure_ascii=False, indent=2))
        else:
            print(format_markdown_report(analysis))
        return

    # ── Weather forecast ──
    city = args.city
    if runner_profile:
        city = runner_profile.get("runner", {}).get("city", city)
    if cycle_config:
        city = cycle_config.get("target_race", {}).get("city", city)

    print(f"正在获取 {city} 天气预报...", file=sys.stderr)
    weather = get_weather_forecast(city)
    if weather:
        print(f"  获取到 {len(weather)} 天天气数据", file=sys.stderr)

    # ── Generate prompt ──
    if args.json:
        output = json.dumps({
            "coros_analysis": analysis,
            "week_info": week_info,
            "paces": {k: v for k, v in paces.items() if k != "paces_raw"},
            "weather": weather,
        }, ensure_ascii=False, indent=2)
    else:
        output = generate_skill_prompt(
            analysis, week_info, paces, weather,
            runner_profile, cycle_config,
        )

    # ── Output ──
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"输出已保存: {args.output}", file=sys.stderr)
    else:
        print(output)

    print("\n✅ 完成! 将以上内容发送给 training-weekly 技能即可生成完整周计划。",
          file=sys.stderr)


if __name__ == "__main__":
    main()
