# AstroFiler Command Line Utilities

This folder contains command line utilities for automating AstroFiler operations.

## Available Scripts

### LoadRepo.py
**Purpose**: Load FITS files from source folder into the repository

**Description**: This script scans the configured source folder for FITS files and processes them into the repository structure. It can either move files from source to repository (default) or sync existing repository files with the database.

**Usage**:
```bash
# Basic repository load
python LoadRepo.py

# Verbose output
python LoadRepo.py -v

# Sync mode (don't move files, just register)
python LoadRepo.py -n

# Override source folder
python LoadRepo.py -s /path/to/source

# Custom config file
python LoadRepo.py -c /path/to/config.ini
```

**Options**:
- `-h, --help`: Show help message
- `-v, --verbose`: Enable verbose logging
- `-c, --config`: Path to configuration file (default: astrofiler.ini)
- `-s, --source`: Override source folder path
- `-r, --repo`: Override repository folder path
- `-n, --no-move`: Sync mode - register files without moving them

**Output**: Creates `loadrepo.log` with processing details

### CreateSessions.py
**Purpose**: Create sessions for unassigned FITS files

**Description**: This script creates light sessions and calibration sessions for FITS files that have been processed into the repository but haven't been assigned to sessions yet. It groups light frames by object and creates separate calibration sessions for bias, dark, and flat files.

**Usage**:
```bash
# Create both light and calibration sessions
python CreateSessions.py

# Verbose output
python CreateSessions.py -v

# Only create light sessions
python CreateSessions.py -l

# Only create calibration sessions  
python CreateSessions.py -C

# Custom config file
python CreateSessions.py -c /path/to/config.ini
```

**Options**:
- `-h, --help`: Show help message
- `-v, --verbose`: Enable verbose logging
- `-c, --config`: Path to configuration file (default: astrofiler.ini)
- `-l, --lights`: Only create light sessions
- `-C, --calibs`: Only create calibration sessions

**Output**: Creates `createsessions.log` with processing details

### LinkSessions.py
**Purpose**: Link calibration sessions to light sessions

**Description**: This script links calibration sessions (bias, dark, flat) to light sessions based on matching telescope and imager combinations. For each light session, it finds the most recent calibration sessions that match the telescope and imager, and updates the light session records to reference the appropriate calibration sessions.

**Usage**:
```bash
# Link calibration sessions to light sessions
python LinkSessions.py

# Verbose output
python LinkSessions.py -v

# Custom config file
python LinkSessions.py -c /path/to/config.ini
```

**Options**:
- `-h, --help`: Show help message
- `-v, --verbose`: Enable verbose logging
- `-c, --config`: Path to configuration file (default: astrofiler.ini)

**Output**: Creates `linksessions.log` with processing details

### cron_loadrepo.sh
**Purpose**: Example bash script for cron automation

**Description**: A shell script wrapper for LoadRepo.py that can be used with cron for scheduled processing.

**Setup**:
1. Edit the script to set correct paths
2. Make executable: `chmod +x cron_loadrepo.sh`
3. Add to crontab: `crontab -e`
4. Add line: `0 10 * * * /path/to/astrofiler-gui/commands/cron_loadrepo.sh`

### cron_createsessions.sh
**Purpose**: Example bash script for cron automation

**Description**: A shell script wrapper for CreateSessions.py that can be used with cron for scheduled session creation.

**Setup**:
1. Edit the script to set correct paths
2. Make executable: `chmod +x cron_createsessions.sh`
3. Add to crontab: `crontab -e`
4. Add line: `30 10 * * * /path/to/astrofiler-gui/commands/cron_createsessions.sh`

### cron_linksessions.sh
**Purpose**: Example bash script for cron automation

**Description**: A shell script wrapper for LinkSessions.py that can be used with cron for scheduled session linking.

**Setup**:
1. Edit the script to set correct paths
2. Make executable: `chmod +x cron_linksessions.sh`
3. Add to crontab: `crontab -e`
4. Add line: `0 11 * * * /path/to/astrofiler-gui/commands/cron_linksessions.sh`

### astrofiler_workflow.sh
**Purpose**: Complete Linux automation workflow

**Description**: A comprehensive bash script that runs both repository loading and session creation in sequence. Includes error handling and logging.

**Usage**:
```bash
./astrofiler_workflow.sh           # Run complete workflow
./astrofiler_workflow.sh load      # Only load repository  
./astrofiler_workflow.sh sessions  # Only create sessions
./astrofiler_workflow.sh link      # Only link sessions
./astrofiler_workflow.sh manual    # Run with pause for manual testing
```

**Setup**:
1. Edit the script to set correct paths (ASTROFILER_DIR variable)
2. Make executable: `chmod +x astrofiler_workflow.sh`
3. Test manually: `./astrofiler_workflow.sh manual`
4. Add to crontab for automated execution

### cron_loadrepo.bat
**Purpose**: Windows batch script for repository loading

**Description**: A Windows batch file wrapper for LoadRepo.py that can be used with Task Scheduler for scheduled processing.

**Setup**:
1. Edit the script to set correct paths (ASTROFILER_DIR variable)
2. Open Task Scheduler (taskschd.msc)
3. Create Basic Task → Daily → Set time → Start a program
4. Browse to select this batch file
5. Optionally add argument "manual" for interactive testing

### cron_createsessions.bat
**Purpose**: Windows batch script for session creation

**Description**: A Windows batch file wrapper for CreateSessions.py that can be used with Task Scheduler for scheduled session creation.

**Setup**:
1. Edit the script to set correct paths (ASTROFILER_DIR variable)
2. Open Task Scheduler (taskschd.msc)
3. Create Basic Task → Daily → Set time → Start a program
4. Browse to select this batch file
5. Optionally add argument "manual" for interactive testing

### cron_linksessions.bat
**Purpose**: Windows batch script for session linking

**Description**: A Windows batch file wrapper for LinkSessions.py that can be used with Task Scheduler for scheduled session linking.

**Setup**:
1. Edit the script to set correct paths (ASTROFILER_DIR variable)
2. Open Task Scheduler (taskschd.msc)
3. Create Basic Task → Daily → Set time → Start a program
4. Browse to select this batch file
5. Optionally add argument "manual" for interactive testing

### astrofiler_workflow.bat
**Purpose**: Complete Windows automation workflow

**Description**: A comprehensive batch file that runs both repository loading and session creation in sequence. Includes error handling and logging.

**Usage**:
```batch
astrofiler_workflow.bat           REM Run complete workflow
astrofiler_workflow.bat load      REM Only load repository  
astrofiler_workflow.bat sessions  REM Only create sessions
astrofiler_workflow.bat link      REM Only link sessions
astrofiler_workflow.bat manual    REM Run with pause for manual testing
```

**Setup**:
1. Edit the script to set correct paths (ASTROFILER_DIR variable)
2. Test manually: `astrofiler_workflow.bat manual`
3. Schedule with Task Scheduler for automated execution

### CloudSync.py
**Purpose**: Cloud synchronization with Google Cloud Storage

**Description**: This script provides comprehensive cloud synchronization capabilities including backup, analysis, and duplicate detection. It supports multiple sync profiles and can be used for both manual operations and automated scheduling.

**Usage**:
```bash
# Basic cloud sync using configured profile
python CloudSync.py

# Analyze cloud storage without syncing
python CloudSync.py --analyze

# Override sync profile
python CloudSync.py -p backup    # Force backup profile
python CloudSync.py -p complete  # Force complete profile

# Auto-confirm for unattended operation
python CloudSync.py --yes

# Verbose output with detailed logging
python CloudSync.py -v

# Custom config file
python CloudSync.py -c /path/to/config.ini
```

**Options**:
- `-h, --help`: Show help message
- `-v, --verbose`: Enable verbose logging
- `-c, --config`: Path to configuration file (default: astrofiler.ini)
- `-p, --profile`: Override sync profile (backup, complete)
- `--analyze`: Analyze cloud storage without performing sync
- `--yes`: Auto-confirm operations for unattended execution

**Features**:
- **Hash-Based Duplicate Detection**: Prevents unnecessary uploads by comparing MD5 hashes
- **Cloud Storage Analysis**: Identifies duplicate files in cloud storage to optimize costs
- **Multiple Sync Profiles**: Backup Only (one-way) and Complete (bidirectional) synchronization
- **Progress Tracking**: Real-time progress with file-by-file updates
- **Error Recovery**: Handles network issues and authentication failures gracefully
- **Automation Ready**: Perfect for cron/Task Scheduler with --yes flag

**Output**: Creates timestamped logs in `logs/cloudsync_YYYYMMDD_HHMMSS.log`

### cron_cloudsync.sh
**Purpose**: Linux automation script for cloud sync

**Description**: A shell script wrapper for CloudSync.py that can be used with cron for scheduled cloud synchronization.

**Setup**:
1. Edit the script to set correct paths
2. Make executable: `chmod +x cron_cloudsync.sh`
3. Add to crontab: `crontab -e`
4. Add line: `0 2 * * * /path/to/astrofiler-gui/commands/cron_cloudsync.sh`

### cron_cloudsync.bat
**Purpose**: Windows automation script for cloud sync

**Description**: A Windows batch file wrapper for CloudSync.py that can be used with Task Scheduler for scheduled cloud synchronization.

**Setup**:
1. Edit the script to set correct paths (ASTROFILER_DIR variable)
2. Open Task Scheduler (taskschd.msc)
3. Create Basic Task → Daily → Set time → Start a program
4. Browse to select this batch file
5. Optionally add argument "manual" for interactive testing

### AutoCalibration.py
**Purpose**: Automated calibration system for master frame creation and light calibration

**Description**: This script provides comprehensive automated calibration capabilities including master frame creation, calibration opportunity detection, light frame calibration, and quality assessment.

**Usage**:
```bash
# Run complete auto-calibration workflow
python AutoCalibration.py

# Analyze calibration opportunities only
python AutoCalibration.py --mode analyze

# Create master frames only
python AutoCalibration.py --mode masters

# Calibrate light frames only
python AutoCalibration.py --mode calibrate

# Quality assessment only
python AutoCalibration.py --mode quality

# Force operations (bypass safety checks)
python AutoCalibration.py --force

# Dry run (show what would be done)
python AutoCalibration.py --dry-run

# Session-specific operations
python AutoCalibration.py -s 123    # Specific session ID
python AutoCalibration.py -o M31    # Specific object name

# Custom config file
python AutoCalibration.py -c /path/to/config.ini
```

**Options**:
- `-h, --help`: Show help message
- `-v, --verbose`: Enable verbose logging
- `-c, --config`: Path to configuration file (default: astrofiler.ini)
- `--mode`: Operation mode (analyze, masters, calibrate, quality, all)
- `-s, --session`: Process specific session ID
- `-o, --object`: Process specific object name
- `-f, --files`: Process specific file list
- `--force`: Force operations bypassing safety checks
- `--dry-run`: Show what would be done without making changes

**Features**:
- **Master Frame Creation**: Automatically creates master bias, dark, and flat frames
- **Intelligent Session Matching**: Matches calibration frames based on equipment and settings
- **Light Frame Calibration**: Applies appropriate master calibration frames to light images
- **Quality Assessment**: Evaluates frame quality using FWHM, noise, and uniformity metrics
- **Progress Tracking**: Real-time progress with detailed phase reporting
- **Comprehensive Logging**: Detailed logs for troubleshooting and audit trails

**Output**: Creates `autocalibration.log` with processing details

### calibrateLights.py
**Purpose**: Professional light frame calibration using PySiril integration

**Description**: This script provides production-quality light frame calibration using Siril's proven calibration engine. It supports flexible input options, complete pipeline processing, and quality assessment.

**Usage**:
```bash
# Calibrate by session ID
python calibrateLights.py -s 123

# Calibrate by object name
python calibrateLights.py -o M31

# Calibrate specific files
python calibrateLights.py -f file1.fits file2.fits file3.fits

# Full pipeline (calibrate + register + stack)
python calibrateLights.py -s 123 --pipeline full

# Quality assessment only
python calibrateLights.py -s 123 --pipeline quality

# Custom master frame directory
python calibrateLights.py -s 123 --masters /path/to/masters

# Multi-threading
python calibrateLights.py -s 123 --threads 8

# Verbose output
python calibrateLights.py -s 123 -v
```

**Options**:
- `-h, --help`: Show help message
- `-v, --verbose`: Enable verbose logging
- `-c, --config`: Path to configuration file (default: astrofiler.ini)
- `-s, --session`: Session ID to process
- `-o, --object`: Object name to process
- `-f, --files`: Specific files to process
- `--masters`: Directory containing master calibration frames
- `--pipeline`: Processing pipeline (calibrate, register, stack, full, quality)
- `--threads`: Number of processing threads
- `--output`: Output directory for processed files
- `--temp`: Temporary directory for processing

**Features**:
- **PySiril Integration**: Professional-grade processing using Siril's calibration engine
- **Flexible Input Options**: Process by session, object, or specific file list
- **Complete Pipeline**: Individual calibration or full processing including registration and stacking
- **CFA/OSC Support**: Automatic Color Filter Array processing with debayering
- **Quality Assessment**: Built-in FWHM analysis, noise metrics, and quality scoring
- **Multi-Threading**: Configurable thread count for optimal performance
- **Batch Processing**: Efficient processing of large datasets

**Output**: Creates `calibratelights.log` with processing details

### cron_autocalibration.sh
**Purpose**: Linux automation script for auto-calibration

**Description**: A shell script wrapper for AutoCalibration.py that can be used with cron for scheduled automated calibration.

**Setup**:
1. Edit the script to set correct paths
2. Make executable: `chmod +x cron_autocalibration.sh`
3. Add to crontab: `crontab -e`
4. Add line: `0 3 * * * /path/to/astrofiler-gui/commands/cron_autocalibration.sh`

### cron_autocalibration.bat
**Purpose**: Windows automation script for auto-calibration

**Description**: A Windows batch file wrapper for AutoCalibration.py that can be used with Task Scheduler for scheduled automated calibration.

**Setup**:
1. Edit the script to set correct paths (ASTROFILER_DIR variable)
2. Open Task Scheduler (taskschd.msc)
3. Create Basic Task → Daily → Set time → Start a program
4. Browse to select this batch file

### cron_calibrate_lights.sh
**Purpose**: Linux automation script for light calibration

**Description**: A shell script wrapper for calibrateLights.py that can be used with cron for scheduled light frame calibration.

**Setup**:
1. Edit the script to set correct paths
2. Make executable: `chmod +x cron_calibrate_lights.sh`
3. Add to crontab: `crontab -e`
4. Add line: `0 4 * * * /path/to/astrofiler-gui/commands/cron_calibrate_lights.sh`

### cron_calibrate_lights.bat
**Purpose**: Windows automation script for light calibration

**Description**: A Windows batch file wrapper for calibrateLights.py that can be used with Task Scheduler for scheduled light frame calibration.

**Setup**:
1. Edit the script to set correct paths (ASTROFILER_DIR variable)
2. Open Task Scheduler (taskschd.msc)
3. Create Basic Task → Daily → Set time → Start a program
4. Browse to select this batch file

## Automation Examples

### Complete Daily Processing Workflow (Individual Scripts)
```bash
# Add to crontab for complete automated workflow
# Load repository at 10:00 AM
0 10 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/LoadRepo.py -v

# Create sessions at 10:30 AM (after files are loaded)
30 10 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/CreateSessions.py -v

# Link sessions at 11:00 AM (after sessions are created)
0 11 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/LinkSessions.py -v

# Cloud sync at 2:00 AM (off-peak hours)
0 2 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/CloudSync.py --yes -v

# Auto-calibration at 3:00 AM (after cloud sync)
0 3 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/AutoCalibration.py -v

# Light calibration at 4:00 AM (after master creation)
0 4 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/calibrateLights.py -o M31 -v
```

### Complete Daily Processing Workflow (Combined Scripts)
```bash
# Add to crontab for complete automated workflow using wrapper scripts
# Run complete workflow at 10:00 AM
0 10 * * * /home/user/astrofiler-gui/commands/astrofiler_workflow.sh

# Cloud sync at 2:00 AM
0 2 * * * /home/user/astrofiler-gui/commands/cron_cloudsync.sh

# Auto-calibration at 3:00 AM
0 3 * * * /home/user/astrofiler-gui/commands/cron_autocalibration.sh

# Light calibration at 4:00 AM
0 4 * * * /home/user/astrofiler-gui/commands/cron_calibrate_lights.sh
```

### Cloud Sync Automation
```bash
# Daily cloud backup at 2:00 AM
0 2 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/CloudSync.py -p backup --yes

# Weekly cloud analysis on Sundays at 1:00 AM
0 1 * * 0 /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/CloudSync.py --analyze --yes

# Complete sync twice weekly (Tuesday and Saturday at 3:00 AM)
0 3 * * 2,6 /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/CloudSync.py -p complete --yes
```

### Calibration Automation
```bash
# Auto-calibration after session creation
30 11 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/AutoCalibration.py --mode masters

# Light calibration for specific objects
0 12 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/calibrateLights.py -o M31
30 12 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/calibrateLights.py -o M42

# Quality assessment weekly on Sundays
0 5 * * 0 /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/AutoCalibration.py --mode quality
```

### Hourly Sync (without moving files)
```bash
# Add to crontab  
0 * * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/LoadRepo.py -n
```

### Session Creation Only
```bash
# Create sessions twice daily
0 12,18 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/CreateSessions.py
```

### Windows Task Scheduler
Create a batch file:
```batch
@echo off
cd /d "C:\path\to\astrofiler-gui"
.venv\Scripts\python.exe commands\LoadRepo.py -v
```

## Prerequisites

- AstroFiler must be properly configured (astrofiler.ini)
- Python virtual environment must be activated or use full path to python executable
- Source and repository folders must exist and be accessible
- Database must be writable
- For cloud sync: Google Cloud Storage bucket and service account configured
- For calibration: Siril 1.4+ and PySiril package installed (for calibrateLights.py)

## Troubleshooting

1. **Import Errors**: Ensure you're running from the astrofiler-gui directory or using the full path to the python executable in the virtual environment.

2. **Permission Errors**: Check that the script has write access to:
   - Repository folder
   - Log files
   - Database file
   - Cloud storage bucket (for cloud sync)

3. **Configuration Errors**: Verify astrofiler.ini exists and contains valid source/repo paths, and cloud sync configuration if using cloud features.

4. **No Files Found**: Check that source folder contains FITS files with extensions .fits, .fit, or .fts

5. **Cloud Sync Errors**: 
   - Verify Google Cloud Storage configuration is correct
   - Check service account permissions
   - Ensure network connectivity
   - Validate bucket access

6. **Calibration Errors**:
   - Verify Siril is installed and accessible
   - Check PySiril package installation
   - Ensure sufficient calibration frames exist
   - Verify master frame directory permissions

## Advanced Usage

### Cloud Sync Integration with Processing Pipeline
```bash
# Complete processing pipeline with cloud integration
#!/bin/bash

# 1. Load new files
python LoadRepo.py -v

# 2. Create sessions
python CreateSessions.py -v

# 3. Link calibration sessions
python LinkSessions.py -v

# 4. Auto-calibration
python AutoCalibration.py -v

# 5. Calibrate light frames
python calibrateLights.py -o M31 --pipeline full

# 6. Backup to cloud
python CloudSync.py -p backup --yes -v

# 7. Clean up (optional)
# Files marked for soft deletion are handled automatically during cloud sync
```

### Quality Assessment Workflow
```bash
# Comprehensive quality assessment
python AutoCalibration.py --mode quality -v > quality_report.txt
python calibrateLights.py -o M31 --pipeline quality >> quality_report.txt
```

### Selective Cloud Operations
```bash
# Analyze cloud storage for duplicates
python CloudSync.py --analyze --yes

# Backup only new files
python CloudSync.py -p backup --yes

# Complete bidirectional sync
python CloudSync.py -p complete --yes
```

## Future Enhancements

The following command line utilities are planned or under development:
- **CreateStacks.py**: Create stacked master images from session files
- **GenerateReport.py**: Generate processing reports and statistics
- **ArchiveManager.py**: Automated archival and cleanup of old data
- **QualityMonitor.py**: Continuous quality monitoring and alerting
