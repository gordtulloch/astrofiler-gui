![Astrofile icon](/astrofiler.ico) 

# AstroFiler

**A comprehensive astronomical image file management tool**

[![Python3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![AstroPy](https://img.shields.io/badge/astronomy-AstroPy-orange.svg)](https://www.astropy.org/)

AstroFiler is a powerful application designed for astronomers and astrophotographers to efficiently manage, organize, and catalog their FITS image files. With an intuitive graphical interface, it provides tools for batch processing, file organization, metadata extraction, and session analysis. Detailed documentation is in the Gitub Wiki.

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
- **Session Linking**: Automatically link calibration sessions to light sessions
- **Session Export**: Export Lights and Calibration files ready for SIRIL processing

### **Future Versions**
- **XISF support**: Load XISF files and extract FITS headers
- **Processed Images**: Support for processed images and formats (XISF, TIFF, JPG)
- **Archiving**: Saving images to Google Cloud Services, Dropbox, Amazon etc.
- **Auto-Calibration**: Calibrate any lights with calibration files (build masters first) with Siril
- **Thumbnails/Sample Stacks**: Use Siril to create stacked images, stretch, and create thumbnail

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
