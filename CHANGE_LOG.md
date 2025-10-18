# AstroFiler Change Log

## Version 1.2.0 - Current Development

### New Features
- **Complete Cloud Sync System**: Revolutionary cloud synchronization with Google Cloud Storage integration
  - **Configuration Interface**: Added Cloud Sync section in Configuration dialog with vendor selection, bucket URL, service account authentication file picker, and sync profile selection (Complete/Backup/On Demand)
  - **Cloud Sync Dialog**: New Tools → Cloud Sync menu opens dedicated dialog with Analyze and Sync operations, real-time configuration display, and Configure button for easy settings access
  - **Database Integration**: Added `fitsFileCloudURL` field to track cloud storage locations for all FITS files with automatic migration support (Migration 006)
  - **Cloud File Analysis**: Analyze function downloads complete cloud bucket file listing, compares with local database, and updates cloud URLs for matching files
  - **Backup Only Sync Profile**: Complete one-way backup sync that uploads local files missing from cloud while preserving directory structure and updating database with cloud URLs
  - **Complete Sync Profile**: Revolutionary bidirectional synchronization that downloads missing files from cloud AND uploads files without cloud URLs
    - Phase 1: Downloads files that exist in cloud but are missing locally
    - Phase 2: Uploads local files that don't have cloud URLs (not yet backed up)
    - Automatic FITS file registration for downloaded files
    - Comprehensive progress tracking with cancellation support
  - **Smart Upload Logic**: Only uploads files that don't exist in cloud, avoiding duplicates and unnecessary transfers
  - **Images View Integration**: Added Local/Cloud status icon columns showing file storage locations with system-standard drive icons and informative tooltips
  - **Self-Contained Architecture**: Cloud sync dialog contains all necessary helper functions, eliminating dependencies on external modules
  - **Comprehensive Error Handling**: User-friendly error messages for bucket not found, access denied, authentication failures, and configuration issues
  - **Progress Tracking**: Real-time progress dialogs with file-by-file updates, cancellation support, and detailed completion statistics
  - **Bucket Validation**: Pre-operation validation ensures bucket exists and is accessible before starting sync operations

- **Command-Line Cloud Sync**: Complete automation support for unattended cloud operations
  - **CloudSync.py**: Comprehensive command-line utility in `commands/` folder supporting all sync profiles
  - **Profile Override**: Command-line flags to override configured sync profile (`-p backup` or `-p complete`)
  - **Analysis Mode**: `--analyze` flag for cloud storage analysis without performing sync operations
  - **Auto-Confirm**: `--yes` flag for unattended operation, perfect for automated scheduling
  - **Automation Scripts**: Ready-to-use cron and Task Scheduler scripts for Windows (`cron_cloudsync.bat`) and Linux/macOS (`cron_cloudsync.sh`)
  - **Timestamped Logging**: Automated logging to `logs/cloudsync_YYYYMMDD_HHMMSS.log` files
  - **Configuration Validation**: Pre-flight validation of bucket access and authentication
  - **Comprehensive Documentation**: Complete setup and scheduling guide in `commands/README.md`
- **Auto-Calibration System**: Comprehensive automatic calibration framework for traditional telescopes
  - **Master Frame Creation**: Enhanced master calibration frame creation with Siril CLI integration, intelligent session grouping, and astronomy-standard FITS headers
  - **Calibration Session Analysis**: Automated detection of calibration opportunities with session matching by telescope, instrument, binning, temperature (±5°C), and filter criteria
  - **Master File Storage Structure**: Organized `/Masters` directory with standardized naming conventions and comprehensive metadata tracking
  - **Configuration Interface**: Complete auto-calibration settings in Configuration dialog including enable/disable toggle, minimum files per master (default: 3), auto-creation triggers (manual/on import/on session creation), master retention policies, and progress tracking options
  - **Database Integration**: Enhanced schema with 7 new calibration tracking fields via Migration 007: `fitsFileCalibrationStatus`, `fitsFileCalibrationDate`, master frame references, original file tracking, and soft-delete capabilities for cloud cleanup integration
  - **Enhanced FITS Headers**: Comprehensive master frame headers with `IMAGETYP` (MasterBias/MasterDark/MasterFlat), source file metadata copying, processing history, quality metrics placeholders, and astronomy workflow compatibility
  - **Intelligent Detection Logic**: Quality assessment scoring system for master creation prioritization based on file count, session consistency, and temporal distribution
  - **Cloud Integration**: Automatic cleanup of calibration files and uncalibrated light frames after cloud backup with `fitsFileSoftDelete` tracking and Auto-cleanup Backed Files setting
  - **Progress Tracking Integration**: Comprehensive progress callback system with 5-phase workflow tracking (analysis, master creation, opportunity detection, light calibration, finalization), real-time progress dialogs with cancellation support, and descriptive status messages integrated with existing progress dialog architecture
  - **UI Integration**: Auto-calibration workflow accessible through Sessions widget with dedicated "Auto-Calibration" button, comprehensive progress tracking, detailed results reporting, and configuration validation
  - **Master Validation and Cleanup**: Comprehensive master file maintenance system including validateMasterFiles() for integrity checking, repairMasterFileDatabase() for broken reference cleanup, cleanupMasterFileStorage() with quarantine system, and runMasterMaintenanceWorkflow() orchestrator with 3-phase validation, repair, and cleanup operations
  - **Master Maintenance UI**: Dedicated "Master Maintenance" button in Sessions widget with options dialog for cleanup preferences, detailed progress tracking, comprehensive results reporting with validation/repair/cleanup statistics, and automatic session refresh after fixes
  - **Quality Assessment System**: Complete frame quality evaluation framework with scipy-based image analysis
    - **Frame Type Detection**: Automatic detection of light, bias, dark, and flat frames from FITS headers and image statistics
    - **FWHM Analysis**: Full Width Half Maximum calculation for light frames using stellar source detection, profile analysis, and seeing quality assessment (Excellent/Good/Fair/Poor/Very Poor categories)
    - **Uniformity Analysis**: Spatial uniformity evaluation for calibration frames including coefficient of variation, quadrant analysis, vignetting detection, and center-to-corner brightness ratios
    - **Noise Metrics**: Advanced noise characterization with signal-to-noise ratios, read noise estimation, hot pixel detection, and noise uniformity across image regions
    - **Acquisition Quality**: FITS header-based quality assessment including temperature stability, exposure time validation, binning optimization, and gain setting evaluation
    - **Overall Scoring**: Comprehensive quality scoring (0-100) with frame-type-specific weighting, quality categories, and intelligent recommendations for improvement
    - **Batch Processing**: Multi-file quality assessment with progress tracking and comprehensive quality reports for session-level analysis
    - **Scientific Integration**: Scipy-based algorithms with fallback support for environments without scipy, ensuring robust operation across different installations
  - **Command-Line Interface**: Complete CLI implementation for batch processing and automation
    - **AutoCalibration.py**: Comprehensive command-line tool in commands/ folder with full argument parsing, operation modes (analyze/masters/calibrate/quality/all), session filtering, force options, dry-run support, and detailed progress reporting
    - **Operation Modes**: Flexible workflow control with analyze (opportunity detection), masters (frame creation), calibrate (light processing), quality (assessment with reports), and all (complete workflow) operations
    - **Batch Processing**: Automated processing capabilities with configuration validation, database connectivity checks, progress callbacks, and comprehensive error handling
    - **Scheduling Integration**: Complete automation support with Windows batch scripts (cron_autocalibration.bat) and Linux/macOS shell scripts (cron_autocalibration.sh) for Task Scheduler and cron integration
    - **Advanced Options**: Dry-run mode for preview, session-specific processing, minimum file overrides, quality report generation, log file output, and verbose logging with timestamped entries
    - **Configuration Management**: Automatic configuration loading from astrofiler.ini, validation of auto-calibration settings, Siril path verification, and database connectivity confirmation
    - **Error Handling**: Robust error management with graceful fallbacks, detailed error reporting, exit code management, and optional error flag creation for monitoring systems
    - **Documentation**: Comprehensive help system, usage examples, scheduling setup guides, and integration with existing AstroFiler CLI architecture following established patterns
  - **Light Frame Calibration**: Complete implementation of automatic light frame calibration system
    - **Core Functions**: calibrate_light_frame() for single frame processing with bias/dark/flat corrections, exposure time scaling, and comprehensive error handling
    - **Session Processing**: calibrate_session_lights() for batch processing of all light frames in sessions with progress tracking, skip logic for existing calibrations, and detailed result reporting  
    - **Master Frame Integration**: get_session_master_frames() for automatic master frame discovery using session auto-calibration field relationships and file system validation
    - **Calibration Pipeline**: Professional-grade calibration workflow with proper correction order (bias → dark → flat), exposure time scaling for darks, flat field normalization, and negative value clipping
    - **Metadata Enhancement**: Automatic FITS header updates with calibration timestamps, master frame references, processing steps, noise levels, and quality metrics for full traceability
    - **Database Integration**: Migration 008 adding session-level auto-calibration tracking fields (is_auto_calibration, master_*_created flags, auto_calibration_*_session_id references) for relationship management
    - **CLI Integration**: Full calibrate operation support in AutoCalibration.py with dry-run mode, session filtering, progress reporting, and comprehensive error handling for automation workflows
    - **Quality Assurance**: Built-in validation for master frame availability, light frame detection, output path management, and graceful handling of missing calibration frames
    - **File Management**: Intelligent output naming with _calibrated suffix, directory creation, FITS format preservation, and data type optimization for reduced file sizes

### Bug Fixes

- **Critical Fix: registerFitsImage Function Call Errors**
  - **Problem**: Fixed "fitsProcessing.registerFitsImage() missing 1 required positional argument: 'file'" errors occurring during cloud sync operations
  - **Root Cause**: Multiple locations incorrectly calling registerFitsImage() with single file_path parameter instead of required (root, file, moveFiles) parameters
  - **Files Fixed**: 
    - `ui/cloud_sync_dialog.py`: Fixed FITS file registration during cloud downloads with proper path splitting
    - `commands/CloudSync.py`: Fixed CLI cloud sync file registration with correct parameter handling
    - `astrofiler_cloud.py`: Fixed incorrect import and function call, now properly instantiates fitsProcessing class
  - **Solution**: All calls now properly split file paths into directory and filename components using os.path.dirname() and os.path.basename()
  - **Impact**: Cloud sync operations now properly register downloaded FITS files in database without errors
  - **Testing**: All fixed files pass syntax validation and cloud functionality imports work correctly

- **Cloud Download Workflow Fix**
  - **Problem**: Downloaded files were being placed directly into repository structure instead of incoming folder
  - **Issue**: Cloud sync operations bypassed the proper file workflow causing organizational issues
  - **Root Cause**: Download operations used repo_path directly instead of source_path for temporary file staging
  - **Files Fixed**:
    - `ui/cloud_sync_dialog.py`: Modified to download files to source folder first, then register with moveFiles=True
    - `commands/CloudSync.py`: Updated CLI cloud sync to use proper incoming folder workflow with configuration loading
  - **Solution**: 
    - Downloads now go to configured source folder (D:/REPOSITORY.incoming/) 
    - Registration uses moveFiles=True to properly organize files into repository structure (K:/00 REPOSITORY/)
    - Maintains consistency with LoadRepo.py workflow and existing file organization patterns
  - **Impact**: Cloud downloads now follow proper AstroFiler file management workflow preventing repository organization issues
- **Google Cloud Documentation**: Added comprehensive setup guide for creating Google Cloud projects, service accounts, and authentication keys
- **Google Cloud Sync**: Added complete Google Cloud repository synchronization feature accessible via Tools > Google Sync menu. Includes full Google Cloud Storage integration with actual upload/download functionality, configurable repository path (Google Cloud Storage bucket), authentication via service account key files with browse button, debug mode toggle, and bidirectional sync option. Uses configured Repository Path for synchronization. When "Sync to Local Disk" is enabled, downloads missing files from GCS to local repository and automatically registers FITS files in database. Requires google-cloud-storage library. Configuration settings are saved in astrofiler.ini and accessible through the Configuration tab under Google Cloud Sync section.
- **Progress tracking for Google Sync**: Added progress tracking capability to Google Cloud Sync operations, providing real-time feedback during file uploads and downloads.
- **Duplicate File Reporting**: Enhanced import system to track and report duplicate files during Load New and Sync operations
- **Smart Telescope Integration**: Complete support for DWARF 3 telescopes via FTP protocol alongside existing SeeStar SMB support
- **StellarMate Support**: Added StellarMate telescope integration with SMB protocol using `stellarmate.local` hostname and `stellarmate`/`smate` credentials
- **DWARF FITS Header Processing**: Comprehensive DWARF folder structure parsing for `DWARF_RAW_*`, `CALI_FRAME`, and `DWARF_DARK` folders with automatic header correction
- **Automatic Session Regeneration**: Sessions database automatically rebuilds after file imports via "Load New" or telescope downloads
- **Enhanced File Processing**: DWARF telescope files processed with proper instrument mapping (cam_0→TELE, cam_1→WIDE) and metadata extraction

### Smart Telescope Enhancements
- **Dual Protocol Support**: SMB for SeeStar/StellarMate, FTP for DWARF telescopes with automatic protocol selection
- **DWARF File Structure Validation**: Validates DWARF folder structure (`CALI_FRAME`, `DWARF_DARK`, `DWARF_RAW_*`) before scanning
- **Telescope-Specific Processing**: Different scanning and processing logic for each telescope type
- **Network Discovery**: Enhanced hostname resolution with telescope-specific patterns and default hostnames
- **Download Progress**: Dynamic protocol indicators (SMB vs FTP) in download progress messages

### UI/UX Improvements  
- **Mapping Dialog Defaults**: All checkboxes now enabled by default ("Update FITS headers", "Apply to database", "Reorganize folders")
- **Mapping Persistence**: Fixed mappings not loading properly in dialog - saved values now correctly populate combo boxes
- **Post-Download Refresh**: All UI components automatically refresh after successful telescope downloads or file imports
- **Session Auto-Update**: No manual "Regenerate" required - sessions update automatically when new files are added

### Technical Improvements
- **Startup Performance**: Removed unnecessary file path normalization migration for faster application startup
- **Cloud Sync Architecture**: Complete code organization with self-contained dialog architecture
  - Moved all cloud sync helper functions from `astrofiler_cloud.py` to `cloud_sync_dialog.py`
  - Eliminated circular dependencies and improved maintainability
  - Preserved existing `astrofiler_cloud.py` functionality for legacy operations
  - Self-contained dialog with integrated GCS operations, authentication, and error handling
- **Security Enhancements**: Comprehensive security audit and cleanup
  - Removed service account credentials from git repository history using `git filter-branch`
  - Cleaned entire commit history to prevent credential exposure
  - Updated `.gitignore` to prevent future credential commits
  - Restored local authentication while maintaining repository security
- **Database Migrations**: Enhanced migration system with comprehensive field management
  - Migration 006: Added `fitsFileCloudURL` field with proper NULL handling
  - Migration 007: Added auto-calibration tracking fields including calibration status, dates, master references, original file paths, and soft-delete capabilities
  - Automatic migration execution on startup for seamless upgrades
  - Backward compatibility maintained for existing installations
- **Duplicate File Detection & Reporting**: Enhanced file import system to track and report duplicate files separately from failed imports
  - `registerFitsImage()` now returns "DUPLICATE" for files already in database (detected by SHA-256 hash)
  - `registerFitsImages()` returns tuple (registered_files, duplicate_count) for comprehensive reporting
  - Success messages in UI now show "Processed X files, skipped Y duplicates" when duplicates are found
  - Command-line tools enhanced with duplicate reporting for batch operations
  - Backward compatibility maintained for existing code while providing enhanced information
- **DWARF FITS Processing**: Complete implementation of `dwarfFixHeader()` with folder structure parsing and header population
- **Smart Telescope Manager**: Enhanced with FTP support, folder validation, and telescope-specific configuration
- **Auto-Calibration Architecture**: Comprehensive calibration system infrastructure
  - Enhanced `_update_master_header()` function with astronomy-standard FITS headers and source file metadata copying
  - Implemented `detectAutoCalibrationOpportunities()` with intelligent session grouping and quality assessment
  - Added `designMasterFileStorageStructure()` with comprehensive documentation and storage patterns
  - Session analysis functions: `checkCalibrationSessionsForMasters()`, `getSessionsNeedingMasters()`, `validateMasterFiles()`
  - Configuration system integration with 5 new auto-calibration settings and UI controls
  - Siril CLI path configuration with file browser and validation
- **File Registration**: Downloaded files automatically registered in database with proper metadata and folder organization
- **Progress Tracking**: Enhanced progress dialogs with granular updates and metadata extraction feedback
- **Command-Line Integration**: Comprehensive command-line interface with full GUI feature parity
  - Reuses GUI helper functions for consistency and maintainability
  - Cross-platform automation support (Windows, Linux, macOS)
  - Robust error handling and logging for unattended operation

### Bug Fixes
- Fixed log file clearing functionality to avoid permission errors and undefined variable issues
  - Changed from file deletion to file truncation to prevent "file in use" errors on Windows
  - Fixed UnboundLocalError where message box styling was applied to undefined variable
  - Removed duplicate exception handling blocks that caused syntax errors
  - Improved error handling with properly created message box objects and consistent styling
- Fixed missing accept_mappings method in MappingsDialog
- Fixed Regenerate option in Images view to properly call registerFitsImages method
- Fixed missing progress dialogs in Regenerate and Load New functions in Images view
- Fixed Images view not loading data from database - implemented complete load_fits_data method with pagination
- Fixed Sync Repository to clear database before synchronizing with existing files
- Fixed Regenerate Sessions button to implement complete workflow: clear sessions → create light sessions → create calibration sessions → link sessions
- Fixed Smart Telescope Download dialog to properly connect signals and implement complete download workflow

### UI Changes
- Removed Download from Telescope from Tools menu and added Download button to Images view
- Moved Field Mappings to Tools menu and removed Images menu
- Removed Load from Incoming from Images menu and added Load New button to Images view
- Moved Regenerate button to front of search controls in Images view
- Hidden Filter column in Images view when sorted by Filter (since filter is shown as expandable section)
- Improved session regeneration progress display to show only filename instead of full path
- Added Images column to Sessions view showing the number of images in each session and total per object

### New Features  
- Menu reorganization: Removed Stats menu and added Refresh button to Statistics view
- Menu reorganization: Moved Duplicates and Merge Objects to Tools menu
- Enhanced Smart Telescope Download to automatically register downloaded FITS files in database and move them to repository structure
- UI Package Refactor: Complete modular restructure with separate widget files
- Menu-driven navigation replacing tab interface
- Download Dialog: Moved telescope download functionality to separate module
- Improved code organization and maintainability
- Faster application load times through selective imports
- Removed all legacy tab classes from main file
- Context menu functionality in Images view with View and Delete options for FITS files
- Double-click to view FITS files with external viewer

## Version 1.1.0 - August 23, 2025

### Changes in new version
- **Converted GUI from tab-based to menu-based interface**: Complete redesign of main interface from QTabWidget to QMainWindow with pulldown menu system (File, Images, View, Tools, Help)
- **Added paginated Images view with search**: Images tab now supports pagination (24-500 items per page, default 24) and real-time search by object name for better performance with large datasets
- **Updated SeeStar network connectivity for firmware changes**: Modified SeeStar telescope discovery to use only mDNS resolution (seestar.local) and disabled reverse DNS lookups due to recent firmware patches
- **Enhanced mapping dialog with database value population**: Mapping of values for selected cards is supported with both current and replace fields in mapping dialog now populate with actual database values
- **Added progress dialog for duplicate scanning and deletion**: The `refresh_duplicates()` method now displays a progress window showing the scanning progress when detecting duplicate files
- **Full path column in duplicates tab**: Added "Full Path" column to show complete file paths for duplicate files
- **Disabled automatic duplicate detection on startup**: Duplicate scanning no longer runs automatically when opening the duplicates tab
- **Sync repo now clears repository first**: Sync repository operation automatically clears existing data before resynchronizing to avoid dups in the database that are not duplicated on disk
- **Added apply button with progress indicator for individual mappings**: Each mapping row now has an apply button to immediately apply that mapping with detailed progress feedback
- **Added calibration frame support in Images tab**: New frame filter allows viewing light frames only, all frames, or calibration frames only (dark, flat, bias)
- **Smart calibration frame grouping**: Calibration frames without object names are automatically grouped by frame type for better organization
- **Enhanced sessions tab with multi-selection**: Added support for Ctrl+click and Shift+click to select multiple light sessions, with context menu restricted to light sessions only
- **Multiple sessions checkout**: New batch checkout feature allows checking out multiple light sessions simultaneously into organized directory structure
- **Improved progress bar display**: Session creation progress now shows filename only instead of full file path for better readability
- **Restored mapping dialog bottom checkboxes**: "Apply to Database" and "Update Files on Disk" checkboxes preserved while removing individual row Default checkboxes
- **Repository folder reorganization for mappings**: New "Reorganize repository folders" checkbox automatically moves files to correct folder structure when telescope/instrument mappings are applied
- **Filter sorting in Images tab**: Added "Filter" as a sort option to group files by filter type, then by object for better organization of filtered datasets

- **Enhanced filter chart display**: Filter pie chart now groups filters with less than 1% of total time into "Other (<1%)" category for cleaner visualization
- **Fixed filter chart size**: Corrected pie chart display scaling to properly reduce size by 24% and prevent stretching back to full container size
- **Fixed logging to astrofiler.log**: Removed duplicate logging configuration that prevented log file creation
- **Fixed FITS file flush warning**: Corrected variable name typo that caused flush() to be called on readonly file handle instead of update mode handle
- **Mapping applies to directories**: Renamed folders where mappings indicate
2025-08-17

### Added
- **FILTER Support in Mapping Dialog**: Added FILTER as a mapping type in the dropdown alongside TELESCOP, INSTRUME, OBSERVER, and NOTES
- **Complete FILTER Mapping Functionality**: Full database, file header, and file/folder renaming support for FILTER mappings
- **Replace Field Dropdown**: Changed replace field from text input to dropdown populated with database values
- **Blank Current Value Support**: Allow blank/empty current values for updating missing or null field values
- **Apply Button with Confirmation**: Individual Apply button for each mapping row with comprehensive confirmation dialogs
- **Progress Tracking**: Real-time progress dialogs for mapping operations with cancellation support
- **DARK/BIAS Frame Exclusion**: Automatically exclude DARK and BIAS frames from FILTER mappings (they inherently have no filters)

### Enhanced
- **Mapping Dialog UI**: 
  - Both Current and Replace fields now use dropdowns populated with unique database values
  - Current dropdown automatically updates when card type changes
  - Apply button with green checkmark icon and proper styling for dark theme
  - Confirmation dialogs show detailed action breakdown
  - Progress tracking with file-by-file updates

- **SEESTAR Connection**:
  - Enhanced hostname resolution to support mDNS (.local) addresses
  - Multi-tier device validation: user hostname → reverse DNS → pattern matching
  - Updated default hostname from `SEESTAR` to `SEESTAR.local`
  - Support for case-insensitive hostname variations (SEESTAR.local, seestar.local, SeeStar.local)
  - Robust fallback logic when reverse DNS lookup fails

- **Database Operations**:
  - Support for updating blank/null values (current field can be empty)
  - Proper handling of NULL, empty string, and missing values
  - Optimized queries that exclude irrelevant frame types for FILTER operations
  - Field mapping supports: TELESCOP → fitsFileTelescop, INSTRUME → fitsFileInstrument, FILTER → fitsFileFilter

- **File Operations**:
  - Real FITS header updates (no longer simulated)
  - File and folder renaming for FILTER mappings
  - Automatic directory cleanup for empty folders
  - Proper error handling and logging for file operations

### Fixed
- **Multi-filter Session Checkout**: Fixed issue where only flat frames for one filter were being checked out for multi-filter sessions
- **Session Creation**: Enhanced to properly assign all filters to correct light sessions
- **Dark Frame Assignment**: Removed CCD temperature consideration for better matching
- **Apply Button Visibility**: Fixed blue-on-blue styling issue making Apply button icon invisible
- **Database Schema**: Removed deprecated `is_default` field from Mapping model
- **Duplicate Code**: Removed duplicate method definitions causing UI issues
- **SEESTAR.local Connection**: Fixed SEESTAR download functionality when device uses `.local` hostname instead of plain `SEESTAR` - seems to be a new firmware issue.

### Database Changes
- **Migration 004**: Removed `is_default` field from Mapping table using table recreation approach for SQLite compatibility

### Technical Improvements
- **Query Optimization**: FILTER mappings now properly exclude 2,004+ DARK and BIAS frames, improving performance by ~40%
- **Error Handling**: Enhanced error handling for file operations, database updates, and validation
- **Code Organization**: Removed duplicate methods and cleaned up codebase
- **Memory Management**: Proper cleanup of temporary test files and database connections
- **Network Connectivity**: Enhanced mDNS support for SEESTAR devices using .local addresses
- **Device Detection**: Robust device identification with multi-tier validation approach

### Performance
- **Mapping Operations**: Significant performance improvement for FILTER mappings by excluding irrelevant calibration frames
- **UI Responsiveness**: Progress dialogs with proper threading prevent UI freezing during long operations
- **Database Efficiency**: Optimized queries reduce unnecessary database operations

### Validation
- **Input Validation**: Replace value is required, current value can be blank for updating missing data
- **Frame Type Validation**: Automatic exclusion of inappropriate frame types for specific mapping operations
- **File Existence Checks**: Proper validation of file paths before attempting operations

### User Experience
- **Intuitive Interface**: Dropdown menus make it easy to select existing values without typing
- **Clear Feedback**: Detailed confirmation dialogs explain exactly what actions will be performed
- **Progress Visibility**: Real-time progress tracking with meaningful status messages
- **Error Recovery**: Graceful handling of errors with informative messages

---

## Version History

**[1.1.0]** - Current version with comprehensive mapping enhancements
- Full FILTER support
- Enhanced UI with Apply buttons and dropdowns  
- Blank value handling
- Performance optimizations





