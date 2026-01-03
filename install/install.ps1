# AstroFiler Installation Script for Windows (PowerShell)
# This script checks for Python, helps install it if needed, creates a virtual environment,
# and installs all required dependencies.

param(
    [switch]$Force,
    [switch]$Quiet
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AstroFiler Installation Script for Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host

# Change to parent directory (where astrofiler.py is located)
Set-Location (Split-Path -Parent $PSScriptRoot)

# Function to test if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Function to check if Python is installed
function Test-PythonInstalled {
    try {
        $pythonVersion = python --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Found Python: $pythonVersion" -ForegroundColor Green
            return $true
        }
    } catch {
        return $false
    }
    return $false
}

# Function to check Python version
function Test-PythonVersion {
    try {
        python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

# Function to download and install Python
function Install-Python {
    Write-Host "Python is not installed or not in PATH." -ForegroundColor Yellow
    Write-Host
    
    $installChoice = "Y"
    if (-not $Quiet) {
        $installChoice = Read-Host "Do you want to download and install Python? [Y/n]"
    }
    
    if ($installChoice -match "^[Yy].*" -or $installChoice -eq "") {
        Write-Host "Downloading Python installer..." -ForegroundColor Yellow
        
        # Get latest Python 3.11 installer URL
        $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $installerPath = "$env:TEMP\python-installer.exe"
        
        try {
            Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath -UseBasicParsing
            Write-Host "Download completed." -ForegroundColor Green
            
            Write-Host "Installing Python..." -ForegroundColor Yellow
            Write-Host "Note: This will install Python for all users and add it to PATH." -ForegroundColor Yellow
            
            # Install Python silently with all users and add to PATH
            $arguments = "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0"
            $process = Start-Process -FilePath $installerPath -ArgumentList $arguments -Wait -PassThru
            
            if ($process.ExitCode -eq 0) {
                Write-Host "Python installed successfully!" -ForegroundColor Green
                Write-Host "Please restart your PowerShell session and run this script again." -ForegroundColor Yellow
                
                # Remove installer
                Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
                
                Read-Host "Press Enter to exit"
                exit 0
            } else {
                Write-Host "Python installation failed with exit code: $($process.ExitCode)" -ForegroundColor Red
                throw "Installation failed"
            }
        } catch {
            Write-Host "Error downloading or installing Python: $_" -ForegroundColor Red
            Write-Host
            Write-Host "Please install Python manually from: https://www.python.org/downloads/" -ForegroundColor Yellow
            Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
            Read-Host "Press Enter to exit"
            exit 1
        }
    } else {
        Write-Host "Please install Python manually from: https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Main installation process
Write-Host "Checking Python installation..." -ForegroundColor Yellow

if (-not (Test-PythonInstalled)) {
    Install-Python
}

if (-not (Test-PythonVersion)) {
    Write-Host "Error: Python 3.8 or higher is required." -ForegroundColor Red
    Write-Host "Please upgrade your Python installation." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Python version is compatible." -ForegroundColor Green
Write-Host

# Check if virtual environment already exists
if (Test-Path ".venv") {
    Write-Host "Virtual environment already exists." -ForegroundColor Yellow
    
    if ($Force) {
        $recreate = "Y"
    } elseif ($Quiet) {
        $recreate = "N"
    } else {
        $recreate = Read-Host "Do you want to recreate it? (This will remove all installed packages) [y/N]"
    }
    
    if ($recreate -match "^[Yy].*") {
        Write-Host "Removing existing virtual environment..." -ForegroundColor Yellow
        Remove-Item ".venv" -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "Using existing virtual environment." -ForegroundColor Green
    }
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    
    try {
        python -m venv .venv
        Write-Host "Virtual environment created successfully." -ForegroundColor Green
    } catch {
        Write-Host "Error: Failed to create virtual environment." -ForegroundColor Red
        Write-Host "Make sure you have the venv module installed." -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }
}

Write-Host

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow

try {
    & ".venv\Scripts\Activate.ps1"
    Write-Host "Virtual environment activated." -ForegroundColor Green
} catch {
    Write-Host "Error: Failed to activate virtual environment." -ForegroundColor Red
    Write-Host "Trying alternative activation method..." -ForegroundColor Yellow
    
    # Try batch file activation
    cmd /c ".venv\Scripts\activate.bat && python -m pip --version" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Could not activate virtual environment." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

Write-Host

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

Write-Host

# Install requirements
Write-Host "Installing required packages..." -ForegroundColor Yellow

if (Test-Path "requirements.txt") {
    try {
        python -m pip install -r requirements.txt
        Write-Host "Core packages installed successfully!" -ForegroundColor Green
    } catch {
        Write-Host "Error: Failed to install some packages." -ForegroundColor Red
        Write-Host "Please check the error messages above." -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "Warning: requirements.txt not found." -ForegroundColor Yellow
    Write-Host "Installing packages manually..." -ForegroundColor Yellow
    
    $packages = @("astropy", "peewee", "numpy", "matplotlib", "pytz", "PySide6")
    foreach ($package in $packages) {
        Write-Host "Installing $package..." -ForegroundColor Cyan
        python -m pip install $package
    }
}

Write-Host
Write-Host "========================================" -ForegroundColor Green
Write-Host "Installation completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host
Write-Host "To run AstroFiler:" -ForegroundColor Cyan
Write-Host "1. Open PowerShell in this directory" -ForegroundColor White
Write-Host "2. Run: .venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "3. Run: python astrofiler.py" -ForegroundColor White
Write-Host
Write-Host "You can also use the run_astrofiler.ps1 script for convenience." -ForegroundColor Cyan
Write-Host

# Create convenience run script (PowerShell)
Write-Host "Creating run scripts..." -ForegroundColor Yellow

# PowerShell run script
$psScript = @"
# AstroFiler Runner Script
Set-Location -Path `$PSScriptRoot
& ".\`.venv\Scripts\Activate.ps1"
python astrofiler.py
Read-Host "Press Enter to exit"
"@

$psScript | Out-File -FilePath "run_astrofiler.ps1" -Encoding UTF8

# Batch run script for compatibility
$batScript = @"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python astrofiler.py
pause
"@

$batScript | Out-File -FilePath "run_astrofiler.bat" -Encoding ASCII

# Create custom launch script based on auto-update preference
Write-Host "Creating launch script..." -ForegroundColor Yellow
$autoUpdateEnabled = ($enableAutoUpdate -match "^[Yy].*" -or $enableAutoUpdate -eq "")

$launchScript = @"
# AstroFiler Desktop Launcher for Windows (PowerShell)
# This script launches AstroFiler from any location

param(
    [switch]`$NoWait
)

# Get the directory where this script is located and go to parent
`$ScriptDir = Split-Path -Parent `$MyInvocation.MyCommand.Path

# Change to the AstroFiler directory (parent of install folder)
Set-Location (Split-Path -Parent `$ScriptDir)
"@

if ($autoUpdateEnabled) {
    $launchScript += @"

# Check for updates from GitHub if this is a git repository
if (Test-Path ".git") {
    Write-Host "Checking for updates from GitHub..." -ForegroundColor Yellow
    Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Checking for updates from GitHub..."
    try {
        & git fetch origin main 2>`$null
        `$updateCount = & git rev-list HEAD..origin/main --count 2>`$null
        if (`$updateCount -and `$updateCount -gt 0) {
            Write-Host "Updates available! Pulling latest changes..." -ForegroundColor Green
            Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Updates available! `$updateCount commits behind. Pulling latest changes..."
            & git fetch origin
            & git reset --hard origin/main
            if (`$LASTEXITCODE -eq 0) {
                Write-Host "Successfully updated to latest version." -ForegroundColor Green
                Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Successfully updated to latest version from GitHub"
                # Run database migrations after successful update
                Write-Host "Running database migrations..." -ForegroundColor Yellow
                Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Running database migrations after update"
                if (Test-Path ".venv\Scripts\python.exe") {
                    try {
                        & ".venv\Scripts\python.exe" migrate.py run
                        if (`$LASTEXITCODE -eq 0) {
                            Write-Host "Database migrations completed successfully." -ForegroundColor Green
                            Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Database migrations completed successfully"
                        } else {
                            Write-Host "Warning: Database migration failed. AstroFiler may not function correctly." -ForegroundColor Yellow
                            Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - WARNING - Database migration failed after update"
                        }
                    } catch {
                        Write-Host "Warning: Error running database migrations: `$_" -ForegroundColor Yellow
                        Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - WARNING - Error running database migrations: `$_"
                    }
                }
            } else {
                Write-Host "Warning: Failed to update from GitHub. Continuing with current version." -ForegroundColor Yellow
                Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - WARNING - Failed to update from GitHub. Continuing with current version"
            }
        } else {
            Write-Host "Already up to date." -ForegroundColor Green
            Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Repository already up to date"
        }
    } catch {
        Write-Host "Note: Could not check for updates (git not available or not connected to internet)." -ForegroundColor Yellow
        Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Could not check for updates (git not available or not connected to internet)"
    }
    Write-Host
}
"@
}

$launchScript += @"

# Check if virtual environment exists
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Error: AstroFiler virtual environment not found." -ForegroundColor Red
    Write-Host "Please run install.ps1 first to set up AstroFiler." -ForegroundColor Yellow
    Write-Host
    if (-not `$NoWait) {
        Read-Host "Press Enter to exit"
    }
    exit 1
}

Write-Host "Starting AstroFiler..." -ForegroundColor Green
Add-Content -Path "astrofiler.log" -Value "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Starting AstroFiler application via launch script"

try {
    # Activate virtual environment
    & ".venv\Scripts\Activate.ps1"
    
    # Run AstroFiler
    python astrofiler.py
    
    if (`$LASTEXITCODE -ne 0) {
        Write-Host
        Write-Host "AstroFiler exited with an error." -ForegroundColor Red
        Write-Host "Error code: `$LASTEXITCODE" -ForegroundColor Red
        if (-not `$NoWait) {
            Read-Host "Press Enter to exit"
        }
    }
} catch {
    Write-Host "Error launching AstroFiler: `$_" -ForegroundColor Red
    if (-not `$NoWait) {
        Read-Host "Press Enter to exit"
    }
    exit 1
}
"@

$launchScript | Out-File -FilePath "install\launch_astrofiler.ps1" -Encoding UTF8

# Create batch file version of the launcher
$launchBat = @"
@echo off
cd /d "%~dp0\.."
"@

if ($autoUpdateEnabled) {
    $launchBat += @"

REM Check for updates from GitHub if this is a git repository
if exist ".git" (
    echo Checking for updates from GitHub...
    echo %date% %time% - launch_astrofiler.bat - INFO - Checking for updates from GitHub... >> astrofiler.log
    git fetch origin main >nul 2>&1
    if not errorlevel 1 (
        for /f %%i in ('git rev-list HEAD..origin/main --count 2^>nul') do set UPDATE_COUNT=%%i
        if not "!UPDATE_COUNT!"=="0" (
            if not "!UPDATE_COUNT!"=="" (
                echo Updates available! Pulling latest changes...
                echo %date% %time% - launch_astrofiler.bat - INFO - Updates available. Pulling latest changes... >> astrofiler.log
                git fetch origin && git reset --hard origin/main
                if not errorlevel 1 (
                    echo Successfully updated to latest version.
                    echo %date% %time% - launch_astrofiler.bat - INFO - Successfully updated to latest version from GitHub >> astrofiler.log
                    echo Running database migrations...
                    echo %date% %time% - launch_astrofiler.bat - INFO - Running database migrations after update >> astrofiler.log
                    if exist ".venv\Scripts\python.exe" (
                        .venv\Scripts\python.exe migrate.py run
                        if not errorlevel 1 (
                            echo Database migrations completed successfully.
                            echo %date% %time% - launch_astrofiler.bat - INFO - Database migrations completed successfully >> astrofiler.log
                        ) else (
                            echo Warning: Database migration failed. AstroFiler may not function correctly.
                            echo %date% %time% - launch_astrofiler.bat - WARNING - Database migration failed after update >> astrofiler.log
                        )
                    )
                ) else (
                    echo Warning: Failed to update from GitHub. Continuing with current version.
                    echo %date% %time% - launch_astrofiler.bat - WARNING - Failed to update from GitHub. Continuing with current version >> astrofiler.log
                )
            )
        ) else (
            echo Already up to date.
            echo %date% %time% - launch_astrofiler.bat - INFO - Repository already up to date >> astrofiler.log
        )
    ) else (
        echo Note: Could not check for updates (git not available or not connected to internet^).
        echo %date% %time% - launch_astrofiler.bat - INFO - Could not check for updates (git not available or not connected to internet^) >> astrofiler.log
    )
    echo.
)
"@
}

$launchBat += @"

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Error: AstroFiler virtual environment not found.
    echo Please run install.ps1 first to set up AstroFiler.
    echo.
    pause
    exit /b 1
)

echo Starting AstroFiler...
echo %date% %time% - launch_astrofiler.bat - INFO - Starting AstroFiler application via launch script >> astrofiler.log

REM Activate virtual environment and run AstroFiler
call .venv\Scripts\activate.bat
python astrofiler.py

if errorlevel 1 (
    echo.
    echo AstroFiler exited with an error.
    pause
)
"@

$launchBat | Out-File -FilePath "install\launch_astrofiler.bat" -Encoding ASCII

Write-Host "Run scripts created:" -ForegroundColor Green
Write-Host "  - run_astrofiler.ps1 (PowerShell)" -ForegroundColor White
Write-Host "  - run_astrofiler.bat (Command Prompt)" -ForegroundColor White
if ($autoUpdateEnabled) {
    Write-Host "  - launch_astrofiler.ps1 (with auto-updates)" -ForegroundColor White
    Write-Host "  - launch_astrofiler.bat (with auto-updates)" -ForegroundColor White
} else {
    Write-Host "  - launch_astrofiler.ps1 (without auto-updates)" -ForegroundColor White
    Write-Host "  - launch_astrofiler.bat (without auto-updates)" -ForegroundColor White
}
Write-Host

# Ask if user wants automatic updates
$enableAutoUpdate = "Y"
if (-not $Quiet) {
    $enableAutoUpdate = Read-Host "Do you want automatic updates? (Updates will be checked on each launch) [Y/n]"
}

# Ask if user wants to create desktop shortcut
$createShortcut = "Y"
if (-not $Quiet) {
    $createShortcut = Read-Host "Do you want to create a desktop shortcut? [Y/n]"
}

if ($createShortcut -match "^[Yy].*" -or $createShortcut -eq "") {
    Write-Host "Creating desktop shortcut..." -ForegroundColor Yellow
    
    try {
        $WshShell = New-Object -comObject WScript.Shell
        $DesktopPath = $WshShell.SpecialFolders("Desktop")
        $CurrentPath = $PWD.Path
        $Shortcut = $WshShell.CreateShortcut("$DesktopPath\AstroFiler.lnk")
        $Shortcut.TargetPath = "$CurrentPath\install\launch_astrofiler.bat"
        $Shortcut.WorkingDirectory = $CurrentPath
        $Shortcut.Description = "AstroFiler - Astronomy File Management Tool"
        if (Test-Path "astrofiler.ico") {
            $Shortcut.IconLocation = "$CurrentPath\astrofiler.ico"
        }
        $Shortcut.Save()
        
        Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
    } catch {
        Write-Host "Warning: Could not create desktop shortcut: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping desktop shortcut creation." -ForegroundColor Yellow
}

Write-Host

if (-not $Quiet) {
    Read-Host "Press Enter to exit"
}
