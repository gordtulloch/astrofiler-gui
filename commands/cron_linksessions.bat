@echo off
REM 
REM cron_linksessions.bat - Windows batch script for linking calibration sessions
REM
REM This script can be used with Windows Task Scheduler to automatically link
REM calibration sessions to light sessions based on telescope and imager matching.
REM
REM To use with Task Scheduler:
REM 1. Open Task Scheduler (taskschd.msc)
REM 2. Create Basic Task
REM 3. Set trigger (e.g., Daily at 11:00 AM)
REM 4. Set action to start this batch file
REM 5. Configure additional settings as needed
REM
REM Example: Run daily at 11:00 AM (after sessions have been created)

REM Configuration - EDIT THESE PATHS FOR YOUR INSTALLATION
set ASTROFILER_DIR=C:\path\to\astrofiler-gui
set PYTHON_VENV=%ASTROFILER_DIR%\.venv\Scripts\python.exe
set LINKSESSIONS_SCRIPT=%ASTROFILER_DIR%\commands\LinkSessions.py
set LOG_FILE=%ASTROFILER_DIR%\cron_linksessions.log

REM Change to the astrofiler directory
cd /d "%ASTROFILER_DIR%"

REM Log the start time
echo %date% %time%: Starting session linking via Task Scheduler >> "%LOG_FILE%"

REM Run the LinkSessions script with verbose output
"%PYTHON_VENV%" "%LINKSESSIONS_SCRIPT%" -v >> "%LOG_FILE%" 2>&1

REM Log completion
echo %date% %time%: Session linking completed (exit code: %ERRORLEVEL%) >> "%LOG_FILE%"
echo ---------------------------------------- >> "%LOG_FILE%"

REM Pause only if run manually (not from Task Scheduler)
if "%1"=="manual" pause
