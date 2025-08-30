# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-08-17

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
