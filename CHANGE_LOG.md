# AstroFiler Change Log

This document tracks major changes and new features in AstroFiler.

## Version 1.1.0

### New Features
- **Master Calibration Frame Creation**: New "Create Masters" button in Sessions tab
- **Siril CLI Integration**: Automated master bias, dark, and flat frame creation using Siril CLI
- **Enhanced Session Tracking**: Added `fitsBiasMaster`, `fitsDarkMaster`, and `fitsFlatMaster` fields to track master calibration frames
- **Database Migration System**: Implemented peewee-migrate for database version control and schema migrations
- **Performance Optimization**: File linking instead of copying during master creation for improved efficiency

### Improvements
- **Intelligent File Handling**: Uses symbolic links, hard links, or copying (in that order) for optimal performance
- **Professional Master Naming**: Systematic naming convention using FITS header metadata
- **Comprehensive Logging**: Enhanced logging for master creation and migration processes
- **Error Handling**: Robust error handling and user feedback throughout the application

### Technical Changes
- Added migration system with `migrate.py` script and `migrations/` directory
- Enhanced database models with master calibration frame fields
- Integrated Siril CLI for professional-grade image stacking
- Updated launch scripts to automatically apply database migrations

### Documentation
- Added `MASTER_CREATION.md` with comprehensive usage guide
- Added `MIGRATIONS.md` with database migration documentation
- Updated `README.md` with new features and requirements

## Version 1.0.0

### Initial Release
- Core FITS file processing and database management
- Session creation and calibration linking
- GUI interface with multiple tabs for different functions
- Basic repository management and file organization
- Logging and configuration management
