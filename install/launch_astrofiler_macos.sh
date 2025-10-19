#!/bin/bash
# AstroFiler Desktop Launcher for macOS
# This script launches AstroFiler from any location

# Get the directory where this script is located and go to parent
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the AstroFiler directory (parent of install folder)
cd "$SCRIPT_DIR/.."

# Check for updates from GitHub if this is a git repository
if [ -d ".git" ]; then
    echo "Checking for updates from GitHub..."
    echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - INFO - Checking for updates from GitHub..." >> astrofiler.log
    if command -v git >/dev/null 2>&1; then
        git fetch origin main >/dev/null 2>&1
        UPDATE_COUNT=$(git rev-list HEAD..origin/main --count 2>/dev/null || echo "0")
        if [ "$UPDATE_COUNT" -gt 0 ] 2>/dev/null; then
            echo "Updates available! Pulling latest changes..."
            echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - INFO - Updates available! $UPDATE_COUNT commits behind. Pulling latest changes..." >> astrofiler.log
            if git fetch origin && git reset --hard origin/main; then
                echo "Successfully updated to latest version."
                echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - INFO - Successfully updated to latest version from GitHub" >> astrofiler.log
                # Run database migrations after successful update
                echo "Running database migrations..."
                echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - INFO - Running database migrations after update" >> astrofiler.log
                if [ -f ".venv/bin/python" ]; then
                    if .venv/bin/python migrate.py run; then
                        echo "Database migrations completed successfully."
                        echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - INFO - Database migrations completed successfully" >> astrofiler.log
                    else
                        echo "Warning: Database migration failed. AstroFiler may not function correctly."
                        echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - WARNING - Database migration failed after update" >> astrofiler.log
                    fi
                fi
            else
                echo "Warning: Failed to update from GitHub. Continuing with current version."
                echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - WARNING - Failed to update from GitHub. Continuing with current version" >> astrofiler.log
            fi
        else
            echo "Already up to date."
            echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - INFO - Repository already up to date" >> astrofiler.log
        fi
    else
        echo "Note: git not available, skipping update check."
        echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - INFO - git not available, skipping update check" >> astrofiler.log
    fi
    echo
fi

# Check if virtual environment exists
if [ ! -f ".venv/bin/activate" ]; then
    # Show error dialog on macOS
    osascript -e 'tell application "System Events" to display dialog "AstroFiler virtual environment not found. Please run install_macos.sh first to set up AstroFiler." with title "AstroFiler Error" buttons {"OK"} default button "OK"'
    exit 1
fi

# Activate virtual environment
echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - INFO - Starting AstroFiler application via launch script" >> astrofiler.log
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler_macos.sh - ERROR - Failed to activate virtual environment" >> astrofiler.log
    osascript -e 'tell application "System Events" to display dialog "Failed to activate virtual environment." with title "AstroFiler Error" buttons {"OK"} default button "OK"'
    exit 1
fi

# Run AstroFiler
python astrofiler.py

# If AstroFiler exits with an error, show the error
if [ $? -ne 0 ]; then
    osascript -e 'tell application "System Events" to display dialog "AstroFiler exited with an error. Check the terminal for details." with title "AstroFiler Error" buttons {"OK"} default button "OK"'
fi
