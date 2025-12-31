# iTelescope Smart Telescope Integration

This document describes the iTelescope smart telescope integration in AstroFiler, which allows automatic downloading of calibrated FITS files from your iTelescope account.

## Overview

The iTelescope integration connects to `data.itelescope.net` via secure FTPS (FTP over TLS) to:
- Discover calibrated FITS files in your iTelescope account
- Download files that start with "calibrated" prefix
- Integrate them into your AstroFiler repository

## Configuration

1. **Open AstroFiler Configuration**
   - Go to the Config tab in AstroFiler
   - Scroll down to the "iTelescope Configuration" section

2. **Enter Credentials**
   - **Username**: Your iTelescope account username
   - **Password**: Your iTelescope account password
   - Click "Save Settings" to store the configuration

## Usage

### Using the Smart Telescope Feature

1. **Access Smart Telescope**
   - Go to the main AstroFiler interface
   - Look for the Smart Telescope feature (typically in the menu or toolbar)

2. **Select iTelescope**
   - Choose "iTelescope" from the telescope type dropdown
   - The system will automatically use `data.itelescope.net` as the hostname

3. **Scan for Files**
   - Click "Scan" or "Connect" to discover files
   - The system will:
     - Connect to iTelescope via FTPS
     - Recursively scan all directories
     - Find files starting with "calibrated"
     - Display them in a list

4. **Download Files**
   - Select the files you want to download
   - Choose your local destination
   - Click "Download" to transfer the files

### File Organization

Downloaded files will be:
- **Organized**: Files maintain their directory structure
- **Catalogued**: Automatically imported into AstroFiler database
- **Parsed**: FITS headers analyzed for object, instrument, and date information

## Technical Details

### Protocol
- **FTPS (FTP over TLS)**: Secure encrypted connection
- **Port**: 21 (standard FTP port with TLS negotiation)
- **Authentication**: Username/password based

### File Discovery
- **Selective Root Directory Scanning**: Only scans root-level directories that start with 'T' or 't' (telescope directories)
- **Complete Subfolder Scanning**: Within telescope directories, recursively scans ALL subdirectories
- **Filter Criteria**: Files must start with "calibrated"
- **File Types**: `.fit.zip` files (iTelescope's compressed FITS format)
- **Metadata Extraction**: Object name extracted from filename when possible

### Security
- Credentials stored in `astrofiler.ini` configuration file
- TLS encryption for all data transfer
- No credential caching in memory

## Testing

A test script is provided to verify the integration:

```bash
python test_itelescope.py
```

This script will:
1. Check if credentials are configured
2. Test hostname resolution
3. Attempt FTPS connection
4. List available files

## Troubleshooting

### Common Issues

1. **"Username and password required"**
   - Ensure credentials are configured in Config → iTelescope Configuration
   - Save settings after entering credentials

2. **"FTPS connection error"**
   - Check internet connectivity
   - Verify iTelescope credentials are correct
   - Ensure firewall allows outbound FTP/FTPS (port 21)

3. **"Unable to resolve iTelescope hostname"**
   - Check DNS configuration
   - Try accessing `data.itelescope.net` in a web browser

4. **"No calibrated files found"**
   - Check if you have recent iTelescope sessions
   - Verify files are marked as "calibrated" in your iTelescope account
   - Files must start with "calibrated" prefix

### Logging

Enable debug logging to troubleshoot connection issues:
- Check AstroFiler logs for detailed FTPS connection information
- Look for authentication, file discovery, and download progress messages

## Supported File Types

- **Calibrated Light Frames**: Primary target files
- **File Formats**: Compressed FITS files (.fit.zip)
- **Naming Convention**: Files starting with "calibrated"
- **Compression**: iTelescope provides FITS files in ZIP format for efficient transfer

## Limitations

- Only downloads files with "calibrated" prefix
- Requires valid iTelescope account and credentials
- Internet connection required for operation
- Large files may take time to download

## Future Enhancements

Potential future improvements:
- Selective download filters (by object, date, instrument)
- Automatic sync scheduling
- Progress tracking for large downloads
- Integration with iTelescope session management

## Support

For issues specific to iTelescope integration:
1. Run the test script to diagnose connection issues
2. Check AstroFiler logs for detailed error messages
3. Verify iTelescope account access via web interface
4. Ensure network connectivity and firewall settings