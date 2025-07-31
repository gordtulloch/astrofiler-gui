@echo off
REM AstroFiler Desktop Launcher for Windows
REM This script launches AstroFiler from any location

REM Get the directory where this script is located and go to parent
set "SCRIPT_DIR=%~dp0"

REM Change to the AstroFiler directory (parent of install folder)
cd /d "%SCRIPT_DIR%\.."

REM Check for updates from GitHub if this is a git repository
if exist ".git" (
    echo Checking for updates from GitHub...
    echo %date% %time% - launch_astrofiler.bat - INFO - Checking for updates from GitHub... >> astrofiler.log
    git fetch origin main >nul 2>&1
    for /f %%i in ('git rev-list HEAD..origin/main --count 2^>nul') do set UPDATE_COUNT=%%i
    if not "%UPDATE_COUNT%"=="0" (
        echo Updates available! Pulling latest changes...
        echo %date% %time% - launch_astrofiler.bat - INFO - Updates available! %UPDATE_COUNT% commits behind. Pulling latest changes... >> astrofiler.log
        git pull origin main
        if errorlevel 1 (
            echo Warning: Failed to update from GitHub. Continuing with current version.
            echo %date% %time% - launch_astrofiler.bat - WARNING - Failed to update from GitHub. Continuing with current version >> astrofiler.log
        ) else (
            echo Successfully updated to latest version.
            echo %date% %time% - launch_astrofiler.bat - INFO - Successfully updated to latest version from GitHub >> astrofiler.log
            REM Run database migrations after successful update
            echo Running database migrations...
            echo %date% %time% - launch_astrofiler.bat - INFO - Running database migrations after update >> astrofiler.log
            if exist ".venv\Scripts\python.exe" (
                .venv\Scripts\python.exe migrate.py run
                if errorlevel 1 (
                    echo Warning: Database migration failed. AstroFiler may not function correctly.
                    echo %date% %time% - launch_astrofiler.bat - WARNING - Database migration failed after update >> astrofiler.log
                ) else (
                    echo Database migrations completed successfully.
                    echo %date% %time% - launch_astrofiler.bat - INFO - Database migrations completed successfully >> astrofiler.log
                )
            )
        )
    ) else (
        echo Already up to date.
        echo %date% %time% - launch_astrofiler.bat - INFO - Repository already up to date >> astrofiler.log
    )
    echo.
)

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Error: AstroFiler virtual environment not found.
    echo Please run install.bat first to set up AstroFiler.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment and run AstroFiler
echo Starting AstroFiler...
echo %date% %time% - launch_astrofiler.bat - INFO - Starting AstroFiler application via launch script >> astrofiler.log
call ".venv\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo Error: Failed to activate virtual environment.
    echo %date% %time% - launch_astrofiler.bat - ERROR - Failed to activate virtual environment >> astrofiler.log
    pause
    exit /b 1
)

REM Run AstroFiler
python astrofiler.py

REM If AstroFiler exits with an error, show the error
if %errorlevel% neq 0 (
    echo.
    echo AstroFiler exited with an error.
    echo Error code: %errorlevel%
    pause
)
