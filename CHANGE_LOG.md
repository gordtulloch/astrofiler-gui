# AstroFiler Change Log

This document tracks major changes and new features in AstroFiler.

## Version 1.1.0

### New Features
- **Smart Telescope Integration**: Cross-platform SMB/CIFS support for SEESTAR and other smart telescopes
  - **Network Discovery**: Automatic scanning for telescopes on local network
  - **FITS File Download**: Direct download of FITS files from telescope storage with progress tracking
  - **Header Modification**: Automatic OBJECT and MOSAIC header updates based on folder structure
  - **Filtered Folder Scanning**: Only scans folders ending with "_sub" for targeted data retrieval
  - **Progress Dialog**: Real-time download progress with file-by-file status updates
  - **Cancellation Support**: Graceful download cancellation with proper cleanup
  - **Delete Files on Host**: Optional deletion of files from telescope after successful download and processing
    - **Safety Confirmation**: Double confirmation dialog before enabling deletion
    - **Post-Processing Deletion**: Files only deleted after successful download and database registration
    - **Error Handling**: Comprehensive error reporting for deletion failures
    - **Selective Deletion**: Only successfully processed files are deleted from the host
- **Master Calibration Frame Creation**: New "Create Masters" button in Sessions tab
- **Siril CLI Integration**: Automated master bias, dark, and flat frame creation using Siril CLI
- **Enhanced Session Tracking**: Added `fitsBiasMaster`, `fitsDarkMaster`, and `fitsFlatMaster` fields to track master calibration frames
- **Database Migration System**: Implemented peewee-migrate for database version control and schema migrations
- **Performance Optimization**: File linking instead of copying during master creation for improved efficiency
- **Mapping Functionality**: Comprehensive FITS header field mapping and standardization system
  - **Mapping Dialog**: New modal dialog for creating and managing field mappings
  - **Database Integration**: Mapping table with support for TELESCOP, INSTRUME, OBSERVER, and NOTES fields
  - **File/Folder Renaming**: Automatic renaming of files and folders based on mapping rules
  - **Progress Tracking**: Real-time progress dialogs for mapping operations
  - **Batch Operations**: Apply mappings to all files in repository with comprehensive status reporting
  - **Automatic Load Repo Integration**: Mappings automatically applied during file import process

### Improvements
- **Intelligent File Handling**: Uses symbolic links, hard links, or copying (in that order) for optimal performance
- **Enhanced User Interface**: 
  - Moved Mapping button from Merge tab to Images tab for better workflow
  - Improved delete button styling with red color for better visibility
  - Dynamic row management in mapping dialog with add/delete functionality
  - Top-justified layout for mapping rows in dialog
- **Database Operations**: 
  - Comprehensive FITS header updates with mapping application
  - Automatic database path updates when files/folders are renamed
  - Support for both specific value mappings and default mappings for null/empty values
- **Automatic FITS Header Standardization**: 
  - Mappings automatically applied during Load Repo operations
  - Header modifications properly tracked and saved to disk when configured
  - Seamless integration with existing file processing workflow

### Technical Changes
- **Smart Telescope Module**: New `astrofiler_smart.py` module with comprehensive SMB/CIFS support
  - `SmartTelescopeManager` class for telescope communication and file operations
  - `ProgressFileWrapper` for cancellation-aware file downloads with progress tracking
  - Cross-platform network scanning using socket connections on port 445
  - Guest credential authentication for SEESTAR telescopes
  - Robust error handling and connection management
- **GUI Threading**: Enhanced Qt threading implementation for smart telescope operations
  - `TelescopeDownloadWorker` QThread for non-blocking downloads
  - `SmartTelescopeDownloadDialog` with real-time progress updates
  - Proper signal-slot communication for thread safety
  - Graceful cancellation handling with worker thread termination
- **File Deletion System**: Secure file deletion with multiple safety checks
  - SMB `deleteFiles()` operation for remote file removal
  - Confirmation dialogs with clear warnings about permanent deletion
  - Only delete files after successful local processing and database registration
  - Comprehensive error logging for deletion failures
- Added migration system with `migrate.py` script and `migrations/` directory
- Enhanced database models with master calibration frame fields
- Siril CLI integration for master creation and image stacking
- Updated launch scripts to automatically apply database migrations
- **Mapping System Implementation**:
  - Added `Mapping` database model with migration `003_add_mapping_table.py`
  - Implemented `MappingsDialog` class with comprehensive UI and functionality
  - Added `apply_database_mappings()` and `apply_file_folder_mappings()` methods
  - Integrated progress dialogs and error handling for all mapping operations
  - Added comprehensive test suite with 12 tests covering all mapping functionality
  - **New `mapFitsHeader()` function**: Automatically applies mappings during file processing
    - Supports specific value mappings and default value assignments
    - Handles missing cards and empty/unknown values intelligently
    - Integrates seamlessly with Load Repo workflow
    - Proper error handling and logging for all mapping operations

### Documentation
- Added `SMART_TELESCOPE_GUIDE.md` with comprehensive smart telescope usage guide
- Added `MASTER_CREATION.md` with comprehensive usage guide
- Added `MIGRATIONS.md` with database migration documentation
- Updated `README.md` with smart telescope features and technical requirements
- Updated `CHANGE_LOG.md` with new features and requirements

## Version 1.0.0

### Initial Release
- Core FITS file processing and database management
- Session creation and calibration linking
- GUI interface with multiple tabs for different functions
- Basic repository management and file organization
- Logging and configuration management
