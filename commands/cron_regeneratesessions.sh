#!/bin/bash
# Shell script to regenerate all AstroFiler sessions
# This script clears all existing sessions and recreates them from FITS files

echo "AstroFiler Session Regeneration Starting..."
echo "This will clear all existing sessions and recreate them."

# Change to the parent directory of this script
cd "$(dirname "$0")/.."

# Run the regeneration with verbose output
python commands/CreateSessions.py --regenerate --verbose

# Check exit code
if [ $? -eq 0 ]; then
    echo "Session regeneration completed successfully!"
    exit 0
else
    echo "Session regeneration failed with error code $?"
    exit 1
fi