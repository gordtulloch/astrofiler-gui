# AstroFiler v1.2.0 Release Notes

**Major Release: Auto-Calibration System & Advanced Quality Analysis**

## 🚀 **Auto-Calibration System**

### Master Frame Creation
- **Automated Master Creation**: One-click creation of master bias, dark, and flat frames using Siril CLI
- **Intelligent Session Grouping**: Automatically groups calibration frames by telescope, instrument, binning, and temperature
- **Quality Validation**: Built-in validation ensures master frames meet quality standards before checkout or creation of stacked light images
- **Professional FITS Headers**: Master frames include comprehensive astronomy-standard metadata and processing history
- **Smart File Management**: Organized `/Masters` directory structure with standardized naming conventions

### Light Frame Calibration
- **One-Click Calibration**: Right-click context menu for instant light frame calibration
- **Automatic Master Detection**: Finds and applies appropriate master calibration frames based on session matching
- **Enhanced Metadata**: Calibrated frames include full calibration history and master frame references
- **Batch Processing**: Process entire sessions or individual frames with progress tracking

### Quality Assessment System
- **SEP-Based Star Detection**: Professional Source Extractor Python integration for robust star analysis
- **Comprehensive Quality Metrics**: 
  - FWHM (seeing quality) in arcseconds
  - Star eccentricity (tracking quality)
  - Half Flux Radius (HFR) for focus assessment
  - Image SNR and star count
  - Automatic image scale calculation
- **Database Integration**: Quality metrics stored and searchable (Migration 009)
- **Dual Detection Methods**: Primary SEP with photutils fallback for maximum reliability
- **Real-Time Analysis**: Quality assessment integrated into calibration workflow

### UI Enhancements
- **Visual Status Indicators**: Color-coded calibration status throughout the interface
- **Progress Tracking**: Real-time progress with descriptive status messages and ETA
- **Context Menus**: Professional right-click menus with calibration operations
- **Smart Session Linking**: Automatic linking of calibration and light sessions
- **Master Frame Management**: Browse, validate, and maintain master calibration files

## ☁️ **Cloud Sync Enhancements**

### Advanced Duplicate Detection
- **Hash-Based Prevention**: MD5 hash comparison prevents duplicate uploads and reduces storage costs
- **Cloud Analysis**: Identifies duplicate files in cloud storage with wasted space calculation
- **Bulk Optimization**: Efficient metadata retrieval improves sync performance
- **Smart Upload Logic**: Skip identical files, upload new content, overwrite changes

### Enhanced File Matching
- **Multi-Tier Matching**: Exact filename, partial filename, and hash-based content verification
- **Improved Reliability**: Better local-to-cloud file matching for accurate sync operations

## 📱 **Smart Telescope Integration**

### iTelescope Network Support
- **Secure FTPS Connection**: Direct encrypted connection to iTelescope remote observatories
- **Selective Scanning**: Intelligent telescope directory discovery and calibrated file detection
- **Compressed File Support**: Native handling of iTelescope's .fit.zip format
- **Credential Management**: Secure authentication to iTelescope through configuration interface

### Enhanced Telescope Support
- **Improved Protocol Handling**: Better SMB/CIFS for SeeStar/StellarMate, FTP for DWARF
- **Network Discovery**: Enhanced hostname resolution and telescope identification
- **Download Progress**: Real-time file transfer monitoring with protocol indicators

## 🔧 **Installation & Dependencies**

### Enhanced Installation System
- **Automatic pysiril Installation**: All install scripts now automatically download and install pysiril
- **Multi-Platform Support**: Enhanced Windows, Linux, and macOS installation that allows users to specify automatic download of updates or manual process
- **PyWinInstall Integration**: Special automation for SETUP.EXE users
- **Fallback Methods**: Git source installation when downloads fail
- **Installation Verification**: Post-install testing ensures successful setup

### Configuration Interface
- **Tabbed Configuration**: Modern tabbed interface with organized sections:
  - General settings and display preferences
  - Cloud sync configuration and authentication
  - Auto-calibration settings and Siril integration
  - Smart telescope credentials and configuration

## 🛠️ **Technical Improvements**

### Code Architecture
- **Modular Design**: Clean separation of concerns with dedicated analysis methods
- **Database Integration**: Built-in methods for seamless database operations
- **Robust Error Handling**: Graceful fallback mechanisms and comprehensive validation

### Database Enhancements
- **Migration 009**: New quality metrics fields for FWHM, eccentricity, HFR, SNR, star count, and image scale
- **Enhanced Schema**: Comprehensive calibration tracking and master frame relationships
- **Automatic Migration**: Seamless upgrades with backward compatibility

## 📋 **Command-Line Interface**

### AutoCalibration.py
- **Complete Automation**: Full CLI interface for batch processing and automation
- **Operation Modes**: Analyze, masters, calibrate, quality, and complete workflow options
- **Enhanced Analysis**: Reports uncalibrated light frames, soft-deleted frame statistics by type
- **Scheduling Support**: Windows and Linux automation scripts for cron/Task Scheduler
- **Progress Reporting**: Detailed status updates and comprehensive result summaries

### LoadRepo.py Enhancements
- **Temporary Mappings**: New `-s` flag for one-time FITS header mappings (e.g., `-s OBJECT/Unknown/M31`)
- **Multiple Mappings**: Support for multiple temporary mappings in a single run
- **Auto Cleanup**: Temporary mappings automatically removed after processing completes
- **Batch Processing**: Ideal for importing files that need special handling without permanent database changes

## 🏷️ **FITS Header Mapping System**

### Standardized Header Management
- **Database-Driven Mappings**: Define FITS header value standardizations in the GUI that are automatically applied during file ingestion
- **Comprehensive Card Support**: Map TELESCOP, INSTRUME, OBSERVER, OBJECT, FILTER, and NOTES headers
- **Automatic Application**: Mappings applied during telescope downloads (Download.py) and local file loads (LoadRepo.py)
- **Unknown Value Handling**: Support for default mappings when expected header values are missing
- **File Organization**: Correct header values ensure proper file naming and folder structure in repository
- **Temporary Mappings**: LoadRepo.py now supports one-time mappings via `-s CARD/INPUT/OUTPUT` flag for batch-specific adjustments without permanent database entries

### Mapping Dialog Enhancements
- **OBJECT Card Support**: Added OBJECT to mappable cards for standardizing target names
- **Visual Interface**: Easy-to-use dialog for creating and managing header value mappings
- **Current Value Detection**: Shows existing header values to help identify mapping needs

## 🗂️ **File Management**

### Soft Delete System
- **Non-Destructive Deletion**: Files marked as deleted remain on disk but hidden from view
- **Automatic Soft-Delete**: Source calibration frames automatically soft-deleted after master creation
- **Show Deleted Toggle**: Images view includes "Show Deleted" checkbox to view/hide soft-deleted frames
- **Recovery Capability**: Soft-deleted files can be recovered or permanently removed via Duplicates widget
- **Analysis Reporting**: AutoCalibration analyze command reports soft-deleted frame statistics

### Images View Enhancements
- **Soft Delete Support**: Delete operation now performs soft-delete instead of permanent removal
- **Visual Feedback**: Clear messaging about soft-delete vs permanent delete operations
- **Filtered Views**: Soft-deleted frames hidden by default, toggle to show when needed

## 🐛 **Bug Fixes**

### Session Creation Fixes
- **Calibration Session Grouping**: Fixed bug where each calibration frame was creating its own session instead of proper grouping
- **Session Counting**: Corrected session counting logic to count unique sessions, not file assignments
- **Workflow Alignment**: Session creation now properly matches astronomical workflows (bias ~n/100, dark/flat ~n/25 frames per session)

### Master Frame Improvements
- **Observation Date Usage**: Master calibration filenames now use observation date from session instead of processing date
- **Proper Dating**: Ensures master frames are correctly dated for historical tracking
- **Source Frame Management**: Source calibration frames automatically soft-deleted after successful master creation

### Logging Centralization
- **Unified Log File**: All command-line utilities now log to single `astrofiler.log` file with 5MB rotation
- **Consistent Logging**: Download.py, LoadRepo.py, CreateSessions.py, and all other commands use centralized logging
- **Improved Debugging**: Single log location simplifies troubleshooting and monitoring

### Path Configuration
- **Download.py Module Loading**: Fixed ModuleNotFoundError by applying proper Python path configuration
- **Import Consistency**: Ensured consistent module loading across all command-line utilities

### Previous Fixes
- **Cloud Download Workflow**: Fixed file organization and registration issues
- **registerFitsImage Calls**: Corrected parameter handling across all cloud sync operations
- **Installation Dependencies**: Resolved pysiril installation and dependency management
- **Progress Dialog Integration**: Enhanced progress tracking throughout the application

## 🔄 **Migration Notes**

- **Database Migration 009**: Automatically adds quality metrics fields on startup
- **Configuration Updates**: New auto-calibration settings automatically added to existing configurations
- **Backward Compatibility**: All existing functionality preserved during upgrade

---

**Installation**: Download from GitHub releases or use automated install scripts for your platform

**Requirements**: Python 3.8+, Siril (for auto-calibration), recommended 8GB+ RAM for large datasets

**Documentation**: Complete setup guides and user documentation in GitHub Wiki

**Community**: Join the discussion on [Cloudy Nights](https://www.cloudynights.com/topic/975026-astrofiler-11-astronomical-image-management-system-released/)