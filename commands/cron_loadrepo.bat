@echo off
REM 
REM cron_loadrepo.bat - Windows batch script for loading repository
REM
REM This script can be used with Windows Task Scheduler to automatically load
REM new FITS files into the repository from the source folder.
REM
REM To use with Task Scheduler:
REM 1. Open Task Scheduler (taskschd.msc)
REM 2. Create Basic Task
REM 3. Set trigger (e.g., Daily at 10:00 AM)
REM 4. Set action to start this batch file
REM 5. Configure additional settings as needed
REM
REM Example: Run daily at 10:00 AM when imaging operations are complete

REM Configuration - EDIT THESE PATHS FOR YOUR INSTALLATION
set ASTROFILER_DIR=C:\path\to\astrofiler-gui
set PYTHON_VENV=%ASTROFILER_DIR%\.venv\Scripts\python.exe
set LOADREPO_SCRIPT=%ASTROFILER_DIR%\commands\LoadRepo.py
set LOG_FILE=%ASTROFILER_DIR%\cron_loadrepo.log

REM Change to the astrofiler directory
cd /d "%ASTROFILER_DIR%"

REM Log the start time
echo %date% %time%: Starting repository load via Task Scheduler >> "%LOG_FILE%"

REM Run the LoadRepo script with verbose output
"%PYTHON_VENV%" "%LOADREPO_SCRIPT%" -v >> "%LOG_FILE%" 2>&1

REM Log completion
echo %date% %time%: Repository load completed (exit code: %ERRORLEVEL%) >> "%LOG_FILE%"
echo ---------------------------------------- >> "%LOG_FILE%"

REM Pause only if run manually (not from Task Scheduler)
if "%1"=="manual" pause
