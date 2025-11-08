# Cloud Services Integration Guide

## Google Cloud Storage Setup

AstroFiler supports comprehensive cloud synchronization with Google Cloud Storage for backing up your astronomy files and databases. The new Cloud Sync system provides multiple sync profiles, real-time progress tracking, and intelligent file management.

### Prerequisites

- Google Cloud Platform account
- A Google Cloud project (or create a new one)
- AstroFiler v1.2.0 or later

### Key Features

- **Multiple Sync Profiles**: 
  - **Complete Sync**: Revolutionary bidirectional synchronization - downloads missing files from cloud AND uploads files without cloud URLs
  - **Backup Only**: One-way backup - uploads local files to cloud for safe storage
  - **On Demand**: Manual file-by-file synchronization (coming soon)
- **Smart File Detection**: Only uploads files that don't exist in cloud to avoid duplicates and reduce transfer time
- **Database Integration**: Tracks cloud URLs for all files with `fitsFileCloudURL` field enabling future remote access features
- **Images View Integration**: Local/Cloud status icons show file storage locations at a glance
- **Command-Line Automation**: Complete command-line interface (`CloudSync.py`) with automation scripts for cron/Task Scheduler
- **Analysis Mode**: Analyze cloud storage contents and compare with local database without performing sync
- **Real-time Progress**: Live progress tracking with file-by-file updates and cancellation support
- **Comprehensive Error Handling**: Clear error messages for authentication, bucket access, and network configuration issues
- **Directory Structure Preservation**: Maintains your local repository folder structure in cloud storage
- **Self-Contained Architecture**: All cloud operations integrated for improved reliability and maintainability

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top of the page
3. Click "New Project"
4. Enter a project name (e.g., "astrofiler-backup")
5. Click "Create"

## Step 2: Enable Cloud Storage API

1. In the Google Cloud Console, ensure your project is selected
2. Navigate to **APIs & Services** > **Library**
3. Search for "Cloud Storage API"
4. Click on "Cloud Storage API" and click **Enable**

## Step 3: Create a Storage Bucket

1. Navigate to **Cloud Storage** > **Buckets**
2. Click **Create Bucket**
3. Choose a globally unique bucket name (e.g., "my-astrofiler-backup-2025")
4. Choose a location (select one close to you for better performance)
5. Choose "Standard" storage class for frequent access
6. Choose "Uniform" access control
7. Click **Create**

## Step 4: Create a Service Account

1. Navigate to **IAM & Admin** > **Service Accounts**
2. Click **Create Service Account**
3. Enter details:
   - **Service account name**: `astrofiler-sync`
   - **Description**: `Service account for AstroFiler cloud synchronization`
4. Click **Create and Continue**
5. Assign the following role:
   - **Storage Object Admin** (allows read/write access to bucket objects)
6. Click **Continue**
7. Click **Done**

## Step 5: Create and Download Service Account Key

1. In the Service Accounts list, find your newly created service account
2. Click on the service account name
3. Go to the **Keys** tab
4. Click **Add Key** > **Create New Key**
5. Select **JSON** format
6. Click **Create**
7. The JSON key file will be automatically downloaded
8. **Important**: Store this file securely and never share it publicly
9. Move the file to a secure location on your computer (e.g., `~/.config/astrofiler/gcs-key.json`)

## Step 6: Configure AstroFiler Cloud Sync

### Open Cloud Sync Configuration

1. Launch AstroFiler
2. Go to **Tools** > **Configuration**
3. Navigate to the **Cloud Sync** section

### Configure Cloud Settings

1. **Cloud Vendor**: Select "Google Cloud Storage" from the dropdown

2. **Bucket URL**: Enter your bucket name (with or without gs:// prefix):
   ```
   astrofiler-repository
   ```
   or
   ```
   gs://astrofiler-repository
   ```

3. **Authentication File**: 
   - Click the **Browse...** button
   - Navigate to and select your downloaded JSON key file
   - Or manually enter the full path: `D:/path/to/your-service-account-key.json`

4. **Sync Profile**: Choose your synchronization strategy:
   - **Complete**: Full bidirectional sync (future implementation)
   - **Backup**: Upload local files that don't exist in cloud (recommended for initial backup)
   - **On Demand**: Manual file selection (future implementation)

5. Click **OK** to save settings

### Verify Configuration

The Cloud Sync dialog displays your current configuration:
- Cloud Vendor: Google Cloud Storage
- Bucket: your-bucket-name
- Authentication: Configured ✓
- Sync Profile: Selected profile with description

## Step 7: Using Cloud Sync Operations

### Analyze Cloud Storage

Before performing sync operations, analyze your cloud storage:

1. Go to **Tools** > **Cloud Sync**
2. Click **Analyze**
3. This will:
   - Download a listing of all files in your cloud bucket
   - Compare with local files in the database
   - Update cloud URLs for files that exist in both locations
   - Show progress with real-time updates

### Backup Only Sync (Recommended First Step)

For initial cloud backup of your FITS files:

1. Ensure your sync profile is set to **Backup**
2. In the Cloud Sync dialog, click **Sync**
3. Confirm the operation details
4. The system will:
   - Check each local FITS file in the database
   - Upload files that don't exist in the cloud
   - Skip files that already exist (no duplicates)
   - Update database with cloud URLs for all processed files
   - Show detailed progress and statistics

### Sync Profile Details

#### Backup Only Profile
- **Purpose**: One-way backup from local to cloud
- **Behavior**: 
  - Uploads local files missing from cloud
  - Preserves original directory structure
  - Updates database with cloud URLs
  - Never overwrites existing cloud files
- **Best for**: Initial backup, periodic backup of new files

#### Complete Profile (Future)
- **Purpose**: Full bidirectional synchronization
- **Behavior**: 
  - Uploads missing local files to cloud
  - Downloads missing cloud files to local
  - Resolves conflicts with user input
- **Best for**: Multi-device synchronization

#### On Demand Profile (Future)
- **Purpose**: Selective file synchronization
- **Behavior**: 
  - User selects specific files or folders
  - Choose upload or download direction
  - Manual conflict resolution
- **Best for**: Selective backup, sharing specific observations

## Understanding the Cloud Sync System

### Database Integration

The Cloud Sync system is tightly integrated with AstroFiler's database:

- **Cloud URL Tracking**: Each FITS file record includes a `fitsFileCloudURL` field
- **Automatic Updates**: Sync operations automatically update database records
- **Persistent Links**: Cloud URLs are preserved across application restarts
- **Query Integration**: Future features will leverage cloud URLs for remote access

### File Processing Logic

#### Path Handling
- **Repository Structure**: Maintains your local repository folder structure in cloud
- **Relative Paths**: Uses relative paths from repository root for cloud storage
- **Cross-Platform**: Normalizes path separators for consistent cloud naming
- **External Files**: Files outside repository use filename only

#### Upload Intelligence
- **Existence Check**: Verifies if file exists in cloud before upload
- **Duplicate Prevention**: Skips upload if file already exists
- **Progress Tracking**: Real-time updates during upload process
- **Error Recovery**: Continues processing if individual files fail

### Progress and Monitoring

#### Real-time Feedback
- **File-by-File Progress**: Shows current file being processed
- **Statistics**: Displays counts of processed, uploaded, and error files
- **Cancellation**: User can cancel operation at any time
- **Completion Summary**: Detailed results after operation finishes

#### Error Handling
- **Bucket Validation**: Checks bucket exists before starting operations
- **Authentication Verification**: Validates service account access
- **Permission Checking**: Specific errors for access denied scenarios
- **Network Resilience**: Handles temporary network issues gracefully

## Advanced Features (v1.2.0+)

### Hash-Based Duplicate Detection and Optimization

AstroFiler's cloud sync system includes advanced duplicate detection and performance optimization features:

#### Smart Upload Prevention
- **MD5 Hash Comparison**: Calculates MD5 hashes for local files and compares with cloud metadata
- **Content-Based Detection**: Identifies identical files even with different names or paths
- **Bandwidth Optimization**: Skips uploads for files that already exist with identical content
- **Performance Enhancement**: Bulk metadata retrieval reduces API calls and speeds up sync operations

#### Cloud Storage Duplicate Analysis
The **Analyze** function now includes comprehensive duplicate detection:

1. **Duplicate Scanning**: Analyzes all cloud files for identical content based on MD5 hashes
2. **Storage Optimization**: Identifies wasted storage space from duplicate files
3. **Detailed Reporting**: Shows duplicate groups with file paths and space calculations
4. **Cost Reduction**: Helps identify files that can be safely removed to reduce storage costs

#### Enhanced Analysis Features
- **Multi-Tier File Matching**: 
  - Exact filename matching with hash verification
  - Partial filename matching with content verification
  - Pure hash-based matching across all files for maximum accuracy
- **Progress Phases**: 
  - "Downloading file listing from cloud..."
  - "Analyzing cloud storage for duplicates..."
  - "Analyzing matches with local files..."
- **Comprehensive Statistics**:
  - Local match breakdown (exact filename, hash-verified, partial matches)
  - Duplicate detection results (groups found, total duplicates, wasted space)
  - Storage optimization opportunities

#### Using Duplicate Detection

**Basic Analysis with Duplicate Detection:**
1. Go to **Tools** > **Cloud Sync**
2. Click **Analyze**
3. Review results showing:
   - Cloud files found
   - Local matches identified
   - Duplicate groups detected
   - Wasted storage space

**Detailed Duplicate Report:**
1. If duplicates are found, click **Help** in the results dialog
2. View detailed report showing:
   - Each duplicate group with file count and wasted space
   - Full file paths for all duplicates
   - MD5 hash information for verification
   - Storage space calculations

**Optimizing Storage:**
- Use duplicate reports to identify redundant files
- Safely remove duplicate files from cloud storage to reduce costs
- Consider standardizing file naming conventions to prevent future duplicates

### Performance Improvements

#### Efficient Sync Operations
- **Bulk Hash Retrieval**: Downloads all cloud file metadata in one operation
- **Smart Upload Logic**: Three-tier decision system (skip/upload/overwrite)
- **Reduced API Calls**: Minimizes individual file checks for better performance
- **Progress Optimization**: Shows efficiency statistics (files skipped vs uploaded)

#### Enhanced User Experience
- **Real-time Feedback**: Live progress updates with descriptive messages
- **Cancellation Support**: User can abort operations cleanly at any time
- **Detailed Completion**: Comprehensive statistics showing time and bandwidth saved
- **Error Recovery**: Graceful handling of network issues and partial failures

## Step 8: Best Practices

### Initial Setup Workflow

1. **Configure Cloud Sync**: Set up bucket, authentication, and sync profile
2. **Test Bucket Access**: Use Analyze function to verify connectivity
3. **Initial Backup**: Run Backup Only sync to upload all existing files
4. **Verify Results**: Check completion statistics and error reports
5. **Monitor Progress**: Review logs for any configuration issues

### Ongoing Usage

#### For Backup Workflows
- Run Backup Only sync periodically to upload new observations
- Use Analyze function to verify cloud storage consistency
- Monitor storage usage in Google Cloud Console
- Review sync logs for any upload failures

#### File Organization
- Maintain consistent directory structure in repository
- Avoid moving files after they've been synced to cloud
- Use meaningful folder names that translate well to cloud storage
- Consider storage costs when organizing large file collections

### Storage Management

#### Cost Optimization
- **Storage Classes**: Use Standard for frequently accessed files, Nearline/Coldline for archival
- **Lifecycle Policies**: Automatically move old files to cheaper storage classes
- **Compression**: Consider compressing non-FITS files before upload
- **Monitoring**: Set up billing alerts to track storage costs

#### Security Considerations
- **Access Control**: Use least-privilege principle for service accounts
- **Key Rotation**: Regularly rotate service account keys
- **Audit Logging**: Enable Cloud Audit Logs for access monitoring
- **Encryption**: Data is encrypted in transit and at rest by default

## Security Best Practices

### Protect Your Service Account Key

1. **Never commit** the JSON key file to version control
2. **Restrict file permissions**: `chmod 600 ~/.config/astrofiler/gcs-key.json`
3. **Use a dedicated directory** for storing cloud credentials
4. **Regularly rotate** service account keys (recommended every 90 days)

### Bucket Security

1. **Enable versioning** on your bucket to protect against accidental overwrites
2. **Configure lifecycle policies** to manage storage costs
3. **Monitor access** through Cloud Logging
4. **Consider encryption** for sensitive astronomical data

## Troubleshooting

### Common Issues

#### Configuration Problems

**"Cloud sync is not configured"**
- Verify all fields in Cloud Sync configuration are filled
- Ensure bucket URL is not empty
- Check that authentication file path is set

**"Authentication file is not configured or not found"**
- Verify the JSON key file exists at the specified path
- Check file permissions (should be readable by AstroFiler)
- Ensure the file is a valid JSON service account key

**"Error validating cloud configuration: Failed to authenticate"**
- Verify the JSON key file is valid and not corrupted
- Check that the service account still exists in Google Cloud
- Ensure the service account has proper permissions

#### Bucket Access Issues

**"The bucket 'bucket-name' does not exist"**
- Verify bucket name is correct in configuration
- Check that bucket exists in Google Cloud Console
- Ensure bucket name doesn't include gs:// prefix in some configurations

**"Access denied to bucket 'bucket-name'"**
- Verify service account has Storage Object Admin role
- Check bucket permissions in Google Cloud Console
- Ensure service account key is still valid

**"Authentication failed"**
- Service account key may be expired or revoked
- Generate new service account key
- Update authentication file path in configuration

#### Upload/Sync Issues

**"Local file not found"**
- Database may contain outdated file paths
- Run Load Repository to refresh database
- Check that files haven't been moved or deleted

**"Failed to upload file"**
- Check network connectivity
- Verify sufficient storage quota in Google Cloud
- Review error logs for specific network issues

#### Performance Issues

**Slow upload speeds**
- Check internet connection bandwidth
- Consider bucket location relative to your location
- Large files may take significant time to upload

**High memory usage during sync**
- Large number of files may consume memory
- Consider syncing in smaller batches
- Monitor system resources during operations

### Advanced Troubleshooting

#### Enable Detailed Logging

1. Check AstroFiler log files for detailed error messages
2. Look for specific error codes (404, 403, 401) in logs
3. Review Google Cloud Console for API usage and errors

#### Test Bucket Access Manually

Using Google Cloud SDK (gsutil):
```bash
# Test bucket access
gsutil ls gs://your-bucket-name/

# Test file upload
echo "test" | gsutil cp - gs://your-bucket-name/test.txt

# Test file download
gsutil cp gs://your-bucket-name/test.txt -
```

#### Verify Service Account Permissions

1. Go to Google Cloud Console → IAM & Admin → IAM
2. Find your service account in the list
3. Verify it has "Storage Object Admin" role
4. Check bucket-level permissions if using bucket-specific access

### Getting Help

If you continue to experience issues:

1. **Check Logs**: Review astrofiler.log for detailed error messages
2. **Update Software**: Ensure you're using the latest version of AstroFiler
3. **Documentation**: Consult Google Cloud Storage documentation for API limits
4. **Community Support**: Post questions with log excerpts and configuration details

### Migration from Legacy Google Sync

If upgrading from the previous Google Sync feature:

1. **Backup Configuration**: Note your current bucket and authentication settings
2. **Update Configuration**: Use new Cloud Sync configuration interface
3. **Verify Settings**: Ensure bucket URL and authentication file are correctly set
4. **Test Connection**: Use Analyze function to verify connectivity
5. **Gradual Migration**: Start with Backup Only profile for safety
- Check that the service account has Storage Object Admin role
- Ensure the Cloud Storage API is enabled

**Permission Denied**
- Verify bucket name is correct
- Check that the service account has access to the bucket
- Ensure the bucket exists and is in the correct project

**Network Issues**
- Check internet connectivity
- Verify firewall settings allow HTTPS traffic to googleapis.com
- Consider network timeouts for large files

### Debug Information

When debug mode is enabled, check the AstroFiler log file (`astrofiler.log`) for detailed information about:
- Files that would be synchronized
- Authentication status
- Bucket connectivity
- Any errors or warnings

### Getting Help

If you encounter issues:
1. Enable debug mode and check the logs
2. Verify your Google Cloud setup following this guide
3. Check the [Google Cloud Storage documentation](https://cloud.google.com/storage/docs)
4. Report issues on the AstroFiler project repository

## Cost Considerations

### Google Cloud Storage Pricing

- **Storage**: ~$0.02 per GB per month (Standard storage)
- **Operations**: Small cost per API operation
- **Network**: Egress charges may apply for downloads

### Estimating Costs

For typical astronomy workflows:
- 100GB of FITS files: ~$2/month storage
- Regular sync operations: ~$0.01-0.10/month
- Most amateur astronomy setups: <$5/month total

### Cost Optimization

1. **Use lifecycle policies** to move old data to cheaper storage classes
2. **Consider regional buckets** to reduce network costs
3. **Monitor usage** through the Google Cloud Console billing section
4. **Set up billing alerts** to avoid unexpected charges

## Advanced Configuration

### Custom Bucket Policies

You can create more restrictive IAM policies for enhanced security:

```json
{
  "bindings": [
    {
      "role": "roles/storage.objectCreator",
      "members": ["serviceAccount:astrofiler-sync@your-project.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/storage.objectViewer", 
      "members": ["serviceAccount:astrofiler-sync@your-project.iam.gserviceaccount.com"]
    }
  ]
}
```

### Multiple Bucket Setup

For organizing different types of data:
- `gs://my-astrofiler-backup/raw/` - Raw FITS files
- `gs://my-astrofiler-backup/processed/` - Processed images  
- `gs://my-astrofiler-backup/database/` - Database backups

## Command-Line Automation

AstroFiler v1.2.0 includes comprehensive command-line automation capabilities for unattended cloud sync operations.

### CloudSync.py Command-Line Utility

The `CloudSync.py` utility in the `commands/` folder provides full command-line access to all cloud sync features:

```bash
# Basic sync using configured profile
python CloudSync.py

# Override sync profile
python CloudSync.py -p backup    # Backup only
python CloudSync.py -p complete  # Complete bidirectional sync

# Analysis mode (no sync, just analyze)
python CloudSync.py -a

# Unattended operation (auto-confirm)
python CloudSync.py -y -v        # Verbose with auto-confirm

# Custom configuration file
python CloudSync.py -c /path/to/custom.ini
```

### Scheduling Cloud Sync Operations

#### Windows Task Scheduler

Use the provided `cron_cloudsync.bat` script or create a custom scheduled task:

1. **Program**: `C:\path\to\astrofiler-gui\.venv\Scripts\python.exe`
2. **Arguments**: `C:\path\to\astrofiler-gui\commands\CloudSync.py -y -v`
3. **Start in**: `C:\path\to\astrofiler-gui`
4. **Schedule**: Daily at 11:00 PM (or after imaging sessions)

#### Linux/macOS Cron

Use the provided `cron_cloudsync.sh` script or add directly to crontab:

```bash
# Make script executable
chmod +x /path/to/astrofiler-gui/commands/cron_cloudsync.sh

# Edit crontab
crontab -e

# Add daily sync at 11 PM
0 23 * * * /path/to/astrofiler-gui/commands/cron_cloudsync.sh

# Or sync every 4 hours
0 */4 * * * /path/to/astrofiler-gui/commands/cron_cloudsync.sh
```

### Logging and Monitoring

All automated operations create timestamped log files in the `logs/` directory:
- Log format: `logs/cloudsync_YYYYMMDD_HHMMSS.log`
- Includes detailed operation results and error information
- Perfect for monitoring automated sync operations

### Example Automation Workflow

1. **After Imaging Session** (manually): `python CloudSync.py -p backup -y`
2. **Daily Maintenance** (automated): Complete sync to ensure all files are synchronized
3. **Weekly Analysis** (automated): `python CloudSync.py -a` to generate storage reports

### Integration with Other Automation

The command-line interface makes it easy to integrate cloud sync with other astronomical workflows:

```bash
# Complete workflow: Load new files then sync to cloud
python commands/LoadRepo.py -v
python commands/CloudSync.py -p backup -y -v

# Analysis and reporting
python commands/CloudSync.py -a > sync_report.txt
```

---

*This guide covers Google Cloud Storage integration. The command-line automation features enable seamless integration with existing astronomical data processing workflows.*
