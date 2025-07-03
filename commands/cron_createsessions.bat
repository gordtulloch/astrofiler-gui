@echo off
REM 
REM cron_createsessions.bat - Windows batch script for creating sessions
REM
REM This script can be used with Windows Task Scheduler to automatically create
REM light and calibration sessions for FITS files that have been processed
REM but not yet assigned to sessions.
REM
REM To use with Task Scheduler:
REM 1. Open Task Scheduler (taskschd.msc)
REM 2. Create Basic Task
REM 3. Set trigger (e.g., Daily at 10:30 AM)
REM 4. Set action to start this batch file
REM 5. Configure additional settings as needed
REM
REM Example: Run daily at 10:30 AM (after LoadRepo has run at 10:00 AM)

REM Configuration - EDIT THESE PATHS FOR YOUR INSTALLATION
set ASTROFILER_DIR=C:\path\to\astrofiler-gui
set PYTHON_VENV=%ASTROFILER_DIR%\.venv\Scripts\python.exe
set CREATESESSIONS_SCRIPT=%ASTROFILER_DIR%\commands\CreateSessions.py
set LOG_FILE=%ASTROFILER_DIR%\cron_createsessions.log

REM Change to the astrofiler directory
cd /d "%ASTROFILER_DIR%"

REM Log the start time
echo %date% %time%: Starting session creation via Task Scheduler >> "%LOG_FILE%"

REM Run the CreateSessions script with verbose output
"%PYTHON_VENV%" "%CREATESESSIONS_SCRIPT%" -v >> "%LOG_FILE%" 2>&1

REM Log completion
echo %date% %time%: Session creation completed (exit code: %ERRORLEVEL%) >> "%LOG_FILE%"
echo ---------------------------------------- >> "%LOG_FILE%"

REM Pause only if run manually (not from Task Scheduler)
if "%1"=="manual" pause
