#!/bin/bash
# AstroFiler Register Existing Files - Unix Shell Script
# Convenience script to run the existing file registration command

# Get the directory this script is in
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

# Run the registration command
python commands/RegisterExisting.py "$@"

# Check exit code
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "Registration completed successfully"
else
    echo ""
    echo "Registration failed with error code $EXIT_CODE"
    exit $EXIT_CODE
fi