#!/bin/bash
# cron_autocalibration.sh - Linux/macOS shell script for scheduled auto-calibration
#
# This script runs the AutoCalibration.py tool on a schedule using cron.
# It includes error handling, logging, and notification capabilities.
#
# Usage:
#   ./cron_autocalibration.sh [operation] [options]
#
# Examples:
#   ./cron_autocalibration.sh                    # Run complete workflow
#   ./cron_autocalibration.sh masters            # Create masters only
#   ./cron_autocalibration.sh analyze            # Analyze opportunities only
#
# Setup for cron:
#   # Add to crontab (crontab -e):
#   # Run daily at 2 AM
#   0 2 * * * /path/to/astrofiler/commands/cron_autocalibration.sh
#   
#   # Run every 6 hours
#   0 */6 * * * /path/to/astrofiler/commands/cron_autocalibration.sh
#   
#   # Run weekly on Sunday at 3 AM
#   0 3 * * 0 /path/to/astrofiler/commands/cron_autocalibration.sh

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_ENV="$PROJECT_DIR/.venv/bin/python"
AUTOCALIBRATION_SCRIPT="$PROJECT_DIR/commands/AutoCalibration.py"
LOG_DIR="$PROJECT_DIR/logs"
TIMESTAMP=$(date "+%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/autocalibration_$TIMESTAMP.log"

# Ensure we can write logs
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Error handling function
error_exit() {
    log "ERROR: $1"
    echo "Auto-calibration failed at $(date)" > "$PROJECT_DIR/autocalibration_error.flag"
    exit 1
}

# Start logging
{
    echo "================================================================"
    echo "AstroFiler Auto-Calibration Scheduled Run"
    echo "Started: $(date)"
    echo "================================================================"
} >> "$LOG_FILE"

log "Auto-calibration cron job starting..."

# Check if Python environment exists
if [[ ! -f "$PYTHON_ENV" ]]; then
    error_exit "Python environment not found: $PYTHON_ENV. Please ensure AstroFiler is properly installed."
fi

# Check if AutoCalibration script exists
if [[ ! -f "$AUTOCALIBRATION_SCRIPT" ]]; then
    error_exit "AutoCalibration script not found: $AUTOCALIBRATION_SCRIPT"
fi

# Change to project directory
cd "$PROJECT_DIR"

# Build command with parameters
OPERATION="${1:-all}"
shift || true  # Don't fail if no parameters

# Build Python command
PYTHON_CMD="$PYTHON_ENV $AUTOCALIBRATION_SCRIPT -o $OPERATION -v --log-file $LOG_FILE"

# Add additional parameters
for arg in "$@"; do
    PYTHON_CMD="$PYTHON_CMD $arg"
done

log "Running: $PYTHON_CMD"
echo >> "$LOG_FILE"

# Execute the Python script
set +e  # Temporarily disable exit on error to capture exit code
eval "$PYTHON_CMD"
EXIT_CODE=$?
set -e

# Log completion
{
    echo
    echo "================================================================"
    echo "Completed: $(date)"
    echo "Exit code: $EXIT_CODE"
    
    if [[ $EXIT_CODE -eq 0 ]]; then
        echo "Status: SUCCESS"
    else
        echo "Status: FAILED"
    fi
    
    echo "================================================================"
} >> "$LOG_FILE"

# Handle success/failure
if [[ $EXIT_CODE -eq 0 ]]; then
    log "Auto-calibration completed successfully"
    # Remove any existing error flag
    rm -f "$PROJECT_DIR/autocalibration_error.flag"
else
    error_exit "Auto-calibration failed with exit code $EXIT_CODE"
fi

# Optional: Cleanup old log files (keep last 30 days)
find "$LOG_DIR" -name "autocalibration_*.log" -type f -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE