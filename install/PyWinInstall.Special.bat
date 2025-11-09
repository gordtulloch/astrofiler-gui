@echo off
REM AstroFiler Special Installation Script for PyWinInstall
REM This script handles pysiril installation for Windows SETUP.EXE users
REM Called automatically by PyWinInstall at the end of the main installation

echo.
echo ========================================
echo AstroFiler Special Setup - pysiril
echo ========================================
echo.

REM Change to the installation directory (parent of install folder)
cd /d "%~dp0\.."

REM Check if we're in the right directory
if not exist "astrofiler.py" (
    echo Error: Could not find astrofiler.py in the expected location.
    echo Current directory: %CD%
    echo Script directory: %~dp0
    echo.
    echo This script should be run from the AstroFiler installation directory.
    pause
    exit /b 1
)

echo Installing pysiril from wheel file...
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Error: AstroFiler virtual environment not found.
    echo The main installation may have failed.
    echo Please run the full installation again.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment.
    echo The main installation may have failed.
    pause
    exit /b 1
)

echo Virtual environment activated successfully.
echo.

REM Find pysiril wheel file
echo Looking for pysiril wheel file...
for %%f in (pysiril-*.whl) do (
    set PYSIRIL_WHEEL=%%f
    goto found_wheel
)

REM No wheel file found - attempt to download
echo No pysiril wheel file found. Attempting to download...
echo.

REM Try to download the latest pysiril wheel file
echo Downloading latest pysiril wheel from GitLab...
set DOWNLOAD_URL=https://gitlab.com/free-astro/pysiril/-/jobs/artifacts/main/download?job=build
set TEMP_ZIP=%TEMP%\pysiril_artifacts.zip
set TEMP_DIR=%TEMP%\pysiril_extract

REM Create temporary directory
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

REM Download artifacts using PowerShell
powershell -Command "& {try { Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%TEMP_ZIP%' -UseBasicParsing -ErrorAction Stop; Write-Host 'Download completed successfully.' } catch { Write-Host 'Download failed:' $_.Exception.Message; exit 1 }}"
if errorlevel 1 (
    echo.
    echo Failed to download pysiril artifacts.
    echo Trying alternative method...
    goto try_pip_install
)

REM Extract the zip file using PowerShell
echo Extracting wheel file...
powershell -Command "& {try { Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP_DIR%' -Force; Write-Host 'Extraction completed.' } catch { Write-Host 'Extraction failed:' $_.Exception.Message; exit 1 }}"
if errorlevel 1 (
    echo Failed to extract artifacts.
    goto try_pip_install
)

REM Find the wheel file in extracted contents
for /r "%TEMP_DIR%" %%f in (pysiril-*.whl) do (
    echo Found wheel file: %%~nxf
    copy "%%f" "%CD%\%%~nxf" >nul
    set PYSIRIL_WHEEL=%%~nxf
    goto cleanup_and_install
)

echo No wheel file found in downloaded artifacts.
goto try_pip_install

:cleanup_and_install
REM Cleanup temporary files
if exist "%TEMP_ZIP%" del "%TEMP_ZIP%"
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
goto found_wheel

:try_pip_install
REM Cleanup temporary files
if exist "%TEMP_ZIP%" del "%TEMP_ZIP%"
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"

echo.
echo Direct download failed. Trying pip install from source...
python -m pip install git+https://gitlab.com/free-astro/pysiril.git --quiet
if errorlevel 1 (
    echo.
    echo Warning: Failed to install pysiril automatically.
    echo.
    echo pysiril is required for advanced image processing features.
    echo AstroFiler will still work without pysiril, but some features may be limited.
    echo.
    echo You can try installing manually later with:
    echo python -m pip install git+https://gitlab.com/free-astro/pysiril.git
    echo.
    pause
    goto end
) else (
    echo.
    echo pysiril installed successfully from source!
    goto verify_installation
)

:found_wheel
echo Found pysiril wheel: %PYSIRIL_WHEEL%
echo.

REM Install pysiril from wheel file
echo Installing pysiril...
python -m pip install "%PYSIRIL_WHEEL%" --force-reinstall --quiet
if errorlevel 1 (
    echo.
    echo Warning: Failed to install pysiril from wheel file.
    echo.
    echo This may be due to:
    echo - Missing dependencies
    echo - Incompatible wheel file
    echo - Network connectivity issues
    echo.
    echo You can try installing manually later with:
    echo python -m pip install "%PYSIRIL_WHEEL%" --force-reinstall
    echo.
    echo AstroFiler will still work without pysiril, but some features may be limited.
    pause
    goto end
)

echo.
echo pysiril installed successfully!
echo.

:verify_installation
REM Verify installation
echo Verifying pysiril installation...
python -c "import pysiril; print('pysiril version:', pysiril.__version__)" 2>nul
if errorlevel 1 (
    echo Warning: pysiril installation verification failed.
    echo The module may not have installed correctly.
) else (
    echo pysiril installation verified successfully.
)

echo.
echo ========================================
echo Special Setup Completed
echo ========================================
echo.
echo pysiril installation process finished.
echo AstroFiler is now ready to use with advanced image processing capabilities.
echo.

:end
REM Deactivate virtual environment
if defined VIRTUAL_ENV (
    deactivate
)

echo Press any key to continue...
pause >nul