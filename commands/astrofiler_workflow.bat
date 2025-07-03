@echo off
REM 
REM astrofiler_workflow.bat - Complete Windows automation workflow
REM
REM This script runs the complete AstroFiler workflow:
REM 1. Load repository (move files from source to repository)
REM 2. Create sessions (group files into light and calibration sessions)
REM
REM Can be run manually or scheduled with Task Scheduler
REM
REM Usage:
REM   astrofiler_workflow.bat           - Run complete workflow
REM   astrofiler_workflow.bat load      - Only load repository  
REM   astrofiler_workflow.bat sessions  - Only create sessions
REM   astrofiler_workflow.bat link      - Only link sessions
REM   astrofiler_workflow.bat manual    - Run with pause for manual execution

REM Configuration - EDIT THESE PATHS FOR YOUR INSTALLATION
set ASTROFILER_DIR=C:\path\to\astrofiler-gui
set PYTHON_VENV=%ASTROFILER_DIR%\.venv\Scripts\python.exe
set LOADREPO_SCRIPT=%ASTROFILER_DIR%\commands\LoadRepo.py
set CREATESESSIONS_SCRIPT=%ASTROFILER_DIR%\commands\CreateSessions.py
set LINKSESSIONS_SCRIPT=%ASTROFILER_DIR%\commands\LinkSessions.py
set LOG_FILE=%ASTROFILER_DIR%\astrofiler_workflow.log

REM Change to the astrofiler directory
cd /d "%ASTROFILER_DIR%"

REM Parse command line arguments
set RUN_LOAD=1
set RUN_SESSIONS=1
set RUN_LINK=1
set MANUAL_MODE=0

if "%1"=="load" (
    set RUN_SESSIONS=0
    set RUN_LINK=0
    goto :start
)
if "%1"=="sessions" (
    set RUN_LOAD=0
    set RUN_LINK=0
    goto :start
)
if "%1"=="link" (
    set RUN_LOAD=0
    set RUN_SESSIONS=0
    goto :start
)
if "%1"=="manual" (
    set MANUAL_MODE=1
    goto :start
)

:start
REM Log the start time
echo. >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
echo %date% %time%: Starting AstroFiler workflow >> "%LOG_FILE%"

if %RUN_LOAD%==1 (
    echo %date% %time%: Running repository load... >> "%LOG_FILE%"
    if %MANUAL_MODE%==1 echo Running repository load...
    
    "%PYTHON_VENV%" "%LOADREPO_SCRIPT%" -v >> "%LOG_FILE%" 2>&1
    set LOAD_EXIT=%ERRORLEVEL%
    
    echo %date% %time%: Repository load completed (exit code: %LOAD_EXIT%) >> "%LOG_FILE%"
    
    if %LOAD_EXIT% neq 0 (
        echo ERROR: Repository load failed with exit code %LOAD_EXIT% >> "%LOG_FILE%"
        if %MANUAL_MODE%==1 echo ERROR: Repository load failed!
        goto :error
    )
)

if %RUN_SESSIONS%==1 (
    echo %date% %time%: Running session creation... >> "%LOG_FILE%"
    if %MANUAL_MODE%==1 echo Running session creation...
    
    "%PYTHON_VENV%" "%CREATESESSIONS_SCRIPT%" -v >> "%LOG_FILE%" 2>&1
    set SESSIONS_EXIT=%ERRORLEVEL%
    
    echo %date% %time%: Session creation completed (exit code: %SESSIONS_EXIT%) >> "%LOG_FILE%"
    
    if %SESSIONS_EXIT% neq 0 (
        echo ERROR: Session creation failed with exit code %SESSIONS_EXIT% >> "%LOG_FILE%"
        if %MANUAL_MODE%==1 echo ERROR: Session creation failed!
        goto :error
    )
)

if %RUN_LINK%==1 (
    echo %date% %time%: Running session linking... >> "%LOG_FILE%"
    if %MANUAL_MODE%==1 echo Running session linking...
    
    "%PYTHON_VENV%" "%LINKSESSIONS_SCRIPT%" -v >> "%LOG_FILE%" 2>&1
    set LINK_EXIT=%ERRORLEVEL%
    
    echo %date% %time%: Session linking completed (exit code: %LINK_EXIT%) >> "%LOG_FILE%"
    
    if %LINK_EXIT% neq 0 (
        echo ERROR: Session linking failed with exit code %LINK_EXIT% >> "%LOG_FILE%"
        if %MANUAL_MODE%==1 echo ERROR: Session linking failed!
        goto :error
    )
)

REM Success
echo %date% %time%: AstroFiler workflow completed successfully >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

if %MANUAL_MODE%==1 (
    echo.
    echo AstroFiler workflow completed successfully!
    pause
)
exit /b 0

:error
echo %date% %time%: AstroFiler workflow completed with errors >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

if %MANUAL_MODE%==1 (
    echo.
    echo AstroFiler workflow completed with errors. Check the log file:
    echo %LOG_FILE%
    pause
)
exit /b 1
