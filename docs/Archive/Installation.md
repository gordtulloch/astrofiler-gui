# AstroFiler Installation Guide

AstroFiler is a Python-based astronomy file management tool. This guide provides installation scripts for Windows, Linux, and macOS that automatically handle Python installation, virtual environment setup, and dependency installation. Users are given the option of automatically updating the program every time it is run or doing manual updates.

## Quick Start

### Windows

**Option 1: PowerShell (Recommended)**
```powershell
# Right-click PowerShell and "Run as Administrator" (optional but recommended)
.\install\install.ps1
```

**Option 2: Command Prompt**
```cmd
install\install.bat
```

**Option 3: SETUP.exe**
In the Releases section of the Astrofiler Github site download SETUP.ZIP, decompress, and run SETUP.EXE. This program will do a complete install.

### Linux
```bash
chmod +x install/install.sh
./install/install.sh
```

### macOS
```bash
chmod +x install/install_macos.sh
./install/install_macos.sh
```

## What the Installation Scripts Do

1. **Check for Python**: Verify that Python 3.8+ is installed
2. **Install Python**: If not found, help install Python using:
   - Windows: Download and install from python.org
   - Linux: Use system package manager (apt, yum, dnf, pacman, zypper)
   - macOS: Use Homebrew
3. **Create Virtual Environment**: Set up an isolated Python environment
4. **Install Dependencies**: Install all required packages from requirements.txt
5. **Create Run Scripts**: Generate convenient scripts to launch AstroFiler
6. **Create Desktop Integration**: 
   - Windows: Desktop shortcut (.lnk file)
   - Linux: Desktop file and application menu entry
   - macOS: App bundle and optional desktop alias

All installation scripts are located in the `install/` folder for better organization.

## System Requirements

- **Python**: 3.8 or higher
- **Operating System**:
  - Windows 10 or later
  - Linux (any modern distribution)
  - macOS 10.15 (Catalina) or later
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space for dependencies

## Dependencies

The following Python packages will be installed:
- `astropy` - Astronomy data processing
- `peewee` - Database ORM
- `numpy` - Numerical computing
- `matplotlib` - Plotting and visualization
- `pytz` - Timezone handling
- `PySide6` - GUI framework

## Manual Installation

If the automatic scripts don't work for your system:

1. **Install Python 3.8+** from [python.org](https://www.python.org/downloads/)
2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   ```
3. **Activate virtual environment**:
   - Windows: `.venv\Scripts\activate`
   - Linux/macOS: `source .venv/bin/activate`
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Run AstroFiler**:
   ```bash
   python astrofiler.py
   ```

## Running AstroFiler

After installation, you can run AstroFiler using:

### Desktop Integration
All platforms create desktop launchers for easy access:

**Windows:**
- Double-click the "AstroFiler" shortcut on your desktop
- Or use Start Menu search for "AstroFiler"

**Linux:**
- Double-click the "AstroFiler" icon on your desktop
- Or find "AstroFiler" in your applications menu under Science/Education

**macOS:**
- Double-click `AstroFiler.app` on your desktop or in Applications folder
- Or use Spotlight search for "AstroFiler"

**Auto-Update Feature:**
All launcher scripts automatically check for updates from GitHub when AstroFiler starts. If the project was cloned from git, the launchers will:
- Check for new updates from the main branch
- Automatically pull and apply updates if available
- Continue with the current version if update fails
- Skip update check if git is not available or not an internet connection

### Manual Launch Methods

**Windows:**
- Double-click `install/launch_astrofiler.bat` or `install/launch_astrofiler.ps1`
- Or manually:
  ```cmd
  .venv\Scripts\activate
  python astrofiler.py
  ```

**Linux:**
- Run `./install/launch_astrofiler.sh`
- Or manually:
  ```bash
  source .venv/bin/activate
  python astrofiler.py
  ```

**macOS:**
- Run `./install/launch_astrofiler_macos.sh`
- Or manually:
  ```bash
  source .venv/bin/activate
  python astrofiler.py
  ```

## Troubleshooting

### Python Not Found
- **Windows**: Make sure "Add Python to PATH" was checked during installation
- **Linux**: Install python3 using your package manager
- **macOS**: Install via Homebrew or from python.org

### Permission Errors
- **Windows**: Run PowerShell/Command Prompt as Administrator
- **Linux/macOS**: Use `sudo` when prompted by the installation script

### Package Installation Fails
1. Make sure you have internet connection
2. Try upgrading pip: `python -m pip install --upgrade pip`
3. On some systems, you might need development tools:
   - **Windows**: Install Visual Studio Build Tools
   - **Linux**: Install `build-essential` or equivalent
   - **macOS**: Install Xcode Command Line Tools: `xcode-select --install`

### Virtual Environment Issues
1. Delete `.venv` folder and run installation script again
2. Make sure you have sufficient disk space
3. Check that your user has write permissions in the directory

### Apple Silicon Mac Issues
If you encounter issues on Apple Silicon Macs:
```bash
arch -arm64 python -m pip install -r requirements.txt
```

## Updating AstroFiler

To update to a newer version:
1. Download the new version
2. Copy your data files (if needed)
3. Run the installation script again
4. It will ask if you want to recreate the virtual environment

## Uninstalling

To remove AstroFiler:
1. Delete the entire AstroFiler folder
2. The virtual environment and all dependencies will be removed with it

## Development Setup

For developers who want to modify AstroFiler:
1. Run the installation script
2. Activate the virtual environment
3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt  # if available
   ```

## Getting Help

If you encounter issues:
1. Check this README for common solutions
2. Ensure your system meets the requirements
3. Try manual installation steps
4. Check the AstroFiler documentation
5. Report issues on the project repository

---

**Note**: The installation scripts are designed to be safe and non-destructive. They will ask for confirmation before making system changes and can be run multiple times safely.
