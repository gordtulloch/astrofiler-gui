#!/bin/bash
# AstroFiler Desktop Launcher for Linux
# This script launches AstroFiler from any location

# Get the directory where this script is located and go to parent
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the AstroFiler directory (parent of install folder)
cd "$SCRIPT_DIR/.."

# Check for updates from GitHub if this is a git repository
if [ -d ".git" ]; then
    echo "Checking for updates from GitHub..."
    if command -v git >/dev/null 2>&1; then
        git fetch origin main >/dev/null 2>&1
        UPDATE_COUNT=$(git rev-list HEAD..origin/main --count 2>/dev/null || echo "0")
        if [ "$UPDATE_COUNT" -gt 0 ] 2>/dev/null; then
            echo "Updates available! Pulling latest changes..."
            if git pull origin main; then
                echo "Successfully updated to latest version."
            else
                echo "Warning: Failed to update from GitHub. Continuing with current version."
            fi
        else
            echo "Already up to date."
        fi
    else
        echo "Note: git not available, skipping update check."
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

# Activate virtual environment
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Error: Failed to activate virtual environment."
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
