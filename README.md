![Astrofile icon](/astrofiler.ico) 

# AstroFiler

**A comprehensive astronomical image file management tool**

[![Python3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![AstroPy](https://img.shields.io/badge/astronomy-AstroPy-orange.svg)](https://www.astropy.org/)

AstroFiler is a powerful application designed for astronomers and astrophotographers to efficiently manage, organize, and catalog their FITS image files. With an intuitive graphical interface, it provides tools for batch processing, file organization, metadata extraction, session analysis, and direct integration with smart telescopes for seamless data acquisition. Detailed documentation is in the Github Wiki. Astrofiler is a tool to manage FITS files (currently, XISF files and other non-FITS images are coming in the next version!) using FITS header data. FITS Headers are embedded with the image when created as metadata. Astrofiler reads this information to rename the file and file it appropriately in the Repository.

**Current Status**: Development V1.2.0 (Auto-Calibration System)

Getting started guide [here](https://github.com/gordtulloch/astrofiler-gui/wiki/Getting-Started!)

See discussion thread on Cloudy Nights [here](https://www.cloudynights.com/topic/975026-astrofiler-11-astronomical-image-management-system-released/)

## ✨ Features

### � **Smart Telescope Integration**
- **SEESTAR Support**: Direct connection to SEESTAR smart telescopes via SMB/CIFS protocol
- **StellarMate Support**: Direct connection to StellarMate systems via SMB/CIFS protocol
- **DWARF Support**: Direct connection to DWARF smart telescopes via FTP protocol (experimental)
- **iTelescope Support**: Secure FTPS connection to iTelescope network for downloading calibrated files
- **Network Discovery**: Automatic scanning of local network to locate telescopes
- **Remote File Access**: Browse and download FITS files directly from telescope storage
- **Selective Download**: Filter and download only from "_sub" folders for targeted data retrieval
- **Header Enhancement**: Automatic OBJECT and MOSAIC header updates based on telescope folder structure
- **Progress Tracking**: Real-time download progress with file-by-file status updates
- **Safe Cancellation**: Graceful download interruption with proper cleanup
- **Delete on Host**: Optional secure deletion of files from telescope after successful download
  - **Safety Confirmations**: Multiple warning dialogs before enabling deletion
  - **Post-Processing Only**: Files deleted only after successful local processing and database registration
  - **Error Reporting**: Comprehensive feedback on deletion operations

### ☁️ **Cloud Sync Integration**
- **Google Cloud Storage**: Complete integration with Google Cloud Storage for backup and synchronization
- **Multiple Sync Profiles**: 
  - **Complete Sync**: Bidirectional sync - downloads missing files from cloud AND uploads files without cloud URLs
  - **Backup Only**: One-way backup - uploads local files to cloud for safe storage
  - **On Demand**: Manual file-by-file synchronization (coming soon)
- **Advanced Duplicate Detection**: Hash-based duplicate prevention and storage optimization
  - **MD5 Hash Comparison**: Prevents duplicate uploads by comparing file content hashes
  - **Cloud Storage Analysis**: Identifies duplicate files in cloud storage to reduce costs
  - **Bulk Performance Optimization**: Efficient metadata retrieval reduces API calls and improves sync speed
  - **Detailed Duplicate Reports**: Shows duplicate groups, wasted space, and optimization opportunities
- **Smart Upload Logic**: Three-tier decision system (skip identical files, upload new files, overwrite changed content)
- **Enhanced File Matching**: Multi-tier local file matching using exact filename, partial filename, and hash-based verification
- **Database Integration**: Tracks cloud URLs for all files with `fitsFileCloudURL` field enabling future remote access features
- **Images View Integration**: Local/Cloud status icons show file storage locations at a glance
- **Real-time Progress**: Live progress tracking with efficiency statistics and detailed completion summaries
- **Command-Line Automation**: Complete command-line interface (`CloudSync.py`) with automation scripts for cron/Task Scheduler
- **Analysis Mode**: Analyze cloud storage contents, detect duplicates, and compare with local database without performing sync
- **Comprehensive Error Handling**: User-friendly error messages for authentication, bucket access, and network issues
- **Directory Structure Preservation**: Maintains your local repository folder structure in cloud storage
- **Bucket Validation**: Pre-operation checks ensure bucket exists and is accessible
- **Service Account Authentication**: Secure authentication using Google Cloud service account keys
- **Tabbed Configuration Interface**: Modern tabbed configuration dialog with organized sections:
  - **General Tab**: General settings, display preferences, external tools, and warning suppression
  - **Cloud Sync Tab**: Dedicated cloud synchronization configuration with vendor selection and authentication
  - **Calibration Tab**: Auto-calibration settings including master frame creation
  - **Smart Telescopes Tab**: Telescope-specific configurations including iTelescope credentials
- **Self-Contained Architecture**: All cloud operations integrated into dialog for improved maintainability

### 🗂️ **File Management**
- **Repository Scanning**: Recursively scan directories for FITS files, rename to a descriptive name, and move into a centralized repository
- **Batch Processing**: Process multiple files with progress tracking
- **File Organization**: Automatically organize files based on metadata
- **Duplicate Detection**: SHA-256 hash-based duplicate file identification
- **Duplicate Management**: Safely remove duplicate files while preserving one copy
- **Command Line Utilities**: Comprehensive command-line interface for automation and scripting
  - **CloudSync.py**: Complete cloud synchronization with all GUI features available from command line
  - **LoadRepo.py**: Batch file processing and repository loading
  - **Automation Scripts**: Ready-to-use cron and Task Scheduler scripts for Windows/Linux/macOS
  - **Unattended Operation**: Auto-confirm flags for scheduled and automated operations

### 📊 **Metadata & Analysis**
- **Stats Page**: Provides basic statistics on the files contained in the Repository
- **FITS Header Extraction**: Automatically extract and catalog metadata
- **Object Identification**: Track astronomical targets and sessions
- **Date/Time Analysis**: Organize by objects, observation dates, instruments, and cameras
- **File Integrity**: SHA-256 hashing for duplicate detection and verification

### 🛠️ **Tools & Integration**
- **Smart Telescope Downloads**: Direct FITS file acquisition from SEESTAR and StellarMate telescopes
  - One-click network scanning and connection
  - Batch download with progress monitoring
  - Optional remote file deletion after successful processing
  - Automatic header standardization and metadata extraction
- **External Viewer Support**: Launch your favorite FITS viewer directly from AstroFiler
- **Comprehensive Siril CLI Integration**: Full integration with Siril for professional-grade image processing
  - Master calibration frame creation (bias, dark, flat)
  - Automated light frame calibration workflows
  - Progress monitoring with real-time status updates
  - Quality validation and error handling
  - Batch processing capabilities for large datasets
- **Professional Calibration System**: Complete auto-calibration workflow from raw frames to calibrated images
  - Intelligent session detection and grouping
  - Automatic master frame creation with optimal parameters
  - Smart calibration file matching based on camera settings
  - Quality assessment and validation systems
  - Enhanced metadata tracking throughout the calibration process

### 📈 **Advanced Session Management**
- **Intelligent Session Detection**: Automatically group lights and calibration images based on FITS metadata
- **Comprehensive Session Operations**: Create, update, clear, and manage session groupings with advanced tools
- **Smart Session Linking**: Automatically link calibration sessions to light sessions based on camera, binning, and temperature matching
- **Professional Session Export**: Export sessions with organized folder structures ready for external processing
- **Master Frame Management**: Complete master calibration frame lifecycle management
  - Create master frames with optimal Siril parameters
  - Validate master frame quality and integrity
  - Track master frame usage and relationships
  - Browse and manage master frame files
  - Cleanup and maintenance tools for master frame storage
- **Context-Aware Operations**: Right-click context menus with session-specific tools and batch operations
- **Calibration Workflow Integration**: Seamless integration between session management and auto-calibration system
- **Progress Tracking**: Real-time status updates for all session operations with detailed progress monitoring

### 🚀 **Auto-Calibration System**
- **Intelligent Master Frame Creation**: Automatically creates master bias, dark, and flat frames using Siril CLI
- **Smart Session Linking**: Automatically links calibration sessions to light frame sessions based on camera, binning, and temperature
- **Calibration Workflow**: One-click calibration of light frames using appropriate master calibration files
- **Advanced Quality Assessment**: SEP-based image analysis with FWHM, HFR, eccentricity, and SNR calculations
- **Professional Quality Metrics**: Comprehensive quality analysis including star detection, seeing quality, and image statistics
- **Progress Tracking**: Real-time progress monitoring with detailed status updates and ETA calculations
- **Enhanced FITS Headers**: Automatic addition of comprehensive calibration metadata to processed files
- **Professional Context Menus**: Right-click context menus with master frame management, calibration operations, and session tools
- **Existing File Detection**: Smart duplicate prevention and master frame reuse to avoid unnecessary processing
- **Command-Line Automation**: Complete CLI interface for automated calibration workflows and batch processing
- **Advanced UI Indicators**: Visual status indicators showing calibration status, master frame availability, and processing state
- **Database Integration**: Quality metrics stored in database for analysis and filtering (Migration 009)
- **Modular Architecture**: Comprehensive refactoring with dedicated `enhanced_quality.py` module for professional-grade quality analysis

### **Future Versions**
- **XISF import**: Load XISF files, extract headers and data, save to FITS format (optional)
- **Thumbnails/Sample Stacks**: Use Siril to create stacked images, stretch, and create thumbnail

## 🔧 Technical Requirements

### System Requirements
- **Python**: 3.8 or higher
- **Operating System**: Windows 10+, Linux (Ubuntu 18.04+), macOS 10.14+
- **Memory**: 4GB RAM minimum, 8GB+ recommended for large datasets
- **Storage**: Variable (depends on FITS repository size)

### Network Requirements (for Smart Telescope Features)
- **SMB/CIFS Protocol**: Port 445 access to telescope network
- **Local Network**: Telescope and computer on same network segment
- **Supported Telescopes**: SEESTAR, StellarMate, DWARF 3 (experimental)

### Key Dependencies
- **PySide6**: Modern Qt6-based GUI framework
- **AstroPy**: FITS file handling and astronomical data processing
- **peewee**: Lightweight ORM for database operations
- **peewee-migrate**: Database migration system
- **pysmb**: SMB/CIFS protocol support for telescope communication
- **google-cloud-storage**: Google Cloud Storage integration for cloud sync features
- **google-auth**: Authentication library for Google Cloud services
- **Pillow**: Image processing for thumbnails and previews
- **Siril**: Command-line integration for master frame creation and calibration workflows
- **SEP**: Source Extractor Python library for advanced star detection and quality analysis
- **pysiril**: Python interface to Siril (automatically installed by install scripts)

### Optional Dependencies
- **Git**: Required for auto-update functionality
- **Siril**: Required for auto-calibration features (must be in system PATH)

## 🚀 Quick Installation

AstroFiler includes automated installation scripts for all major platforms:

### Windows - Easy Setup
Download SETUP.ZIP, unzip it, and run it. It will download everything needed and install it, putting an icon on your desktop.

You will need to install and run Git for updates however. Download git, and from the astrofiler-gui folder run

```bash
git fetch origin
git reset --hard origin/main
```

### Windows - Install Script
Install Git - There are also a few ways to install Git on Windows. The most official build is available for download on the Git website. Just go to https://git-scm.com/download/win and the download will start automatically. Note that this is a project called Git for Windows, which is separate from Git itself; for more information on it, go to https://gitforwindows.org.

Once git is installed, you can open a powershell command line (run as Admin) and enter:

```powershell
C:
cd \
Set-ExecutionPolicy -Scope LocalMachine -ExecutionPolicy RemoteSigned -Force
git clone https://github.com/gordtulloch/astrofiler-gui.git
cd astrofiler-gui
.\install\install.ps1
```

### Linux
In Linux you can install git from Debian distros via:

```bash
apt install git      # Debian distros
sudo yum install git # CentOS distros
cd $HOME
git clone https://github.com/gordtulloch/astrofiler-gui.git
cd astrofiler-gui
chmod +x install/install.sh && ./install/install.sh
```

### macOS
There are several ways to install Git on macOS. The easiest is probably to install the Xcode Command Line Tools. On Mavericks (10.9) or above you can do this simply by trying to run git from the Terminal the very first time.

```bash
git --version # If you don’t have it installed already, it will prompt you to install it.
git clone https://github.com/gordtulloch/astrofiler-gui.git
cd astrofiler-gui
chmod +x install/install_macos.sh && ./install/install_macos.sh
```

**What the installer does:**
- Checks for Python 3.8+ (installs if needed)
- Creates virtual environment
- Installs all dependencies
- **Automatically downloads and installs pysiril** from GitLab CI/CD artifacts
- Creates desktop shortcuts and application menu entries
- Sets up automatic update checking from GitHub

**Auto-Update Feature:**
Desktop launchers automatically check for and install updates from GitHub when starting AstroFiler (if installed via git clone).

📖 **See the Wiki for detailed installation instructions and troubleshooting.**

## 🎯 Usage Examples

### Basic Repository Management
1. **Setup Repository**: Configure your FITS file repository location in Config → General tab
2. **Scan Files**: Use "Load Repository" to scan and catalog your FITS files
3. **View Statistics**: Check the Stats tab for repository overview and file counts

### Auto-Calibration Workflow
1. **Organize Sessions**: AstroFiler automatically groups your calibration and light frames into sessions
2. **Create Masters**: Right-click on calibration sessions → "Create Master Frame" 
3. **Link Sessions**: Use "Link Sessions to Masters" to automatically match calibration and light sessions
4. **Calibrate**: Right-click on light sessions → "Calibrate Session" for one-click calibration
5. **Monitor Progress**: Real-time progress tracking with detailed status updates

### Smart Telescope Integration
1. **Network Scan**: Tools → "Download from Smart Telescope" → "Scan Network"
2. **Connect**: Select your telescope from discovered devices
3. **Browse & Download**: Navigate telescope folders and download FITS files
4. **Auto-Process**: Files are automatically processed and added to your repository

### iTelescope Integration
1. **Configure Credentials**: Config → Smart Telescopes tab → Enter iTelescope username/password
2. **Connect**: Tools → "Download from Smart Telescope" → Select "iTelescope"
3. **Scan Files**: System discovers all calibrated files in your iTelescope account
4. **Download**: Select and download calibrated files directly to your repository

### Cloud Sync Setup
1. **Google Cloud Setup**: Follow the [GCS Setup Guide](GCS_SETUP_GUIDE.md)
2. **Configure Sync**: Config → Cloud Sync tab → Configure your bucket and credentials  
3. **Choose Profile**: Select Complete Sync, Backup Only, or On Demand
4. **Sync**: Tools → "Cloud Sync" → Monitor progress with real-time status updates

## 🗄️ Database Migrations

AstroFiler uses `peewee-migrate` for database version control and schema migrations. This ensures smooth upgrades when the database structure changes in future versions.

### For Users
- **Automatic Migration**: When you start AstroFiler, any pending database migrations are automatically applied
- **No Manual Action Required**: The application handles database updates transparently
- **Backup Recommended**: While migrations are tested, it's always good practice to backup your `astrofiler.db` file before major updates

### For Developers
Database schema changes are managed through migrations:

```bash
# Check current migration status
python migrate.py status

# Create a new migration
python migrate.py create add_new_field

# Run pending migrations
python migrate.py run

# Initial database setup
python migrate.py setup
```

See [MIGRATIONS.md](MIGRATIONS.md) for detailed migration development guidelines.

## 📚 Documentation

- **[Getting Started Guide](https://github.com/gordtulloch/astrofiler-gui/wiki/Getting-Started!)** - Quick start guide for new users
- **[GCS Setup Guide](GCS_SETUP_GUIDE.md)** - Complete guide for setting up Google Cloud Storage integration
- **[Cloud Sync Configuration](CLOUD_SYNC_CONFIG.md)** - Technical documentation for cloud sync features
- **[GitHub Wiki](https://github.com/gordtulloch/astrofiler-gui/wiki)** - Comprehensive documentation and guides
- **[Cloudy Nights Discussion](https://www.cloudynights.com/topic/975026-astrofiler-11-astronomical-image-management-system-released/)** - Community discussion and support

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

If you wish to make a cash contribution to assist the author in continuing to produce quality open source software please feel free to make a Paypal contribution to gord.tulloch@gmail.com.

## 📄 License

This project is licensed under the terms specified in the LICENSE file.

## 🙏 Acknowledgments

- **AstroPy Project**: For excellent FITS file handling capabilities
- **Qt Project**: For the robust PySide6 GUI framework
- **Python Community**: For the amazing ecosystem of scientific packages

---

**Made with ❤️ for the astronomy community**

*For questions, bug reports, or feature requests, please open an issue on the project repository.*

Telescope icon created by Freepik - [Flaticon](https://www.flaticon.com/free-icons/telescope)
