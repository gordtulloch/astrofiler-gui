# Cloud Sync Configuration - Implementation Summary

⚠️ **Note**: This is a technical implementation document. For user setup instructions, see:
📖 **[Cloud Services.md](./Cloud%20Services.md)**

## Overview
This document describes the technical implementation of the Cloud Sync system added to AstroFiler v1.2.0.

## Implementation Summary

### New Features Implemented
- **Cloud Sync Configuration Interface**: Complete UI for configuring cloud storage settings
- **Cloud Sync Dialog**: New Tools → Cloud Sync menu with Analyze and Sync operations
- **Database Integration**: Added `fitsFileCloudURL` field to track cloud storage locations
- **Backup Only Sync**: Fully implemented one-way backup sync profile with smart upload logic
- **Complete Sync**: Revolutionary bidirectional sync (download missing + upload new files)
- **Images View Integration**: Local/Cloud status icons showing file storage locations
- **Command-Line Interface**: Complete automation support with `CloudSync.py` utility
- **Self-Contained Architecture**: All cloud helper functions integrated in dialog
- **Comprehensive Error Handling**: User-friendly error messages for all common scenarios
- **Progress Tracking**: Real-time progress dialogs with cancellation support

### Technical Architecture

#### Database Schema Changes
- Added `fitsFileCloudURL` field to `fitsFile` table via migration 006
- Field stores cloud URLs in format: `gs://bucket-name/path/to/file.fits`

#### New Modules and Functions
- `ui/cloud_sync_dialog.py`: Self-contained cloud sync dialog with integrated helper functions
  - `_get_gcs_client()`: GCS client authentication and initialization
  - `check_file_exists_in_gcs()`: Check file existence without download
  - `upload_file_to_backup()`: Smart upload with duplicate prevention
  - `list_gcs_bucket_files()`: Complete bucket file listing with metadata
  - `download_file_from_gcs()`: Download files from cloud storage
  - `validate_bucket_access()`: Pre-operation bucket validation
  - `perform_backup_sync()`: Complete one-way backup sync implementation
  - `perform_complete_sync()`: Bidirectional sync (download + upload)
  - Real-time progress tracking and user feedback
- `astrofiler_cloud.py`: Legacy cloud operations (preserved for existing functionality)
- `commands/CloudSync.py`: Command-line automation utility
  - Full command-line interface with argument parsing
  - Support for all sync profiles via command-line flags
  - Analysis mode for storage reporting
  - Auto-confirm flags for unattended operation
  - Comprehensive logging and error handling
- `commands/cron_cloudsync.bat` / `commands/cron_cloudsync.sh`: Automation scripts

#### Configuration Integration
- Extended configuration system to include cloud sync settings
- Integration with existing `astrofiler.ini` configuration file
- Backward compatibility with existing configuration structure

## New Configuration Options

### 1. Cloud Vendor Selection
- **Type**: Dropdown/ComboBox
- **Default**: "Google Cloud Storage"
- **Purpose**: Selects the cloud storage provider
- **Current Options**: Google Cloud Storage (more can be added in the future)

### 2. Bucket URL
- **Type**: Text input field
- **Default**: "astrofiler-repository"
- **Purpose**: Specifies the cloud storage bucket/container name
- **Example**: "astrofiler-repository", "my-astronomy-data", etc.

### 3. Authentication File Path
- **Type**: Text input with "Browse" button
- **Default**: Empty
- **Purpose**: Path to the authentication file (typically JSON for Google Cloud)
- **File Filter**: JSON files (*.json)
- **Example**: "/path/to/service-account-key.json"

### 4. Sync Profile
- **Type**: Dropdown/ComboBox
- **Default**: "Complete Sync"
- **Options**:
  - **Complete Sync**: All files kept both local and in the Cloud
  - **Backup Only**: All files updated to the Cloud but do not download if missing
  - **On Demand**: Download files if required
- **Purpose**: Defines the synchronization behavior between local and cloud storage

## Technical Implementation

### Files Modified
- `ui/config_widget.py` - Added Cloud Sync UI section and configuration handling

### Configuration Storage
All settings are stored in the `astrofiler.ini` file under the `[DEFAULT]` section:
```ini
cloud_vendor = Google Cloud Storage
bucket_url = astrofiler-repository
auth_file_path = /path/to/auth.json
sync_profile = complete
```

### Methods Added
1. **UI Components**: Cloud sync group box with vendor dropdown, bucket URL field, auth file selector, and sync profile selection
2. **browse_auth_file()**: File dialog for selecting authentication files
3. **get_cloud_config()**: Helper method that returns cloud configuration in the format expected by `astrofiler_cloud.py`
4. **Updated save_settings()**: Saves cloud sync settings (including sync profile) to INI file
5. **Updated load_settings()**: Loads cloud sync settings (including sync profile) from INI file
6. **Updated reset_settings()**: Resets cloud sync settings to defaults

### Integration with Existing Cloud Module
The configuration integrates seamlessly with the existing `astrofiler_cloud.py` module:
- Uses the same `auth_info` dictionary format with `auth_string` key
- Compatible with Google Cloud Storage authentication methods
- Provides bucket URL for GCS operations

### Configuration Access
Other modules can access the cloud configuration using:
```python
from ui.config_widget import ConfigWidget
config_widget = ConfigWidget()
config_widget.load_settings()
cloud_config = config_widget.get_cloud_config()

# cloud_config contains:
# {
#     'vendor': 'Google Cloud Storage',
#     'bucket_url': 'astrofiler-repository',
#     'sync_profile': 'complete',
#     'auth_info': {'auth_string': '/path/to/auth.json'}
# }
```

## Future Enhancements
- Add support for additional cloud providers (AWS S3, Azure Blob Storage)
- Add connection testing functionality
- Add encryption options
- Add sync scheduling options

## Google Cloud Storage Setup Instructions

### Prerequisites
- A Google Cloud Platform (GCP) account
- A GCP project with billing enabled
- Google Cloud Storage API enabled

### Step 1: Create a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" at the top of the page
3. Click "New Project"
4. Enter a project name (e.g., "astrofiler-storage")
5. Select your billing account
6. Click "Create"

### Step 2: Enable the Cloud Storage API
1. In the Google Cloud Console, navigate to "APIs & Services" > "Library"
2. Search for "Cloud Storage API"
3. Click on "Cloud Storage API"
4. Click "Enable"

### Step 3: Create a Service Account
1. Navigate to "IAM & Admin" > "Service Accounts"
2. Click "Create Service Account"
3. Enter a service account name (e.g., "astrofiler-service")
4. Enter a description (e.g., "Service account for AstroFiler cloud sync")
5. Click "Create and Continue"

### Step 4: Grant Permissions
1. In the "Grant this service account access to project" section:
2. Add the role "Storage Object Admin" (for full read/write access to storage objects)
3. Optionally add "Storage Bucket Reader" if you need to list buckets
4. Click "Continue"
5. Skip the "Grant users access to this service account" section
6. Click "Done"

### Step 5: Create and Download the Authentication Key
1. In the Service Accounts list, find your newly created service account
2. Click on the service account name
3. Go to the "Keys" tab
4. Click "Add Key" > "Create new key"
5. Select "JSON" as the key type
6. Click "Create"
7. The JSON key file will be automatically downloaded to your computer
8. **Important**: Keep this file secure and never share it publicly

### Step 6: Create a Storage Bucket
1. Navigate to "Cloud Storage" > "Buckets"
2. Click "Create Bucket"
3. Choose a globally unique bucket name (e.g., "your-name-astrofiler-repository")
4. Select a location (choose based on your geographic location for better performance)
5. Choose storage class (Standard is recommended for frequently accessed data)
6. Set access control to "Uniform" (recommended)
7. Click "Create"

### Step 7: Configure AstroFiler
1. Open AstroFiler and go to the Configuration dialog
2. In the Cloud Sync section:
   - **Cloud Vendor**: Select "Google Cloud Storage"
   - **Bucket URL**: Enter your bucket name (e.g., "your-name-astrofiler-repository")
   - **Auth File**: Browse and select the JSON key file you downloaded in Step 5
   - **Sync Profile**: Choose your preferred sync behavior
3. Click "Save Settings"

### Security Best Practices
- **Never commit the JSON key file to version control**
- Store the key file in a secure location on your system
- Consider using environment variables or Google Application Default Credentials in production
- Regularly rotate service account keys
- Use the principle of least privilege - only grant necessary permissions

## Command-Line Interface Technical Details

### CloudSync.py Implementation
The command-line utility provides full automation capabilities:

#### Architecture
- **Modular Design**: Imports helper functions directly from `ui.cloud_sync_dialog`
- **Configuration Reuse**: Uses same `astrofiler.ini` configuration as GUI
- **Database Integration**: Full database operations for file registration and URL tracking
- **Progress Reporting**: Command-line appropriate progress indicators
- **Error Handling**: Comprehensive error handling with meaningful exit codes

#### Command-Line Arguments
```python
parser.add_argument('-p', '--profile', choices=['backup', 'complete'])
parser.add_argument('-a', '--analyze', action='store_true')
parser.add_argument('-y', '--yes', action='store_true')
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('-c', '--config', default='astrofiler.ini')
```

#### Integration Points
- **Configuration Validation**: Pre-flight checks ensure valid cloud configuration
- **Bucket Access**: Tests bucket connectivity before operations
- **Database Operations**: Uses same ORM models as GUI for consistency
- **Repository Path**: Respects configured repository path settings
- **Logging**: Creates timestamped log files for monitoring

#### Automation Scripts
- **Windows**: `cron_cloudsync.bat` with Task Scheduler integration
- **Linux/macOS**: `cron_cloudsync.sh` with cron integration
- **Cross-Platform**: Consistent interface across all platforms
- **Logging**: Automated log file creation with timestamps
- **Error Handling**: Proper exit codes for automation monitoring

### Troubleshooting
- **Authentication Error**: Verify the JSON key file path is correct and the file is readable
- **Permission Denied**: Ensure the service account has the correct IAM roles
- **Bucket Not Found**: Verify the bucket name is correct and exists in your project
- **API Not Enabled**: Ensure the Cloud Storage API is enabled in your project

### Alternative Authentication Methods
While service account keys (JSON files) are the most straightforward method for desktop applications, Google Cloud also supports:
- **Application Default Credentials (ADC)**: Automatically discovers credentials
- **User Credentials**: OAuth 2.0 flow for user authentication
- **Workload Identity**: For applications running on Google Cloud

For AstroFiler desktop use, the service account JSON key method described above is recommended.