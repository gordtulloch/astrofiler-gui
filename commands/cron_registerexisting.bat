@echo off
REM AstroFiler Register Existing Files - Windows Batch Script
REM Convenience script to run the existing file registration command

cd /d "%~dp0\.."
python commands\RegisterExisting.py %*

if errorlevel 1 (
    echo.
    echo Registration failed with error code %errorlevel%
    pause
) else (
    echo.
    echo Registration completed successfully
)