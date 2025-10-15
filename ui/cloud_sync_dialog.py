import os
import logging
import configparser
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QFrame, QMessageBox, QGroupBox, QApplication)
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

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
            'ondemand': 'On Demand (Download files if required)'
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
            from astrofiler_cloud import _get_gcs_client
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
        import astrofiler_cloud
        
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
            
            # Update progress
            progress.setLabelText("Comparing with local files...")
            progress.setMaximum(len(cloud_files))
            QApplication.processEvents()
            
            # Compare with local files and update URLs
            matches_found = 0
            for i, cloud_file in enumerate(cloud_files):
                if progress.wasCanceled():
                    break
                    
                progress.setValue(i)
                progress.setLabelText(f"Processing: {cloud_file['name']}")
                QApplication.processEvents()
                
                # Try to find matching local file
                # This is a simplified match - you might want to implement more sophisticated matching
                local_file = self.find_matching_local_file(cloud_file)
                
                if local_file:
                    # Update the cloud URL in the database
                    cloud_url = self.build_cloud_url(cloud_file)
                    fitsFile.update(fitsFileCloudURL=cloud_url).where(
                        fitsFile.fitsFileId == local_file.fitsFileId
                    ).execute()
                    matches_found += 1
                    logger.info(f"Updated cloud URL for file: {local_file.fitsFileName}")
            
            progress.close()
            
            # Show results
            QMessageBox.information(
                self,
                "Analysis Complete",
                f"Cloud analysis completed successfully!\n\n"
                f"• Cloud files found: {len(cloud_files)}\n"
                f"• Local matches found: {matches_found}\n"
                f"• Database records updated: {matches_found}\n\n"
                f"Files with cloud URLs can now be synchronized."
            )
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            raise e
    
    def get_cloud_file_list(self, bucket_name, auth_info):
        """Get list of files from cloud storage"""
        import astrofiler_cloud
        
        try:
            logger.info(f"Getting file list from bucket: {bucket_name}")
            
            # Use the new list function from astrofiler_cloud
            cloud_files = astrofiler_cloud.list_gcs_bucket_files(bucket_name, auth_info)
            
            logger.info(f"Retrieved {len(cloud_files)} files from cloud storage")
            return cloud_files
            
        except Exception as e:
            logger.error(f"Error getting cloud file list: {e}")
            raise Exception(f"Failed to get cloud file listing: {str(e)}")
    
    def find_matching_local_file(self, cloud_file):
        """Find local file that matches the cloud file"""
        from astrofiler_db import fitsFile
        
        try:
            # Get the filename from the cloud file path
            filename = cloud_file.get('name', '').split('/')[-1]
            
            if not filename:
                return None
            
            # Try to match by filename first
            try:
                local_file = fitsFile.get(fitsFile.fitsFileName == filename)
                logger.debug(f"Found exact filename match: {filename}")
                return local_file
            except fitsFile.DoesNotExist:
                pass
            
            # Try to match by partial filename (without extension)
            base_filename = filename.rsplit('.', 1)[0]  # Remove extension
            try:
                local_file = fitsFile.get(fitsFile.fitsFileName.contains(base_filename))
                logger.debug(f"Found partial filename match: {base_filename}")
                return local_file
            except fitsFile.DoesNotExist:
                pass
            
            # Could add more sophisticated matching here:
            # - Match by MD5 hash if available
            # - Match by file size
            # - Match by FITS header metadata
            
            # Try hash matching if available
            if 'md5_hash' in cloud_file and cloud_file['md5_hash']:
                try:
                    # Note: This would require storing MD5 hashes in the local database
                    # For now, we'll skip this matching method
                    pass
                except:
                    pass
            
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
            QMessageBox.information(
                self,
                "Complete Sync",
                "Complete sync functionality will be implemented in a future version.\n\n"
                "This will synchronize files in both directions between local and cloud storage."
            )
        elif sync_profile == 'on demand':
            QMessageBox.information(
                self,
                "On Demand Sync",
                "On Demand sync functionality will be implemented in a future version.\n\n"
                "This will allow selective synchronization of individual files or folders."
            )
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
        import astrofiler_cloud
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
            
            # Get all FITS files from database
            fits_files = list(fitsFile.select().where(fitsFile.fitsFileName.is_null(False)))
            
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
                    success, cloud_url, message = astrofiler_cloud.upload_file_to_backup(
                        bucket_name, auth_info, full_path, relative_path
                    )
                    
                    if success:
                        # Update the database with cloud URL
                        fits_file.fitsFileCloudURL = cloud_url
                        fits_file.save()
                        updated_count += 1
                        
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