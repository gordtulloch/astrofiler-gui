# AstroFiler Change Log

## Version 1.2.0 - Current Development

### New Features
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
- **Duplicate File Detection & Reporting**: Enhanced file import system to track and report duplicate files separately from failed imports
  - `registerFitsImage()` now returns "DUPLICATE" for files already in database (detected by SHA-256 hash)
  - `registerFitsImages()` returns tuple (registered_files, duplicate_count) for comprehensive reporting
  - Success messages in UI now show "Processed X files, skipped Y duplicates" when duplicates are found
  - Command-line tools enhanced with duplicate reporting for batch operations
  - Backward compatibility maintained for existing code while providing enhanced information
- **DWARF FITS Processing**: Complete implementation of `dwarfFixHeader()` with folder structure parsing and header population
- **Smart Telescope Manager**: Enhanced with FTP support, folder validation, and telescope-specific configuration
- **File Registration**: Downloaded files automatically registered in database with proper metadata and folder organization
- **Progress Tracking**: Enhanced progress dialogs with granular updates and metadata extraction feedback

### Bug Fixes
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





