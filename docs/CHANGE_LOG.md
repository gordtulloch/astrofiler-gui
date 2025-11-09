# AstroFiler Change Log

## Version 1.2.0 - Current Development

### New Features

- **Advanced Quality Analysis System**: SEP-based image quality assessment integrated into AutoCalibration workflow
  - **SEP Integration**: Source Extractor Python (SEP) library for robust star detection and photometry with automatic background subtraction and advanced source extraction algorithms
  - **Enhanced Quality Metrics**: Comprehensive quality analysis including average FWHM in arcseconds, star eccentricity (0-1 scale), Half Flux Radius (HFR) in arcseconds, image signal-to-noise ratio, detected star count, and image scale calculation from FITS headers
  - **Dual Detection Methods**: Primary SEP-based detection with photutils DAOStarFinder fallback for maximum reliability across different image conditions
  - **Database Integration**: New quality metrics fields in fitsFile table via Migration 009: `fitsFileAvgFWHMArcsec`, `fitsFileAvgEccentricity`, `fitsFileAvgHFRArcsec`, `fitsFileImageSNR`, `fitsFileStarCount`, `fitsFileImageScale`
  - **AutoCalibration Integration**: Quality analysis fully integrated into AutoCalibration workflow with progress tracking, real-time feedback, and automatic database updates
  - **Advanced Image Scale Detection**: Multi-method image scale calculation using WCS headers, PIXSCALE/SCALE keywords, CDELT values, focal length calculations, and instrument-specific defaults
  - **Robust Error Handling**: Graceful fallback mechanisms, comprehensive parameter validation, and detailed logging for troubleshooting
  - **Performance Optimization**: Configurable star count limits (3-200 stars), efficient source filtering, and optimized processing for large datasets
  - **Professional Accuracy**: Astronomy-grade calculations with proper units conversion, scientific validation, and industry-standard methodologies
  - **Progress Callback System**: Real-time progress updates with descriptive status messages, cancellation support, and 5-phase workflow tracking
  - **CLI Integration**: Full command-line support through AutoCalibration.py with quality assessment mode, batch processing, and automated reporting

- **Enhanced Installation System**: Streamlined pysiril installation across all platforms with automatic download capabilities
  - **Automated Wheel Installation**: All install scripts now automatically detect and install pysiril wheel files with `--force-reinstall` for clean installation
  - **Automatic Download Support**: When wheel files not found, scripts automatically download latest pysiril build artifacts from GitLab CI/CD pipeline
  - **Multi-Platform Coverage**: Enhanced Windows PowerShell (`install.ps1`), Linux (`install.sh`), and macOS (`install_macos.sh`) scripts with platform-specific optimizations
  - **Fallback Installation**: Git source installation as secondary method when artifact download fails using `git+https://gitlab.com/free-astro/pysiril.git`
  - **PyWinInstall Integration**: Special `PyWinInstall.Special.bat` script for automated SETUP.EXE installations with PowerShell-based download, extraction, and validation
  - **Robust Error Handling**: Comprehensive error checking, temporary file cleanup, network failure recovery, and informative user feedback
  - **Silent Operation**: Automated installations suitable for unattended deployment with progress tracking and verification steps
  - **Cross-Platform Tools**: Uses native tools (PowerShell, curl, wget, unzip) for reliable operation across different environments
  - **Installation Verification**: Post-installation verification with version checking and import testing to confirm successful setup

- **iTelescope Smart Telescope Integration**: Revolutionary integration with iTelescope remote observatory network
  - **Secure FTPS Connection**: Direct connection to data.itelescope.net using FTPS (FTP over TLS) for encrypted data transfer
  - **Selective Root Directory Scanning**: Intelligent scanning that only explores root directories starting with 'T' or 't' to focus on telescope directories
  - **Compressed FITS Support**: Handles iTelescope's .fit.zip format for efficient file transfer and storage
  - **Automatic File Discovery**: Recursively scans telescope directories for calibrated FITS files (files starting with "calibrated")
  - **Configuration Integration**: Added iTelescope credentials configuration in Smart Telescopes tab of Config dialog
  - **Progress Tracking**: Real-time download progress with file-by-file status updates and comprehensive error handling
  - **Metadata Extraction**: Automatic extraction of object names, file sizes, dates, and paths from iTelescope file structure
  - **Secure Authentication**: Username/password authentication with TLS encryption for all data transfers
  - **Smart Telescope Framework Integration**: Fully integrated with existing telescope management system alongside SeeStar, StellarMate, and DWARF support

- **Tabbed Configuration Interface**: Complete redesign of configuration dialog for improved usability
  - **General Tab**: Consolidated General Settings, Display Settings, External Tools, and Suppress Warnings
  - **Cloud Sync Tab**: Dedicated tab for all cloud synchronization settings and authentication
  - **Calibration Tab**: Focused tab for Auto-Calibration configuration and master frame settings  
  - **Smart Telescopes Tab**: New dedicated tab for telescope-specific configurations including iTelescope credentials
  - **Improved Organization**: Logical grouping reduces interface clutter and improves configuration workflow
  - **Better User Experience**: Tabbed interface allows for larger, more detailed configuration sections without overwhelming the user

- **FITS File Compression System**: Revolutionary lossless compression for astronomical images with significant space savings
  - **Lossless Gzip Compression**: Implements industry-standard gzip compression achieving 30-70% file size reduction while preserving all FITS metadata and image data
  - **Transparent Operation**: Compressed files seamlessly replace originals with `.Z` extension maintaining full compatibility with existing workflows
  - **Configuration-Driven Activation**: Enable compression through `astrofiler.ini` with `compress_fits=True` setting for new file imports
  - **Advanced Compression Options**: Configurable compression level (1-9, default: 6), optional integrity verification, and minimum file size thresholds
  - **Smart Integration**: Automatic compression during Download and LoadRepo operations with graceful error handling and fallback to uncompressed files
  - **Professional Verification**: Optional hash-based verification ensures perfect compression fidelity with zero data loss
  - **Performance Optimized**: Fast compression/decompression suitable for real-time processing with configurable parameters for optimal speed/size balance
  - **Core Module Architecture**: New `compress_files.py` module with `FitsCompressor` class providing complete compression lifecycle management
  - **Seamless File Processing**: Integrated into `FileProcessor` class for automatic compression during file registration and import workflows
  - **Configuration Settings**: 
    - `compress_fits`: Enable/disable compression (default: False)
    - `compression_level`: Compression level 1-9 (default: 6)  
    - `verify_compression`: Enable integrity verification (default: True)
    - `min_compression_size`: Minimum file size to compress in bytes (default: 1024)
  - **Command-Line Testing**: Includes comprehensive test suite (`test_compression.py`) for validation and troubleshooting
  - **Future-Ready Architecture**: Designed for expansion to additional compression algorithms and advanced storage optimizations

### Fixes
- **FRAME cards** - images with FRAME cards but no IMAGETYP have had  
- **Cloud Sync Header Modification Issue**: Fixed critical issue where downloaded files were being re-uploaded due to FITS header modifications during registration
  - Problem: Files downloaded from cloud had headers modified (FRAME → IMAGETYP, etc.) during database registration, causing hash changes
  - Solution: Cloud sync now detects when downloaded files were modified and replaces the cloud version instead of creating duplicates
  - Prevents accumulation of near-duplicate files in cloud storage with only header differences
  - Enhanced logging shows when files are being "replaced after download" vs normal uploads
  - Tracks replaced file count separately in sync reports for transparency  

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
  - **Enhanced Cloud Safety System**: Revolutionary safety features for data protection and automated calibration file management
    - **Cloud Verification Before Deletion**: Mandatory cloud backup verification using `check_file_exists_in_gcs()` before any local file deletion, preventing data loss from failed uploads
    - **Soft-Deleted File Management**: Automatic handling of calibration files marked for deletion after master frame creation with `fitsFileSoftDelete` database field tracking
    - **Smart Sync Profile Behavior**: 
      - Complete Sync: Maintains files in both local and cloud storage (NO deletion of soft-deleted files)
      - Backup Sync: Uploads and safely deletes soft-deleted files after cloud verification
      - On Demand Sync: Targets only soft-deleted files for immediate upload and cleanup with verification
    - **Master Frame Cloud Integration**: All master calibration frames automatically included in cloud backup operations through enhanced database queries
    - **Safety Error Handling**: Comprehensive error management with graceful fallbacks - if cloud verification fails, local files are preserved with detailed error logging
    - **Enhanced CLI Safety**: All command-line cloud sync operations include identical safety checks with cloud verification before deletion
    - **Intelligent File Detection**: Updated queries to include all file types (regular FITS, soft-deleted calibration files, master frames) in appropriate sync operations
  - **Advanced Duplicate Detection and Hash-Based Optimization**: Revolutionary performance and storage optimization features
    - **MD5 Hash-Based Duplicate Prevention**: Intelligent upload prevention system that calculates MD5 hashes for local files and compares with cloud metadata to avoid duplicate uploads
    - **Bulk Cloud Metadata Retrieval**: Efficient cloud file hash collection using Google Cloud Storage metadata API, dramatically reducing API calls and improving sync performance
    - **Smart Upload Decision Logic**: Three-tier upload decision system - skip identical files (MD5 match), upload new files, and overwrite files with different content
    - **Enhanced Sync Performance**: Bulk hash comparison operations replace individual file checks, resulting in significantly faster sync operations and reduced bandwidth usage
    - **Comprehensive Progress Reporting**: Enhanced progress dialogs with "Checking cloud for existing files" phase, efficiency statistics showing files skipped vs uploaded, and detailed completion summaries
    - **Cloud Duplicate Analysis**: Advanced duplicate detection in cloud storage during Analyze operations
      - **Hash-Based File Grouping**: Groups cloud files by MD5 hash to identify identical content stored under different names or paths
      - **Wasted Space Calculation**: Calculates storage space wasted by duplicate files with human-readable size formatting (MB/GB/TB)
      - **Detailed Duplicate Reports**: Optional detailed view showing duplicate groups, file paths, and wasted space per group with professional formatting
      - **Enhanced Analysis Results**: Comprehensive analysis statistics including duplicate groups found, total duplicate files, and storage optimization opportunities
    - **Advanced File Matching for Analysis**: Multi-tier local file matching system combining exact filename matching, partial filename matching, and hash-based content verification for maximum accuracy
    - **Consistent Hash Implementation**: Unified hash-based duplicate detection across both Sync and Analyze operations ensuring consistent behavior and accurate results

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
  - **Soft Deletion and Cloud Integration**: Revolutionary automated cleanup system for calibration files
    - **Automatic Soft Deletion**: Calibration files used to create master frames are automatically marked with `fitsFileSoftDelete=True` after successful master creation
    - **Cloud Sync Integration**: Soft-deleted files are automatically uploaded to cloud storage and safely removed from local storage during sync operations
    - **Safety First Architecture**: Local files are never deleted without verification that they exist in cloud storage using mandatory cloud backup verification
    - **Storage Optimization**: Frees up significant disk space by moving processed calibration files to cloud while maintaining full data integrity and accessibility
- **Professional Light Frame Calibration**: Advanced PySiril-powered light frame calibration system for production-quality results
  - **calibrateLights.py Command**: Comprehensive command-line utility for light frame calibration using PySiril integration
    - **Flexible Input Options**: Process by session ID (`-s`), object name (`-o`), or specific file list (`-f`) with automatic database integration
    - **Smart Master Detection**: Automatically finds appropriate master calibration frames from AstroFiler database or specified directories
    - **PySiril Integration**: Professional-grade processing using Siril's proven calibration engine for maximum compatibility and quality
    - **CFA/OSC Support**: Complete Color Filter Array processing with automatic detection and optional debayering for one-shot color cameras
    - **Complete Pipeline Options**: Individual calibration, calibration + registration, calibration + stacking, or full pipeline processing
    - **Quality Assessment Integration**: Built-in FWHM analysis, noise metrics, star detection, and quality scoring with configurable thresholds
    - **Batch Processing**: Efficient processing of large datasets with progress tracking and comprehensive error handling
    - **Flexible Output Options**: Individual calibrated frames or stacked master light frames with customizable stacking parameters
  - **Advanced Processing Features**:
    - **Registration/Alignment**: Optional star-based frame registration using Siril's proven algorithms
    - **Intelligent Stacking**: Multiple stacking methods (median, average, sigma-clipping) with configurable rejection parameters
    - **Normalization Options**: Additive scale, multiplicative scale, or no normalization for different imaging scenarios  
    - **Multi-Threading**: Configurable thread count for optimal performance on multi-core systems
    - **Temporary File Management**: Intelligent temporary directory handling with optional cleanup or preservation for debugging
  - **Automation Support**:
    - **Windows Automation**: `cron_calibrate_lights.bat` script with Task Scheduler integration and multiple operation modes
    - **Linux/macOS Automation**: `cron_calibrate_lights.sh` script with cron integration and comprehensive logging
    - **Operation Modes**: Auto calibration, session-specific, object-specific, quality assessment only, and help modes
    - **Monitoring Integration**: Automatic log cleanup, error flag creation, and timestamped logging for system monitoring
  - **Prerequisites**: Requires Siril 1.4+ installation and PySiril Python package for professional-grade processing capabilities
  - **Calibration Session Analysis**: Automated detection of calibration opportunities with session matching by telescope, instrument, binning, temperature (±5°C), and filter criteria
  - **Master File Storage Structure**: Organized `/Masters` directory with standardized naming conventions and comprehensive metadata tracking
  - **Configuration Interface**: Complete auto-calibration settings in Configuration dialog including enable/disable toggle, minimum files per master (default: 3), and progress tracking options
  - **Database Integration**: Enhanced schema with 7 new calibration tracking fields via Migration 007: `fitsFileCalibrationStatus`, `fitsFileCalibrationDate`, master frame references, original file tracking, and soft-delete capabilities for cloud cleanup integration
  - **Enhanced FITS Headers**: Comprehensive master frame headers with `IMAGETYP` (MasterBias/MasterDark/MasterFlat), source file metadata copying, processing history, quality metrics placeholders, and astronomy workflow compatibility
  - **Filesystem Sanitization**: Comprehensive filename and path sanitization system for cross-platform compatibility
    - **Universal Sanitization Function**: `sanitize_filesystem_name()` handles all invalid characters (spaces, slashes, colons, asterisks, quotes, pipes, etc.) with underscore replacement
    - **FITS Header Compliance**: All FITS header keywords shortened to ≤8 characters per FITS standard (QUALSTD, QUALMEAN, QUALREJ, QUALSCOR)
    - **Master Frame Naming**: Standardized naming convention using underscores for cross-platform compatibility (Master_Bias_Telescope_Instrument_Binning_Date.fits)
    - **Repository Organization**: Applied sanitization throughout folder creation, file naming, and metadata extraction for consistent filesystem structure
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

- **Enhanced FITS Header Metadata**: Comprehensive calibration metadata system for professional astronomy workflows
  - **Calibration Identification**: CALIBRAT='Y', IMAGETYP='Light (Calibrated)', CALDATE timestamp, and CALSOFT='AstroFiler' headers for clear calibration status
  - **Master Frame References**: BIASMAST, DARKMAST, FLATMAST with full file paths and corresponding MD5 checksums (BIASMD5, DARKMD5, FLATMD5) for verification
  - **Frame Count Tracking**: BIASCNT, DARKCNT, FLATCNT headers recording number of frames used in each master calibration frame
  - **Processing History**: CALSTEPS counter with detailed STEP1-STEP9 processing log documenting complete calibration workflow
  - **Quality Metrics**: CALMEAN, CALSTD, CALNOISE, CALSNR headers providing statistical analysis of calibrated frame quality
  - **Astronomy Software Compatibility**: Industry-standard headers for seamless integration with PixInsight, MaxIm DL, and other professional astronomy applications
  - **MD5 Verification**: Automatic calculation and storage of master frame checksums enabling integrity validation of calibration references

- **Advanced UI Status Indicators**: Professional visual calibration status system with comprehensive user feedback
  - **Enhanced Status Summary Bar**: Real-time calibration coverage statistics with color-coded progress bar (green/yellow/orange/red), light session counts, and visual legend for calibration indicators
  - **Smart Calibration Column**: Color-coded backgrounds based on completeness (100%=green, 67-99%=yellow, 33-66%=orange, 0-32%=red) with detailed hover tooltips
  - **Visual Calibration Icons**: Colored shape system - blue circles (bias), dark squares (dark), orange triangles (flat), green circles (masters) for instant status recognition
  - **Parent Object Statistics**: Overall calibration coverage per object showing "calibrated_sessions/total_sessions (percentage%)" with matching color coding
  - **Interactive Elements**: Rich tooltips with calibration breakdown ("✓ Bias frames available", "✗ No dark frames"), hover details, and comprehensive status explanations
  - **Automatic Updates**: Status indicators refresh dynamically when calibration data changes, ensuring real-time accuracy

- **Existing File Registration System**: Intelligent duplicate work prevention with comprehensive file discovery
  - **Master Frame Detection**: Multi-method identification via filename patterns (Master-Bias, Master-Dark, etc.) and FITS headers (IMAGETYP, CALTYPE, OBJECT)
  - **Calibrated Light Detection**: FITS header analysis for CALIBRAT='Y', CALDATE, CALSOFT, and master frame references (BIASMAST, DARKMAST, FLATMAST)
  - **Smart Database Integration**: Automatic updates of fitsFileCalibrated status, calibration dates, and master frame references for existing files
  - **Session Linking**: Intelligent matching of discovered master frames to appropriate sessions based on telescope, instrument, and binning parameters
  - **Consistency Validation**: Broken reference cleanup, orphaned file detection, and database integrity maintenance
  - **UI Integration**: "Register Existing" button with options dialog (recursive scanning, header verification) and comprehensive results reporting
  - **CLI Support**: RegisterExisting.py command-line tool with full automation capabilities, dry-run mode, and batch processing for unattended operation

- **Professional Context Menu System**: Comprehensive master frame management with enhanced UI integration
  - **Smart Context-Aware Menus**: Dynamic menu adaptation based on selection type (light sessions, calibration sessions, parent objects)
  - **Master Frame Operations**: Create master frames (🔨), view detailed master info (👁️), validate integrity (✅), and link sessions to masters (🔗)
  - **Calibration Management**: View detailed calibration status (📊), calibrate light frames (🌟), browse master files (📁), and cleanup operations (🧹)
  - **Session Tools**: Refresh calibration links (🔄), export session information to CSV (📤), and comprehensive properties dialog (🔍)
  - **Visual Enhancement**: Emoji icons for menu clarity, hierarchical organization with submenus, descriptive tooltips, and professional styling
  - **Batch Operations**: Multi-session support for master creation, validation, calibration, and link management with progress tracking
  - **Information Dialogs**: Detailed master frame properties with FITS header analysis, file system information, and quality assessment results

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
- **Enhanced Quality Analysis Module**: Complete refactoring of quality assessment system with professional-grade architecture
  - **New `enhanced_quality.py` Module**: Comprehensive quality analyzer with `EnhancedQualityAnalyzer` class for modular, reusable quality assessment
  - **SEP Integration Architecture**: Primary SEP-based detection with photutils fallback, robust parameter validation, and graceful error handling
  - **Database Integration Methods**: `update_file_quality_metrics()` and `analyze_and_update_file()` methods for seamless database operations
  - **Multi-Method Image Scale Detection**: `_calculate_image_scale()` with WCS, header keywords, focal length calculations, and instrument-specific defaults
  - **Advanced Star Analysis Pipeline**: Comprehensive star property analysis including FWHM radial profiling, eccentricity moments calculation, and HFR measurement
  - **Robust Error Handling**: Graceful degradation with detailed logging, parameter validation, and comprehensive fallback mechanisms
  - **Progress Callback Integration**: Built-in progress tracking with descriptive status messages and cancellation support
  - **Professional Code Organization**: Clean separation of concerns with dedicated methods for detection, analysis, and database operations
  - **Scientific Accuracy**: Astronomy-grade calculations with proper units conversion, statistical validation, and industry-standard methodologies
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





