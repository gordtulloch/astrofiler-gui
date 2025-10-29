import os
import logging
import configparser
import base64
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QFrame, QMessageBox, QGroupBox, QApplication)
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

# Import hash functions from astrofiler_cloud for duplicate detection
try:
    from astrofiler_cloud import _calculate_md5_hash, _get_cloud_file_hashes
except ImportError:
    # Fallback in case of import issues
    logger.warning("Could not import hash functions from astrofiler_cloud")
    _calculate_md5_hash = None
    _get_cloud_file_hashes = None


# Cloud Sync Helper Functions
def _get_gcs_client(auth_info):
    """
    Create and return a Google Cloud Storage client.
    
    Args:
        auth_info (dict): Authentication information
        
    Returns:
        storage.Client: Authenticated GCS client
    """
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
        
        if 'auth_string' in auth_info and auth_info['auth_string']:
            # Check if it's a file path to a service account key
            auth_path = auth_info['auth_string']
            if os.path.exists(auth_path) and auth_path.endswith('.json'):
                # Use service account key file
                credentials = service_account.Credentials.from_service_account_file(auth_path)
                client = storage.Client(credentials=credentials)
                logger.info(f"Authenticated using service account key: {auth_path}")
            else:
                # Try default credentials
                client = storage.Client()
                logger.info("Using default Google Cloud credentials")
        else:
            # Use default credentials (ADC, environment, etc.)
            client = storage.Client()
            logger.info("Using default Google Cloud credentials")
            
        return client
        
    except ImportError:
        raise ImportError("Google Cloud Storage library not installed. Run: pip install google-cloud-storage")
    except Exception as e:
        raise Exception(f"Failed to authenticate with Google Cloud: {e}")


def check_file_exists_in_gcs(client, bucket_name, gcs_object_name):
    """
    Check if a file exists in Google Cloud Storage.
    
    Args:
        client: GCS client
        bucket_name (str): Name of the GCS bucket
        gcs_object_name (str): Object name in GCS
        
    Returns:
        bool: True if file exists, False otherwise
    """
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_object_name)
        return blob.exists()
    except Exception as e:
        logger.error(f"Failed to check if file exists: gs://{bucket_name}/{gcs_object_name}: {e}")
        return False


def upload_file_to_backup(bucket_name, auth_info, local_file_path, relative_path):
    """
    Upload a single file to cloud backup if it doesn't already exist.
    
    Args:
        bucket_name (str): Name of the GCS bucket
        auth_info (dict): Authentication information
        local_file_path (str): Full path to local file
        relative_path (str): Relative path to maintain directory structure
        
    Returns:
        tuple: (success: bool, cloud_url: str, message: str)
    """
    try:
        logger.info(f"Processing backup for: {relative_path}")
        
        # Get authenticated client
        client = _get_gcs_client(auth_info)
        
        # Normalize the path for cloud storage (use forward slashes)
        gcs_object_name = relative_path.replace('\\', '/')
        
        # Check if file already exists
        if check_file_exists_in_gcs(client, bucket_name, gcs_object_name):
            # File exists, just build the cloud URL
            cloud_url = f"gs://{bucket_name}/{gcs_object_name}"
            logger.info(f"File already exists in cloud: {gcs_object_name}")
            return True, cloud_url, "File already exists in cloud"
        
        # File doesn't exist, upload it
        logger.info(f"Uploading to cloud: {gcs_object_name}")
        _upload_file_to_gcs(client, bucket_name, local_file_path, gcs_object_name)
        cloud_url = f"gs://{bucket_name}/{gcs_object_name}"
        logger.info(f"Successfully uploaded: {gcs_object_name}")
        return True, cloud_url, "File uploaded successfully"
        
    except Exception as e:
        logger.error(f"Failed to upload file to backup: {local_file_path}: {e}")
        return False, "", str(e)


def _upload_file_to_gcs(client, bucket_name, local_file_path, gcs_object_name):
    """
    Upload a file to Google Cloud Storage, preserving the local directory structure.
    
    Args:
        client: GCS client
        bucket_name (str): Name of the GCS bucket
        local_file_path (str): Full path to local file
        gcs_object_name (str): Object name in GCS (includes directory structure)
    """
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_object_name)
        
        blob.upload_from_filename(local_file_path)
        logger.debug(f"Successfully uploaded: {local_file_path} -> gs://{bucket_name}/{gcs_object_name}")
        
    except Exception as e:
        logger.error(f"Failed to upload {local_file_path}: {e}")
        raise


def list_gcs_bucket_files(bucket_name, auth_info, prefix=""):
    """
    List all files in a Google Cloud Storage bucket.
    
    Args:
        bucket_name (str): Name of the GCS bucket
        auth_info (dict): Authentication information
        prefix (str): Optional prefix to filter files
        
    Returns:
        list: List of dictionaries containing file information
    """
    try:
        logger.info(f"Listing files in bucket: {bucket_name}")
        
        # Get authenticated client
        client = _get_gcs_client(auth_info)
        bucket = client.bucket(bucket_name)
        
        # List all blobs with optional prefix
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        files = []
        for blob in blobs:
            # Skip directory markers (objects ending with /)
            if blob.name.endswith('/'):
                continue
            
            # Convert MD5 hash from base64 to hex format for comparison
            md5_hash_hex = None
            if blob.md5_hash:
                try:
                    # GCS returns MD5 as base64, convert to hex for comparison
                    md5_hash_hex = base64.b64decode(blob.md5_hash).hex()
                except Exception as e:
                    logger.warning(f"Failed to convert MD5 hash for {blob.name}: {e}")
                    md5_hash_hex = None
                
            file_info = {
                'name': blob.name,
                'size': blob.size,
                'created': blob.time_created.isoformat() if blob.time_created else None,
                'updated': blob.updated.isoformat() if blob.updated else None,
                'md5_hash': md5_hash_hex,  # Now in hex format for easy comparison
                'md5_hash_base64': blob.md5_hash,  # Keep original for reference
                'crc32c': blob.crc32c,
                'content_type': blob.content_type,
                'url': f"gs://{bucket_name}/{blob.name}",
                'public_url': blob.public_url if hasattr(blob, 'public_url') else None
            }
            files.append(file_info)
            
        logger.info(f"Found {len(files)} files in bucket")
        return files
        
    except Exception as e:
        logger.error(f"Error listing bucket files: {e}")
        error_msg = str(e)
        
        # Provide more specific error messages for common issues
        if "404" in error_msg or "not found" in error_msg.lower():
            raise Exception(f"Failed to list files in bucket {bucket_name}: 404 GET https://storage.googleapis.com/storage/v1/b/{bucket_name}/o?projection=noAcl&prefix=&prettyPrint=false: The specified bucket does not exist.")
        elif "403" in error_msg or "access denied" in error_msg.lower():
            raise Exception(f"Failed to list files in bucket {bucket_name}: Access denied. Check your service account permissions.")
        elif "401" in error_msg or "unauthorized" in error_msg.lower():
            raise Exception(f"Failed to list files in bucket {bucket_name}: Authentication failed. Check your service account key file.")
        else:
            raise Exception(f"Failed to list files in bucket {bucket_name}: {error_msg}")


def download_file_from_gcs(bucket_name, auth_info, gcs_object_name, local_file_path):
    """
    Download a file from Google Cloud Storage to local disk.
    
    Args:
        bucket_name (str): Name of the GCS bucket
        auth_info (dict): Authentication information
        gcs_object_name (str): Object name in GCS
        local_file_path (str): Full path where to save the file locally
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        logger.info(f"Downloading from cloud: {gcs_object_name}")
        
        # Get authenticated client
        client = _get_gcs_client(auth_info)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_object_name)
        
        # Create directory structure if it doesn't exist
        local_dir = os.path.dirname(local_file_path)
        if local_dir:
            os.makedirs(local_dir, exist_ok=True)
        
        # Download the file
        blob.download_to_filename(local_file_path)
        logger.info(f"Successfully downloaded: gs://{bucket_name}/{gcs_object_name} -> {local_file_path}")
        return True, "File downloaded successfully"
        
    except Exception as e:
        logger.error(f"Failed to download gs://{bucket_name}/{gcs_object_name}: {e}")
        return False, str(e)


def find_cloud_duplicates(cloud_files):
    """
    Find duplicate files in cloud storage based on MD5 hash.
    
    Args:
        cloud_files (list): List of cloud file dictionaries
        
    Returns:
        dict: Dictionary with duplicate statistics and details
    """
    try:
        hash_groups = {}
        files_with_hashes = 0
        
        # Group files by MD5 hash
        for file_info in cloud_files:
            md5_hash = file_info.get('md5_hash')
            if md5_hash:
                files_with_hashes += 1
                if md5_hash not in hash_groups:
                    hash_groups[md5_hash] = []
                hash_groups[md5_hash].append(file_info)
        
        # Find duplicates (hash groups with more than one file)
        duplicates = {}
        total_duplicate_files = 0
        total_wasted_space = 0
        
        for hash_value, files in hash_groups.items():
            if len(files) > 1:
                duplicates[hash_value] = {
                    'files': files,
                    'count': len(files),
                    'size': files[0].get('size', 0),  # All files with same hash have same size
                    'wasted_space': (len(files) - 1) * files[0].get('size', 0)
                }
                total_duplicate_files += len(files)
                total_wasted_space += duplicates[hash_value]['wasted_space']
        
        return {
            'total_files': len(cloud_files),
            'files_with_hashes': files_with_hashes,
            'duplicate_groups': len(duplicates),
            'duplicate_files': total_duplicate_files,
            'unique_duplicates': len(duplicates),  # Number of unique content duplicated
            'wasted_space_bytes': total_wasted_space,
            'details': duplicates
        }
        
    except Exception as e:
        logger.error(f"Error finding cloud duplicates: {e}")
        return {
            'total_files': len(cloud_files) if cloud_files else 0,
            'files_with_hashes': 0,
            'duplicate_groups': 0,
            'duplicate_files': 0,
            'unique_duplicates': 0,
            'wasted_space_bytes': 0,
            'details': {},
            'error': str(e)
        }


def format_file_size(size_bytes):
    """Convert bytes to human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


class CloudSyncDialog(QDialog):
    """Dialog for Cloud Sync operations"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cloud Sync")
        self.setModal(True)
        self.resize(600, 400)
        self.cloud_config = self.load_cloud_config()
        self.init_ui()
    
    def load_cloud_config(self):
        """Load cloud configuration from astrofiler.ini"""
        try:
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            
            return {
                'vendor': config.get('DEFAULT', 'cloud_vendor', fallback='Not configured'),
                'bucket_url': config.get('DEFAULT', 'bucket_url', fallback='Not configured'),
                'auth_file_path': config.get('DEFAULT', 'auth_file_path', fallback='Not configured'),
                'sync_profile': config.get('DEFAULT', 'sync_profile', fallback='complete')
            }
        except Exception as e:
            logger.error(f"Error loading cloud config: {e}")
            return {
                'vendor': 'Error loading config',
                'bucket_url': 'Error loading config',
                'auth_file_path': 'Error loading config',
                'sync_profile': 'complete'
            }
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Cloud Sync Operations")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Configuration info
        config_group = QGroupBox("Current Configuration")
        config_layout = QVBoxLayout(config_group)
        
        # Display current settings
        vendor_label = QLabel(f"Cloud Vendor: {self.cloud_config['vendor']}")
        bucket_label = QLabel(f"Bucket: {self.cloud_config['bucket_url']}")
        
        # Show auth file status (not the full path for security)
        auth_status = "Configured" if self.cloud_config['auth_file_path'] and self.cloud_config['auth_file_path'] != 'Not configured' else "Not configured"
        auth_label = QLabel(f"Authentication: {auth_status}")
        
        # Show sync profile with description
        sync_descriptions = {
            'complete': 'Complete Sync (All files kept both local and in the Cloud)',
            'backup': 'Backup Only (Upload to Cloud, don\'t download missing)',
            'ondemand': 'On Demand (Upload soft-deleted files and remove from local storage)'
        }
        sync_desc = sync_descriptions.get(self.cloud_config['sync_profile'], self.cloud_config['sync_profile'])
        sync_label = QLabel(f"Sync Profile: {sync_desc}")
        
        config_layout.addWidget(vendor_label)
        config_layout.addWidget(bucket_label)
        config_layout.addWidget(auth_label)
        config_layout.addWidget(sync_label)
        
        # Add Configure button to the config group
        config_button_layout = QHBoxLayout()
        config_button_layout.addStretch()
        configure_button = QPushButton("Configure...")
        configure_button.setMinimumSize(100, 30)
        configure_button.clicked.connect(self.on_configure_clicked)
        config_button_layout.addWidget(configure_button)
        config_layout.addLayout(config_button_layout)
        
        layout.addWidget(config_group)
        
        # Add some spacing
        layout.addSpacing(10)
        
        # Analyze section
        analyze_frame = self.create_operation_frame(
            "Analyze",
            "Compare local with the Cloud",
            self.on_analyze_clicked
        )
        layout.addWidget(analyze_frame)
        
        # Sync section
        sync_frame = self.create_operation_frame(
            "Sync",
            "Move files to / from the Cloud based on Profile",
            self.on_sync_clicked
        )
        layout.addWidget(sync_frame)
        
        # Add stretch to push Cancel button to bottom
        layout.addStretch()
        
        # Cancel button at bottom
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setMinimumSize(100, 35)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def create_operation_frame(self, button_text, description, callback):
        """Create a frame for an operation with button and description"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("QFrame { border: 1px solid gray; border-radius: 5px; padding: 10px; }")
        
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(15, 15, 15, 15)
        
        # Operation button
        button = QPushButton(button_text)
        button.setMinimumSize(100, 40)
        button.setMaximumSize(120, 40)
        button.clicked.connect(callback)
        frame_layout.addWidget(button)
        
        # Description label
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        frame_layout.addWidget(desc_label, 1)  # Stretch factor of 1
        
        return frame
    
    def on_analyze_clicked(self):
        """Handle Analyze button click"""
        logger.info("Cloud Sync: Analyze operation requested")
        
        # Check if cloud is configured
        if self.cloud_config['vendor'] == 'Not configured' or self.cloud_config['bucket_url'] == 'Not configured':
            QMessageBox.warning(
                self,
                "Configuration Required",
                "Cloud sync is not configured.\n\n"
                "Please go to Tools → Configuration and set up your cloud storage settings first."
            )
            return
        
        # Check if auth file exists
        auth_path = self.cloud_config['auth_file_path']
        if not auth_path or auth_path == 'Not configured' or not os.path.exists(auth_path):
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Authentication file is not configured or not found.\n\n"
                "Please go to Tools → Configuration and set up your authentication file."
            )
            return
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Analyze Cloud Storage",
            f"This will:\n\n"
            f"1. Download a listing of all files in cloud bucket: {self.cloud_config['bucket_url']}\n"
            f"2. Compare with local files in the database\n"
            f"3. Update cloud URLs for files that exist in both locations\n\n"
            f"This process may take several minutes depending on the number of files.\n\n"
            f"Do you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # First validate bucket access
                if not self.validate_bucket_access():
                    return
                    
                self.perform_cloud_analysis()
            except Exception as e:
                logger.error(f"Error during cloud analysis: {e}")
                
                # Provide user-friendly error messages
                error_msg = str(e)
                if "does not exist" in error_msg.lower():
                    QMessageBox.critical(
                        self,
                        "Bucket Not Found",
                        f"The specified bucket could not be found.\n\n"
                        f"Error: {error_msg}\n\n"
                        f"Please check:\n"
                        f"• Bucket name is correct: '{self.cloud_config['bucket_url']}'\n"
                        f"• Bucket exists in your Google Cloud project\n"
                        f"• You have the correct project selected\n\n"
                        f"You can update the bucket name in Tools → Configuration."
                    )
                elif "access denied" in error_msg.lower() or "403" in error_msg:
                    QMessageBox.critical(
                        self,
                        "Access Denied",
                        f"Access denied to the cloud storage bucket.\n\n"
                        f"Error: {error_msg}\n\n"
                        f"Please check:\n"
                        f"• Your service account has the correct permissions\n"
                        f"• The bucket exists in the correct project\n"
                        f"• Your authentication file is valid\n\n"
                        f"You may need to grant 'Storage Object Viewer' or 'Storage Object Admin' role to your service account."
                    )
                elif "authentication failed" in error_msg.lower() or "401" in error_msg:
                    QMessageBox.critical(
                        self,
                        "Authentication Failed",
                        f"Failed to authenticate with Google Cloud Storage.\n\n"
                        f"Error: {error_msg}\n\n"
                        f"Please check:\n"
                        f"• Your service account key file is valid\n"
                        f"• The file path is correct\n"
                        f"• The service account still exists\n\n"
                        f"You can update the authentication file in Tools → Configuration."
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Analysis Error",
                        f"An error occurred during cloud analysis:\n\n{str(e)}\n\n"
                        f"Please check your cloud configuration and try again."
                    )
    
    def validate_bucket_access(self):
        """Validate that the configured bucket exists and is accessible."""
        try:
            # Get bucket name from URL
            bucket_url = self.cloud_config['bucket_url']
            if bucket_url.startswith('gs://'):
                bucket_name = bucket_url.replace('gs://', '').rstrip('/')
            else:
                bucket_name = bucket_url.rstrip('/')
            
            # Try to list one file to test access

            auth_info = {'auth_string': self.cloud_config['auth_file_path']}
            client = _get_gcs_client(auth_info)
            bucket = client.bucket(bucket_name)
            
            # Test bucket access with minimal operation
            try:
                list(bucket.list_blobs(max_results=1))
                return True
            except Exception as e:
                if "404" in str(e) or "not found" in str(e).lower():
                    QMessageBox.critical(self, "Bucket Not Found", 
                                       f"The bucket '{bucket_name}' does not exist.\n\n"
                                       f"Please check your bucket configuration or create the bucket in Google Cloud Console.")
                elif "403" in str(e) or "access denied" in str(e).lower():
                    QMessageBox.critical(self, "Access Denied", 
                                       f"Access denied to bucket '{bucket_name}'.\n\n"
                                       f"Please check your service account permissions.")
                elif "401" in str(e) or "unauthorized" in str(e).lower():
                    QMessageBox.critical(self, "Authentication Failed", 
                                       f"Authentication failed.\n\n"
                                       f"Please check your service account key file.")
                else:
                    QMessageBox.critical(self, "Cloud Error", f"Error accessing bucket: {str(e)}")
                return False
                
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", 
                               f"Error validating cloud configuration: {str(e)}")
            return False

    def perform_cloud_analysis(self):
        """Perform the actual cloud analysis and update database"""
        from astrofiler_db import fitsFile
        
        try:
            # Show progress dialog
            from PySide6.QtWidgets import QProgressDialog
            from PySide6.QtCore import Qt
            
            progress = QProgressDialog("Analyzing cloud storage...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.setAutoReset(True)
            progress.show()
            
            # Update progress
            progress.setLabelText("Connecting to cloud storage...")
            QApplication.processEvents()
            
            # Prepare auth info for cloud module
            auth_info = {
                'auth_string': self.cloud_config['auth_file_path']
            }
            
            # Get cloud file listing
            progress.setLabelText("Downloading file listing from cloud...")
            QApplication.processEvents()
            
            cloud_files = self.get_cloud_file_list(
                self.cloud_config['bucket_url'], 
                auth_info
            )
            
            if progress.wasCanceled():
                return
            
            # Analyze for duplicates in cloud storage
            progress.setLabelText("Analyzing cloud storage for duplicates...")
            QApplication.processEvents()
            
            duplicate_analysis = find_cloud_duplicates(cloud_files)
            
            if progress.wasCanceled():
                return
            
            # Update progress
            progress.setLabelText("Analyzing matches with local files...")
            progress.setMaximum(len(cloud_files))
            QApplication.processEvents()
            
            # Track different types of matches
            matches_found = 0
            filename_matches = 0
            hash_matches = 0
            partial_matches = 0
            
            for i, cloud_file in enumerate(cloud_files):
                if progress.wasCanceled():
                    break
                    
                progress.setValue(i)
                filename = cloud_file.get('name', '').split('/')[-1]
                progress.setLabelText(f"Analyzing: {filename}")
                QApplication.processEvents()
                
                # Try to find matching local file using enhanced matching
                local_file = self.find_matching_local_file(cloud_file)
                
                if local_file:
                    # Update the cloud URL in the database
                    cloud_url = self.build_cloud_url(cloud_file)
                    fitsFile.update(fitsFileCloudURL=cloud_url).where(
                        fitsFile.fitsFileId == local_file.fitsFileId
                    ).execute()
                    matches_found += 1
                    
                    # Track match type for reporting
                    if local_file.fitsFileName == filename:
                        filename_matches += 1
                    elif cloud_file.get('md5_hash') and _calculate_md5_hash:
                        try:
                            local_hash = _calculate_md5_hash(local_file.fitsFilePath)
                            if local_hash == cloud_file['md5_hash']:
                                hash_matches += 1
                            else:
                                partial_matches += 1
                        except:
                            partial_matches += 1
                    else:
                        partial_matches += 1
                    logger.info(f"Updated cloud URL for file: {local_file.fitsFileName}")
            
            progress.close()
            
            # Build detailed results message
            hash_function_available = _calculate_md5_hash is not None
            results_message = (
                f"Cloud analysis completed successfully!\n\n"
                f"📊 Analysis Results:\n"
                f"• Cloud files found: {len(cloud_files)}\n"
                f"• Total local matches: {matches_found}\n"
                f"• Database records updated: {matches_found}\n\n"
            )
            
            # Add duplicate analysis results
            if duplicate_analysis.get('duplicate_groups', 0) > 0:
                wasted_space = duplicate_analysis.get('wasted_space_bytes', 0)
                results_message += (
                    f"🔍 Duplicate Detection:\n"
                    f"• Duplicate file groups: {duplicate_analysis['duplicate_groups']}\n"
                    f"• Total duplicate files: {duplicate_analysis['duplicate_files']}\n"
                    f"• Wasted storage space: {format_file_size(wasted_space)}\n\n"
                )
            else:
                results_message += (
                    f"✅ No duplicates found in cloud storage!\n\n"
                )
            
            if hash_function_available and matches_found > 0:
                results_message += (
                    f"🔍 Local Match Breakdown:\n"
                    f"• Exact filename matches: {filename_matches}\n"
                    f"• Hash-verified matches: {hash_matches}\n"
                    f"• Partial/fallback matches: {partial_matches}\n\n"
                )
            
            results_message += (
                f"✅ Files with cloud URLs can now be synchronized.\n"
                f"💡 Use the Sync button to upload/download files."
            )
            
            # Show results with option to view duplicate details
            result = QMessageBox.information(
                self,
                "Analysis Complete",
                results_message,
                QMessageBox.Ok | (QMessageBox.Help if duplicate_analysis.get('duplicate_groups', 0) > 0 else QMessageBox.Ok)
            )
            
            # If user clicked Help and there are duplicates, show detailed report
            if (result == QMessageBox.Help and 
                duplicate_analysis.get('duplicate_groups', 0) > 0):
                self.show_duplicate_details(duplicate_analysis)
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            raise e
    
    def show_duplicate_details(self, duplicate_analysis):
        """Show detailed duplicate file report in a separate dialog"""
        try:
            details = duplicate_analysis.get('details', {})
            if not details:
                QMessageBox.information(self, "No Details", "No duplicate details available.")
                return
            
            # Create detailed report text
            report_lines = [
                "🔍 Detailed Duplicate Analysis Report",
                "=" * 50,
                "",
                f"Summary:",
                f"• Total cloud files: {duplicate_analysis.get('total_files', 0)}",
                f"• Files with hash data: {duplicate_analysis.get('files_with_hashes', 0)}",
                f"• Duplicate groups found: {duplicate_analysis.get('duplicate_groups', 0)}",
                f"• Total duplicate files: {duplicate_analysis.get('duplicate_files', 0)}",
                f"• Wasted storage space: {format_file_size(duplicate_analysis.get('wasted_space_bytes', 0))}",
                "",
                "Duplicate Groups:",
                "-" * 30
            ]
            
            # Add details for each duplicate group
            for i, (hash_value, group_info) in enumerate(details.items(), 1):
                files = group_info.get('files', [])
                file_size = group_info.get('size', 0)
                wasted_space = group_info.get('wasted_space', 0)
                
                report_lines.extend([
                    "",
                    f"Group {i}: {len(files)} identical files",
                    f"  File size: {format_file_size(file_size)}",
                    f"  Wasted space: {format_file_size(wasted_space)}",
                    f"  MD5 hash: {hash_value[:16]}...",
                    "  Files:"
                ])
                
                for file_info in files:
                    file_name = file_info.get('name', 'Unknown')
                    file_path = file_name.split('/')[-1] if '/' in file_name else file_name
                    report_lines.append(f"    • {file_path}")
                    if len(file_name) > 50:  # Show full path for long names
                        report_lines.append(f"      Path: {file_name}")
            
            # Join all lines into report text
            report_text = "\n".join(report_lines)
            
            # Create and show dialog
            from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QPushButton
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Cloud Storage Duplicate Analysis")
            dialog.setModal(True)
            dialog.resize(700, 500)
            
            layout = QVBoxLayout(dialog)
            
            # Add text area
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(report_text)
            text_edit.setFont(QFont("Courier", 10))
            layout.addWidget(text_edit)
            
            # Add close button
            close_button = QPushButton("Close")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Error showing duplicate details: {e}")
            QMessageBox.critical(self, "Error", f"Failed to show duplicate details: {str(e)}")
    
    def get_cloud_file_list(self, bucket_name, auth_info):
        """Get list of files from cloud storage"""
        try:
            logger.info(f"Getting file list from bucket: {bucket_name}")
            
            # Use the list function
            cloud_files = list_gcs_bucket_files(bucket_name, auth_info)
            
            logger.info(f"Retrieved {len(cloud_files)} files from cloud storage")
            return cloud_files
            
        except Exception as e:
            logger.error(f"Error getting cloud file list: {e}")
            raise Exception(f"Failed to get cloud file listing: {str(e)}")
    
    def find_matching_local_file(self, cloud_file):
        """Find local file that matches the cloud file using filename and hash-based matching"""
        from astrofiler_db import fitsFile
        
        try:
            # Get the filename from the cloud file path
            filename = cloud_file.get('name', '').split('/')[-1]
            
            if not filename:
                return None
            
            # Try to match by filename first (fastest method)
            filename_match = None
            try:
                filename_match = fitsFile.get(fitsFile.fitsFileName == filename)
                logger.debug(f"Found exact filename match: {filename}")
                
                # If we have a filename match and hash functions are available,
                # verify content matches using hash comparison
                if _calculate_md5_hash and cloud_file.get('md5_hash'):
                    try:
                        local_hash = _calculate_md5_hash(filename_match.fitsFilePath)
                        cloud_hash = cloud_file['md5_hash']
                        
                        if local_hash == cloud_hash:
                            logger.debug(f"Hash verification successful for {filename}")
                            return filename_match
                        else:
                            logger.info(f"Filename match but content differs for {filename} (hash mismatch)")
                            # Continue to other matching methods
                    except Exception as e:
                        logger.warning(f"Could not verify hash for {filename}: {e}")
                        # Return filename match as fallback
                        return filename_match
                else:
                    # No hash available, trust filename match
                    return filename_match
                    
            except fitsFile.DoesNotExist:
                pass
            
            # Try to match by partial filename (without extension)
            try:
                base_filename = filename.rsplit('.', 1)[0]  # Remove extension
                partial_match = fitsFile.get(fitsFile.fitsFileName.contains(base_filename))
                logger.debug(f"Found partial filename match: {base_filename}")
                
                # If we have a partial match and hash functions are available, verify with hash
                if _calculate_md5_hash and cloud_file.get('md5_hash'):
                    try:
                        local_hash = _calculate_md5_hash(partial_match.fitsFilePath)
                        cloud_hash = cloud_file['md5_hash']
                        
                        if local_hash == cloud_hash:
                            logger.debug(f"Hash verification successful for partial match {base_filename}")
                            return partial_match
                        else:
                            logger.debug(f"Partial filename match but content differs for {base_filename}")
                    except Exception as e:
                        logger.warning(f"Could not verify hash for partial match {base_filename}: {e}")
                        return partial_match
                else:
                    return partial_match
                    
            except fitsFile.DoesNotExist:
                pass
            
            # Try hash-based matching across all local files (most thorough but slower)
            if _calculate_md5_hash and cloud_file.get('md5_hash'):
                try:
                    cloud_hash = cloud_file['md5_hash']
                    logger.debug(f"Attempting hash-based matching for {filename}")
                    
                    # Get all local files and check their hashes
                    # Note: This could be optimized by storing hashes in the database
                    local_files = fitsFile.select()
                    for local_file in local_files:
                        try:
                            if os.path.exists(local_file.fitsFilePath):
                                local_hash = _calculate_md5_hash(local_file.fitsFilePath)
                                if local_hash == cloud_hash:
                                    logger.info(f"Found hash-based match: {local_file.fitsFileName} matches cloud file {filename}")
                                    return local_file
                        except Exception as e:
                            logger.debug(f"Could not calculate hash for {local_file.fitsFilePath}: {e}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Error during hash-based matching: {e}")
            
            logger.debug(f"No local match found for cloud file: {filename}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding matching local file: {e}")
            return None
    
    def build_cloud_url(self, cloud_file):
        """Build the cloud URL for a file"""
        try:
            # Use the URL already provided by the cloud listing
            if 'url' in cloud_file and cloud_file['url']:
                return cloud_file['url']
            
            # Fallback: Build URL based on cloud vendor and file location
            if self.cloud_config['vendor'] == 'Google Cloud Storage':
                bucket = self.cloud_config['bucket_url']
                file_path = cloud_file.get('name', '')
                return f"gs://{bucket}/{file_path}"
            
            # Add other cloud vendors as needed
            return ''
            
        except Exception as e:
            logger.error(f"Error building cloud URL: {e}")
            return ''
    
    def on_sync_clicked(self):
        """Handle Sync button click"""
        logger.info("Cloud Sync: Sync operation requested")
        
        # Check if cloud is configured
        if self.cloud_config['vendor'] == 'Not configured' or self.cloud_config['bucket_url'] == 'Not configured':
            QMessageBox.warning(
                self,
                "Configuration Required",
                "Cloud sync is not configured.\n\n"
                "Please go to Tools → Configuration and set up your cloud storage settings first."
            )
            return
        
        # Check if auth file exists
        auth_path = self.cloud_config['auth_file_path']
        if not auth_path or auth_path == 'Not configured' or not os.path.exists(auth_path):
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Authentication file is not configured or not found.\n\n"
                "Please go to Tools → Configuration and set up your authentication file."
            )
            return
        
        # First validate bucket access
        if not self.validate_bucket_access():
            return
        
        # Check sync profile and handle accordingly
        sync_profile = self.cloud_config['sync_profile'].lower()
        
        if sync_profile == 'backup':
            self.perform_backup_sync()
        elif sync_profile == 'complete':
            self.perform_complete_sync()
        elif sync_profile == 'on demand':
            self.perform_on_demand_sync()
        else:
            QMessageBox.warning(
                self,
                "Unknown Sync Profile",
                f"Unknown sync profile: {sync_profile}\n\n"
                f"Please check your configuration."
            )
    
    def perform_backup_sync(self):
        """Perform backup-only sync: upload local files that don't exist in cloud"""
        from astrofiler_db import fitsFile
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        import configparser
        
        try:
            # Get repository path from configuration
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            repo_path = config.get('DEFAULT', 'repo', fallback='')
            
            if not repo_path or not os.path.exists(repo_path):
                QMessageBox.critical(
                    self,
                    "Configuration Error",
                    "Repository path is not configured or does not exist.\n\n"
                    "Please configure your repository path in Tools → Configuration."
                )
                return
            
            # Confirm operation
            reply = QMessageBox.question(
                self,
                "Backup Sync",
                f"This will:\n\n"
                f"1. Check all local FITS files in the database\n"
                f"2. Upload files that don't exist in cloud bucket: {self.cloud_config['bucket_url']}\n"
                f"3. Update cloud URLs for all processed files\n\n"
                f"Repository path: {repo_path}\n\n"
                f"This operation may take several minutes depending on the number of files.\n\n"
                f"Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Get all FITS files from database (including soft-deleted files for backup)
            fits_files = list(fitsFile.select().where(
                fitsFile.fitsFileName.is_null(False)
            ))
            
            if not fits_files:
                QMessageBox.information(
                    self,
                    "No Files Found",
                    "No FITS files found in the database.\n\n"
                    "Please scan your repository first using the Load Repository function."
                )
                return
            
            # Setup progress dialog
            progress = QProgressDialog("Starting backup sync...", "Cancel", 0, len(fits_files), self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.setAutoReset(True)
            progress.show()
            
            # Prepare bucket info
            bucket_url = self.cloud_config['bucket_url']
            if bucket_url.startswith('gs://'):
                bucket_name = bucket_url.replace('gs://', '').rstrip('/')
            else:
                bucket_name = bucket_url.rstrip('/')
            
            auth_info = {'auth_string': self.cloud_config['auth_file_path']}
            
            # Process each file
            uploaded_count = 0
            updated_count = 0
            error_count = 0
            
            for i, fits_file in enumerate(fits_files):
                if progress.wasCanceled():
                    break
                
                try:
                    # Update progress
                    progress.setValue(i)
                    progress.setLabelText(f"Processing file {i+1} of {len(fits_files)}: {os.path.basename(fits_file.fitsFileName)}")
                    QApplication.processEvents()
                    
                    # Get relative path from repository root
                    full_path = fits_file.fitsFileName
                    if full_path.startswith(repo_path):
                        relative_path = os.path.relpath(full_path, repo_path)
                    else:
                        # File is outside repo, use just the filename
                        relative_path = os.path.basename(full_path)
                    
                    # Check if local file exists
                    if not os.path.exists(full_path):
                        logger.warning(f"Local file not found: {full_path}")
                        error_count += 1
                        continue
                    
                    # Upload to backup if needed
                    success, cloud_url, message = upload_file_to_backup(
                        bucket_name, auth_info, full_path, relative_path
                    )
                    
                    if success:
                        # Update the database with cloud URL
                        fits_file.fitsFileCloudURL = cloud_url
                        fits_file.save()
                        updated_count += 1
                        
                        # Check if this is a soft-deleted file and verify cloud backup before deleting
                        if fits_file.fitsFileSoftDelete:
                            # Verify the file exists in cloud storage before deleting
                            try:
                                from astrofiler_cloud import _get_gcs_client
                                client = _get_gcs_client(auth_info)
                                gcs_object_name = relative_path.replace('\\', '/')
                                
                                if check_file_exists_in_gcs(client, bucket_name, gcs_object_name):
                                    # File verified in cloud, safe to delete locally
                                    os.remove(full_path)
                                    logger.info(f"Deleted local soft-deleted file after verifying cloud backup: {relative_path}")
                                else:
                                    logger.error(f"SAFETY CHECK FAILED: File not found in cloud, keeping local copy: {relative_path}")
                            except OSError as e:
                                logger.warning(f"Failed to delete soft-deleted file {relative_path}: {e}")
                            except Exception as e:
                                logger.error(f"Cloud verification failed for {relative_path}, keeping local copy: {e}")
                        
                        if "uploaded" in message.lower():
                            uploaded_count += 1
                            logger.info(f"Uploaded: {relative_path}")
                        else:
                            logger.info(f"Already exists: {relative_path}")
                    else:
                        logger.error(f"Failed to process {relative_path}: {message}")
                        error_count += 1
                
                except Exception as e:
                    logger.error(f"Error processing file {fits_file.fitsFileName}: {e}")
                    error_count += 1
            
            progress.setValue(len(fits_files))
            
            # Show results
            if not progress.wasCanceled():
                QMessageBox.information(
                    self,
                    "Backup Sync Complete",
                    f"Backup sync completed successfully!\n\n"
                    f"• Files processed: {len(fits_files)}\n"
                    f"• Files uploaded: {uploaded_count}\n"
                    f"• Database records updated: {updated_count}\n"
                    f"• Errors: {error_count}\n\n"
                    f"All processed files now have cloud URLs in the database."
                )
            else:
                QMessageBox.information(
                    self,
                    "Backup Sync Cancelled",
                    f"Backup sync was cancelled by user.\n\n"
                    f"Partial results:\n"
                    f"• Files processed: {i}\n"
                    f"• Files uploaded: {uploaded_count}\n"
                    f"• Database records updated: {updated_count}\n"
                    f"• Errors: {error_count}"
                )
        
        except Exception as e:
            logger.error(f"Error during backup sync: {e}")
            QMessageBox.critical(
                self,
                "Backup Sync Error",
                f"An error occurred during backup sync:\n\n{str(e)}\n\n"
                f"Please check the logs for more details."
            )
    
    def perform_complete_sync(self):
        """Perform complete bidirectional sync: download missing files from cloud and upload files without cloud URLs"""
        from astrofiler_db import fitsFile
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        import configparser
        
        try:
            # Get repository path from configuration
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            repo_path = config.get('DEFAULT', 'repo', fallback='')
            
            if not repo_path or not os.path.exists(repo_path):
                QMessageBox.critical(
                    self,
                    "Configuration Error",
                    "Repository path is not configured or does not exist.\n\n"
                    "Please configure your repository path in Tools → Configuration."
                )
                return
            
            # Confirm operation
            reply = QMessageBox.question(
                self,
                "Complete Sync",
                f"This will perform bidirectional synchronization:\n\n"
                f"DOWNLOAD:\n"
                f"1. Check all files in cloud bucket: {self.cloud_config['bucket_url']}\n"
                f"2. Download files that exist in cloud but missing locally\n"
                f"3. Register downloaded files in the database\n\n"
                f"UPLOAD:\n"
                f"4. Check all local FITS files in the database\n"
                f"5. Upload files that don't have cloud URLs (not yet backed up)\n"
                f"6. Update cloud URLs for all processed files\n\n"
                f"Repository path: {repo_path}\n\n"
                f"This operation may take considerable time depending on file count and sizes.\n\n"
                f"Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Setup progress dialog
            progress = QProgressDialog("Starting complete sync...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.setAutoReset(True)
            progress.show()
            
            # Prepare bucket info
            bucket_url = self.cloud_config['bucket_url']
            if bucket_url.startswith('gs://'):
                bucket_name = bucket_url.replace('gs://', '').rstrip('/')
            else:
                bucket_name = bucket_url.rstrip('/')
            
            auth_info = {'auth_string': self.cloud_config['auth_file_path']}
            
            # Phase 1: Download missing files from cloud
            progress.setLabelText("Phase 1: Getting cloud file list...")
            progress.setValue(10)
            QApplication.processEvents()
            
            if progress.wasCanceled():
                return
            
            cloud_files = list_gcs_bucket_files(bucket_name, auth_info)
            logger.info(f"Found {len(cloud_files)} files in cloud storage")
            
            # Download missing files
            progress.setLabelText("Phase 1: Checking for missing local files...")
            progress.setValue(20)
            QApplication.processEvents()
            
            downloaded_count = 0
            registered_count = 0
            
            for i, cloud_file in enumerate(cloud_files):
                if progress.wasCanceled():
                    break
                
                progress.setLabelText(f"Phase 1: Checking {cloud_file['name']}")
                progress.setValue(20 + int((i / len(cloud_files)) * 30))
                QApplication.processEvents()
                
                # Check if file already exists in database (already processed)
                from astrofiler_db import fitsFile
                filename_only = os.path.basename(cloud_file['name'])
                cloud_url = f"gs://{bucket_name}/{cloud_file['name']}"
                
                # Check if file is already in database/repository by multiple methods
                existing_file = None
                
                # Method 1: Check by exact filename
                try:
                    existing_file = fitsFile.get(fitsFile.fitsFileName == filename_only)
                    logger.info(f"File already exists in repository (by filename): {filename_only}")
                except fitsFile.DoesNotExist:
                    pass
                
                # Method 2: Check by cloud URL (for files downloaded previously)
                if existing_file is None:
                    try:
                        existing_file = fitsFile.get(fitsFile.fitsFileCloudURL == cloud_url)
                        logger.info(f"File already exists in repository (by cloud URL): {filename_only}")
                    except fitsFile.DoesNotExist:
                        pass
                
                # Method 3: Check by timestamp pattern (extract date/time from filename)
                if existing_file is None:
                    import re
                    # Extract timestamp pattern like "20240116031554" from filename
                    timestamp_match = re.search(r'-(\d{14})[s-]', filename_only)
                    if timestamp_match:
                        timestamp = timestamp_match.group(1)
                        try:
                            # Look for any file with this timestamp
                            existing_file = fitsFile.get(fitsFile.fitsFileName.contains(timestamp))
                            logger.info(f"File already exists in repository (by timestamp {timestamp}): {filename_only}")
                        except fitsFile.DoesNotExist:
                            pass
                
                if existing_file is None:
                    try:
                        # Download to incoming/source folder first
                        logger.info(f"Downloading missing file: {cloud_file['name']}")
                        
                        # Get source folder from configuration
                        source_path = config.get('DEFAULT', 'source', fallback='')
                        if not source_path:
                            logger.error("Source folder not configured. Cannot download files.")
                            continue
                            
                        # Ensure source folder exists
                        os.makedirs(source_path, exist_ok=True)
                        
                        # Download to source folder (incoming)
                        incoming_file_path = os.path.join(source_path, os.path.basename(cloud_file['name']))
                        
                        success, message = download_file_from_gcs(
                            bucket_name, auth_info, cloud_file['name'], incoming_file_path
                        )
                        
                        if success:
                            downloaded_count += 1
                            
                            # Register the downloaded file (moveFiles=True will move it from incoming to repo)
                            if incoming_file_path.lower().endswith(('.fits', '.fit', '.fts')):
                                from astrofiler_file import fitsProcessing
                                processor = fitsProcessing()
                                # Split path into directory and filename for registerFitsImage
                                root_dir = os.path.dirname(incoming_file_path)
                                filename = os.path.basename(incoming_file_path)
                                result = processor.registerFitsImage(root_dir, filename, moveFiles=True)
                                if result:  # Success includes both new registrations and duplicates
                                    registered_count += 1
                                    if result == "DUPLICATE":
                                        # File already exists in repository, delete the downloaded copy
                                        try:
                                            os.remove(incoming_file_path)
                                            logger.info(f"Downloaded file already exists in repository, deleted incoming copy: {cloud_file['name']}")
                                        except OSError as e:
                                            logger.warning(f"Failed to delete duplicate file from incoming: {e}")
                                    else:
                                        logger.info(f"Downloaded and registered file: {cloud_file['name']}")
                                else:
                                    logger.warning(f"Downloaded but failed to register file: {cloud_file['name']}")
                            else:
                                logger.info(f"Downloaded non-FITS file: {cloud_file['name']}")
                        
                    except Exception as e:
                        logger.error(f"Failed to download {cloud_file['name']}: {e}")
            
            if progress.wasCanceled():
                return
            
            # Phase 2: Upload local files without cloud URLs (same as backup sync)
            progress.setLabelText("Phase 2: Getting local files without cloud URLs...")
            progress.setValue(50)
            QApplication.processEvents()
            
            # Get all FITS files from database that don't have cloud URLs (including soft-deleted)
            fits_files = list(fitsFile.select().where(
                (fitsFile.fitsFileName.is_null(False)) &
                ((fitsFile.fitsFileCloudURL.is_null(True)) | (fitsFile.fitsFileCloudURL == ""))
            ))
            
            logger.info(f"Found {len(fits_files)} local files without cloud URLs")
            
            uploaded_count = 0
            updated_count = 0
            error_count = 0
            
            for i, fits_file in enumerate(fits_files):
                if progress.wasCanceled():
                    break
                
                try:
                    progress.setLabelText(f"Phase 2: Processing {os.path.basename(fits_file.fitsFileName)}")
                    progress.setValue(50 + int((i / len(fits_files)) * 50))
                    QApplication.processEvents()
                    
                    # Get relative path from repository root
                    full_path = fits_file.fitsFileName
                    if full_path.startswith(repo_path):
                        relative_path = os.path.relpath(full_path, repo_path)
                    else:
                        # File is outside repo, use just the filename
                        relative_path = os.path.basename(full_path)
                    
                    # Check if local file exists
                    if not os.path.exists(full_path):
                        logger.warning(f"Local file not found: {full_path}")
                        error_count += 1
                        continue
                    
                    # Upload to cloud if needed
                    success, cloud_url, message = upload_file_to_backup(
                        bucket_name, auth_info, full_path, relative_path
                    )
                    
                    if success:
                        # Update the database with cloud URL
                        fits_file.fitsFileCloudURL = cloud_url
                        fits_file.save()
                        updated_count += 1
                        
                        # Complete Sync keeps files in both local and cloud storage
                        # No deletion of soft-deleted files in Complete Sync mode
                        
                        if "uploaded" in message.lower():
                            uploaded_count += 1
                            logger.info(f"Uploaded: {relative_path}")
                        else:
                            logger.info(f"Already exists: {relative_path}")
                    else:
                        logger.error(f"Failed to process {relative_path}: {message}")
                        error_count += 1
                
                except Exception as e:
                    logger.error(f"Error processing file {fits_file.fitsFileName}: {e}")
                    error_count += 1
            
            progress.setValue(100)
            
            # Show results
            if not progress.wasCanceled():
                QMessageBox.information(
                    self,
                    "Complete Sync Finished",
                    f"Complete bidirectional sync completed!\n\n"
                    f"DOWNLOAD PHASE:\n"
                    f"• Cloud files checked: {len(cloud_files)}\n"
                    f"• Files downloaded: {downloaded_count}\n"
                    f"• Files registered: {registered_count}\n\n"
                    f"UPLOAD PHASE:\n"
                    f"• Local files processed: {len(fits_files)}\n"
                    f"• Files uploaded: {uploaded_count}\n"
                    f"• Database records updated: {updated_count}\n"
                    f"• Errors: {error_count}\n\n"
                    f"Your local and cloud storage are now synchronized!"
                )
            else:
                QMessageBox.information(
                    self,
                    "Complete Sync Cancelled",
                    f"Complete sync was cancelled by user.\n\n"
                    f"Partial results:\n"
                    f"• Files downloaded: {downloaded_count}\n"
                    f"• Files registered: {registered_count}\n"
                    f"• Files uploaded: {uploaded_count}\n"
                    f"• Database records updated: {updated_count}\n"
                    f"• Errors: {error_count}"
                )
        
        except Exception as e:
            logger.error(f"Error during complete sync: {e}")
            QMessageBox.critical(
                self,
                "Complete Sync Error",
                f"An error occurred during complete sync:\n\n{str(e)}\n\n"
                f"Please check the logs for more details."
            )
    
    def perform_on_demand_sync(self):
        """Perform on-demand sync: upload soft-deleted files and delete them locally"""
        from astrofiler_db import fitsFile
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        import configparser
        
        try:
            # Get repository path from configuration
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            repo_path = config.get('DEFAULT', 'repo', fallback='')
            
            if not repo_path or not os.path.exists(repo_path):
                QMessageBox.critical(
                    self,
                    "Configuration Error",
                    "Repository path is not configured or does not exist.\n\n"
                    "Please configure your repository path in Tools → Configuration."
                )
                return
            
            # Get soft-deleted files that need to be uploaded
            soft_deleted_files = list(fitsFile.select().where(
                (fitsFile.fitsFileName.is_null(False)) &
                (fitsFile.fitsFileSoftDelete == True)
            ))
            
            if not soft_deleted_files:
                QMessageBox.information(
                    self,
                    "No Soft-Deleted Files",
                    "No soft-deleted files found in the database.\n\n"
                    "Soft-deleted files are created when master calibration frames are generated."
                )
                return
            
            # Confirm operation
            reply = QMessageBox.question(
                self,
                "On Demand Sync",
                f"This will:\n\n"
                f"1. Upload {len(soft_deleted_files)} soft-deleted files to cloud bucket: {self.cloud_config['bucket_url']}\n"
                f"2. Update cloud URLs for all uploaded files\n"
                f"3. Delete local copies of uploaded files to free up disk space\n\n"
                f"Repository path: {repo_path}\n\n"
                f"This operation cannot be undone locally (files will only exist in cloud).\n\n"
                f"Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Setup progress dialog
            progress = QProgressDialog("Starting on-demand sync...", "Cancel", 0, len(soft_deleted_files), self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.setAutoReset(True)
            progress.show()
            
            # Prepare bucket info
            bucket_url = self.cloud_config['bucket_url']
            if bucket_url.startswith('gs://'):
                bucket_name = bucket_url.replace('gs://', '').rstrip('/')
            else:
                bucket_name = bucket_url.rstrip('/')
            
            auth_info = {'auth_string': self.cloud_config['auth_file_path']}
            
            # Process each soft-deleted file
            uploaded_count = 0
            deleted_count = 0
            updated_count = 0
            error_count = 0
            
            for i, fits_file in enumerate(soft_deleted_files):
                if progress.wasCanceled():
                    break
                
                try:
                    # Update progress
                    progress.setValue(i)
                    progress.setLabelText(f"Processing file {i+1} of {len(soft_deleted_files)}: {os.path.basename(fits_file.fitsFileName)}")
                    QApplication.processEvents()
                    
                    # Get relative path from repository root
                    full_path = fits_file.fitsFileName
                    if full_path.startswith(repo_path):
                        relative_path = os.path.relpath(full_path, repo_path)
                    else:
                        # File is outside repo, use just the filename
                        relative_path = os.path.basename(full_path)
                    
                    # Check if local file exists
                    if not os.path.exists(full_path):
                        logger.warning(f"Local soft-deleted file not found: {full_path}")
                        error_count += 1
                        continue
                    
                    # Upload to cloud
                    success, cloud_url, message = upload_file_to_backup(
                        bucket_name, auth_info, full_path, relative_path
                    )
                    
                    if success:
                        # Update the database with cloud URL
                        fits_file.fitsFileCloudURL = cloud_url
                        fits_file.save()
                        updated_count += 1
                        
                        # Verify cloud backup before deleting local file
                        try:
                            from astrofiler_cloud import _get_gcs_client
                            client = _get_gcs_client(auth_info)
                            gcs_object_name = relative_path.replace('\\', '/')
                            
                            if check_file_exists_in_gcs(client, bucket_name, gcs_object_name):
                                # File verified in cloud, safe to delete locally
                                os.remove(full_path)
                                deleted_count += 1
                                logger.info(f"Uploaded and deleted soft-deleted file after cloud verification: {relative_path}")
                            else:
                                logger.error(f"SAFETY CHECK FAILED: File not found in cloud, keeping local copy: {relative_path}")
                        except OSError as e:
                            logger.warning(f"Failed to delete local file {relative_path} after upload: {e}")
                        except Exception as e:
                            logger.error(f"Cloud verification failed for {relative_path}, keeping local copy: {e}")
                        
                        if "uploaded" in message.lower():
                            uploaded_count += 1
                            logger.info(f"Uploaded: {relative_path}")
                        else:
                            logger.info(f"Already exists: {relative_path}")
                    else:
                        logger.error(f"Failed to upload {relative_path}: {message}")
                        error_count += 1
                
                except Exception as e:
                    logger.error(f"Error processing soft-deleted file {fits_file.fitsFileName}: {e}")
                    error_count += 1
            
            progress.setValue(len(soft_deleted_files))
            
            # Show results
            if not progress.wasCanceled():
                QMessageBox.information(
                    self,
                    "On Demand Sync Complete",
                    f"On-demand sync completed successfully!\n\n"
                    f"• Soft-deleted files processed: {len(soft_deleted_files)}\n"
                    f"• Files uploaded: {uploaded_count}\n"
                    f"• Local files deleted: {deleted_count}\n"
                    f"• Database records updated: {updated_count}\n"
                    f"• Errors: {error_count}\n\n"
                    f"All soft-deleted files have been moved to cloud storage."
                )
            else:
                QMessageBox.information(
                    self,
                    "On Demand Sync Cancelled",
                    f"On-demand sync was cancelled by user.\n\n"
                    f"Partial results:\n"
                    f"• Files processed: {i}\n"
                    f"• Files uploaded: {uploaded_count}\n"
                    f"• Local files deleted: {deleted_count}\n"
                    f"• Database records updated: {updated_count}\n"
                    f"• Errors: {error_count}"
                )
        
        except Exception as e:
            logger.error(f"Error during on-demand sync: {e}")
            QMessageBox.critical(
                self,
                "On Demand Sync Error",
                f"An error occurred during on-demand sync:\n\n{str(e)}\n\n"
                f"Please check the logs for more details."
            )
    
    def on_configure_clicked(self):
        """Handle Configure button click"""
        logger.info("Cloud Sync: Configure button clicked")
        
        # Import ConfigWidget here to avoid circular imports
        from .config_widget import ConfigWidget
        
        try:
            # Create and show the configuration widget as a dialog
            config_dialog = QDialog(self)
            config_dialog.setWindowTitle("Configuration - Cloud Sync")
            config_dialog.setModal(True)
            config_dialog.resize(700, 600)
            
            # Create layout and add config widget
            layout = QVBoxLayout(config_dialog)
            layout.setContentsMargins(10, 10, 10, 10)
            
            config_widget = ConfigWidget()
            layout.addWidget(config_widget)
            
            # Add close button
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            close_button = QPushButton("Close")
            close_button.clicked.connect(config_dialog.accept)
            button_layout.addWidget(close_button)
            layout.addLayout(button_layout)
            
            # Show the dialog
            if config_dialog.exec() == QDialog.Accepted:
                # Reload configuration after dialog closes
                self.cloud_config = self.load_cloud_config()
                # Refresh the dialog to show updated config
                self.refresh_config_display()
                
        except Exception as e:
            logger.error(f"Error opening configuration dialog: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open configuration dialog: {e}"
            )
    
    def refresh_config_display(self):
        """Refresh the configuration display with current settings"""
        # This is a simplified refresh - in a full implementation,
        # we would update the labels with the new configuration values
        QMessageBox.information(
            self,
            "Configuration Updated",
            "Configuration has been updated. Please close and reopen this dialog to see the changes."
        )