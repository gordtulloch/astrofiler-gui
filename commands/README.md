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

## Automation Examples

### Daily Processing Workflow (Individual Scripts)
```bash
# Add to crontab for complete automated workflow
# Load repository at 10:00 AM
0 10 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/LoadRepo.py -v

# Create sessions at 10:30 AM (after files are loaded)
30 10 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/CreateSessions.py -v

# Link sessions at 11:00 AM (after sessions are created)
0 11 * * * /home/user/astrofiler-gui/.venv/bin/python /home/user/astrofiler-gui/commands/LinkSessions.py -v
```

### Daily Processing Workflow (Combined Script)
```bash
# Add to crontab for complete automated workflow using the combined script
# Run complete workflow at 10:00 AM
0 10 * * * /home/user/astrofiler-gui/commands/astrofiler_workflow.sh

# Alternative: Run individual components at different times
0 10 * * * /home/user/astrofiler-gui/commands/astrofiler_workflow.sh load
30 10 * * * /home/user/astrofiler-gui/commands/astrofiler_workflow.sh sessions
0 11 * * * /home/user/astrofiler-gui/commands/astrofiler_workflow.sh link
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

## Requirements

- AstroFiler must be properly configured (astrofiler.ini)
- Python virtual environment must be activated or use full path to python executable
- Source and repository folders must exist and be accessible
- Database must be writable

## Troubleshooting

1. **Import Errors**: Ensure you're running from the astrofiler-gui directory or using the full path to the python executable in the virtual environment.

2. **Permission Errors**: Check that the script has write access to:
   - Repository folder
   - Log files
   - Database file

3. **Configuration Errors**: Verify astrofiler.ini exists and contains valid source/repo paths.

4. **No Files Found**: Check that source folder contains FITS files with extensions .fits, .fit, or .fts

## Future Scripts

The following command line utilities are planned:
- **CalibrateImages.py**: Automatically calibrate light images using linked calibration sessions
- **CreateStacks.py**: Create stacked master images from session files
- **GenerateReport.py**: Generate processing reports and statistics
