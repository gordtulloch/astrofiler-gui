#!/bin/bash
# 
# cron_linksessions.sh - Example cron script for linking calibration sessions
#
# This script can be used with cron to automatically link calibration sessions
# to light sessions based on telescope and imager matching.
#
# To use with crontab:
# 1. Make this script executable: chmod +x cron_linksessions.sh
# 2. Edit crontab: crontab -e
# 3. Add a line like: 0 11 * * * /path/to/astrofiler-gui/commands/cron_linksessions.sh
#
# The above example runs daily at 11:00 AM (after sessions have been created)

# Configuration
ASTROFILER_DIR="/home/gtulloch/Projects/astrofiler-gui"
PYTHON_VENV="$ASTROFILER_DIR/.venv/bin/python"
LINKSESSIONS_SCRIPT="$ASTROFILER_DIR/commands/LinkSessions.py"
LOG_FILE="$ASTROFILER_DIR/cron_linksessions.log"

# Change to the astrofiler directory
cd "$ASTROFILER_DIR"

# Log the start time
echo "$(date): Starting session linking via cron" >> "$LOG_FILE"

# Run the LinkSessions script with verbose output
"$PYTHON_VENV" "$LINKSESSIONS_SCRIPT" -v >> "$LOG_FILE" 2>&1

# Log completion
echo "$(date): Session linking completed (exit code: $?)" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
