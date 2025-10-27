# 📖 AstroFiler User Guide

Welcome to AstroFiler, a comprehensive astronomical image file management tool designed for astronomers and astrophotographers. This guide will walk you through all the features and functionality to help you efficiently manage and organize your FITS image files.

## 🚀 Getting Started

### First Launch
When you first launch AstroFiler, you'll see the main window with several tabs:
- **Stats** - Repository statistics and charts (default tab)
- **Images** - File browser and management
- **Sessions** - Observation session management
- **Merge** - Object name merging and renaming
- **Duplicates** - Duplicate file detection and removal
- **Log** - Application log viewer
- **Config** - Application settings
- **About** - Version and author information

### Initial Configuration
Before using AstroFiler, configure the basic settings in the **Config** tab:

1. **Source Path**: Directory where your incoming FITS files are stored
2. **Repository Path**: Directory where AstroFiler will organize your files
3. **FITS Viewer**: Path to your preferred external FITS viewer (optional)
4. **Theme**: Choose Light, Dark, or Auto theme
5. Click **Save Settings** to persist your configuration

---

## 📊 Stats Tab - Repository Analysis

The Stats tab provides comprehensive analysis of your imaging repository.

### Statistics Displayed

#### Recent Activity
- **Last 10 Objects Observed**: Most recently imaged targets
- **Observation dates**: When you last worked on each object

#### Top Targets
- **Top 10 Objects by Integration Time**: Your most imaged subjects
- **Total exposure times**: Hours invested per target
- **Ranking system**: See your imaging priorities

#### Summary Statistics
- **Total Files**: Count of all FITS files
- **Total Objects**: Number of unique targets
- **Total Sessions**: Observation sessions detected
- **File Type Breakdown**: Lights, darks, bias, flats distribution

#### Filter Analysis
- **Visual Chart**: Pie chart of imaging time by filter
- **Filter Distribution**: See which filters you use most
- **Integration Totals**: Hours per filter type

### Cache Management
- Statistics are cached for performance
- **Refresh Stats** button forces recalculation
- Cache status displayed for transparency

---

## 📁 Images Tab - File Management

The Images tab is your primary interface for managing FITS files.

### Main Functions

#### Load Repo
- Scans your source directory for FITS files
- Extracts metadata from FITS headers
- Renames files to descriptive format (names in CAPs FITS header fields)

    ```bash
    OBJECT-TELESCOP-INSTRUME-FILTER-EXPTIMEs-XBINNINGxYBINNING-tCCD-TEMP.fits
    Flat-TELESCOP-INSTRUME-FILTER-EXPTIMEs-XBINNINGxYBINNING-tCCD-TEMP.fits
    Dark-TELESCOP-INSTRUME-EXPTIMEs-XBINNINGxYBINNING-tCCD-TEMP.fits
    Bias-TELESCOP-INSTRUME-XBINNINGxYBINNING-tCCD-TEMP.fits
    ```

- Moves organized files to your repository

    Folder names:
    ```bash
    Light/OBJECT/TELESCOP/INSTRUME/DATE
    Calibrate/Dark/TELESCOP/INSTRUME/EXPTIME/DATE
    Calibrate/Flat/TELESCOP/INSTRUME/FILTER/DATE
    Calibrate/Bias/TELESCOP/INSTRUME/DATE
    ```

- Creates database entries with full metadata
- **Warning**: This process modifies file locations - test with sample data first

#### Sync Repo
- Scans existing repository for new or changed files
- Updates database without moving or renaming files
- Faster than Load Repo for existing repositories
- Safe for production data

#### Clear Repo
- Removes all database entries
- **Does not delete physical files**
- Use to reset the database catalog

#### Refresh
- Reloads the file tree from the current database

### File Organization

**Sort Options:**
- **Object**: Groups files by astronomical object, then by date
- **Date**: Groups files by observation date, then by object

**File Tree Columns:**
- **Object**: Target name (M31, NGC7000, etc.)
- **Type**: Light, Dark, Bias, Flat
- **Date**: Observation date and time
- **Exposure**: Exposure time in seconds
- **Filter**: Filter used (L, R, G, B, Ha, OIII, etc.)
- **Telescope**: Telescope model
- **Instrument**: Camera/detector
- **Temperature**: CCD temperature (°C)
- **Filename**: Current filename

### File Interactions
- **Double-click**: Opens file in configured external FITS viewer
- **Right-click**: Context menu with additional options

---

## 🎯 Sessions Tab - Observation Management

Sessions automatically group related light and calibration frames from the same observation period.

### Session Functions

#### Regenerate Button
Performs a complete session rebuild:
1. Clears existing sessions
2. Creates light sessions (groups light frames)
3. Creates calibration sessions (groups darks, bias, flats)
4. Links appropriate calibration sessions to light sessions

#### Session Linking
AstroFiler intelligently matches calibration frames to light sessions based on:
- **Telescope**: Same instrument setup
- **Camera**: Same detector
- **Binning**: Pixel binning factor
- **Gain/Offset**: Camera settings
- **Filter**: For flat field matching
- **Temperature**: ±5°C tolerance for dark frames
- **Date Proximity**: Calibration frames from nearby dates

### Session Display
- **Hierarchical Tree**: Objects → Sessions
- **Session Info**: Date, telescope, camera details
- **File Counts**: Number of lights and linked calibrations

### Session Checkout
Right-click on any session to **Check out**:
- Creates a temporary directory with symbolic links
- Organizes files in Siril-compatible structure:
  - `/lights/` - Light frames
  - `/darks/` - Dark frames  
  - `/bias/` - Bias frames
  - `/flats/` - Flat frames
- Generates processing scripts for external tools
- Non-destructive - original files remain untouched

---
## 🔄 Merge Tab - Object Management

The Merge tab allows you to rename and consolidate object names across your repository.

### Merge Functions

#### Preview Changes
- Shows what files would be affected
- Displays current vs. new object names
- Safe preview without making changes

#### Execute Merge
- Updates database records
- Optionally renames physical files
- Updates FITS headers with new object names
- Moves files to new directory structure if needed

### Merge Options
- **From Object**: Current object name to change
- **To Object**: New object name
- **Change/Move filenames**: Whether to rename physical files on disk

### Use Cases
- Consolidate variations: "M 31", "M31", "Andromeda" → "M31"
- Fix typos in object names
- Standardize naming conventions
- Merge accidentally split observations

---

## 🔍 Duplicates Tab - File Cleanup

Automatically detects and manages duplicate files using SHA-256 hash comparison.

### Duplicate Detection
- **Content-based**: Compares actual file content, not just names
- **Hash Groups**: Groups identical files together
- **Metadata Display**: Shows object, date, filter for each duplicate

### Duplicate Management
- **Safe Removal**: Keeps one copy of each duplicate group
- **File Information**: See all copies before deletion
- **Batch Processing**: Remove all duplicates at once

### Duplicate Sources
Common causes of duplicates:
- Multiple imports of the same files
- Copying files between directories
- Backup restoration
- File format conversions that create identical content

---

## 🔧 Config Tab - Application Settings

### General Settings
- **Source Path**: Where AstroFiler looks for new files
- **Repository Path**: Where organized files are stored
- **Refresh on Startup**: Auto-refresh data when app starts

### Display Settings
- **Theme**: Light, Dark, or Auto (follows system)
- **Font Size**: Adjust text size (8-24pt)
- **Grid Icon Size**: Adjust grid icon sizes (16-256px)

### External Tools
- **FITS Viewer**: Path to external FITS viewing application
  - Popular options: DS9, PixInsight, SIRIL, Aladin

### Configuration Management
- **Save Settings**: Persist changes to `astrofiler.ini`
- **Reset to Defaults**: Restore factory settings
- **Import/Export Config**: Share settings between installations

---

## 📋 Log Tab - Monitoring & Troubleshooting

### Log Information
- **Real-time Updates**: Shows current application activity
- **Error Tracking**: Detailed error messages and stack traces
- **Performance Info**: Processing times and file counts
- **User Actions**: Record of all operations performed

### Log Management
- **Refresh**: Reload current log content
- **Clear**: Empty the log file (creates new entry)
- **Monospace Font**: Easy-to-read formatting for technical details

### Troubleshooting Tips
- Check logs when operations fail
- Look for file permission errors
- Monitor processing progress
- Verify configuration settings

---

## 💡 Best Practices

### Repository Organization
1. **Test First**: Always test with sample data before using on production files
2. **Backup**: Keep backups of your original files
3. **Consistent Naming**: Use standardized object names from the start
4. **Regular Maintenance**: Periodically check for duplicates and clean up

### Workflow Recommendations
1. **Configure First**: Set up paths and external tools
2. **Sync vs Load**: Use Sync for existing organized repositories
3. **Session Management**: Let AstroFiler automatically create sessions
4. **Regular Stats**: Monitor your imaging progress with Stats tab

### Performance Tips
- **Large Repositories**: Processing time scales with repository size (~100GB/hour)
- **SSD Storage**: Use fast storage for repository location
- **Cache Awareness**: Stats are cached - refresh when needed
- **Background Processing**: Load operations can run in background

---

## 🛠️ Advanced Features

### Command Line Tools
AstroFiler exposes key functions as command-line utilities for automation:
- **Scripts Location**: `/commands/` directory
- **Automation**: Suitable for cron jobs and batch processing
- **Integration**: Use with other astronomy tools

### File Naming Convention
AstroFiler uses a systematic naming pattern:
```
ObjectName_Type_YYYY-MM-DD_HHMMSS_Filter_ExposureTime.fits
```
Examples:
- `M31_Light_2024-10-15_213045_Ha_300s.fits`
- `NGC7000_Dark_2024-10-15_220130_NoFilter_300s.fits`

### Database Schema
- **SQLite Database**: `astrofiler.db`
- **FITS Metadata**: All header information preserved
- **Relationships**: Sessions link lights to calibrations
- **Integrity**: SHA-256 hashes ensure file integrity

---

## 🚨 Important Warnings

### Data Safety
- **Load Repo**: Moves and renames files - test thoroughly first
- **Merge Operations**: Can rename many files at once - use preview
- **Backup**: Always maintain backups of original data
- **Test Environment**: Create test directories for learning

### File Operations
- **Permissions**: Ensure AstroFiler has write access to directories
- **Space**: Repository operations may require significant disk space
- **Network Storage**: Local storage recommended for performance

### Session Checkout
- **Symbolic Links**: Checkout creates links, not copies
- **External Processing**: Some tools may not follow symbolic links
- **Cleanup**: Remove checkout directories when done

---

## ❓ Troubleshooting

### Common Issues

**Files Not Loading**
- Check source path configuration
- Verify file permissions
- Ensure files are valid FITS format
- Check log tab for specific errors

**Slow Performance**
- Large repositories process slowly (~100GB/hour)
- Use SSD storage for better performance
- Consider splitting very large repositories

**Session Linking Problems**
- Ensure FITS headers contain required metadata
- Check telescope/camera names for consistency
- Verify date/time information in headers

**External Viewer Not Working**
- Verify path to FITS viewer in Config tab
- Check that viewer supports your file formats
- Test viewer independently first

### Getting Help
- **Log Files**: Check Log tab for detailed error information
- **GitHub Issues**: Report bugs at project repository
- **Documentation**: Refer to wiki for detailed technical information
- **Contact**: Email gord.tulloch@gmail.com for support

---

## 🎯 Quick Reference

### Essential Keyboard Shortcuts
- **Double-click**: Open file in external viewer
- **Right-click**: Context menu for additional options
- **Tab Navigation**: Switch between main functions

### File Status Indicators
- **Green**: Successfully processed files
- **Red**: Files with errors or missing metadata
- **Gray**: Calibration frames
- **Blue**: Light frames

### Processing Time Estimates
- **Load Repo**: ~100GB per hour (depends on file count and disk speed)
- **Sync Repo**: Much faster, database updates only
- **Session Generation**: Minutes for typical repositories
- **Duplicate Detection**: Fast, hash-based comparison

---

*This user guide covers AstroFiler Version 0.9.0 alpha. For the latest updates and technical documentation, visit the project's GitHub wiki.*
