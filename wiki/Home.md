![Astrofile icon](/astrofiler.png) 

# AstroFiler

**A comprehensive astronomical image file management tool**

[![Python3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![AstroPy](https://img.shields.io/badge/astronomy-AstroPy-orange.svg)](https://www.astropy.org/)

AstroFiler is a powerful Python application designed for astronomers and astrophotographers to efficiently manage, organize, and catalog their astronomical image files. With support for both FITS and XISF formats (input only) and an intuitive graphical interface, it provides tools for batch processing, file organization, metadata extraction, and session analysis.

## ✨ Features

### 🗂️ **File Management**
- **Multi-Format Support**: Full support for FITS and XISF file formats with automatic XISF to FITS conversion
- **Repository Scanning**: Recursively scan directories for astronomical image files, rename to a descriptive name, and move into a centralized repository
- **XISF Processing**: Seamless conversion of XISF files to FITS format while preserving original files
- **Intelligent File Placement**: Converted FITS files placed in incoming folder for processing, original XISF files preserved in place
- **Automated Calibration Processing**: Automatic creation of master calibration frames and calibration of light frames
- **Batch Processing**: Process multiple files with progress tracking
- **File Organization**: Automatically organize files based on metadata
- **Object Merging**: Merge and rename objects across the repository with automatic file and header updates
- **Duplicate Detection**: SHA-256 hash-based duplicate file identification
- **Duplicate Management**: Safely remove duplicate files while preserving one copy
- **Command Line Utilities**: Critical functions exposed as command line utilities to facilitate use of scripts and crontab

### 📊 **Metadata & Analysis**
- **Multi-Format Header Extraction**: Automatically extract and catalog metadata from both FITS and XISF files
- **XISF Metadata Conversion**: Comprehensive conversion of XISF properties to FITS-compatible keywords
- **Object Identification**: Track astronomical targets and sessions across file formats
- **Date/Time Analysis**: Organize by objects, observation dates, instruments, and cameras
- **File Integrity**: SHA-256 hashing for duplicate detection and verification
### 🛠️ **Tools & Integration**
- **External Viewer Support**: Launch your favorite FITS viewer directly from AstroFiler (works with converted XISF files)

### 📈 **Session Management & Auto-Calibration**
- **Session Detection**: Automatically group lights and calibration images
- **Session Operations**: Create, update, and clear session groupings
- **Session Linking**: Automatically link calibration sessions to light sessions
- **Automated Master Creation**: Automatically generate master dark, bias, and flat frames from calibration sessions
- **Auto-Calibration System**: Intelligent calibration of light frames using appropriate master calibration files
- **Smart Calibration Matching**: Matches calibration frames based on telescope, instrument, binning, gain, offset, exposure, temperature, and filter criteria
- **Session Export**: Export Lights and Calibration files ready for SIRIL processing

## 🆕 Recent Updates

### XISF Format Support (V1.2.0)
- **Complete XISF Integration**: Full support for PixInsight XISF files with automatic conversion to FITS format
- **Seamless Processing**: XISF files are automatically detected and converted during import through both UI and command-line tools
- **File Preservation**: Original XISF files are preserved in their original location while converted FITS files are placed in the incoming folder
- **Advanced Format Support**: Handles all XISF sample formats, compression methods (zlib, lz4, gzip), and byte shuffling
- **Metadata Preservation**: Complete preservation of XISF metadata as FITS keywords with additional XISF-specific tracking

### Auto-Calibration System (V1.2.0)
- **Automated Master Generation**: Automatically creates master dark, bias, and flat frames from calibration sessions
- **Intelligent Light Calibration**: Automatically calibrates light frames using the most appropriate master calibration files
- **Smart Matching Algorithm**: Matches calibration frames based on multiple criteria including equipment, settings, and environmental conditions
- **Background Processing**: Auto-calibration runs as a background process with progress tracking and logging
- **Quality Control**: Validates calibration frame quality and reports any issues or missing calibration data
- **Command-Line Automation**: Complete command-line interface for automated calibration workflows and scheduling

### Cloud Sync Integration (V1.2.0)
- **Google Cloud Storage Support**: Complete integration with Google Cloud Storage for backup and synchronization
- **Advanced Duplicate Detection**: Hash-based duplicate prevention and cloud storage optimization
  - **MD5 Hash Comparison**: Prevents duplicate uploads by comparing file content hashes
  - **Cloud Storage Analysis**: Identifies duplicate files in cloud storage to reduce costs and optimize storage
  - **Bulk Performance Optimization**: Efficient metadata retrieval reduces API calls and improves sync performance
  - **Detailed Duplicate Reports**: Shows duplicate groups, wasted space, and optimization opportunities
- **Multiple Sync Profiles**: Complete (bidirectional), Backup Only (one-way), and On Demand synchronization options
- **Smart Upload Logic**: Three-tier decision system prevents unnecessary uploads and optimizes bandwidth usage
- **Enhanced File Matching**: Multi-tier local file matching using exact filename, partial filename, and hash-based verification
- **Real-time Progress Tracking**: Live progress updates with efficiency statistics and detailed completion summaries
- **Command-Line Automation**: Complete CLI interface with cron/Task Scheduler automation scripts
- **Database Integration**: Tracks cloud URLs for all files enabling future remote access features

### Enhanced Merge/Rename Functionality
- **FITS Header Updates**: When files are renamed, OBJECT headers are automatically updated to match
- **Directory Structure Management**: Files are moved to correct directory hierarchy based on new object names
- **Comprehensive Error Handling**: Detailed logging and error reporting for all merge operations
- **Audit Trail**: FITS headers include comments documenting changes made by Astrofiler

### Advanced Calibration & Session Matching
- **Session-Level Metadata**: Enhanced database schema with equipment and acquisition settings
- **Sophisticated Calibration Matching**: Matches calibration frames based on telescope, instrument, binning, gain, offset, exposure, temperature, and filter
- **Temperature Tolerance**: Dark frame matching includes ±5°C CCD temperature tolerance
- **Master Frame Generation**: Automatically combines calibration frames into master dark, bias, and flat files
- **Calibration Validation**: Ensures calibration frame quality and completeness before processing

### Streamlined Session Management
- **One-Click Regeneration**: Consolidated "Regenerate" button performs complete session rebuild
- **Multi-Phase Progress**: Real-time progress tracking across all session operations
- **Session Checkout**: Export sessions to external processing tools with symbolic links and ready-to-use scripts
- **Non-Destructive Operations**: All session management preserves original files



