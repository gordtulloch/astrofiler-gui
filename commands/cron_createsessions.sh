#!/bin/bash
# 
# cron_createsessions.sh - Example cron script for creating sessions
#
# This script can be used with cron to automatically create light and calibration
# sessions for FITS files that have been processed but not yet assigned to sessions.
#
# To use with crontab:
# 1. Make this script executable: chmod +x cron_createsessions.sh
# 2. Edit crontab: crontab -e
# 3. Add a line like: 30 10 * * * /path/to/astrofiler-gui/commands/cron_createsessions.sh
#
# The above example runs daily at 10:30 AM (after LoadRepo has run at 10:00 AM)

# Configuration
ASTROFILER_DIR="/home/gtulloch/Projects/astrofiler-gui"
PYTHON_VENV="$ASTROFILER_DIR/.venv/bin/python"
CREATESESSIONS_SCRIPT="$ASTROFILER_DIR/commands/CreateSessions.py"
LOG_FILE="$ASTROFILER_DIR/cron_createsessions.log"

# Change to the astrofiler directory
cd "$ASTROFILER_DIR"

# Log the start time
echo "$(date): Starting session creation via cron" >> "$LOG_FILE"

# Run the CreateSessions script with verbose output
"$PYTHON_VENV" "$CREATESESSIONS_SCRIPT" -v >> "$LOG_FILE" 2>&1

# Log completion
echo "$(date): Session creation completed (exit code: $?)" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
