import os
import logging
import configparser
import zipfile
from datetime import datetime

from PySide6.QtCore import QThread, Signal, Qt, QUrl
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QFormLayout, QListWidget, QLineEdit, QPushButton, 
                               QCheckBox, QFileDialog, QMessageBox, QProgressDialog,
                               QApplication)
from PySide6.QtGui import QDesktopServices

from astropy.io import fits
from astrofiler_file import fitsProcessing
from astrofiler_smart import smart_telescope_manager

logger = logging.getLogger(__name__)


class TelescopeDownloadWorker(QThread):
    """Worker thread for downloading files from smart telescopes."""
    
    # Signals for thread-safe communication
    progress_updated = Signal(str)
    progress_percent_updated = Signal(int)
    download_completed = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, telescope_type, hostname, network, target_directory, delete_files=False):
        super().__init__()
        self.telescope_type = telescope_type
        self.hostname = hostname
        self.network = network
        self.target_directory = target_directory
        self.delete_files = delete_files
        self._stop_requested = False
    
    def _modify_fits_headers(self, fits_path, folder_name, telescope_type=None):
        """Modify FITS headers based on folder name."""
        try:
            with fits.open(fits_path, mode='update') as hdul:
                header = hdul[0].header
                
                # For iTelescope, preserve the original OBJECT header and don't modify it
                if "seestar" in telescope_type.lower():
                    # Extract OBJECT from folder name (strip _sub or _mosaic_sub suffix)
                    object_name = folder_name
                    if folder_name.endswith('_mosaic_sub'):
                        object_name = folder_name[:-11]  # Remove '_mosaic_sub'
                    elif folder_name.endswith('_sub'):
                        object_name = folder_name[:-4]   # Remove '_sub'
                    
                    # Set OBJECT header
                    header['OBJECT'] = object_name
                
                    # Set MOSAIC header for mosaic folders (for all telescope types)
                    if folder_name.endswith('_mosaic_sub'):
                        header['MOSAIC'] = True
                    else:
                        header['MOSAIC'] = False
                
                hdul.flush()
                
        except Exception as e:
            self.progress_updated.emit(f"Warning: Could not modify headers for {os.path.basename(fits_path)}: {str(e)}")
    
    def _unzip_file(self, zip_path):
        """Unzip a file and return the path to the extracted file."""
        try:
            # Get the directory where the zip file is located
            zip_dir = os.path.dirname(zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # List all files in the zip
                file_list = zip_ref.namelist()
                
                if not file_list:
                    logger.warning(f"No files found in zip archive {zip_path}")
                    return None
                
                # Extract all files to the same directory as the zip file
                zip_ref.extractall(zip_dir)
                
                # Find the main file (usually the largest or first .fit/.fits file)
                extracted_files = []
                for file_name in file_list:
                    if file_name.lower().endswith(('.fit', '.fits')):
                        extracted_path = os.path.join(zip_dir, file_name)
                        if os.path.exists(extracted_path):
                            extracted_files.append(extracted_path)
                
                if extracted_files:
                    # Return the first FITS file found
                    main_file = extracted_files[0]
                    logger.info(f"Successfully extracted {len(extracted_files)} file(s) from {os.path.basename(zip_path)}")
                    
                    # Remove the original zip file after successful extraction
                    try:
                        os.remove(zip_path)
                        logger.debug(f"Removed original zip file {zip_path}")
                    except Exception as e:
                        logger.warning(f"Could not remove original zip file {zip_path}: {e}")
                    
                    return main_file
                else:
                    logger.warning(f"No FITS files found in zip archive {zip_path}")
                    return None
                    
        except zipfile.BadZipFile:
            logger.error(f"Invalid zip file: {zip_path}")
            return None
        except Exception as e:
            logger.error(f"Error extracting zip file {zip_path}: {e}")
            return None
    
    def stop(self):
        """Request the worker to stop."""
        logger.debug("Worker thread stop requested")
        self._stop_requested = True
    
    def run(self):
        """Perform the actual download process."""
        try:
            # Step 1: Find the telescope (10% of progress)
            if self._stop_requested:
                return
            
            if self.telescope_type in ["SeeStar", "StellarMate"]:
                protocol_info = "SMB"
            elif self.telescope_type == "iTelescope":
                protocol_info = "FTPS"
            else:
                protocol_info = "FTP"
            self.progress_updated.emit(f"Scanning network for {self.telescope_type} telescope ({protocol_info})...")
            logger.info(f"Scanning network for {self.telescope_type} telescope ({protocol_info})...")
            self.progress_percent_updated.emit(5)
            
            ip, error = smart_telescope_manager.find_telescope(
                self.telescope_type, 
                network_range=self.network if self.network else None,
                hostname=self.hostname if self.hostname else None
            )
            
            if self._stop_requested:
                return
            
            if not ip:
                self.error_occurred.emit(f"Failed to find telescope: {error}")
                logger.error(f"Failed to find telescope: {error}")
                return
            
            self.progress_updated.emit(f"Connected to {self.telescope_type} at {ip}")
            logger.info(f"Connected to {self.telescope_type} at {ip}")
            self.progress_percent_updated.emit(10)
            
            # Step 2: Get list of FITS files (20% of progress)
            if self._stop_requested:
                return
            
            self.progress_updated.emit("Scanning for FITS files...")
            logger.info("Scanning for FITS files...")
            self.progress_percent_updated.emit(20)
            
            # Get credentials for iTelescope if needed
            self.username = None
            self.password = None
            if self.telescope_type == "iTelescope":
                self.username, self.password = smart_telescope_manager.get_itelescope_credentials()
                if not self.username or not self.password:
                    self.error_occurred.emit("iTelescope credentials not configured. Please configure in Config → Smart Telescopes tab.")
                    logger.error("iTelescope credentials not configured")
                    return
            
            fits_files, error = smart_telescope_manager.get_fits_files(self.telescope_type, ip, self.username, self.password)
            
            if self._stop_requested:
                return
            
            if error:
                self.error_occurred.emit(f"Failed to get file list: {error}")
                logger.error(f"Failed to get file list: {error}")
                return
            
            if not fits_files:
                self.download_completed.emit("No FITS files found on telescope")
                logger.info("No FITS files found on telescope")
                return
            
            self.progress_updated.emit(f"Found {len(fits_files)} FITS files")
            logger.info(f"Found {len(fits_files)} FITS files")
            self.progress_percent_updated.emit(30)
            
            # Step 3: Download files (30% to 90% of progress)
            if self._stop_requested:
                return
            
            downloaded_files = 0
            failed_files = []
            deleted_files = 0
            registered_files = 0
            
            for i, file_info in enumerate(fits_files):
                if self._stop_requested:
                    break
                
                file_name = file_info['name']
                self.progress_updated.emit(f"Processing {file_name} ({i+1}/{len(fits_files)})...")
                
                # Calculate progress (30% to 90% for downloads)
                download_progress = 30 + int((i / len(fits_files)) * 60)
                self.progress_percent_updated.emit(download_progress)
                
                # Create local file path
                folder_name = file_info.get('folder_name', 'unknown')
                
                # For iTelescope, store files directly in target directory without preserving folder structure
                if self.telescope_type == 'iTelescope':
                    local_path = os.path.join(self.target_directory, file_name)
                else:
                    # For other telescopes, maintain folder structure
                    local_dir = os.path.join(self.target_directory, folder_name)
                    local_path = os.path.join(local_dir, file_name)
                
                # Download the file
                success, error = smart_telescope_manager.download_file(
                    self.telescope_type, ip, file_info, local_path,
                    self.username, self.password,
                    progress_callback=lambda progress: not self._stop_requested
                )
                
                if self._stop_requested:
                    break
                
                if success:
                    downloaded_files += 1
                    logger.info(f"Downloaded {file_name}")
                    
                    # Unzip files if they have .zip extension
                    if file_name.lower().endswith('.zip'):
                        try:
                            unzipped_path = self._unzip_file(local_path)
                            if unzipped_path:
                                logger.info(f"Unzipped {file_name} to {os.path.basename(unzipped_path)}")
                                # Update local_path to point to the unzipped file for further processing
                                local_path = unzipped_path
                                file_name = os.path.basename(unzipped_path)
                            else:
                                logger.warning(f"Failed to unzip {file_name}, continuing with zip file")
                        except Exception as e:
                            logger.error(f"Error unzipping {file_name}: {e}, continuing with zip file")
                    
                    # Modify FITS headers based on folder name
                    self._modify_fits_headers(local_path, folder_name, self.telescope_type)
                    
                    # Register the downloaded FITS file in the database
                    try:
                        processor = fitsProcessing()
                        root_dir = os.path.dirname(local_path)
                        file_name_only = os.path.basename(local_path)
                        
                        # Register the file (moveFiles=True to move from download location to repository)
                        registered_id = processor.registerFitsImage(root_dir, file_name_only, moveFiles=True)
                        
                        if registered_id:
                            registered_files += 1
                            logger.info(f"Successfully registered {file_name} in database with ID {registered_id}")
                        else:
                            logger.warning(f"Failed to register {file_name} in database")
                            
                    except Exception as e:
                        logger.error(f"Error registering {file_name} in database: {e}")
                    
                    # Delete file from telescope if requested
                    if self.delete_files:
                        delete_success, delete_error = smart_telescope_manager.delete_file(
                            self.telescope_type, ip, file_info
                        )
                        if delete_success:
                            deleted_files += 1
                            logger.info(f"Deleted {file_name} from telescope")
                        else:
                            logger.warning(f"Failed to delete {file_name}: {delete_error}")
                else:
                    failed_files.append(f"{file_name}: {error}")
                    logger.error(f"Failed to download {file_name}: {error}")
            
            # Step 4: Complete (90% to 100%)
            if self._stop_requested:
                self.progress_updated.emit("Download cancelled")
                return
            
            self.progress_percent_updated.emit(95)
            
            # Step 5: Generate completion message
            completion_message = f"Download completed!\n\n"
            completion_message += f"Downloaded: {downloaded_files} files\n"
            completion_message += f"Registered in database: {registered_files} files\n"
            
            if failed_files:
                completion_message += f"Failed: {len(failed_files)} files\n"
                completion_message += "Failed files:\n" + "\n".join(failed_files[:5])
                if len(failed_files) > 5:
                    completion_message += f"\n... and {len(failed_files) - 5} more"
            
            if self.delete_files:
                completion_message += f"\nDeleted from telescope: {deleted_files} files"
            
            completion_message += f"\n\nFiles processed and moved to repository structure"
            
            self.progress_percent_updated.emit(100)
            self.download_completed.emit(completion_message)
            logger.info(f"Download process completed: {downloaded_files} downloaded, {registered_files} registered, {len(failed_files)} failed")
            
        except Exception as e:
            if not self._stop_requested:
                self.error_occurred.emit(f"Unexpected error during download: {str(e)}")
                logger.error(f"Unexpected error during download: {str(e)}")


class SmartTelescopeDownloadDialog(QDialog):
    """Dialog for downloading files from smart telescopes."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Repository")
        self.setModal(True)
        self.resize(400, 300)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Telescope selection
        telescope_group = QGroupBox("Smart Telescope")
        telescope_layout = QFormLayout(telescope_group)
        
        self.telescope_list = QListWidget()
        self.telescope_list.addItem("SeeStar")
        self.telescope_list.addItem("StellarMate")
        self.telescope_list.addItem("DWARF 3")
        self.telescope_list.addItem("iTelescope")
        self.telescope_list.setCurrentRow(0)
        self.telescope_list.setMaximumHeight(100)
        
        telescope_layout.addRow("Telescope Type:", self.telescope_list)
        
        # Connection settings
        connection_group = QGroupBox("Connection Settings")
        connection_layout = QFormLayout(connection_group)
        
        self.hostname_edit = QLineEdit("seestar.local")
        self.hostname_edit.setToolTip("Hostname or IP address of the telescope")
        
        self.network_edit = QLineEdit()
        default_network = smart_telescope_manager.get_local_network()
        self.network_edit.setText(default_network)
        self.network_edit.setToolTip("Network range to scan (e.g., 10.0.0.0/24)")
        
        # Target directory for downloads
        self.target_dir_edit = QLineEdit()
        self.target_dir_edit.setToolTip("Directory where downloaded files will be stored")
        
        default_target_dir = self.get_default_target_directory()
        self.target_dir_edit.setText(default_target_dir)
        
        self.browse_target_button = QPushButton("Browse...")
        self.browse_target_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.browse_target_button.clicked.connect(self.browse_target_directory)
        
        target_dir_layout = QHBoxLayout()
        target_dir_layout.addWidget(self.target_dir_edit)
        target_dir_layout.addWidget(self.browse_target_button)
        
        connection_layout.addRow("Hostname:", self.hostname_edit)
        connection_layout.addRow("Network:", self.network_edit)
        connection_layout.addRow("Target Directory:", target_dir_layout)
        
        # Delete files option
        self.delete_files_checkbox = QCheckBox("Delete files on host after download")
        self.delete_files_checkbox.setChecked(False)
        self.delete_files_checkbox.setToolTip("WARNING: This will permanently delete files from the telescope after successful download")
        connection_layout.addRow("", self.delete_files_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.download_button = QPushButton("Download")
        self.download_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("QPushButton { font-size: 11px; }")
        
        button_layout.addStretch()
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addWidget(telescope_group)
        layout.addWidget(connection_group)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        # Connect signals
        self.telescope_list.currentTextChanged.connect(self.on_telescope_changed)
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button.clicked.connect(self.reject)
        
        self.on_telescope_changed()
    
    def get_default_target_directory(self):
        """Get the default target directory from configuration (source path)."""
        try:
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            
            if config.has_option('DEFAULT', 'source'):
                source_path = config.get('DEFAULT', 'source')
                if source_path and os.path.exists(source_path):
                    return source_path
            
            return os.getcwd()
            
        except Exception as e:
            logger.debug(f"Error reading configuration: {e}")
            return os.getcwd()
    
    def browse_target_directory(self):
        """Open directory picker for target directory."""
        current_dir = self.target_dir_edit.text().strip()
        if not current_dir or not os.path.exists(current_dir):
            current_dir = os.getcwd()
        
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Target Directory for Downloads",
            current_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.target_dir_edit.setText(directory)
    
    def on_telescope_changed(self):
        """Handle telescope selection change."""
        current_telescope = self.telescope_list.currentItem()
        if current_telescope:
            telescope_type = current_telescope.text()
            if telescope_type == "SeeStar":
                self.hostname_edit.setText("seestar.local")
            elif telescope_type == "StellarMate":
                self.hostname_edit.setText("stellarmate.local")
            elif telescope_type == "DWARF 3":
                self.hostname_edit.setText("dwarf.local")
            elif telescope_type == "iTelescope":
                self.hostname_edit.setText("data.itelescope.net")
    
    def start_download(self):
        """Start the download process."""
        current_telescope = self.telescope_list.currentItem()
        if not current_telescope:
            QMessageBox.warning(self, "Warning", "Please select a telescope type.")
            return
        
        telescope_type = current_telescope.text()
        hostname = self.hostname_edit.text().strip()
        network = self.network_edit.text().strip()
        target_directory = self.target_dir_edit.text().strip()
        delete_files = self.delete_files_checkbox.isChecked()
        
        if not network:
            QMessageBox.warning(self, "Warning", "Please enter a network range.")
            return
        
        if not target_directory:
            QMessageBox.warning(self, "Warning", "Please specify a target directory.")
            return
        
        # Create progress dialog
        self.progress_dialog = QProgressDialog("Initializing download...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Downloading from Smart Telescope")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()
        
        # Create and configure worker thread
        self.worker = TelescopeDownloadWorker(telescope_type, hostname, network, target_directory, delete_files)
        
        # Connect worker signals to handlers
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.progress_percent_updated.connect(self.on_progress_percent_updated)
        self.worker.download_completed.connect(self.on_download_completed)
        self.worker.error_occurred.connect(self.on_error_occurred)
        
        # Connect progress dialog cancel to worker stop
        self.progress_dialog.canceled.connect(self.on_download_cancelled)
        
        # Start the worker thread
        self.worker.start()
        logger.info(f"Started download from {telescope_type} to {target_directory}")
    
    def on_progress_updated(self, message):
        """Handle progress text updates from worker thread."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
            self.progress_dialog.setLabelText(message)
            QApplication.processEvents()
    
    def on_progress_percent_updated(self, percent):
        """Handle progress percentage updates from worker thread."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
            self.progress_dialog.setValue(percent)
            QApplication.processEvents()
    
    def on_download_completed(self, message):
        """Handle download completion from worker thread."""
        logger.info(f"Download completed: {message}")
        
        # Close progress dialog
        self.close_progress_dialog()
        
        # Show completion message
        QMessageBox.information(self, "Download Complete", message)
        
        # Refresh the Images view in the main window if available
        if self.parent() and hasattr(self.parent(), 'images_widget'):
            if hasattr(self.parent().images_widget, 'load_fits_data'):
                logger.info("Refreshing Images view after download completion")
                self.parent().images_widget.load_fits_data()
        
        # Close the download dialog
        self.accept()
    
    def on_error_occurred(self, error_message):
        """Handle errors from worker thread."""
        logger.error(f"Download error: {error_message}")
        
        # Close progress dialog
        self.close_progress_dialog()
        
        # Show error message
        QMessageBox.critical(self, "Download Error", error_message)
    
    def on_download_cancelled(self):
        """Handle download cancellation."""
        logger.info("Download cancelled by user")
        
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(3000):
                self.worker.terminate()
                self.worker.wait(1000)
        
        # Close progress dialog
        self.close_progress_dialog()
    
    def closeEvent(self, event):
        """Handle dialog close event to ensure worker thread is stopped."""
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(3000):
                self.worker.terminate()
                self.worker.wait(1000)
        event.accept()
    
    def reject(self):
        """Handle dialog rejection (ESC key, X button, etc.)."""
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(3000):
                self.worker.terminate()
                self.worker.wait(1000)
        super().reject()
    
    # ...existing code for progress handling methods...
    
    def close_progress_dialog(self):
        """Close the progress dialog safely."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
            self.progress_dialog.close()
            self.progress_dialog = None
