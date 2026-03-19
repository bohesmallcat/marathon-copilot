#!/bin/bash
# Daily Marathon Weather Report - Cron Wrapper
# Runs at 6:00 AM Beijing time daily until all races are over (2026-03-22)
#
# Crontab entry:
#   0 6 * * * /path/to/marathon-training/PB/api-tools/run_daily_weather.sh >> /tmp/weather_cron.log 2>&1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
LOG_FILE="/tmp/weather_cron.log"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') Weather Report Cron Start ====="

# Check if races are over (after 2026-03-22)
TODAY=$(date '+%Y%m%d')
if [ "$TODAY" -gt "20260322" ]; then
    echo "[INFO] All races concluded. Removing cron job."
    crontab -l 2>/dev/null | grep -v "run_daily_weather.sh" | crontab -
    exit 0
fi

# Run the report
cd "$SCRIPT_DIR"
"$PYTHON" daily_weather_email.py 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') Weather Report Cron End ====="
echo ""
