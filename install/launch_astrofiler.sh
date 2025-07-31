#!/bin/bash
# AstroFiler Desktop Launcher for Linux
# This script launches AstroFiler from any location

# Get the directory where this script is located and go to parent
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the AstroFiler directory (parent of install folder)
cd "$SCRIPT_DIR/.."

# Verify we're in the right directory
if [ ! -f "astrofiler.py" ]; then
    echo "Error: Could not find astrofiler.py in the expected location."
    echo "Current directory: $(pwd)"
    echo "Script directory: $SCRIPT_DIR"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check for updates from GitHub if this is a git repository
if [ -d ".git" ]; then
    echo "Checking for updates from GitHub..."
    echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - INFO - Checking for updates from GitHub..." >> astrofiler.log
    if command -v git >/dev/null 2>&1; then
        git fetch origin main >/dev/null 2>&1
        UPDATE_COUNT=$(git rev-list HEAD..origin/main --count 2>/dev/null || echo "0")
        if [ "$UPDATE_COUNT" -gt 0 ] 2>/dev/null; then
            echo "Updates available! Pulling latest changes..."
            echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - INFO - Updates available! $UPDATE_COUNT commits behind. Pulling latest changes..." >> astrofiler.log
            if git pull origin main; then
                echo "Successfully updated to latest version."
                echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - INFO - Successfully updated to latest version from GitHub" >> astrofiler.log
                # Run database migrations after successful update
                echo "Running database migrations..."
                echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - INFO - Running database migrations after update" >> astrofiler.log
                if [ -f ".venv/bin/python" ]; then
                    if .venv/bin/python migrate.py run; then
                        echo "Database migrations completed successfully."
                        echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - INFO - Database migrations completed successfully" >> astrofiler.log
                    else
                        echo "Warning: Database migration failed. AstroFiler may not function correctly."
                        echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - WARNING - Database migration failed after update" >> astrofiler.log
                    fi
                fi
            else
                echo "Warning: Failed to update from GitHub. Continuing with current version."
                echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - WARNING - Failed to update from GitHub. Continuing with current version" >> astrofiler.log
            fi
        else
            echo "Already up to date."
            echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - INFO - Repository already up to date" >> astrofiler.log
        fi
    else
        echo "Note: git not available, skipping update check."
        echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - INFO - git not available, skipping update check" >> astrofiler.log
    fi
    echo
fi

# Check if virtual environment exists
if [ ! -f ".venv/bin/activate" ]; then
    echo "Error: AstroFiler virtual environment not found."
    echo "Please run install.sh first to set up AstroFiler."
    echo
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Starting AstroFiler..."
echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - INFO - Starting AstroFiler application via launch script" >> astrofiler.log

# Activate virtual environment
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Error: Failed to activate virtual environment."
    echo "$(date '+%Y-%m-%d %H:%M:%S') - launch_astrofiler.sh - ERROR - Failed to activate virtual environment" >> astrofiler.log
    read -p "Press Enter to exit..."
    exit 1
fi

# Run AstroFiler
python astrofiler.py

# If AstroFiler exits with an error, show the error
if [ $? -ne 0 ]; then
    echo
    echo "AstroFiler exited with an error."
    echo "Error code: $?"
    read -p "Press Enter to exit..."
fi
