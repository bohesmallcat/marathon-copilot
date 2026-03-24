#!/bin/bash
# Pre-Race Daily Briefing — Cron Wrapper
#
# Runs at 08:00 AM Beijing time daily until race day.
# Race date is read from race_config.yaml (no more hardcoding).
#
# Crontab entry example:
#   0 8 * * * /path/to/api-tools/run_daily_briefing.sh >> /path/to/reports/cron.log 2>&1

set -euo pipefail
export TZ='Asia/Shanghai'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
LOG_DIR="${REPORTS_DIR:-$SCRIPT_DIR/reports}"
LOG_FILE="$LOG_DIR/cron.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR" || { echo "[ERROR] Cannot create $LOG_DIR" >&2; exit 1; }

echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') Daily Briefing Start =====" >> "$LOG_FILE"

# Check Python availability
if ! command -v "$PYTHON" &> /dev/null; then
    echo "[ERROR] Python not found: $PYTHON" >> "$LOG_FILE"
    exit 1
fi

# Check if race is over (read date from config)
TODAY=$(date '+%Y%m%d')
RACE_DATE=$("$PYTHON" -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
try:
    import yaml
    cfg = yaml.safe_load(open('$SCRIPT_DIR/race_config.yaml'))
    print(cfg['race']['date'].replace('-', ''))
except Exception as e:
    print('ERROR', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null) || RACE_DATE=""

if [ -n "$RACE_DATE" ] && [ "$TODAY" -gt "$RACE_DATE" ]; then
    echo "[INFO] Race concluded ($RACE_DATE). Stopping." >> "$LOG_FILE"
    exit 0
fi

# Run the briefing generator
cd "$SCRIPT_DIR" || { echo "[ERROR] Cannot cd to $SCRIPT_DIR" >&2; exit 1; }
if ! "$PYTHON" generate_daily_briefing.py 2>&1 | tee -a "$LOG_FILE"; then
    echo "[ERROR] Script failed at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    exit 1
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') Daily Briefing End =====" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Log rotation: keep last 500 lines
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt 1000 ]; then
    tail -500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
