# Cloud Services Integration Guide

## Google Cloud Storage Setup

AstroFiler supports synchronization with Google Cloud Storage for backing up your astronomy files and databases. This guide will walk you through setting up Google Cloud Storage and configuring AstroFiler to use it.

### Prerequisites

- Google Cloud Platform account
- A Google Cloud project (or create a new one)
- AstroFiler v1.2.0 or later

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

## Step 6: Configure AstroFiler

### Open AstroFiler Configuration

1. Launch AstroFiler
2. Go to **View** > **Configuration** (or press Ctrl+,)
3. Scroll down to the **Google Cloud Sync** section

### Configure Settings

1. **Repository Path**: Enter your bucket path in the format:
   ```
   gs://your-bucket-name/astrofiler/
   ```
   Example: `gs://my-astrofiler-backup-2025/astrofiler/`

2. **Authentication Info**: 
   - Click the **Browse...** button
   - Navigate to and select your downloaded JSON key file
   - Or manually enter the full path: `/home/username/.config/astrofiler/gcs-key.json`

3. **Debug Mode**: 
   - Keep **checked** for initial testing (default)
   - When checked, AstroFiler will only report what would be synchronized without actually uploading files

4. Click **Save Settings**

## Step 7: Test the Configuration

### Initial Test (Debug Mode)

1. Go to **Tools** > **Google Sync**
2. AstroFiler will scan your local files and report what would be synchronized
3. Check the log for any errors
4. If successful, you'll see a list of files that would be uploaded

### Live Synchronization

1. Once you've verified the configuration works in debug mode:
2. Go back to **View** > **Configuration**
3. Uncheck **Debug Mode** in the Google Cloud Sync section
4. Click **Save Settings**
5. Run **Tools** > **Google Sync** again to perform actual synchronization

## Understanding the Synchronization Process

### What Gets Synchronized

- All files in your AstroFiler directory
- Excludes hidden files (starting with `.`)
- Excludes Python cache files (`__pycache__`, `*.pyc`)
- Includes:
  - FITS files
  - Database files (`*.db`)
  - Configuration files (`*.ini`)
  - Log files
  - Documentation
  - Scripts and programs

### Synchronization Behavior

- **Debug Mode ON**: Reports files that would be uploaded, no actual transfer
- **Debug Mode OFF**: Uploads all local files to the specified bucket path
- Files are uploaded with their relative paths preserved
- Existing files in the bucket may be overwritten

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

**Authentication Errors**
- Verify the JSON key file path is correct
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

### Automation Ideas

Future enhancements could include:
- Scheduled automatic backups
- Selective file synchronization
- Compression before upload
- Integration with other cloud providers

---

*This guide covers Google Cloud Storage integration. Support for other cloud providers may be added in future versions of AstroFiler.*
