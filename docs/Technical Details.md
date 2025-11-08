# 🔬 Technical Details

## Architecture

- **Frontend**: PySide6 (Qt6) for cross-platform GUI
- **Database**: SQLite with Peewee ORM for data persistence
- **FITS Processing**: AstroPy for astronomical file handling
- **Configuration**: INI file format for settings storage

## Dependencies

- **astropy**: FITS file reading and metadata extraction
- **peewee**: Database ORM and SQLite management
- **numpy**: Numerical computations and data handling
- **matplotlib**: Plotting and visualization capabilities
- **pytz**: Timezone handling for astronomical observations
- **PySide6**: Modern Qt6-based GUI framework

## FITS File Processing

### File Registration (`astrofiler_file.py`)

**registerFitsImage()**: Core function that processes individual FITS files
- Validates FITS file format and essential headers
- Corrects WCS information when needed
- Generates standardized filenames based on metadata
- Creates appropriate directory structures
- Calculates SHA-256 hashes for duplicate detection

**Filename Generation Pattern**:
- **Light frames**: `{OBJECT}-{TELESCOPE}-{INSTRUMENT}-{FILTER}-{DATE}-{EXPOSURE}s-{BINNING}x{BINNING}-t{TEMP}.fits`
- **Calibration frames**: `{TYPE}-{TELESCOPE}-{INSTRUMENT}-{FILTER/DATE}-{DATE}-{EXPOSURE}s-{BINNING}x{BINNING}-t{TEMP}.fits`

### FITS Header Management

**Header Updates During File Processing**:
- **WCS Correction**: Adds CD matrix values when only CDELT/CROTA values are present

**Header Updates During Merge Operations**:
- **Object Name Updates**: When files are renamed, the OBJECT header is updated to match
- **Comment Addition**: Adds descriptive comments showing the change history
- **Safe Operation**: Uses `mode='update'` with proper error handling
- **Conditional Updates**: Only modifies headers when files are actually renamed on disk

### Session Management

**Session Creation Logic**:
- **Light Sessions**: Groups files by object name and observation date
- **Calibration Sessions**: Groups bias, dark, and flat frames by type, equipment, and date
- **Enhanced Matching**: Uses telescope, instrument, binning, gain, offset, exposure, temperature, and filter criteria

**Session Linking Algorithm**:
- **Bias Linking**: Matches telescope, instrument, binning, gain, and offset
- **Dark Linking**: Adds exposure time and CCD temperature (±5°C tolerance) matching
- **Flat Linking**: Adds filter matching for color-specific calibration

**Session Regeneration Workflow**:
The Sessions tab provides a consolidated "Regenerate" button that performs a complete session rebuild:

1. **Clear Phase**: Removes all existing session records and assignments from database
2. **Light Session Creation**: Groups light frames using `createLightSessions()` 
3. **Calibration Session Creation**: Groups calibration frames using `createCalibrationSessions()`
4. **Session Linking**: Links calibrations to lights using `linkSessions()`

**Progress Tracking Implementation**:
- **Multi-Phase Progress**: Overall progress dialog spans all four regeneration phases
- **Per-Phase Progress**: Individual progress callbacks for each operation type
- **Cancellation Support**: User can interrupt at any point with proper cleanup
- **Real-Time Updates**: Shows current file/session being processed with estimated completion

**Session Checkout System**:
- **Symbolic Link Creation**: Platform-aware linking (symlinks on Unix, junction points on Windows)
- **Directory Structure**: Creates Siril-compatible folder layout with lights/darks/flats/bias
- **Script Generation**: Automatically creates processing scripts for common workflows
- **Non-Destructive**: Original files remain untouched and in original locations

## Error Handling and Logging

### Comprehensive Error Management
- **File-Level Errors**: Individual file processing failures don't stop batch operations
- **FITS Header Errors**: Graceful handling of corrupted or missing headers
- **Database Errors**: Transaction rollback and detailed error reporting
- **File System Errors**: Safe handling of permission and disk space issues

### Logging System
- **Hierarchical Logging**: DEBUG, INFO, WARNING, ERROR levels
- **Operation Tracking**: Detailed logs for all file operations
- **Performance Metrics**: Processing time and file count statistics
- **User Feedback**: Real-time progress updates with cancellation support

## Database Schema Enhancements

### Session-Level Metadata Fields
Recent enhancements add telescope, instrument, and acquisition settings at the session level:
- `fitsSessionTelescope`: Telescope identifier
- `fitsSessionImager`: Camera/instrument identifier  
- `fitsSessionExposure`: Exposure time in seconds
- `fitsSessionBinningX/Y`: Pixel binning settings
- `fitsSessionCCDTemp`: Sensor temperature
- `fitsSessionGain`: Sensor gain setting
- `fitsSessionOffset`: Sensor offset setting
- `fitsSessionFilter`: Filter identifier

### Migration System
- **Automatic Migrations**: Database schema updates applied on startup
- **Data Preservation**: Existing data is preserved during schema changes
- **Error Recovery**: Graceful handling of migration failures

## Performance Optimizations

### Batch Processing
- **Progress Callbacks**: Real-time progress updates for long operations
- **Cancellation Support**: User can interrupt long-running processes
- **Memory Management**: Efficient handling of large FITS files
- **Background Processing**: Non-blocking operations where possible

### Caching System
- **Statistics Caching**: 300-second cache for expensive database queries
- **Smart Invalidation**: Cache cleared when underlying data changes
- **Memory Efficiency**: Prevents repeated expensive calculations
