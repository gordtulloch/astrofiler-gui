# Smart Telescope Integration Guide

This guide provides comprehensive instructions for using AstroFiler's smart telescope integration features with SEESTAR, StellarMate, iTelescope, and DWARF telescopes. These features allow you to directly connect to your smart or remote telescope, browse its file system, and download FITS files directly into your AstroFiler repository.

## Overview

AstroFiler's smart telescope integration eliminates the need for manual file transfers by providing direct network connectivity to your smart telescope. The system automatically discovers telescopes on your network, handles different protocols (SMB for SEESTAR/StellarMate, FTP for DWARF), and manages the complete download and processing workflow.

### Supported Telescopes

| Telescope | Protocol | Status | Features |
|-----------|----------|--------|----------|
| SEESTAR S50/S60 | SMB/CIFS | Stable | Full folder browsing, selective download, header enhancement |
| StellarMate | SMB/CIFS | Stable | Network file access, FITS management, observatory integration |
| iTelescope | FTP | Stable | Downloads calibrated images only from t* folders on data.iTelescope.com |
| DWARF II/III | FTP | Experimental | Folder structure validation, automatic header correction, dual camera support |

---

## SEESTAR Telescope Setup

### Prerequisites

- SEESTAR telescope connected to your local network
- SEESTAR and computer on the same network subnet
- SMB/CIFS networking enabled on your computer

### Network Configuration

#### Automatic Discovery (Recommended)
1. Ensure your SEESTAR is powered on and connected to WiFi
2. The telescope should be accessible via `seestar.local` or `SEESTAR.local`
3. AstroFiler will automatically attempt to connect using mDNS resolution

#### Manual IP Configuration
If automatic discovery fails:
1. Find your SEESTAR's IP address from your router's admin panel
2. Use the IP address directly in AstroFiler's connection dialog
3. Common SEESTAR IP ranges: `192.168.1.x` or `10.0.0.x`

### Connecting to SEESTAR

1. **Launch AstroFiler** and navigate to the **Images** tab
2. **Click "Download from Telescope"** button
3. **Select Protocol**: Choose "SMB (SEESTAR/StellarMate)"
4. **Enter Connection Details**:
   - **Hostname**: `seestar.local` (or your telescope's IP address)
   - **Username**: `root` (default)
   - **Password**: `123456` (default, or your custom password)
   - **Share Name**: `Shares` (default)
5. **Click "Connect"** to establish connection

### SEESTAR File Structure

SEESTAR telescopes organize files in a specific folder structure:
```
/Shares/
├── AstroPhotos/
│   ├── 2024-01-15_ObjectName/
│   │   ├── ObjectName_sub_001.fits    # Light frames
│   │   ├── ObjectName_sub_002.fits
│   │   └── ...
│   ├── Calibration/
│   │   ├── Dark_frames/
│   │   ├── Flat_frames/
│   │   └── Bias_frames/
│   └── ...
```

### Downloading SEESTAR Files

#### Selective Download (Recommended)
1. **Browse Folders**: Navigate through the telescope's folder structure
2. **Select Target Folders**: Choose specific observation sessions
3. **Filter Options**:
   - ✅ **Download only "_sub" files**: Downloads processed light frames only
   - ✅ **Skip calibration folders**: Avoids downloading large calibration datasets
4. **Start Download**: Click "Download Selected" to begin transfer

#### Bulk Download
1. **Select Root Folder**: Choose `/AstroPhotos/` for all observations
2. **Configure Filters** as needed
3. **Monitor Progress**: Real-time progress tracking with file-by-file status
4. **Cancellation**: Use "Cancel" button for graceful interruption

### SEESTAR Header Enhancement

AstroFiler automatically enhances SEESTAR FITS headers during download:

- **OBJECT**: Extracted from folder name (e.g., `2024-01-15_M42` → `OBJECT=M42`)
- **DATE-OBS**: Extracted from filename timestamps
- **INSTRUME**: Set to `SEESTAR` 
- **TELESCOP**: Set to `SEESTAR`
- **Additional metadata**: Session information and processing notes

---

## StellarMate Setup

### Prerequisites

- StellarMate device (any version) with network connectivity
- StellarMate connected to your local network
- SMB/CIFS networking enabled on your computer
- FITS files accessible through StellarMate's file system

### Network Configuration

#### Automatic Discovery (Recommended)
1. Ensure your StellarMate device is powered on and connected to network
2. The device should be accessible via `stellarmate.local`
3. AstroFiler will automatically attempt to connect using mDNS resolution

#### Manual IP Configuration
If automatic discovery fails:
1. Find your StellarMate's IP address from your router's admin panel or StellarMate interface
2. Use the IP address directly in AstroFiler's connection dialog
3. Common StellarMate IP ranges depend on your network configuration

### Connecting to StellarMate

1. **Launch AstroFiler** and navigate to the **Images** tab
2. **Click "Download from Telescope"** button
3. **Select Protocol**: Choose "SMB (SEESTAR/StellarMate)"
4. **Enter Connection Details**:
   - **Hostname**: `stellarmate.local` (or your StellarMate's IP address)
   - **Username**: `stellarmate` (default) or your configured username
   - **Password**: Your StellarMate password
   - **Share Name**: Appropriate share (commonly `home` or configured shares)
5. **Click "Connect"** to establish connection

### StellarMate File Structure

StellarMate devices typically organize astronomical files in user-defined directories:
```
/home/stellarmate/
├── Pictures/
│   ├── YYYY-MM-DD/
│   │   ├── Light_frames/
│   │   ├── Calibration/
│   │   └── Processed/
├── Documents/
└── Observatory_Data/
```

**Note**: File organization varies based on StellarMate configuration and connected software (KStars, EKOS, etc.)

### Downloading StellarMate Files

#### Observatory Integration
1. **Browse Directories**: Navigate through StellarMate's file system
2. **Locate FITS Files**: Find observation sessions and calibration data
3. **Select Files**: Choose specific files or entire observation runs
4. **Download**: Transfer files to AstroFiler for processing

#### Integration with EKOS/KStars
- StellarMate files captured through EKOS are automatically organized
- Observation logs and metadata may be preserved
- Calibration frames can be automatically linked to light sessions

### StellarMate Header Processing

AstroFiler processes StellarMate FITS files with standard FITS header handling:

- **Preservation**: Existing FITS headers maintained
- **Enhancement**: Additional metadata added where beneficial
- **INSTRUME**: Preserved from original equipment settings
- **TELESCOP**: May be enhanced based on observatory configuration
- **Observatory Data**: Location and equipment information preserved

## iTelescope Setup

### Prerequisites

- iTelescope device (any version) with network connectivity
- iTelescope connected to your local network
- SMB/CIFS networking enabled on your computer
- FITS files accessible through iTelescope's file system

### Network Configuration

#### Automatic Discovery (Recommended)
1. Ensure your iTelescope device is powered on and connected to network
2. The device should be accessible via `iTelescope.local`
3. AstroFiler will automatically attempt to connect using mDNS resolution

#### Manual IP Configuration
If automatic discovery fails:
1. Find your iTelescope's IP address from your router's admin panel or iTelescope interface
2. Use the IP address directly in AstroFiler's connection dialog
3. Common iTelescope IP ranges depend on your network configuration

### Connecting to iTelescope

1. **Launch AstroFiler** and navigate to the **Images** tab
2. **Click "Download from Telescope"** button
3. **Select Protocol**: Choose "SMB (SEESTAR/iTelescope)"
4. **Enter Connection Details**:
   - **Hostname**: `iTelescope.local` (or your iTelescope's IP address)
   - **Username**: `iTelescope` (default) or your configured username
   - **Password**: Your iTelescope password
   - **Share Name**: Appropriate share (commonly `home` or configured shares)
5. **Click "Connect"** to establish connection

### Downloading iTelescope Files

#### Observatory Integration
1. **Browse Directories**: Navigate through iTelescope's file system
2. **Locate FITS Files**: Find observation sessions with 'calibrated' prefix
3. **Select Files**: Choose specific files or entire observation runs
4. **Download**: Transfer files to AstroFiler for processing

### iTelescope Header Processing

AstroFiler processes iTelescope FITS files with standard FITS header handling:

- **Preservation**: Existing FITS headers maintained
- **Enhancement**: Additional metadata added where beneficial
- **INSTRUME**: Preserved from original equipment settings
- **TELESCOP**: May be enhanced based on observatory configuration
- **Observatory Data**: Location and equipment information preserved

---

## DWARF Telescope Setup

### Prerequisites

- DWARF II or DWARF III telescope
- FTP service enabled on telescope
- Telescope connected to your local network

### Network Configuration

#### DWARF Network Setup
1. **Enable FTP Service** on your DWARF telescope (consult DWARF manual)
2. **Note FTP Credentials** (usually found in telescope settings)
3. **Verify Network Connectivity** between telescope and computer

### Connecting to DWARF

1. **Navigate to Images Tab** in AstroFiler
2. **Click "Download from Telescope"**
3. **Select Protocol**: Choose "FTP (DWARF)"
4. **Enter Connection Details**:
   - **Hostname**: DWARF telescope IP address
   - **Username**: (from telescope FTP settings)
   - **Password**: (from telescope FTP settings)
   - **Port**: `21` (standard FTP) or custom port
5. **Test Connection** before proceeding

### DWARF File Structure

DWARF telescopes use a structured folder organization:
```
/
├── DWARF_RAW_M42/          # Light frames for M42
│   ├── cam_0/              # Telephoto camera
│   └── cam_1/              # Wide-angle camera
├── DWARF_RAW_M31/          # Light frames for M31
├── CALI_FRAME/             # Calibration frames
│   ├── BIAS/
│   ├── DARK/
│   └── FLAT/
├── DWARF_DARK/             # Dark frames
└── ...
```

### DWARF File Processing

#### Folder Structure Validation
AstroFiler validates DWARF folder structure before download:
- ✅ **DWARF_RAW_*** folders for light frames
- ✅ **CALI_FRAME** folder for calibration data
- ✅ **DWARF_DARK** folder for dark frames
- ❌ **Invalid structure** triggers warning messages

#### Dual Camera Support
DWARF telescopes have two cameras:
- **cam_0**: Telephoto/main imaging camera
- **cam_1**: Wide-angle/guide camera

AstroFiler processes both cameras and sets appropriate headers:
- **INSTRUME**: `TELE` for cam_0, `WIDE` for cam_1
- **TELESCOP**: `DWARF`

#### Header Correction
DWARF FITS files often have incomplete headers. AstroFiler automatically corrects:
- **OBJECT**: Extracted from `DWARF_RAW_*` folder names
- **IMAGETYP**: Set based on folder structure (LIGHT, DARK, BIAS, FLAT)
- **FILTER**: Extracted from metadata when available
- **DATE-OBS**: Corrected format and timezone

---

## Download Workflow

### Pre-Download Checklist

1. ✅ **Network Connectivity**: Telescope accessible from computer
2. ✅ **Credentials Verified**: Username/password correct
3. ✅ **Disk Space**: Sufficient space for downloaded files
4. ✅ **Repository Configured**: AstroFiler source/repo folders set

### Download Process

#### Step 1: Connection
- AstroFiler establishes connection using specified protocol
- Connection status displayed in real-time
- Error messages shown for connection failures

#### Step 2: Discovery
- **Folder Structure Scan**: AstroFiler maps telescope directory structure
- **File Enumeration**: Counts and catalogs available files
- **Size Calculation**: Estimates total download size

#### Step 3: Selection
- **Interactive Browser**: Navigate telescope folders visually
- **Filter Application**: Apply download filters (_sub files, folder types)
- **Preview**: Review selected files before download

#### Step 4: Transfer
- **Progress Tracking**: Real-time download progress per file
- **Error Handling**: Retry failed transfers automatically
- **Integrity Checking**: Verify file completeness after transfer

#### Step 5: Processing
- **Header Enhancement**: Apply telescope-specific header corrections
- **File Placement**: Move files to AstroFiler incoming folder
- **Database Registration**: Register files in AstroFiler database
- **Session Creation**: Automatically create observation sessions

### Post-Download Options

#### Delete on Host (Advanced)
**⚠️ Use with Extreme Caution**

This feature permanently deletes files from the telescope after successful download:

1. **Enable with Care**: Multiple confirmation dialogs required
2. **Safety Checks**: Files deleted only after successful local processing
3. **Verification Required**: Database registration must complete successfully
4. **Error Reporting**: Comprehensive feedback on deletion operations

**When to Use**:
- Limited telescope storage space
- Confident in download integrity
- Have backup procedures in place

**When NOT to Use**:
- First time using AstroFiler
- Network connectivity issues
- Critical observation data

---

## Troubleshooting

### SEESTAR Connection Issues

#### "Cannot Connect to SEESTAR"
**Solutions**:
1. **Check Network**: Ensure SEESTAR and computer on same network
2. **Try IP Address**: Use direct IP instead of `seestar.local`
3. **Verify Credentials**: Confirm username (`root`) and password
4. **Firewall Check**: Ensure SMB ports (445, 139) not blocked

#### "Authentication Failed"
**Solutions**:
1. **Default Credentials**: Try `root` / `123456`
2. **Custom Password**: Use password set in SEESTAR app
3. **Guest Access**: Some SEESTAR firmware allows guest login

#### "No Files Found"
**Solutions**:
1. **Check Share Path**: Verify `/Shares/` or `/AstroPhotos/` exists
2. **File Location**: Ensure observation files are in expected folders
3. **Permissions**: Verify read access to telescope folders

### StellarMate Connection Issues

#### "Cannot Connect to StellarMate"
**Solutions**:
1. **Check Network**: Ensure StellarMate and computer on same network
2. **Try IP Address**: Use direct IP instead of `stellarmate.local`
3. **Verify Credentials**: Confirm username (`stellarmate`) and password
4. **Firewall Check**: Ensure SMB ports (445, 139) not blocked
5. **Service Status**: Verify SMB/CIFS service running on StellarMate

#### "Authentication Failed"
**Solutions**:
1. **Check Credentials**: Use configured StellarMate username and password
2. **User Account**: Ensure user account exists and has appropriate permissions
3. **SSH Access**: Test SSH connectivity to verify credentials

#### "No Observatory Files Found"
**Solutions**:
1. **Check File Paths**: Navigate to correct observation directories
2. **EKOS Integration**: Verify EKOS/KStars has captured files
3. **File Permissions**: Ensure read access to user directories
4. **Share Configuration**: Verify SMB shares are properly configured

### DWARF Connection Issues

#### "FTP Connection Failed"
**Solutions**:
1. **FTP Service**: Ensure FTP enabled on DWARF telescope
2. **Network Settings**: Verify telescope IP address
3. **Port Configuration**: Confirm FTP port (usually 21)
4. **Credentials**: Check username/password from telescope settings

#### "Invalid Folder Structure"
**Solutions**:
1. **Folder Names**: Ensure `DWARF_RAW_*`, `CALI_FRAME` folders exist
2. **File Permissions**: Verify read access to telescope directories
3. **Firmware Version**: Update DWARF firmware if needed

### General Issues

#### "Download Stalled"
**Solutions**:
1. **Network Stability**: Check WiFi connection strength
2. **Telescope Power**: Ensure telescope has adequate power
3. **Restart Connection**: Cancel and reconnect to telescope
4. **Reduce Concurrent Downloads**: Lower transfer threads

#### "Header Processing Errors"
**Solutions**:
1. **File Corruption**: Re-download affected files
2. **FITS Format**: Verify files are valid FITS format
3. **Telescope Firmware**: Update telescope firmware
4. **Manual Correction**: Use AstroFiler's header editing tools

---

## Best Practices

### Network Setup

1. **Dedicated WiFi**: Use dedicated network for astronomy equipment
2. **Static IPs**: Assign static IP addresses to telescopes
3. **Signal Strength**: Ensure strong WiFi signal to telescope location
4. **Bandwidth Management**: Limit other network activity during downloads

### Download Strategy

1. **Test Small Downloads**: Start with single observation sessions
2. **Selective Downloading**: Use filters to download only needed files
3. **Regular Transfers**: Download frequently to avoid storage issues
4. **Backup Verification**: Verify downloads before deleting telescope files

### File Management

1. **Folder Organization**: Let AstroFiler organize files automatically
2. **Session Grouping**: Allow automatic session creation and linking
3. **Header Validation**: Review enhanced headers after download
4. **Duplicate Checking**: Use AstroFiler's duplicate detection features

### Maintenance

1. **Regular Updates**: Keep AstroFiler and telescope firmware updated
2. **Network Monitoring**: Monitor network connectivity during sessions
3. **Storage Management**: Maintain adequate free space on both systems
4. **Log Review**: Check AstroFiler logs for connection issues

---

## Integration with AstroFiler Workflow

### Automated Processing

Downloaded telescope files automatically integrate with AstroFiler's processing pipeline:

1. **File Registration**: Files registered in database with enhanced metadata
2. **Session Creation**: Observation sessions automatically created and linked
3. **Calibration Matching**: Calibration frames matched to light frames
4. **Duplicate Detection**: SHA-256 hashing prevents duplicate imports
5. **Repository Organization**: Files organized in standard repository structure

### Manual Review Options

1. **Header Inspection**: Review and edit enhanced headers if needed
2. **Session Management**: Manually adjust session groupings
3. **Object Naming**: Use merge/rename tools for object standardization
4. **Quality Control**: Review downloaded files for completeness

---

## Future Enhancements

### Planned Features

1. **Additional Telescopes**: Support for more smart telescope brands
2. **Real-time Monitoring**: Live monitoring of telescope status
3. **Scheduled Downloads**: Automatic periodic file retrieval
4. **Advanced Filtering**: More sophisticated file selection criteria
5. **Two-way Sync**: Upload processed images back to telescope

### Experimental Features

1. **DWARF Advanced Integration**: Enhanced DWARF protocol support
2. **Wireless Transfer Optimization**: Improved transfer speeds
3. **Multi-telescope Management**: Simultaneous connections to multiple telescopes

---

## Support and Resources

### Documentation Links

- [Main AstroFiler Documentation](../README.md)
- [Installation Guide](../wiki/Installation.md)
- [User Guide](../wiki/UserGuide.md)
- [Troubleshooting Guide](../wiki/Troubleshooting.md)

### Community Support

- **GitHub Issues**: Report bugs and request features
- **User Forum**: Community discussions and tips
- **Video Tutorials**: Step-by-step setup guides

### Technical Support

For technical issues with smart telescope integration:
1. Check this guide for common solutions
2. Review AstroFiler logs for error details
3. Consult telescope manufacturer documentation
4. Submit detailed bug reports with logs and network configuration