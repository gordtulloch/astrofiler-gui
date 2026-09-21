# =============================================================================
# AstroFiler - Windows Task Scheduler Setup
# =============================================================================
# Creates Windows Scheduled Tasks for AstroFiler commands.
# Run this script once from an elevated (Administrator) PowerShell session.
#
# Usage:
#   .\schedule_tasks.ps1                      # Interactive mode - prompts for each task
#   .\schedule_tasks.ps1 -All                 # Register all tasks with defaults
#   .\schedule_tasks.ps1 -Unregister          # Remove all AstroFiler scheduled tasks
#   .\schedule_tasks.ps1 -ListTasks           # Show currently registered AstroFiler tasks
#
# Examples:
#   # Run Download every night at 2 AM, then SyncRepo, then CreateSessions
#   .\schedule_tasks.ps1 -All -DownloadTime "02:00" -SyncRepoTime "02:30" -CreateSessionsTime "03:00"
# =============================================================================

param(
    [switch]$All,
    [switch]$Interactive,
    [switch]$Unregister,
    [switch]$ListTasks,

    # Optional per-command time overrides (24-hour HH:mm format)
    [string]$DownloadTime        = "10:00",
    [string]$SyncRepoTime        = "10:30",
    [string]$RegisterExistingTime= "11:00",
    [string]$CreateSessionsTime  = "11:15",
    [string]$LinkSessionsTime    = "11:30",
    [string]$AutoCalibrationTime = "11:45",
    [string]$StackTime           = "12:00",
    [string]$CloudSyncTime       = "12:30",

    # Optional extra arguments appended to every python call
    [string]$ExtraArgs = "-v"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Resolve AstroFiler root (parent of the install folder)
# ---------------------------------------------------------------------------
$InstallDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$AstroRoot   = Split-Path -Parent $InstallDir
$PythonExe   = Join-Path $AstroRoot ".venv\Scripts\python.exe"
$CommandsDir = Join-Path $AstroRoot "commands"
$TaskFolder  = "\AstroFiler"   # Task Scheduler folder (keeps tasks organised)

if (-not (Test-Path $PythonExe)) {
    Write-Warning "Virtual-environment Python not found at: $PythonExe"
    Write-Warning "Falling back to system Python - make sure the correct interpreter is on PATH."
    $PythonExe = "python.exe"
}

# ---------------------------------------------------------------------------
# Task definitions
# Each entry:  Name | Script | DefaultTime | Description | ExtraCommandArgs
# ---------------------------------------------------------------------------
$TaskDefs = @(
    [pscustomobject]@{
        Name        = "AstroFiler-Download"
        Script      = "Download.py"
        DefaultTime = $DownloadTime
        Description = "Download new files from connected smart telescopes."
        CmdArgs     = ""
    },
    [pscustomobject]@{
        Name        = "AstroFiler-SyncRepo"
        Script      = "SyncRepo.py"
        DefaultTime = $SyncRepoTime
        Description = "Sync the repository database with files on disk."
        CmdArgs     = ""
    },
    [pscustomobject]@{
        Name        = "AstroFiler-RegisterExisting"
        Script      = "RegisterExisting.py"
        DefaultTime = $RegisterExistingTime
        Description = "Register existing FITS/XISF files that are not yet in the database."
        CmdArgs     = ""
    },
    [pscustomobject]@{
        Name        = "AstroFiler-CreateSessions"
        Script      = "CreateSessions.py"
        DefaultTime = $CreateSessionsTime
        Description = "Create imaging sessions from registered light frames."
        CmdArgs     = ""
    },
    [pscustomobject]@{
        Name        = "AstroFiler-LinkSessions"
        Script      = "LinkSessions.py"
        DefaultTime = $LinkSessionsTime
        Description = "Link sessions to calibration frames."
        CmdArgs     = ""
    },
    [pscustomobject]@{
        Name        = "AstroFiler-AutoCalibration"
        Script      = "AutoCalibration.py"
        DefaultTime = $AutoCalibrationTime
        Description = "Automatically apply calibration frames to light sessions."
        CmdArgs     = ""
    },
    [pscustomobject]@{
        Name        = "AstroFiler-Stack"
        Script      = "Stack.py"
        DefaultTime = $StackTime
        Description = "Stack light sessions that are ready for integration."
        CmdArgs     = "--unstacked"
    },
    [pscustomobject]@{
        Name        = "AstroFiler-CloudSync"
        Script      = "CloudSync.py"
        DefaultTime = $CloudSyncTime
        Description = "Sync stacked images to cloud storage."
        CmdArgs     = ""
    }
)

# ---------------------------------------------------------------------------
# Helper - ensure the Task Scheduler folder exists
# ---------------------------------------------------------------------------
function Initialize-TaskFolder {
    $ts = New-Object -ComObject Schedule.Service
    $ts.Connect()
    $root = $ts.GetFolder("\")
    try {
        $null = $ts.GetFolder($TaskFolder)
    } catch {
        $null = $root.CreateFolder("AstroFiler")
        Write-Host "  Created Task Scheduler folder: $TaskFolder" -ForegroundColor Cyan
    }
}

# ---------------------------------------------------------------------------
# Register a single task
# ---------------------------------------------------------------------------
function Register-AstroTask {
    param(
        [pscustomobject]$Def,
        [string]$RunTime    # HH:mm
    )

    $scriptPath = Join-Path $CommandsDir $Def.Script
    $cmdArgs = "$scriptPath $($Def.CmdArgs) $ExtraArgs".Trim()

    # Build trigger - daily at the specified time
    $trigger = New-ScheduledTaskTrigger -Daily -At $RunTime

    # Run as the current user; store credentials so it runs even when logged off
    $principal = New-ScheduledTaskPrincipal `
        -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
        -LogonType S4U `
        -RunLevel Highest

    # The action: call python with the script
    $action = New-ScheduledTaskAction `
        -Execute "`"$PythonExe`"" `
        -Argument $cmdArgs `
        -WorkingDirectory $AstroRoot

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable:$false `
        -MultipleInstances IgnoreNew

    $fullTaskPath = "$TaskFolder\$($Def.Name)"

    # Remove existing task with the same name first (idempotent)
    if (Get-ScheduledTask -TaskName $Def.Name -TaskPath "$TaskFolder\" -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Def.Name -TaskPath "$TaskFolder\" -Confirm:$false
        Write-Host "  Replaced existing task: $($Def.Name) ($fullTaskPath)" -ForegroundColor Yellow
    }

    Register-ScheduledTask `
        -TaskName  $Def.Name `
        -TaskPath  "$TaskFolder\" `
        -Trigger   $trigger `
        -Action    $action `
        -Principal $principal `
        -Settings  $settings `
        -Description $Def.Description | Out-Null

    Write-Host "  [OK] $($Def.Name)  ->  daily at $RunTime" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# List registered AstroFiler tasks
# ---------------------------------------------------------------------------
function Show-Tasks {
    $tasks = Get-ScheduledTask -TaskPath "$TaskFolder\" -ErrorAction SilentlyContinue
    if (-not $tasks) {
        Write-Host "No AstroFiler scheduled tasks found." -ForegroundColor Yellow
        return
    }
    Write-Host "`nRegistered AstroFiler Tasks:" -ForegroundColor Cyan
    foreach ($t in $tasks) {
        $info  = $t | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue
        $next  = if ($info.NextRunTime) { $info.NextRunTime.ToString("yyyy-MM-dd HH:mm") } else { "N/A" }
        $last  = if ($info.LastRunTime -and $info.LastRunTime -gt [datetime]"1900-01-01") { $info.LastRunTime.ToString("yyyy-MM-dd HH:mm") } else { "Never" }
        $state = $t.State
        Write-Host ("  {0,-35} State:{1,-10} Last:{2}  Next:{3}" -f $t.TaskName, $state, $last, $next)
    }
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Unregister all AstroFiler tasks
# ---------------------------------------------------------------------------
function Remove-AllTasks {
    $tasks = Get-ScheduledTask -TaskPath "$TaskFolder\" -ErrorAction SilentlyContinue
    if (-not $tasks) {
        Write-Host "No AstroFiler tasks to remove." -ForegroundColor Yellow
        return
    }
    foreach ($t in $tasks) {
        Unregister-ScheduledTask -TaskName $t.TaskName -TaskPath "$TaskFolder\" -Confirm:$false
        Write-Host "  Removed: $($t.TaskName)" -ForegroundColor Yellow
    }
    Write-Host "All AstroFiler scheduled tasks removed." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Interactive mode - ask which tasks to enable and at what time
# ---------------------------------------------------------------------------
function Start-Interactive {
    Write-Host "`n=== AstroFiler Task Scheduler Setup (Interactive) ===" -ForegroundColor Cyan
    Write-Host "Press Enter to accept the default time shown in [brackets], or type a new HH:mm time."
    Write-Host "Type 'n' to skip a task.`n"

    Initialize-TaskFolder

    foreach ($def in $TaskDefs) {
        $prompt = "  $($def.Name) [$($def.DefaultTime)] (n=skip): "
        $answer = Read-Host $prompt

        if ($answer -eq 'n') {
            Write-Host "  Skipped." -ForegroundColor DarkGray
            continue
        }

        $time = if ($answer -match '^\d{2}:\d{2}$') { $answer } else { $def.DefaultTime }
        Register-AstroTask -Def $def -RunTime $time
    }

    Write-Host "`nDone! Run with -ListTasks to verify." -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Require elevation for Register-ScheduledTask
$currentPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    if (-not ($ListTasks -or $Unregister)) {
        Write-Warning "This script requires Administrator privileges to create scheduled tasks."
        Write-Warning "Please re-run from an elevated PowerShell session."
        exit 1
    }
}

if ($ListTasks) {
    Show-Tasks
    exit 0
}

if ($Unregister) {
    Remove-AllTasks
    exit 0
}

if ($All) {
    Write-Host "`nRegistering all AstroFiler tasks..." -ForegroundColor Cyan
    Initialize-TaskFolder
    foreach ($def in $TaskDefs) {
        Register-AstroTask -Def $def -RunTime $def.DefaultTime
    }
    Write-Host "`nAll tasks registered. Run with -ListTasks to verify." -ForegroundColor Cyan
    exit 0
}

# Default: interactive
Start-Interactive
