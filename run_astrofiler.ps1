# AstroFiler Runner Script
Set-Location -Path $PSScriptRoot
& ".\.venv\Scripts\Activate.ps1"
python astrofiler.py
Read-Host "Press Enter to exit"
