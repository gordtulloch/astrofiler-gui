![Astrofile icon](/astrofiler.ico) 

# AstroFiler

**A comprehensive astronomical image file management tool**

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![AstroPy](https://img.shields.io/badge/astronomy-AstroPy-orange.svg)](https://www.astropy.org/)

AstroFiler is a powerful Python application designed for astronomers and astrophotographers to efficiently manage, organize, and catalog their FITS image files. With an intuitive graphical interface, it provides tools for batch processing, file organization, metadata extraction, and session analysis.

**NOTE**: This software still in active development. A release version for Linux, Mac, and Windows is expected end of July 2025. 

## ✨ Features

### 🗂️ **File Management**
- **Repository Scanning**: Recursively scan directories for FITS files, rename to a descriptive name, and move into a centralized repository
- **Batch Processing**: Process multiple files with progress tracking
- **File Organization**: Automatically organize files based on metadata
- **Duplicate Detection**: SHA-256 hash-based duplicate file identification
- **Duplicate Management**: Safely remove duplicate files while preserving one copy
- **Command Line Utilities**: Critical functions exposed as command line utilities to facilitate use of scripts and crontab

### 📊 **Metadata & Analysis**
- **FITS Header Extraction**: Automatically extract and catalog metadata
- **Object Identification**: Track astronomical targets and sessions
- **Date/Time Analysis**: Organize by objects, observation dates, instruments, and cameras
- **File Integrity**: SHA-256 hashing for duplicate detection and verification
### 🛠️ **Tools & Integration**
- **External Viewer Support**: Launch your favorite FITS viewer directly from Astrofile

### 📈 **Session Management**
- **Session Detection**: Automatically group lights and calibration images
- **Session Operations**: Create, update, and clear session groupings
- **Session Export**: Export Lights and Calibration files ready for SIRIL processing

## 📖 User Guide

### Prerequisites

- Python 3.8 or higher
- FITS files to manage

### Getting Started

1. **Install Astrofiler**  

A. **Clone the repository:**
   ```bash
   git clone https://github.com/gordtulloch/astrofiler-gui
   cd astrofiler-gui
   ```

B. **Set up Virtual Environment and Install dependencies (first run only):**

   ```bash
   # In Linux/Mac:
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```  
   ```bash
   # In Windows:
   python -m venv .venv
   .venv/Scripts/Activate
   pip install -r requirements.txt
   ```
C. **Run the application:**
   ```bash
   # Linux/Mac (using virtual environment):
   .venv/bin/python astrofiler.py
   
   # Windows (using virtual environment):
   .venv\Scripts\python astrofiler.py
   
   # Or activate environment first:
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   python astrofiler.py
   ```  

2. **Load Repository**: Use the Config tab to set your FITS file directories. 

**Source Path**: Where new files to be added to the repository are located
**Repository Path**: Where all repository files are moved to

3. **Scan Files**: In the Images tab, click "Load Repo" to scan and catalog your files. You can also rescan your repo using the "Sync Repo" button, clear the Repo (does not delete files) with the "Clear Repo" button (which you can then reload with "Sync Repo") or refresh the list.  

4. **Create Sessions**: In the Sessions tab click on Update Lights and Update Calibrations to create session sets for light and calibration settings. These tie together all images taken in one session and link the most recently updated calibration files to the lights so they can be treated as one unit for processing. Click on Assign Calibration to assign calibration frames to light sessions. Double click on a session to pop up a download dialog that allows you to create a folder of lights and associated calibration frames that can easily be loaded into image processing software like Siril. 

5. **Open Files**: If you have specified an external FITS file viewer (I Like the ASIFitsView program from the ASIStudio product, free from ASI at https://www.zwoastro.com/software/) if you double-click any image it will be opened in that viewer.

### Main Interface

The application features a tabbed interface with six main sections:

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
  - Update Sessions: Refresh Session groupings

#### � **Session Tab**
- **Session Management**: View and manage automatically created Session groups
- **Light Sessions**: Update and organize light frame Sessions by object
- **Calibration Sessions**: Group bias, dark, and flat calibration files
- **Session Operations**:
  - **Update Lights**: Create sessions for unassigned light frames
  - **Update Calibrations**: Group calibration frames by type and date
  - **Clear Sessions**: Remove all session records (files remain unassigned)
- **Progress Tracking**: Real-time progress with cancellation support
- **Session Details**: View session IDs, objects, dates, and master calibration assignments

#### �🔄 **Merge/Rename Tab**
- **Session Merging**: Combine related image sessions or rename all sessions of a particular object
- **File Renaming**: Option to update filenames on disk (default: enabled)

#### � **Duplicates Tab**
- **Duplicate Detection**: Automatically identify files with identical content
- **Hash-Based Analysis**: Uses SHA-256 hashing for accurate duplicate detection
- **Hierarchical Display**: View duplicate groups with individual file details
- **Safe Deletion**: Remove duplicate files while preserving the earliest copy
- **Batch Management**: Process all duplicate groups with one action

#### �📋 **Log Tab**
- **Activity Monitoring**: View real-time application logs
- **Error Tracking**: Monitor and troubleshoot issues
- **Log Management**: Clear logs when needed
- **Debugging**: Detailed operation tracking

#### ℹ️ **About Tab**
- **Application Information**: Version and credits
- **Documentation**: Quick reference and help
- **Contact**: Support and contribution information

### Duplicate Management

#### Detecting Duplicates

1. **Automatic Detection**: File hashes are calculated during repository loading
2. **Manual Refresh**: Use the "Refresh Duplicates" button in the Duplicates tab
3. **Hash-Based Comparison**: SHA-256 hashes ensure accurate duplicate detection

#### Managing Duplicates

1. **View Duplicates**: Navigate to the **Duplicates** tab
2. **Review Groups**: Expand duplicate groups to see individual files
3. **Safe Deletion**: Click "Delete Duplicate Files" to remove extras
4. **Preservation**: The earliest file (by date) is always kept

#### Duplicate Detection Features

- **Content-Based**: Uses file content hashing, not just filenames
- **Batch Processing**: Process all duplicate groups simultaneously
- **Confirmation Dialog**: Requires explicit user confirmation before deletion
- **Progress Feedback**: Shows number of files that can be removed
- **Error Handling**: Graceful handling of file system errors

### Command Line Processing

In the Utilities folder there are the following command line utilities:
- **LoadRepo.py** - load the repository from the incoming folder
- **CreateSessions.py** - process any files that do not have sessions applied
- **LinkSessions.py** - link lights to calibration files 

These files can loaded into crontab (Linux) or Task Scheduler (Windows) to automatically register new images in the repository, combine them into sessions and link the appropriate calibration files. 

For example to run LoadRepo.py daily at 10am when imaging operations are complete via cron, do the following in Linux:

`crontab -e`
`0 10 * * * /home/user/astrofiler/.venv/bin/python /home/user/astrofiler/LoadRepo.py`

## 🔧 Configuration Files

### `astrofiler.ini`
Persistent application settings including:
- Repository directory path
- External tool configurations
- Window preferences
- Last used settings

### `astrofiler.db`
SQLite database containing:
- FITS file catalog with metadata
- SHA-256 file hashes for duplicate detection
- Session relationships
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

**Duplicate files not detected:**
- Ensure files have been processed with the latest version
- Use "Refresh Duplicates" to update the duplicate list
- Check that file hashes were calculated during repository loading

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
- fitsFileId (Primary Key)
- fitsFileName (Text)
- fitsFileObject (Text) 
- fitsFileFilter (Text)
- fitsFileExpTime (Text)
- fitsFileDate (Date)
- fitsFileType (Text)
- fitsFileHash (Text) -- SHA-256 hash for duplicate detection
- fitsFileTelescop (Text)
- fitsFileInstrument (Text)
- fitsFileCCDTemp (Text)
- fitsFileXBinning (Text)
- fitsFileYBinning (Text)
- fitsFileSession (Text)

-- Session Management
fitsSession:
- fitsSessionId (Primary Key)
- fitsSessionObjectName (Text)
- fitsSessionDate (Date)
- fitsSessionTelescope (Text)
- fitsSessionImager (Text)
- fitsBiasSession (Text) - Biases matched to this light session
- fitsDarkSession (Text) - Darks matched to this light session
- fitsFlatSession (Text) - Flats matched to this light session
```

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