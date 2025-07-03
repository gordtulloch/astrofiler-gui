#!/bin/bash
# 
# astrofiler_workflow.sh - Complete Linux automation workflow
#
# This script runs the complete AstroFiler workflow:
# 1. Load repository (move files from source to repository)
# 2. Create sessions (group files into light and calibration sessions)
#
# Can be run manually or scheduled with cron
#
# Usage:
#   ./astrofiler_workflow.sh              - Run complete workflow
#   ./astrofiler_workflow.sh load         - Only load repository  
#   ./astrofiler_workflow.sh sessions     - Only create sessions
#   ./astrofiler_workflow.sh link         - Only link sessions
#   ./astrofiler_workflow.sh manual       - Run with pause for manual execution

# Configuration - EDIT THESE PATHS FOR YOUR INSTALLATION
ASTROFILER_DIR="/home/gtulloch/Projects/astrofiler-gui"
PYTHON_VENV="$ASTROFILER_DIR/.venv/bin/python"
LOADREPO_SCRIPT="$ASTROFILER_DIR/commands/LoadRepo.py"
CREATESESSIONS_SCRIPT="$ASTROFILER_DIR/commands/CreateSessions.py"
LINKSESSIONS_SCRIPT="$ASTROFILER_DIR/commands/LinkSessions.py"
LOG_FILE="$ASTROFILER_DIR/astrofiler_workflow.log"

# Change to the astrofiler directory
cd "$ASTROFILER_DIR"

# Parse command line arguments
RUN_LOAD=1
RUN_SESSIONS=1
RUN_LINK=1
MANUAL_MODE=0

case "$1" in
    "load")
        RUN_SESSIONS=0
        RUN_LINK=0
        ;;
    "sessions")
        RUN_LOAD=0
        RUN_LINK=0
        ;;
    "link")
        RUN_LOAD=0
        RUN_SESSIONS=0
        ;;
    "manual")
        MANUAL_MODE=1
        ;;
    "")
        # Default: run both
        ;;
    *)
        echo "Usage: $0 [load|sessions|link|manual]"
        echo "  load     - Only load repository"
        echo "  sessions - Only create sessions"
        echo "  link     - Only link sessions"
        echo "  manual   - Run with pause for manual execution"
        echo "  (no arg) - Run complete workflow"
        exit 1
        ;;
esac

# Log the start time
echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "$(date): Starting AstroFiler workflow" >> "$LOG_FILE"

# Repository loading
if [ $RUN_LOAD -eq 1 ]; then
    echo "$(date): Running repository load..." >> "$LOG_FILE"
    if [ $MANUAL_MODE -eq 1 ]; then
        echo "Running repository load..."
    fi
    
    "$PYTHON_VENV" "$LOADREPO_SCRIPT" -v >> "$LOG_FILE" 2>&1
    LOAD_EXIT=$?
    
    echo "$(date): Repository load completed (exit code: $LOAD_EXIT)" >> "$LOG_FILE"
    
    if [ $LOAD_EXIT -ne 0 ]; then
        echo "ERROR: Repository load failed with exit code $LOAD_EXIT" >> "$LOG_FILE"
        if [ $MANUAL_MODE -eq 1 ]; then
            echo "ERROR: Repository load failed!"
        fi
        
        # Error handling
        echo "$(date): AstroFiler workflow completed with errors" >> "$LOG_FILE"
        echo "========================================" >> "$LOG_FILE"
        
        if [ $MANUAL_MODE -eq 1 ]; then
            echo ""
            echo "AstroFiler workflow completed with errors. Check the log file:"
            echo "$LOG_FILE"
            read -p "Press Enter to continue..."
        fi
        exit 1
    fi
fi

# Session creation
if [ $RUN_SESSIONS -eq 1 ]; then
    echo "$(date): Running session creation..." >> "$LOG_FILE"
    if [ $MANUAL_MODE -eq 1 ]; then
        echo "Running session creation..."
    fi
    
    "$PYTHON_VENV" "$CREATESESSIONS_SCRIPT" -v >> "$LOG_FILE" 2>&1
    SESSIONS_EXIT=$?
    
    echo "$(date): Session creation completed (exit code: $SESSIONS_EXIT)" >> "$LOG_FILE"
    
    if [ $SESSIONS_EXIT -ne 0 ]; then
        echo "ERROR: Session creation failed with exit code $SESSIONS_EXIT" >> "$LOG_FILE"
        if [ $MANUAL_MODE -eq 1 ]; then
            echo "ERROR: Session creation failed!"
        fi
        
        # Error handling
        echo "$(date): AstroFiler workflow completed with errors" >> "$LOG_FILE"
        echo "========================================" >> "$LOG_FILE"
        
        if [ $MANUAL_MODE -eq 1 ]; then
            echo ""
            echo "AstroFiler workflow completed with errors. Check the log file:"
            echo "$LOG_FILE"
            read -p "Press Enter to continue..."
        fi
        exit 1
    fi
fi

# Session linking
if [ $RUN_LINK -eq 1 ]; then
    echo "$(date): Running session linking..." >> "$LOG_FILE"
    if [ $MANUAL_MODE -eq 1 ]; then
        echo "Running session linking..."
    fi
    
    "$PYTHON_VENV" "$LINKSESSIONS_SCRIPT" -v >> "$LOG_FILE" 2>&1
    LINK_EXIT=$?
    
    echo "$(date): Session linking completed (exit code: $LINK_EXIT)" >> "$LOG_FILE"
    
    if [ $LINK_EXIT -ne 0 ]; then
        echo "ERROR: Session linking failed with exit code $LINK_EXIT" >> "$LOG_FILE"
        if [ $MANUAL_MODE -eq 1 ]; then
            echo "ERROR: Session linking failed!"
        fi
        
        # Error handling
        echo "$(date): AstroFiler workflow completed with errors" >> "$LOG_FILE"
        echo "========================================" >> "$LOG_FILE"
        
        if [ $MANUAL_MODE -eq 1 ]; then
            echo ""
            echo "AstroFiler workflow completed with errors. Check the log file:"
            echo "$LOG_FILE"
            read -p "Press Enter to continue..."
        fi
        exit 1
    fi
fi

# Success
echo "$(date): AstroFiler workflow completed successfully" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

if [ $MANUAL_MODE -eq 1 ]; then
    echo ""
    echo "AstroFiler workflow completed successfully!"
    read -p "Press Enter to continue..."
fi

exit 0
