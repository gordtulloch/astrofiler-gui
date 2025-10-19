#!/bin/bash
# ============================================================
# AstroFiler Light Frame Calibration - Linux/macOS Automation
# ============================================================
#
# This script performs automated light frame calibration using PySiril
# Edit the paths below to match your installation
#
# Schedule with cron for regular processing
# Recommended: Run after auto-calibration master creation
#
# Example crontab entries:
# # Daily at 3 AM (after master creation at 2 AM)
# 0 3 * * * /path/to/astrofiler-gui-dev/commands/cron_calibrate_lights.sh auto
# 
# # Process specific sessions on demand
# 0 4 * * * /path/to/astrofiler-gui-dev/commands/cron_calibrate_lights.sh session 123
#
# # Quality assessment every 6 hours
# 0 */6 * * * /path/to/astrofiler-gui-dev/commands/cron_calibrate_lights.sh quality
# ============================================================

# Configuration - EDIT THESE PATHS
ASTROFILER_DIR="/path/to/astrofiler-gui-dev"
PYTHON_EXE="$ASTROFILER_DIR/.venv/bin/python"
SCRIPT_PATH="$ASTROFILER_DIR/commands/calibrateLights.py"
LOG_DIR="$ASTROFILER_DIR/logs"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# Ensure script is executable
chmod +x "$0"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log file path
LOG_FILE="$LOG_DIR/calibrate_lights_$TIMESTAMP.log"

# Change to project directory
cd "$ASTROFILER_DIR" || exit 1

echo "============================================================" > "$LOG_FILE"
echo "AstroFiler Light Calibration Automation" >> "$LOG_FILE"
echo "Started: $(date)" >> "$LOG_FILE"
echo "============================================================" >> "$LOG_FILE"

# Check if Python executable exists
if [ ! -f "$PYTHON_EXE" ]; then
    echo "ERROR: Python executable not found at $PYTHON_EXE" >> "$LOG_FILE"
    echo "Please check the PYTHON_EXE path in this script" >> "$LOG_FILE"
    exit 1
fi

# Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: calibrateLights.py not found at $SCRIPT_PATH" >> "$LOG_FILE"
    echo "Please check the SCRIPT_PATH in this script" >> "$LOG_FILE"
    exit 1
fi

# Parse command line arguments
OPERATION="${1:-auto}"
SESSION_ID="$2"
OBJECT_NAME="$3"

echo "Operation: $OPERATION" >> "$LOG_FILE"
[ -n "$SESSION_ID" ] && echo "Session ID: $SESSION_ID" >> "$LOG_FILE"
[ -n "$OBJECT_NAME" ] && echo "Object Name: $OBJECT_NAME" >> "$LOG_FILE"

# Execute based on operation
case "$OPERATION" in
    "auto")
        echo "Performing automatic light calibration for recent sessions..." >> "$LOG_FILE"
        "$PYTHON_EXE" "$SCRIPT_PATH" --verbose 2>&1 >> "$LOG_FILE"
        ERROR_CODE=$?
        ;;
        
    "session")
        if [ -z "$SESSION_ID" ]; then
            echo "ERROR: Session ID required for session operation" >> "$LOG_FILE"
            exit 1
        fi
        echo "Calibrating session $SESSION_ID..." >> "$LOG_FILE"
        "$PYTHON_EXE" "$SCRIPT_PATH" --session "$SESSION_ID" --verbose 2>&1 >> "$LOG_FILE"
        ERROR_CODE=$?
        ;;
        
    "object")
        if [ -z "$OBJECT_NAME" ]; then
            echo "ERROR: Object name required for object operation" >> "$LOG_FILE"
            exit 1
        fi
        echo "Calibrating object '$OBJECT_NAME'..." >> "$LOG_FILE"
        "$PYTHON_EXE" "$SCRIPT_PATH" --object "$OBJECT_NAME" --verbose 2>&1 >> "$LOG_FILE"
        ERROR_CODE=$?
        ;;
        
    "quality")
        echo "Performing dry run calibration check..." >> "$LOG_FILE"
        "$PYTHON_EXE" "$SCRIPT_PATH" --dry-run --verbose 2>&1 >> "$LOG_FILE"
        ERROR_CODE=$?
        ;;
        
    "help")
        echo "Available operations:" >> "$LOG_FILE"
        echo "  auto          - Automatic calibration for recent sessions" >> "$LOG_FILE"
        echo "  session [ID]  - Calibrate specific session by ID" >> "$LOG_FILE"
        echo "  object [NAME] - Calibrate all sessions for specific object" >> "$LOG_FILE"
        echo "  quality       - Quality assessment only (dry-run)" >> "$LOG_FILE"
        echo "  help          - Show this help message" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        echo "Examples:" >> "$LOG_FILE"
        echo "  $0 auto" >> "$LOG_FILE"
        echo "  $0 session 123" >> "$LOG_FILE"
        echo "  $0 object \"M31\"" >> "$LOG_FILE"
        echo "  $0 quality" >> "$LOG_FILE"
        ERROR_CODE=0
        ;;
        
    *)
        echo "ERROR: Unknown operation '$OPERATION'" >> "$LOG_FILE"
        echo "Use 'help' to see available operations" >> "$LOG_FILE"
        ERROR_CODE=1
        ;;
esac

echo "============================================================" >> "$LOG_FILE"
if [ $ERROR_CODE -eq 0 ]; then
    echo "Light calibration completed successfully" >> "$LOG_FILE"
    echo "Finished: $(date)" >> "$LOG_FILE"
else
    echo "Light calibration failed with error code $ERROR_CODE" >> "$LOG_FILE"
    echo "Finished: $(date)" >> "$LOG_FILE"
    # Create error flag file for monitoring
    echo "$ERROR_CODE" > "$LOG_DIR/calibrate_lights_error_$TIMESTAMP.flag"
fi
echo "============================================================" >> "$LOG_FILE"

# Cleanup old log files (keep last 30 days)
find "$LOG_DIR" -name "calibrate_lights_*.log" -type f -mtime +30 -delete 2>/dev/null
find "$LOG_DIR" -name "calibrate_lights_*.flag" -type f -mtime +30 -delete 2>/dev/null

exit $ERROR_CODE