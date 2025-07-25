@echo off
REM AstroFiler Installation Script for Windows
REM This script checks for Python, installs it if needed, creates a virtual environment,
REM and installs all required dependencies.

echo ========================================
echo AstroFiler Installation Script for Windows
echo ========================================
echo.

REM Change to parent directory (where astrofiler.py is located)
cd /d "%~dp0\.."

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    echo.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    echo After installing Python, run this script again.
    pause
    exit /b 1
)

REM Display Python version
echo Checking Python installation...
python --version
echo.

REM Check Python version (require 3.8+)
python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python 3.8 or higher is required.
    echo Please upgrade your Python installation.
    pause
    exit /b 1
)

echo Python version is compatible.
echo.

REM Check if virtual environment already exists
if exist ".venv" (
    echo Virtual environment already exists.
    echo Do you want to recreate it? (This will remove all installed packages)
    set /p choice="Enter Y to recreate, N to use existing: "
    if /i "%choice%"=="Y" (
        echo Removing existing virtual environment...
        rmdir /s /q .venv
    ) else (
        echo Using existing virtual environment.
        goto activate_venv
    )
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv .venv
if %errorlevel% neq 0 (
    echo Error: Failed to create virtual environment.
    echo Make sure you have the venv module installed.
    echo You can install it with: python -m pip install --user virtualenv
    pause
    exit /b 1
)

echo Virtual environment created successfully.
echo.

:activate_venv
REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Virtual environment activated.
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install requirements
echo Installing required packages...
if exist "requirements.txt" (
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Error: Failed to install some packages.
        echo Please check the error messages above.
        pause
        exit /b 1
    )
) else (
    echo Warning: requirements.txt not found.
    echo Installing packages manually...
    python -m pip install astropy peewee numpy matplotlib pytz PySide6
)

echo.
echo ========================================
echo Installation completed successfully!
echo ========================================
echo.
echo To run AstroFiler:
echo 1. Open Command Prompt in this directory
echo 2. Run: .venv\Scripts\activate.bat
echo 3. Run: python astrofiler.py
echo.
echo You can also use the run_astrofiler.bat script for convenience.
echo.

REM Create convenience run script
echo Creating run script...
(
echo @echo off
echo cd /d "%~dp0"
echo call .venv\Scripts\activate.bat
echo python astrofiler.py
echo pause
) > run_astrofiler.bat

echo run_astrofiler.bat created.
echo.

REM Create desktop launcher scripts
echo Creating desktop launcher scripts...
(
echo @echo off
echo cd /d "%~dp0"
echo call install\launch_astrofiler.bat
) > astrofiler_launcher.bat

echo Desktop launcher created: astrofiler_launcher.bat
echo.

REM Ask if user wants to create desktop shortcut
set /p desktop_shortcut="Do you want to create a desktop shortcut? (Y/n): "
if /i "%desktop_shortcut%"=="Y" goto create_shortcut
if /i "%desktop_shortcut%"=="" goto create_shortcut
goto skip_shortcut

:create_shortcut
echo Creating desktop shortcut...

REM Create VBScript to create shortcut
(
echo Set oWS = WScript.CreateObject("WScript.Shell"^)
echo sLinkFile = oWS.SpecialFolders("Desktop"^) ^& "\AstroFiler.lnk"
echo Set oLink = oWS.CreateShortcut(sLinkFile^)
echo oLink.TargetPath = "%CD%\astrofiler_launcher.bat"
echo oLink.WorkingDirectory = "%CD%"
echo oLink.Description = "AstroFiler - Astronomy File Management Tool"
echo oLink.IconLocation = "%CD%\astrofiler.ico"
echo oLink.Save
) > create_shortcut.vbs

cscript //nologo create_shortcut.vbs
del create_shortcut.vbs

if exist "%USERPROFILE%\Desktop\AstroFiler.lnk" (
    echo Desktop shortcut created successfully!
) else (
    echo Warning: Could not create desktop shortcut.
)

echo.

:skip_shortcut
pause
