# 🌟 AstroFiler GUI

**A comprehensive astronomical image file management and organization tool**

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![AstroPy](https://img.shields.io/badge/astronomy-AstroPy-orange.svg)](https://www.astropy.org/)

AstroFiler GUI is a powerful Python application designed for astronomers and astrophotographers to efficiently manage, organize, and catalog their FITS image files. With an intuitive graphical interface, it provides tools for batch processing, file organization, metadata extraction, and sequence analysis.

## ✨ Features

### 🗂️ **File Management**
- **Repository Scanning**: Recursively scan directories for FITS files
- **Batch Processing**: Process multiple files with progress tracking
- **File Organization**: Automatically organize files based on metadata
- **Duplicate Detection**: Identify and manage duplicate files

### 📊 **Metadata & Analysis**
- **FITS Header Extraction**: Automatically extract and catalog metadata
- **Object Identification**: Track astronomical targets and sequences
- **Filter & Exposure Tracking**: Monitor filter usage and exposure times
- **Date/Time Analysis**: Organize by observation dates and times

### 🔍 **Search & Filter**
- **Advanced Filtering**: Search by object, filter, exposure, date, and more
- **Tree View Navigation**: Hierarchical organization of your image library
- **Quick Access**: Fast lookup of specific images or sequences

### 🛠️ **Tools & Integration**
- **External Viewer Support**: Launch your favorite FITS viewer directly
- **Progress Monitoring**: Real-time progress for long operations
- **Logging System**: Comprehensive activity logging
- **Configuration Management**: Persistent settings and preferences

### 📈 **Sequence Management**
- **Sequence Detection**: Automatically group related images
- **Merge Operations**: Combine sequences with conflict resolution
- **Batch Renaming**: Standardize file naming conventions

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- FITS files to manage

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/gordtulloch/astrofiler-gui
   cd astrofiler-gui
   ```

2. **Set up Virtual Environment and Install dependencies (first run only):**
In Linux/Mac:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
In Windows:

   ```bash
   python -m venv .venv
   .venv/Scripts/Activate
   pip install -r requirements.txt
   ```
3. **Run the application:**
   ```bash
   python astrofiler.py
   ```

## 📖 User Guide

### Getting Started

1. **Launch AstroFiler GUI**: Run `python astrofiler.py`
2. **Load Repository**: Use the Config tab to set your FITS file directory
3. **Scan Files**: Click "Load Repository" to scan and catalog your files
4. **Browse**: Use the Images tab to explore your organized file collection

### Main Interface

The application features a tabbed interface with five main sections:

#### 🖼️ **Images Tab**
- **Tree View**: Hierarchical display of your FITS files organized by:
  - Object name
  - Filter type
  - Individual files with metadata
- **Columns**: Date, Object, Filter, Exposure, Filename
- **Actions**:
  - **Refresh**: Reload the database and update the view
  - **Double-click**: Open files in your configured external viewer
- **Features**: Collapsible tree structure for easy navigation

#### ⚙️ **Config Tab**
- **Repository Settings**:
  - Set the root directory for FITS file scanning
  - Configure recursive scanning options
- **External Tools**:
  - Configure your preferred FITS file viewer
  - Browse and select executable applications
- **Database Management**:
  - Load Repository: Scan and catalog files
  - Sync Repository: Update existing catalog
  - Update Sequences: Refresh sequence groupings

#### 🔄 **Merge Tab**
- **Sequence Merging**: Combine related image sequences
- **Conflict Resolution**: Handle duplicate or conflicting entries
- **Batch Operations**: Process multiple sequences simultaneously
- **File Renaming**: Option to update filenames on disk (default: enabled)

#### 📋 **Log Tab**
- **Activity Monitoring**: View real-time application logs
- **Error Tracking**: Monitor and troubleshoot issues
- **Log Management**: Clear logs when needed
- **Debugging**: Detailed operation tracking

#### ℹ️ **About Tab**
- **Application Information**: Version and credits
- **Documentation**: Quick reference and help
- **Contact**: Support and contribution information

### Configuration

#### Setting Up Your Repository

1. Go to the **Config** tab
2. Click "Browse" next to "Repository directory"
3. Select your FITS files directory
4. Click "Load Repository" to scan files

#### External FITS Viewer

1. Go to the **Config** tab → **External Tools** section
2. Click "Browse" next to "FITS Viewer"
3. Select your preferred FITS viewing application (e.g., DS9, FITS Liberator)
4. Settings are automatically saved

### File Processing

#### Supported Metadata

AstroFiler automatically extracts and catalogs:
- **OBJECT**: Target name
- **FILTER**: Filter designation
- **EXPTIME**: Exposure duration
- **DATE-OBS**: Observation timestamp
- **FILENAME**: File identifier

#### Progress Monitoring

Long-running operations display:
- **Progress Bar**: Real-time completion percentage
- **Status Text**: Current file being processed (filename only)
- **Cancel Option**: Ability to abort operations
- **Time Estimates**: Remaining time calculations

## 🔧 Configuration Files

### `astrofiler.ini`
Persistent application settings including:
- Repository directory path
- External tool configurations
- Window preferences
- Last used settings

### `astrofiler.db`
SQLite database containing:
- FITS file catalog
- Metadata index
- Sequence relationships
- Processing history

## 🐛 Troubleshooting

### Common Issues

**Files not appearing after scan:**
- Verify the repository directory path
- Ensure files have `.fits`, `.fit`, or `.fts` extensions
- Check log tab for processing errors

**External viewer not working:**
- Verify the viewer application path
- Ensure the application accepts FITS files as arguments
- Test the viewer independently

**Slow performance:**
- Large repositories may take time to process
- Use progress dialogs to monitor operations
- Consider processing in smaller batches

**Database corruption:**
- Delete `astrofiler.db` to reset the database
- Reload your repository to rebuild the catalog

### Log Analysis

The Log tab provides detailed information about:
- File processing status
- Error messages and stack traces
- Performance metrics
- Database operations

## 🔬 Technical Details

### Architecture

- **Frontend**: PySide6 (Qt6) for cross-platform GUI
- **Database**: SQLite with Peewee ORM for data persistence
- **FITS Processing**: AstroPy for astronomical file handling
- **Configuration**: INI file format for settings storage

### Dependencies

- **astropy**: FITS file reading and metadata extraction
- **peewee**: Database ORM and SQLite management
- **numpy**: Numerical computations and data handling
- **matplotlib**: Plotting and visualization capabilities
- **pytz**: Timezone handling for astronomical observations
- **PySide6**: Modern Qt6-based GUI framework

### Database Schema

```sql
-- FITS File Catalog
fitsFile:
- id (Primary Key)
- filename (Text)
- object (Text) 
- filter (Text)
- exptime (Real)
- dateObs (DateTime)
- fullPath (Text)
- fitsFileFilter (Text)
```

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Setup

```bash
# Clone and setup development environment
git clone <repository-url>
cd astrofiler-gui
pip install -r requirements.txt

# Run in development mode
python astrofiler.py
```

## 📄 License

This project is licensed under the terms specified in the LICENSE file.

## 🙏 Acknowledgments

- **AstroPy Project**: For excellent FITS file handling capabilities
- **Qt Project**: For the robust PySide6 GUI framework
- **Python Community**: For the amazing ecosystem of scientific packages

---

**Made with ❤️ for the astronomy community**

*For questions, bug reports, or feature requests, please open an issue on the project repository.*