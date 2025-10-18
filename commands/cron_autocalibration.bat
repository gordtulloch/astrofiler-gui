@echo off
REM cron_autocalibration.bat - Windows batch script for scheduled auto-calibration
REM 
REM This script runs the AutoCalibration.py tool on a schedule using Windows Task Scheduler.
REM It includes error handling, logging, and notification capabilities.
REM
REM Usage:
REM   cron_autocalibration.bat [operation] [options]
REM
REM Examples:
REM   cron_autocalibration.bat                    # Run complete workflow
REM   cron_autocalibration.bat masters            # Create masters only
REM   cron_autocalibration.bat analyze            # Analyze opportunities only
REM
REM Setup for Task Scheduler:
REM   1. Open Task Scheduler (taskschd.msc)
REM   2. Create Basic Task
REM   3. Set trigger (daily, weekly, etc.)
REM   4. Action: Start a program
REM   5. Program: Full path to this batch file
REM   6. Start in: AstroFiler project directory

setlocal enabledelayedexpansion

REM Configuration
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
set PYTHON_ENV=%PROJECT_DIR%\.venv\Scripts\python.exe
set AUTOCALIBRATION_SCRIPT=%PROJECT_DIR%\commands\AutoCalibration.py
set LOG_DIR=%PROJECT_DIR%\logs
set TIMESTAMP=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOG_FILE=%LOG_DIR%\autocalibration_%TIMESTAMP%.log

REM Create logs directory if it doesn't exist
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ================================================================ >> "%LOG_FILE%"
echo AstroFiler Auto-Calibration Scheduled Run >> "%LOG_FILE%"
echo Started: %date% %time% >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"

REM Check if Python environment exists
if not exist "%PYTHON_ENV%" (
    echo ERROR: Python environment not found: %PYTHON_ENV% >> "%LOG_FILE%"
    echo Please ensure AstroFiler is properly installed. >> "%LOG_FILE%"
    exit /b 1
)

REM Check if AutoCalibration script exists
if not exist "%AUTOCALIBRATION_SCRIPT%" (
    echo ERROR: AutoCalibration script not found: %AUTOCALIBRATION_SCRIPT% >> "%LOG_FILE%"
    exit /b 1
)

REM Change to project directory
cd /d "%PROJECT_DIR%"

REM Build command with parameters
set OPERATION=%1
if "%OPERATION%"=="" set OPERATION=all

set PYTHON_CMD="%PYTHON_ENV%" "%AUTOCALIBRATION_SCRIPT%" -o %OPERATION% -v --log-file "%LOG_FILE%"

REM Add additional parameters if provided
shift
:param_loop
if "%1"=="" goto run_command
set PYTHON_CMD=%PYTHON_CMD% %1
shift
goto param_loop

:run_command
echo Running: %PYTHON_CMD% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Execute the Python script
%PYTHON_CMD%
set EXIT_CODE=%ERRORLEVEL%

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo Completed: %date% %time% >> "%LOG_FILE%"
echo Exit code: %EXIT_CODE% >> "%LOG_FILE%"

if %EXIT_CODE%==0 (
    echo Status: SUCCESS >> "%LOG_FILE%"
) else (
    echo Status: FAILED >> "%LOG_FILE%"
)

echo ================================================================ >> "%LOG_FILE%"

REM Optional: Send notification email or create alert file on failure
if %EXIT_CODE% neq 0 (
    echo Auto-calibration failed at %date% %time% > "%PROJECT_DIR%\autocalibration_error.flag"
)

exit /b %EXIT_CODE%