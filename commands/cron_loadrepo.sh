#!/bin/bash
# 
# cron_loadrepo.sh - Example cron script for loading repository
#
# This script can be used with cron to automatically load new FITS files
# into the repository at scheduled intervals.
#
# To use with crontab:
# 1. Make this script executable: chmod +x cron_loadrepo.sh
# 2. Edit crontab: crontab -e
# 3. Add a line like: 0 10 * * * /path/to/astrofiler-gui/commands/cron_loadrepo.sh
#
# The above example runs daily at 10:00 AM

# Configuration
ASTROFILER_DIR="/home/gtulloch/Projects/astrofiler-gui"
PYTHON_VENV="$ASTROFILER_DIR/.venv/bin/python"
LOADREPO_SCRIPT="$ASTROFILER_DIR/commands/LoadRepo.py"
LOG_FILE="$ASTROFILER_DIR/cron_loadrepo.log"

# Change to the astrofiler directory
cd "$ASTROFILER_DIR"

# Log the start time
echo "$(date): Starting repository load via cron" >> "$LOG_FILE"

# Run the LoadRepo script with verbose output
"$PYTHON_VENV" "$LOADREPO_SCRIPT" -v >> "$LOG_FILE" 2>&1

# Log completion
echo "$(date): Repository load completed (exit code: $?)" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
