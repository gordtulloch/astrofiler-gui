# AstroFiler Installation Scripts

This folder contains all the installation and launcher scripts for AstroFiler across different platforms.

## Installation Scripts

### Windows
- `install.bat` - Command Prompt installation script
- `install.ps1` - PowerShell installation script (recommended)

### Linux
- `install.sh` - Bash installation script for Linux distributions

### macOS
- `install_macos.sh` - Bash installation script optimized for macOS

## Launcher Scripts

These scripts are created during installation and are used to start AstroFiler:

### Windows
- `launch_astrofiler.bat` - Command Prompt launcher
- `launch_astrofiler.ps1` - PowerShell launcher

### Linux
- `launch_astrofiler.sh` - Bash launcher for Linux

### macOS
- `launch_astrofiler_macos.sh` - Bash launcher optimized for macOS with native dialogs

### Auto-Update Feature
All launcher scripts include automatic update checking:
- Checks for updates from GitHub on each startup (if git repository)
- Automatically pulls and applies updates from the main branch
- Gracefully handles cases where git is unavailable or offline
- Continues with current version if update fails

## Desktop Integration

- `astrofiler.desktop` - Linux desktop file template for application menu integration

## Usage

1. Choose the appropriate installation script for your platform
2. Run the installation script from the parent directory (not from within this folder)
3. The script will create the virtual environment, install dependencies, and set up desktop integration
4. Use the generated launcher scripts or desktop shortcuts to run AstroFiler

## Notes

- All scripts are designed to be run from the main AstroFiler directory
- The installation scripts automatically handle path adjustments
- Desktop shortcuts and application menu entries are created during installation
- The virtual environment and main application files remain in the parent directory

For detailed installation instructions, see the main INSTALL.md file in the parent directory.
