![Astrofile icon](/astrofiler.ico) 

# AstroFiler

**A comprehensive astronomical image file management tool**

[![Python3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![AstroPy](https://img.shields.io/badge/astronomy-AstroPy-orange.svg)](https://www.astropy.org/)

AstroFiler is a powerful application designed for astronomers and astrophotographers to efficiently manage, organize, and catalog their FITS image files. With an intuitive graphical interface, it provides tools for batch processing, file organization, metadata extraction, session analysis, and direct integration with smart telescopes for seamless data acquisition. Detailed documentation is in the Github Wiki.

**Current Status**: Release V1.1.0

## ✨ Features

### � **Smart Telescope Integration**
- **SEESTAR Support**: Direct connection to SEESTAR smart telescopes via SMB/CIFS protocol
- **DWARF Support**: Direct connection to DWARF smart telescopes via FTP protocol
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

### �🗂️ **File Management**
- **Repository Scanning**: Recursively scan directories for FITS files, rename to a descriptive name, and move into a centralized repository
- **Batch Processing**: Process multiple files with progress tracking
- **File Organization**: Automatically organize files based on metadata
- **Duplicate Detection**: SHA-256 hash-based duplicate file identification
- **Duplicate Management**: Safely remove duplicate files while preserving one copy
- **Command Line Utilities**: Critical functions exposed as command line utilities to facilitate use of scripts and crontab

### 📊 **Metadata & Analysis**
- **Stats Page**: Provides basic statistics on the files contained in the Repository
- **FITS Header Extraction**: Automatically extract and catalog metadata
- **Object Identification**: Track astronomical targets and sessions
- **Date/Time Analysis**: Organize by objects, observation dates, instruments, and cameras
- **File Integrity**: SHA-256 hashing for duplicate detection and verification

### 🛠️ **Tools & Integration**
- **Smart Telescope Downloads**: Direct FITS file acquisition from SEESTAR telescopes
  - One-click network scanning and connection
  - Batch download with progress monitoring
  - Optional remote file deletion after successful processing
  - Automatic header standardization and metadata extraction
- **External Viewer Support**: Launch your favorite FITS viewer directly from AstroFiler
- **Siril CLI Integration**: Create master calibration frames using Siril command-line interface
- **Automated Master Creation**: Generate master bias, dark, and flat frames with proper naming and metadata

### 📈 **Session Management**
- **Session Detection**: Automatically group lights and calibration images
- **Session Operations**: Create, update, and clear session groupings
- **Session Linking**: Automatically link calibration sessions to light sessions
- **Session Export**: Export Lights and Calibration files ready for SIRIL processing
- **Master Frame Management**: Track and create master calibration frames per session

### **Future Versions**
- **XISF support**: Load XISF files and extract FITS headers
- **Processed Images**: Support for processed images and formats (XISF, TIFF, JPG)
- **Archiving**: Saving images to Google Cloud Services, Dropbox, Amazon etc.
- **Auto-Calibration**: Calibrate any lights with calibration files (build masters first) with Siril
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
- **Supported Telescopes**: SEESTAR, DWARF 3 (experimental)

### Key Dependencies
- **PySide6**: Modern Qt6-based GUI framework
- **AstroPy**: FITS file handling and astronomical data processing
- **peewee**: Lightweight ORM for database operations
- **peewee-migrate**: Database migration system
- **pysmb**: SMB/CIFS protocol support for telescope communication
- **Pillow**: Image processing for thumbnails and previews

### Optional Dependencies
- **Git**: Required for auto-update functionality

## 🚀 Quick Installation

AstroFiler includes automated installation scripts for all major platforms:

### Windows
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
- Creates desktop shortcuts and application menu entries
- Sets up automatic update checking from GitHub

**Auto-Update Feature:**
Desktop launchers automatically check for and install updates from GitHub when starting AstroFiler (if installed via git clone).

📖 **See the Wiki for detailed installation instructions and troubleshooting.**

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
