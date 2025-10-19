# Google Cloud Storage Setup Guide for AstroFiler

⚠️ **Note**: This guide has been superseded by the comprehensive Cloud Services Integration Guide.

**For complete, up-to-date instructions, please refer to:**
📖 **[Cloud Services.md](./Cloud%20Services.md)**

The new guide includes:
- Complete Google Cloud Storage setup process
- New Cloud Sync system configuration
- Multiple sync profiles (Complete, Backup Only, On Demand)
- Troubleshooting guide
- Best practices and security recommendations

---

## Legacy Content

This document contains the original setup guide. For new installations, please use the updated Cloud Services.md documentation above.

### Quick Setup Checklist (Legacy)

- [ ] Create Google Cloud Platform account
- [ ] Create a GCP project
- [ ] Enable Cloud Storage API
- [ ] Create service account
- [ ] Download JSON authentication key
- [ ] Create storage bucket
- [ ] Configure AstroFiler with new Cloud Sync interface

## Detailed Steps

### 1. Google Cloud Platform Account Setup

1. **Create a GCP Account**
   - Go to [https://cloud.google.com/](https://cloud.google.com/)
   - Click "Get started for free"
   - Sign in with your Google account or create a new one
   - Complete the billing setup (Google provides $300 in free credits)

### 2. Create a New Project

1. **Access the Console**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   
2. **Create Project**
   - Click the project dropdown at the top (next to "Google Cloud")
   - Click "New Project"
   - Enter project name: `astrofiler-storage` (or your preferred name)
   - Leave organization as default
   - Click "Create"
   - Wait for project creation and select the new project

### 3. Enable Required APIs

1. **Navigate to APIs**
   - In the left sidebar, go to "APIs & Services" → "Library"
   
2. **Enable Cloud Storage API**
   - Search for "Cloud Storage API"
   - Click on the result
   - Click "Enable"
   - Wait for activation (usually takes a few seconds)

### 4. Create Service Account for Authentication

1. **Navigate to IAM**
   - Go to "IAM & Admin" → "Service Accounts"
   
2. **Create Service Account**
   - Click "Create Service Account"
   - **Name**: `astrofiler-sync`
   - **Description**: `Service account for AstroFiler cloud synchronization`
   - Click "Create and Continue"
   
3. **Assign Permissions**
   - Click "Select a role"
   - Choose "Cloud Storage" → "Storage Object Admin"
   - Click "Continue"
   - Skip "Grant users access" section
   - Click "Done"

### 5. Generate Authentication Key

1. **Access Service Account**
   - Find your `astrofiler-sync` service account in the list
   - Click on the service account email
   
2. **Create Key**
   - Click the "Keys" tab
   - Click "Add Key" → "Create new key"
   - Select "JSON" format
   - Click "Create"
   
3. **Save the Key File**
   - The JSON file will download automatically
   - **IMPORTANT**: Move this file to a secure location
   - Suggested location: `C:\Users\[YourName]\.astrofiler\gcs-auth.json`
   - **Never share this file or commit it to version control**

### 6. Create Storage Bucket

1. **Navigate to Storage**
   - Go to "Cloud Storage" → "Buckets"
   
2. **Create Bucket**
   - Click "Create Bucket"
   - **Name**: Choose a globally unique name (e.g., `your-name-astrofiler-data`)
   - **Location**: Choose closest to your location for better performance
   - **Storage Class**: Standard (for frequently accessed files)
   - **Access Control**: Uniform (recommended)
   - **Protection Tools**: Leave as default
   - Click "Create"

### 7. Configure AstroFiler

1. **Open AstroFiler Configuration**
   - Launch AstroFiler
   - Go to Settings/Configuration dialog
   
2. **Cloud Sync Settings**
   - **Cloud Vendor**: Select "Google Cloud Storage"
   - **Bucket URL**: Enter your bucket name (e.g., `your-name-astrofiler-data`)
   - **Auth File**: Browse and select the JSON key file from Step 5
   - **Sync Profile**: 
     - "Complete Sync" - Files kept both local and cloud
     - "Backup Only" - Upload to cloud, don't download missing files
     - "On Demand" - Download files when needed
   
3. **Save Configuration**
   - Click "Save Settings"

## Verification

To verify your setup is working:

1. **Check Connection**
   - Try uploading a test file through AstroFiler's cloud sync
   - Check if the file appears in your GCS bucket via the Google Cloud Console

2. **Monitor Usage**
   - Go to "Cloud Storage" → "Buckets" in Google Cloud Console
   - Click on your bucket to see uploaded files

## Cost Considerations

- **Free Tier**: Google Cloud offers 5GB of free storage per month
- **Standard Storage**: ~$0.020 per GB per month (varies by region)
- **Network Egress**: Free for first 1GB per month, then varies by destination
- **Operations**: Small charges for API operations (usually negligible for personal use)

## Security Tips

✅ **DO**:
- Store the JSON key in a secure location
- Regularly review your GCS bucket contents
- Use strong, unique bucket names
- Enable bucket versioning for important data
- Monitor your billing dashboard

❌ **DON'T**:
- Share your JSON authentication key
- Upload sensitive data without encryption
- Use easily guessable bucket names
- Ignore billing alerts
- Leave unused buckets consuming storage

## Troubleshooting

### Common Issues

**"Permission Denied" Error**
- Check that the service account has "Storage Object Admin" role
- Verify the JSON key file path is correct
- Ensure the key file is readable by AstroFiler

**"Bucket Not Found" Error**
- Verify the bucket name is spelled correctly
- Check that the bucket exists in your project
- Ensure you're using the correct project

**"Authentication Failed" Error**
- Verify the JSON key file is valid and not corrupted
- Check that the service account still exists
- Ensure the Cloud Storage API is enabled

**High Costs**
- Check for unexpected large file uploads
- Review your storage class selection
- Monitor network egress charges

## Support

If you encounter issues:
1. Check the AstroFiler logs for detailed error messages
2. Verify your Google Cloud Console settings
3. Review the Google Cloud Storage documentation
4. Contact AstroFiler support with specific error messages

---

**Next Steps**: Once setup is complete, you can use AstroFiler's cloud sync features to automatically backup and synchronize your astronomical data with Google Cloud Storage.