# Smart Telescope Integration Guide

AstroFiler V1.1.0 introduces comprehensive support for smart telescopes, starting with SEESTAR telescopes. This feature allows direct download and processing of FITS files from your telescope's storage.

## 🔭 Supported Telescopes

### SEESTAR
- **Connection**: SMB/CIFS protocol via guest authentication
- **Network Port**: 445 (SMB)
- **Share Name**: "EMMC Images"
- **FITS Path**: "MyWorks" directory
- **Folder Filtering**: Only scans folders ending with "_sub"

## 🚀 Getting Started

### Prerequisites
1. **Network Setup**: Ensure your computer and SEESTAR are on the same network
2. **SMB Access**: Port 445 must be accessible between devices
3. **AstroFiler**: Version 1.1.0 or higher with pysmb dependency

### Quick Start
1. Open AstroFiler
2. Navigate to **Tools** → **Download Repository**
3. Select **SeeStar** from telescope list
4. Enter your network range (auto-detected) or specific hostname
5. Click **Download** to start the process

## 📥 Download Process

### Automatic Network Discovery
- Scans specified network range for active SMB services on port 445
- Attempts connection using SEESTAR hostname
- Falls back to IP scanning if hostname resolution fails

### File Discovery and Filtering
- Connects to "EMMC Images" share
- Scans "MyWorks" directory structure
- **Only processes folders ending with "_sub"** (e.g., "M31_sub", "NGC7000_mosaic_sub")
- Discovers all FITS files within filtered folders

### Download and Processing
1. **Download**: Files downloaded with progress tracking
2. **Header Modification**: 
   - **OBJECT**: Set from folder name (removes "_sub" or "_mosaic_sub" suffix)
   - **MOSAIC**: Set to True for "_mosaic_sub" folders, False otherwise
3. **Repository Integration**: Files processed and added to AstroFiler database
4. **Optional Deletion**: Remove files from telescope after successful processing

## 🗑️ Delete Files on Host Feature

### Safety Features
- **Default State**: Deletion is **disabled by default**
- **Confirmation Dialog**: Multiple warnings before enabling
- **Post-Processing Only**: Files deleted only after successful local processing
- **Error Handling**: Comprehensive error reporting for failed deletions

### How It Works
1. Enable "Delete files on host after download" checkbox
2. Confirm deletion in warning dialog
3. Files are downloaded and processed normally
4. **Only successfully processed files are deleted** from telescope
5. Deletion status reported in progress dialog

### Safety Recommendations
- **Test First**: Always test with a small number of files initially
- **Backup Strategy**: Ensure you have backup procedures for critical data
- **Network Reliability**: Use on stable network connections
- **Monitoring**: Watch progress dialog for any deletion errors

## 🔧 Configuration

### Network Settings
- **Hostname**: Default "SEESTAR" (can be customized)
- **Network Range**: Auto-detected from local IP (e.g., "192.168.1.0/24")
- **Manual IP**: Enter specific IP address if known

### Connection Details
- **Username**: "guest" (fixed for SEESTAR)
- **Password**: "guest" (fixed for SEESTAR)
- **Protocol**: SMB/CIFS over port 445
- **Share**: "EMMC Images" (automatic)

## 📊 Progress Monitoring

### Real-Time Updates
- **Network Scanning**: Shows discovery progress
- **File Discovery**: Reports number of FITS files found
- **Download Progress**: Individual file progress with size information
- **Processing Status**: Header modification and database integration
- **Deletion Status**: Success/failure of remote file deletion

### Cancellation
- **Graceful Stop**: Cancel button stops current operations safely
- **Cleanup**: Temporary files automatically cleaned up
- **Thread Safety**: Proper termination of background operations

## 🐛 Troubleshooting

### Connection Issues
```
Failed to find telescope: Connection timed out
```
**Solutions:**
- Verify SEESTAR is powered on and connected to network
- Check network connectivity between computer and telescope
- Ensure SMB/CIFS is enabled on both devices
- Try using direct IP address instead of hostname

### Permission Errors
```
Failed to connect to telescope: Access denied
```
**Solutions:**
- Verify guest access is enabled on SEESTAR
- Check Windows SMB client settings
- Try connecting manually to `\\SEESTAR\EMMC Images`

### Download Failures
```
Error downloading file: Connection lost
```
**Solutions:**
- Check network stability
- Verify sufficient disk space
- Restart download process
- Check SEESTAR storage status

### Deletion Errors
```
Warning: Failed to delete file from telescope: Permission denied
```
**Solutions:**
- File may be in use by telescope software
- Check telescope storage permissions
- File may have been moved/deleted by telescope
- Try deletion manually through file explorer

## 🔄 Best Practices

### Before Downloading
1. **Test Connection**: Verify you can access `\\SEESTAR\EMMC Images` manually
2. **Check Space**: Ensure sufficient local disk space
3. **Backup**: Consider backing up telescope data before enabling deletion
4. **Network**: Use wired connection for large downloads when possible

### During Downloads
1. **Monitor Progress**: Watch for any error messages
2. **Stable Connection**: Avoid network interruptions
3. **Don't Power Off**: Keep telescope powered during operations

### After Downloads
1. **Verify Files**: Check that all expected files were processed
2. **Review Logs**: Check `astrofiler.log` for any warnings
3. **Validate Headers**: Confirm OBJECT and MOSAIC headers are correct
4. **Backup Database**: Regular backups of `astrofiler.db`

## 🔮 Future Enhancements

### Planned Features
- **Additional Telescopes**: Support for more smart telescope brands
- **Custom Authentication**: Support for password-protected telescopes
- **Selective Download**: Choose specific files/folders before downloading
- **Sync Scheduling**: Automated periodic downloads
- **Cloud Integration**: Direct upload to cloud storage services

### Contributing
- Report telescope compatibility issues
- Submit feature requests for additional telescope support
- Contribute network protocol implementations
- Help with testing on different network configurations

---

For technical support or feature requests, please open an issue on the [AstroFiler GitHub repository](https://github.com/gordtulloch/astrofiler-gui).
