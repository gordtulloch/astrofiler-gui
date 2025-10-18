#!/bin/bash
# 
# cron_cloudsync.sh - Example cron script for cloud synchronization
#
# This script can be used with cron to automatically sync FITS files
# with Google Cloud Storage at scheduled intervals.
#
# To use with crontab:
# 1. Make this script executable: chmod +x cron_cloudsync.sh
# 2. Edit crontab: crontab -e
# 3. Add a line like: 0 23 * * * /path/to/astrofiler-gui/commands/cron_cloudsync.sh
#
# The above example runs daily at 11:00 PM for automated cloud backup

# Configuration
ASTROFILER_DIR="/home/gtulloch/Projects/astrofiler-gui"
PYTHON_VENV="$ASTROFILER_DIR/.venv/bin/python"
CLOUDSYNC_SCRIPT="$ASTROFILER_DIR/commands/CloudSync.py"
LOG_FILE="$ASTROFILER_DIR/cron_cloudsync.log"

# Change to the astrofiler directory
cd "$ASTROFILER_DIR" || exit 1

# Create logs directory if it doesn't exist
mkdir -p logs

# Generate timestamped log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOGFILE="logs/cloudsync_$TIMESTAMP.log"

echo "Starting AstroFiler Cloud Sync at $(date)" > "$LOGFILE"
echo "==============================================" >> "$LOGFILE"

# Execute cloud sync with auto-confirm and verbose logging
"$PYTHON_VENV" "$CLOUDSYNC_SCRIPT" -y -v >> "$LOGFILE" 2>&1

# Check exit code and log result
if [ $? -eq 0 ]; then
    echo "Cloud sync completed successfully at $(date)" >> "$LOGFILE"
    echo "==============================================" >> "$LOGFILE"
    exit 0
else
    echo "Cloud sync failed with error code $? at $(date)" >> "$LOGFILE"
    echo "==============================================" >> "$LOGFILE"
    exit 1
fi