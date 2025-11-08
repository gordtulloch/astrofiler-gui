# AstroFiler Commands

This folder contains command-line utilities and automation scripts for AstroFiler operations.

## Available Commands

### CloudSync.py
Command-line utility for cloud synchronization with Google Cloud Storage.

**Usage:**
```bash
python CloudSync.py [options]

# Examples:
python CloudSync.py                    # Sync using configured profile
python CloudSync.py -p backup -v      # Backup sync with verbose output
python CloudSync.py -p complete -y    # Complete sync with auto-confirm
python CloudSync.py -a                # Analyze cloud storage only
```

**Options:**
- `-p, --profile {backup,complete}`: Override sync profile
- `-a, --analyze`: Only analyze cloud storage, don't sync  
- `-y, --yes`: Skip confirmation prompts (auto-confirm)
- `-v, --verbose`: Enable verbose logging
- `-c, --config`: Path to configuration file (default: astrofiler.ini)

**Sync Profiles:**
- `backup`: Upload local files to cloud (one-way backup)
- `complete`: Bidirectional sync (download missing + upload new)

### LoadRepo.py
Load FITS files from source folder into the repository.

**Usage:**
```bash
python LoadRepo.py [options]

# Examples:
python LoadRepo.py                     # Load with default settings
python LoadRepo.py -v                  # Verbose output
python LoadRepo.py -n                  # Sync mode (don't move files)
```

### CreateSessions.py
Create observation sessions from repository files.

**Usage:**
```bash
python CreateSessions.py [options]

# Examples:
python CreateSessions.py                     # Create both light and calibration sessions
python CreateSessions.py -v                  # Verbose output
python CreateSessions.py -l                  # Only create light sessions
python CreateSessions.py -C                  # Only create calibration sessions
python CreateSessions.py -r                  # Regenerate: Clear all existing sessions first, then recreate
python CreateSessions.py -r -v               # Regenerate with verbose output
```

**Options:**
- `-l, --lights`: Only create light sessions
- `-C, --calibs`: Only create calibration sessions
- `-r, --regenerate`: Clear all existing sessions first, then regenerate all session data
- `-v, --verbose`: Enable verbose logging
- `-c, --config`: Path to configuration file (default: astrofiler.ini)

**Session Regeneration:**
The `--regenerate` option provides a complete session reset:
1. Clears all existing session records from the database
2. Removes session references from all FITS files
3. Recreates both light and calibration sessions from scratch
4. Useful for fixing session assignment issues or after major repository changes

**Note:** The `--regenerate` flag cannot be combined with `--lights` or `--calibs` as it always processes both session types.

### LinkSessions.py  
Link files to observation sessions based on timestamps.

### AutoCalibration.py
Command-line utility for automatic calibration operations including master frame creation, light frame calibration, and quality assessment.

Note: where python is indicated below you should run the correct python to invoke the virtual environment.

.venv\Scripts\python     # Windows
.venv/bin/python         # Linux and Mac

**Usage:**
```bash
python AutoCalibration.py [options]

# Examples:
python AutoCalibration.py                     # Complete auto-calibration workflow
python AutoCalibration.py -o analyze -v      # Analyze calibration opportunities
python AutoCalibration.py -o masters -s 123  # Create masters for session 123
python AutoCalibration.py -o quality -r      # Quality assessment with report
python AutoCalibration.py --dry-run -v       # Preview what would be done
```

**Operations:**
- `analyze`: Analyze sessions for calibration opportunities
- `masters`: Create master calibration frames only  
- `calibrate`: Calibrate light frames using existing masters
- `quality`: Assess frame and master quality only
- `all`: Complete auto-calibration workflow (default)

**Key Options:**
- `-o, --operation {analyze,masters,calibrate,quality,all}`: Operation to perform
- `-s, --session ID`: Specific session ID to process
- `-f, --force`: Force operation even if masters exist
- `-r, --report`: Generate detailed quality report
- `--dry-run`: Show what would be done without making changes
- `--min-files N`: Override minimum files per master
- `-v, --verbose`: Enable verbose logging

**Quality Assessment Features:**
- FWHM analysis for light frames (seeing quality)
- Uniformity analysis for calibration frames
- Noise metrics and signal-to-noise ratios
- Overall quality scoring (0-100)
- Intelligent recommendations for improvement

### calibrateLights.py
Professional light frame calibration using PySiril with comprehensive processing options.

**Usage:**
```bash
python calibrateLights.py [options]

# Examples:
python calibrateLights.py -s 123 -v                        # Calibrate session 123 with verbose output
python calibrateLights.py -o "M31" --cfa --debayer         # Calibrate M31 object with CFA/OSC processing
python calibrateLights.py -f "light1.fits,light2.fits"     # Calibrate specific files
python calibrateLights.py -s 123 --register --stack-output # Full pipeline: calibrate, align, and stack
python calibrateLights.py -s 123 --quality-check -v        # Calibrate with quality assessment
python calibrateLights.py --dry-run -s 123                 # Preview processing plan
```

**Key Features:**
- **PySiril Integration**: Professional-grade calibration using Siril's processing engine
- **Smart Master Detection**: Automatically finds appropriate master frames from database
- **CFA/OSC Support**: Full Color Filter Array processing with debayering options
- **Complete Pipeline**: Calibration, registration, and stacking in single command
- **Quality Assessment**: FWHM analysis, noise metrics, and quality scoring
- **Flexible Input**: Process by session, object, or specific file list
- **Batch Processing**: Efficient processing of large datasets

**Input Options:**
- `-s, --session ID`: Process specific session by ID
- `-o, --object NAME`: Process all sessions for specific object
- `-f, --files LIST`: Process specific FITS files (comma-separated)

**Master Frame Options:**
- `--masters-dir DIR`: Directory containing master frames (default: Masters/)
- `--bias-master FILE`: Specific bias master frame path
- `--dark-master FILE`: Specific dark master frame path  
- `--flat-master FILE`: Specific flat master frame path

**Processing Options:**
- `--cfa`: Treat images as Color Filter Array/OSC cameras
- `--debayer`: Debayer CFA images after calibration
- `--register`: Register (align) calibrated frames using star detection
- `--stack-output`: Stack calibrated frames to single master light
- `--force`: Force recalibration even if outputs exist

**Stacking Parameters:**
- `--stack-method {median,average,sigma}`: Stacking algorithm (default: median)
- `--sigma-low N`: Lower sigma for outlier rejection (default: 3.0)
- `--sigma-high N`: Upper sigma for outlier rejection (default: 3.0)
- `--normalize {addscale,mulscale,none}`: Normalization method (default: addscale)

**Quality Assessment:**
- `--quality-check`: Perform comprehensive quality assessment
- `--fwhm-check`: Analyze FWHM for seeing conditions
- `--noise-analysis`: Detailed noise characterization
- `--quality-threshold N`: Minimum quality score (0-100) to accept frames

**System Options:**
- `--threads N`: Number of processing threads (default: auto-detect)
- `--temp-dir DIR`: Temporary processing directory (default: temp_calibration)
- `--keep-temp`: Preserve temporary files for debugging
- `--dry-run`: Preview processing plan without executing

**Prerequisites:**
- Siril 1.4+ installed and accessible
- PySiril Python package (`pip install pysiril`)
- Master calibration frames available (bias, dark, flat)
- Sufficient disk space for temporary processing files

## Automation Scripts

### Windows (Task Scheduler)

**cron_cloudsync.bat** - Automated cloud sync for Windows
- Edit paths in the script to match your installation
- Use with Windows Task Scheduler for scheduled sync operations
- Creates timestamped log files in the logs directory

**cron_loadrepo.bat** - Automated repository loading for Windows  
- Edit paths in the script to match your installation
- Use with Windows Task Scheduler for scheduled repository updates

**cron_autocalibration.bat** - Automated auto-calibration for Windows
- Edit paths in the script to match your installation
- Use with Windows Task Scheduler for scheduled calibration operations
- Creates timestamped log files and error flags for monitoring

**cron_regeneratesessions.bat** - Complete session regeneration for Windows
- Clears all existing sessions and recreates them from FITS files
- Useful for fixing session assignment issues or after major repository changes
- Run when you need to completely rebuild session structure

### Linux/macOS (Cron)

**cron_cloudsync.sh** - Automated cloud sync for Linux/macOS
- Make executable: `chmod +x cron_cloudsync.sh`
- Edit paths in the script to match your installation
- Add to crontab for scheduled execution

**cron_loadrepo.sh** - Automated repository loading for Linux/macOS
- Make executable: `chmod +x cron_loadrepo.sh` 
- Edit paths in the script to match your installation
- Add to crontab for scheduled execution

**cron_autocalibration.sh** - Automated auto-calibration for Linux/macOS
- Make executable: `chmod +x cron_autocalibration.sh`
- Edit paths in the script to match your installation

**cron_regeneratesessions.sh** - Complete session regeneration for Linux/macOS
- Make executable: `chmod +x cron_regeneratesessions.sh`
- Clears all existing sessions and recreates them from FITS files
- Useful for fixing session assignment issues or after major repository changes
- Run when you need to completely rebuild session structure
- Add to crontab for scheduled calibration operations
- Includes automatic log cleanup (keeps last 30 days)

## Scheduling Examples

### Windows Task Scheduler Setup

1. Open Task Scheduler (`taskschd.msc`)
2. Create Basic Task
3. Set trigger (daily, weekly, etc.)
4. Action: Start a program
5. Program: Full path to batch file
6. Start in: AstroFiler project directory

**Example schedules:**
```
Daily auto-calibration at 2 AM:
cron_autocalibration.bat

Weekly master creation on Sunday at 3 AM:
cron_autocalibration.bat masters

Quality assessment every 6 hours:
cron_autocalibration.bat quality -r
```

### Linux/macOS Crontab Setup

Add to crontab using `crontab -e`:

```bash
# Auto-calibration examples:
# Daily at 2 AM
0 2 * * * /path/to/astrofiler/commands/cron_autocalibration.sh

# Every 6 hours
0 */6 * * * /path/to/astrofiler/commands/cron_autocalibration.sh

# Weekly on Sunday at 3 AM (masters only)
0 3 * * 0 /path/to/astrofiler/commands/cron_autocalibration.sh masters

# Quality assessment every 4 hours with reports
0 */4 * * * /path/to/astrofiler/commands/cron_autocalibration.sh quality -r
```

## Configuration

All commands use the main `astrofiler.ini` configuration file. Key settings:

**For cloud sync operations:**
```ini
[DEFAULT]
repo = /path/to/your/repository
bucket_url = gs://your-bucket-name
auth_file_path = /path/to/service-account-key.json
sync_profile = complete
```

**For auto-calibration operations:**
```ini
[DEFAULT]
min_files_per_master = 3
auto_calibration_progress = true
siril_path = /path/to/siril  # Optional for master creation
```

## Scheduling Examples

### Windows Task Scheduler

1. **Daily Cloud Sync at 11:00 PM:**
   - Program: `C:\path\to\astrofiler-gui\.venv\Scripts\python.exe`
   - Arguments: `C:\path\to\astrofiler-gui\commands\CloudSync.py -y -v`
   - Start in: `C:\path\to\astrofiler-gui`

2. **Using Batch Script:**
   - Program: `C:\path\to\astrofiler-gui\commands\cron_cloudsync.bat`

### Linux/macOS Crontab

1. **Daily Cloud Sync at 11:00 PM:**
   ```bash
   0 23 * * * /path/to/astrofiler-gui/commands/cron_cloudsync.sh
   ```

2. **Repository Load Every 2 Hours:**
   ```bash
   0 */2 * * * /path/to/astrofiler-gui/commands/cron_loadrepo.sh
   ```

## Logging

- CloudSync operations create timestamped log files in the `logs/` directory
- Use `-v` or `--verbose` flag for detailed logging output
- Automation scripts automatically log to timestamped files

## Requirements

- Python virtual environment with required packages installed
- Valid `astrofiler.ini` configuration file
- For cloud operations: Google Cloud Storage credentials and bucket access
- Appropriate file system permissions for repository and log directories