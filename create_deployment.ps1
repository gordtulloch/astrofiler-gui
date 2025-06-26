# AstroFiler Deployment Script
# This script helps package the application for distribution

# Create a deployment folder
$deploymentFolder = "AstroFiler_Deployment"
if (Test-Path $deploymentFolder) {
    Remove-Item -Recurse -Force $deploymentFolder
}
New-Item -ItemType Directory -Path $deploymentFolder

# Copy the entire application folder (onedir approach)
Copy-Item "dist\AstroFiler\*" -Destination $deploymentFolder -Recurse

# Copy essential files to the deployment folder root
Copy-Item "astrofiler.ini" -Destination $deploymentFolder -ErrorAction SilentlyContinue
Copy-Item "css" -Destination $deploymentFolder -Recurse -ErrorAction SilentlyContinue
Copy-Item "images" -Destination $deploymentFolder -Recurse -ErrorAction SilentlyContinue

# Create README for deployment
$readmeContent = @"
AstroFiler - Astronomy Image Management Tool
==========================================

Installation:
1. Extract all files to a folder of your choice
2. Run AstroFiler.exe

Configuration:
- Edit astrofiler.ini to set your source and repository folders
- The application will create an SQLite database (astrofiler.db) on first run

Requirements:
- Windows 10/11 (64-bit)
- No additional software installation required

Support Files:
- AstroFiler.exe: Main application executable
- _internal/: Required application files (do not delete)
- astrofiler.ini: Configuration file
- css/: Application stylesheets
- images/: Application images and icons
- astrofiler.db: Database (created automatically)
- astrofiler.log: Application logs (created automatically)

Note: Keep all files together. The _internal folder contains required 
libraries and must remain in the same directory as AstroFiler.exe.

For support, visit: [Your project repository or contact]
"@

Set-Content -Path "$deploymentFolder\README.txt" -Value $readmeContent

Write-Host "Deployment package created in: $deploymentFolder"
Write-Host "Contents:"
Get-ChildItem $deploymentFolder -Recurse | Where-Object { $_.PSIsContainer -eq $false } | ForEach-Object { 
    $relativePath = $_.FullName.Replace((Get-Location).Path + '\' + $deploymentFolder + '\', '')
    Write-Host "  $relativePath"
}
