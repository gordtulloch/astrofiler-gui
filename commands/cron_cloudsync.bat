@echo off
REM 
REM cron_cloudsync.bat - Windows batch script for cloud synchronization
REM
REM This script can be used with Windows Task Scheduler to automatically sync
REM FITS files with Google Cloud Storage using the configured sync profile.
REM
REM To use with Task Scheduler:
REM 1. Open Task Scheduler (taskschd.msc)
REM 2. Create Basic Task
REM 3. Set trigger (e.g., Daily at 11:00 PM after imaging)
REM 4. Set action to start this batch file
REM 5. Configure additional settings as needed
REM
REM Example: Run daily at 11:00 PM for automated cloud backup

REM Configuration - EDIT THESE PATHS FOR YOUR INSTALLATION
set ASTROFILER_DIR=C:\path\to\astrofiler-gui
set PYTHON_VENV=%ASTROFILER_DIR%\.venv\Scripts\python.exe
set CLOUDSYNC_SCRIPT=%ASTROFILER_DIR%\commands\CloudSync.py

REM Change to the astrofiler directory
cd /d "%ASTROFILER_DIR%"

REM Create log directory if it doesn't exist
if not exist "logs" mkdir logs

REM Generate timestamped log file
set TIMESTAMP=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOGFILE=logs\cloudsync_%TIMESTAMP%.log

echo Starting AstroFiler Cloud Sync at %date% %time% > "%LOGFILE%"
echo ============================================== >> "%LOGFILE%"

REM Execute cloud sync with auto-confirm and verbose logging
"%PYTHON_VENV%" "%CLOUDSYNC_SCRIPT%" -y -v >> "%LOGFILE%" 2>&1

REM Check exit code and log result
if %ERRORLEVEL% EQU 0 (
    echo Cloud sync completed successfully at %date% %time% >> "%LOGFILE%"
    echo ============================================== >> "%LOGFILE%"
    exit /b 0
) else (
    echo Cloud sync failed with error code %ERRORLEVEL% at %date% %time% >> "%LOGFILE%"
    echo ============================================== >> "%LOGFILE%"
    exit /b %ERRORLEVEL%
)