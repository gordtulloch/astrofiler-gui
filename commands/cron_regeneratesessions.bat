@echo off
REM Batch script to regenerate all AstroFiler sessions
REM This script clears all existing sessions and recreates them from FITS files

echo AstroFiler Session Regeneration Starting...
echo This will clear all existing sessions and recreate them.

cd /d "%~dp0\.."
.\.venv\Scripts\python commands/CreateSessions.py --regenerate --verbose

if %ERRORLEVEL% EQU 0 (
    echo Session regeneration completed successfully!
) else (
    echo Session regeneration failed with error code %ERRORLEVEL%
)

pause