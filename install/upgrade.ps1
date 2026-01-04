# AstroFiler Upgrade Script for Windows (PowerShell)
# Runs in its own console window (green on black) and upgrades the working copy.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    # Console colors: green text on black
    $Host.UI.RawUI.BackgroundColor = 'Black'
    $Host.UI.RawUI.ForegroundColor = 'Green'
    Clear-Host
} catch {
    # Ignore if host doesn't support color changes
}

function Show-DoneDialog([string]$message, [string]$title = 'AstroFiler') {
    try {
        Add-Type -AssemblyName PresentationFramework | Out-Null
        [System.Windows.MessageBox]::Show($message, $title, 'OK', 'Information') | Out-Null
    } catch {
        Write-Host $message
    }
}

function Show-ErrorDialog([string]$message, [string]$title = 'AstroFiler Upgrade Failed') {
    try {
        Add-Type -AssemblyName PresentationFramework | Out-Null
        [System.Windows.MessageBox]::Show($message, $title, 'OK', 'Error') | Out-Null
    } catch {
        Write-Host $message
    }
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "AstroFiler Upgrade" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Change to repo root (parent of this install folder)
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $RepoRoot

# Give the main app a moment to exit before pulling files.
Start-Sleep -Seconds 1

Write-Host "Working directory: $RepoRoot" -ForegroundColor Green
Write-Host "" 

# Pull latest code
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Host "Running: git pull" -ForegroundColor Green
    git pull
    Write-Host "" 
} else {
    throw "git was not found on PATH. Install Git for Windows or run upgrade manually."
}

# Choose python interpreter: prefer the bundled venv in this folder
$Python = $null
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = 'python'
} else {
    throw "Python was not found. Please run install\\install.ps1 first."
}

Write-Host "Using Python: $Python" -ForegroundColor Green
Write-Host "" 

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Green
& $Python -m pip install --upgrade pip
Write-Host "" 

# Install requirements
if (Test-Path (Join-Path $RepoRoot 'requirements.txt')) {
    Write-Host "Installing requirements.txt..." -ForegroundColor Green
    & $Python -m pip install -r (Join-Path $RepoRoot 'requirements.txt')
} else {
    throw "requirements.txt not found in $RepoRoot"
}

Write-Host "" 
Write-Host "Upgrade complete." -ForegroundColor Green

Show-DoneDialog "Astrofiler has been upgraded please run again"
exit 0

} catch {
    Write-Host "" 
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Show-ErrorDialog "Upgrade failed:`n`n$($_.Exception.Message)"
    exit 1
}
