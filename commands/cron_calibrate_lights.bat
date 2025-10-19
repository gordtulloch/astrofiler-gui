@echo off
REM ============================================================
REM AstroFiler Light Frame Calibration - Windows Automation
REM ============================================================
REM
REM This script performs automated light frame calibration using PySiril
REM Edit the paths below to match your installation
REM
REM Schedule with Windows Task Scheduler for regular processing
REM Recommended: Run after auto-calibration master creation
REM
REM Example schedules:
REM - Daily at 3 AM (after master creation at 2 AM)  
REM - After new observation sessions are created
REM - On-demand when new light frames need calibration
REM ============================================================

REM Configuration - EDIT THESE PATHS
set ASTROFILER_DIR=D:\Dropbox\Projects\astrofiler-gui-dev
set PYTHON_EXE=%ASTROFILER_DIR%\.venv\Scripts\python.exe
set SCRIPT_PATH=%ASTROFILER_DIR%\commands\calibrateLights.py
set LOG_DIR=%ASTROFILER_DIR%\logs
set TIMESTAMP=%date:~10,4%-%date:~4,2%-%date:~7,2%_%time:~0,2%-%time:~3,2%-%time:~6,2%

REM Clean timestamp (remove spaces and colons)
set TIMESTAMP=%TIMESTAMP: =0%
set TIMESTAMP=%TIMESTAMP::=-%

REM Ensure log directory exists
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Log file path
set LOG_FILE=%LOG_DIR%\calibrate_lights_%TIMESTAMP%.log

REM Change to project directory
cd /d "%ASTROFILER_DIR%"

echo ============================================================ > "%LOG_FILE%"
echo AstroFiler Light Calibration Automation >> "%LOG_FILE%"
echo Started: %date% %time% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

REM Check if Python executable exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python executable not found at %PYTHON_EXE% >> "%LOG_FILE%"
    echo Please check the PYTHON_EXE path in this script >> "%LOG_FILE%"
    exit /b 1
)

REM Check if script exists
if not exist "%SCRIPT_PATH%" (
    echo ERROR: calibrateLights.py not found at %SCRIPT_PATH% >> "%LOG_FILE%"
    echo Please check the SCRIPT_PATH in this script >> "%LOG_FILE%"
    exit /b 1
)

REM Parse command line arguments (allow overrides)
set OPERATION=%1
set SESSION_ID=%2
set OBJECT_NAME=%3

REM Default operation if not specified
if "%OPERATION%"=="" set OPERATION=auto

echo Operation: %OPERATION% >> "%LOG_FILE%"
if not "%SESSION_ID%"=="" echo Session ID: %SESSION_ID% >> "%LOG_FILE%"
if not "%OBJECT_NAME%"=="" echo Object Name: %OBJECT_NAME% >> "%LOG_FILE%"

REM Execute based on operation
if "%OPERATION%"=="auto" goto AUTO_CALIBRATE
if "%OPERATION%"=="session" goto SESSION_CALIBRATE  
if "%OPERATION%"=="object" goto OBJECT_CALIBRATE
if "%OPERATION%"=="quality" goto QUALITY_CHECK
if "%OPERATION%"=="help" goto SHOW_HELP
goto UNKNOWN_OPERATION

:AUTO_CALIBRATE
echo Performing automatic light calibration for recent sessions... >> "%LOG_FILE%"
"%PYTHON_EXE%" "%SCRIPT_PATH%" --verbose 2>&1 >> "%LOG_FILE%"
set ERROR_LEVEL=%ERRORLEVEL%
goto FINISH

:SESSION_CALIBRATE
if "%SESSION_ID%"=="" (
    echo ERROR: Session ID required for session operation >> "%LOG_FILE%"
    exit /b 1
)
echo Calibrating session %SESSION_ID%... >> "%LOG_FILE%"
"%PYTHON_EXE%" "%SCRIPT_PATH%" --session %SESSION_ID% --verbose 2>&1 >> "%LOG_FILE%"
set ERROR_LEVEL=%ERRORLEVEL%
goto FINISH

:OBJECT_CALIBRATE
if "%OBJECT_NAME%"=="" (
    echo ERROR: Object name required for object operation >> "%LOG_FILE%"
    exit /b 1
)
echo Calibrating object "%OBJECT_NAME%"... >> "%LOG_FILE%"
"%PYTHON_EXE%" "%SCRIPT_PATH%" --object "%OBJECT_NAME%" --verbose 2>&1 >> "%LOG_FILE%"
set ERROR_LEVEL=%ERRORLEVEL%
goto FINISH

:QUALITY_CHECK
echo Performing dry run calibration check... >> "%LOG_FILE%"
"%PYTHON_EXE%" "%SCRIPT_PATH%" --dry-run --verbose 2>&1 >> "%LOG_FILE%"
set ERROR_LEVEL=%ERRORLEVEL%
goto FINISH

:SHOW_HELP
echo Available operations: >> "%LOG_FILE%"
echo   auto          - Automatic calibration for recent sessions >> "%LOG_FILE%"
echo   session [ID]  - Calibrate specific session by ID >> "%LOG_FILE%"
echo   object [NAME] - Calibrate all sessions for specific object >> "%LOG_FILE%"
echo   quality       - Quality assessment only (dry-run) >> "%LOG_FILE%"
echo   help          - Show this help message >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"
echo Examples: >> "%LOG_FILE%"
echo   cron_calibrate_lights.bat auto >> "%LOG_FILE%"
echo   cron_calibrate_lights.bat session 123 >> "%LOG_FILE%"
echo   cron_calibrate_lights.bat object "M31" >> "%LOG_FILE%"
echo   cron_calibrate_lights.bat quality >> "%LOG_FILE%"
set ERROR_LEVEL=0
goto FINISH

:UNKNOWN_OPERATION
echo ERROR: Unknown operation "%OPERATION%" >> "%LOG_FILE%"
echo Use "help" to see available operations >> "%LOG_FILE%"
set ERROR_LEVEL=1
goto FINISH

:FINISH
echo ============================================================ >> "%LOG_FILE%"
if %ERROR_LEVEL%==0 (
    echo Light calibration completed successfully >> "%LOG_FILE%"
    echo Finished: %date% %time% >> "%LOG_FILE%"
) else (
    echo Light calibration failed with error level %ERROR_LEVEL% >> "%LOG_FILE%"
    echo Finished: %date% %time% >> "%LOG_FILE%"
    REM Create error flag file for monitoring
    echo %ERROR_LEVEL% > "%LOG_DIR%\calibrate_lights_error_%TIMESTAMP%.flag"
)
echo ============================================================ >> "%LOG_FILE%"

REM Cleanup old log files (keep last 30 days)
forfiles /p "%LOG_DIR%" /s /m calibrate_lights_*.log /d -30 /c "cmd /c del @path" 2>nul
forfiles /p "%LOG_DIR%" /s /m calibrate_lights_*.flag /d -30 /c "cmd /c del @path" 2>nul

exit /b %ERROR_LEVEL%