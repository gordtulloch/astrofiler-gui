# AstroFiler Change Log

## Version 1.1.0 - August 23, 2025

### Changes in new version
- **Enhanced mapping dialog with database value population**: Mapping of values for selected cards is supported with both current and replace fields in mapping dialog now populate with actual database values
- **Added progress dialog for duplicate scanning and deletion**: The `refresh_duplicates()` method now displays a progress window showing the scanning progress when detecting duplicate files
- **Full path column in duplicates tab**: Added "Full Path" column to show complete file paths for duplicate files
- **Disabled automatic duplicate detection on startup**: Duplicate scanning no longer runs automatically when opening the duplicates tab
- **Sync repo now clears repository first**: Sync repository operation automatically clears existing data before resynchronizing to avoid dups in the database that are not duplicated on disk
- **Added apply button with progress indicator for individual mappings**: Each mapping row now has an apply button to immediately apply that mapping with detailed progress feedback
- **Added calibration frame support in Images tab**: New frame filter allows viewing light frames only, all frames, or calibration frames only (dark, flat, bias)
- **Smart calibration frame grouping**: Calibration frames without object names are automatically grouped by frame type for better organization
- **Fixed SEESTAR telescope connectivity**: Updated default hostname from "SEESTAR" to "SEESTAR.local" to resolve network discovery issues
- **Enhanced sessions tab with multi-selection**: Added support for Ctrl+click and Shift+click to select multiple light sessions, with context menu restricted to light sessions only
- **Multiple sessions checkout**: New batch checkout feature allows checking out multiple light sessions simultaneously into organized directory structure
- **Improved progress bar display**: Session creation progress now shows filename only instead of full file path for better readability
- **Restored mapping dialog bottom checkboxes**: "Apply to Database" and "Update Files on Disk" checkboxes preserved while removing individual row Default checkboxes
- **Fixed logging to astrofiler.log**: Removed duplicate logging configuration that prevented log file creation
- **Fixed FITS file flush warning**: Corrected variable name typo that caused flush() to be called on readonly file handle instead of update mode handle
- **Mapping applies to directories**: Renamed folders where mappings indicate




