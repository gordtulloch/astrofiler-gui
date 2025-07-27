# AstroFiler Desktop Launcher for Windows (PowerShell)
# This script launches AstroFiler from any location

param(
    [switch]$NoWait
)

# Get the directory where this script is located and go to parent
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Change to the AstroFiler directory (parent of install folder)
Set-Location (Split-Path -Parent $ScriptDir)

# Check for updates from GitHub if this is a git repository
if (Test-Path ".git") {
    Write-Host "Checking for updates from GitHub..." -ForegroundColor Yellow
    Add-Content -Path "astrofiler.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Checking for updates from GitHub..."
    try {
        & git fetch origin main 2>$null
        $updateCount = & git rev-list HEAD..origin/main --count 2>$null
        if ($updateCount -and $updateCount -gt 0) {
            Write-Host "Updates available! Pulling latest changes..." -ForegroundColor Green
            Add-Content -Path "astrofiler.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Updates available! $updateCount commits behind. Pulling latest changes..."
            & git pull origin main
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Successfully updated to latest version." -ForegroundColor Green
                Add-Content -Path "astrofiler.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Successfully updated to latest version from GitHub"
            } else {
                Write-Host "Warning: Failed to update from GitHub. Continuing with current version." -ForegroundColor Yellow
                Add-Content -Path "astrofiler.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - WARNING - Failed to update from GitHub. Continuing with current version"
            }
        } else {
            Write-Host "Already up to date." -ForegroundColor Green
            Add-Content -Path "astrofiler.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Repository already up to date"
        }
    } catch {
        Write-Host "Note: Could not check for updates (git not available or not connected to internet)." -ForegroundColor Yellow
        Add-Content -Path "astrofiler.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Could not check for updates (git not available or not connected to internet)"
    }
    Write-Host
}

# Check if virtual environment exists
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Error: AstroFiler virtual environment not found." -ForegroundColor Red
    Write-Host "Please run install.ps1 first to set up AstroFiler." -ForegroundColor Yellow
    Write-Host
    if (-not $NoWait) {
        Read-Host "Press Enter to exit"
    }
    exit 1
}

Write-Host "Starting AstroFiler..." -ForegroundColor Green
Add-Content -Path "astrofiler.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - launch_astrofiler.ps1 - INFO - Starting AstroFiler application via launch script"

try {
    # Activate virtual environment
    & ".venv\Scripts\Activate.ps1"
    
    # Run AstroFiler
    python astrofiler.py
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host
        Write-Host "AstroFiler exited with an error." -ForegroundColor Red
        Write-Host "Error code: $LASTEXITCODE" -ForegroundColor Red
        if (-not $NoWait) {
            Read-Host "Press Enter to exit"
        }
    }
} catch {
    Write-Host "Error launching AstroFiler: $_" -ForegroundColor Red
    if (-not $NoWait) {
        Read-Host "Press Enter to exit"
    }
    exit 1
}
