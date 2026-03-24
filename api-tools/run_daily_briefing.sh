#!/bin/bash
# 328 苏河半马 — Daily Briefing Cron Wrapper
# Runs at 08:00 AM Beijing time daily until race day (2026-03-28)
#
# Crontab entry (Beijing time / CST):
#   0 8 * * * /mnt/c/Users/Danna_C/workspace/wsl/marathon-training/PB/api-tools/run_daily_briefing.sh >> "/mnt/c/Users/Danna_C/OneDrive - Dell Technologies/Documents/PB/api-tools/reports/cron.log" 2>&1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/home/ss/.pyenv/versions/3.10.14/bin/python3"
LOG_DIR="/mnt/c/Users/Danna_C/OneDrive - Dell Technologies/Documents/PB/api-tools/reports"
LOG_FILE="$LOG_DIR/cron.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') Daily Briefing Start =====" >> "$LOG_FILE"

# Check if race is over (after 2026-03-28)
TODAY=$(date '+%Y%m%d')
if [ "$TODAY" -gt "20260328" ]; then
    echo "[INFO] Race concluded. Removing cron job." >> "$LOG_FILE"
    crontab -l 2>/dev/null | grep -v "run_daily_briefing.sh" | crontab -
    exit 0
fi

# Run the briefing generator
cd "$SCRIPT_DIR"
"$PYTHON" generate_daily_briefing.py 2>&1 | tee -a "$LOG_FILE"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') Daily Briefing End =====" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
