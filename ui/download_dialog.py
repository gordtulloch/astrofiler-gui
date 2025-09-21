import os
import logging
import configparser
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
    
    def _modify_fits_headers(self, fits_path, folder_name):
        """Modify FITS headers based on folder name."""
        try:
            with fits.open(fits_path, mode='update') as hdul:
                header = hdul[0].header
                
                # Extract OBJECT from folder name (strip _sub or _mosaic_sub suffix)
                object_name = folder_name
                if folder_name.endswith('_mosaic_sub'):
                    object_name = folder_name[:-11]  # Remove '_mosaic_sub'
                elif folder_name.endswith('_sub'):
                    object_name = folder_name[:-4]   # Remove '_sub'
                
                # Set OBJECT header
                header['OBJECT'] = object_name
                
                # Set MOSAIC header for mosaic folders
                if folder_name.endswith('_mosaic_sub'):
                    header['MOSAIC'] = True
                else:
                    header['MOSAIC'] = False
                
                hdul.flush()
                
        except Exception as e:
            self.progress_updated.emit(f"Warning: Could not modify headers for {os.path.basename(fits_path)}: {str(e)}")
    
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
            
            self.progress_updated.emit("Scanning network for SeeStar telescope (mDNS only)...")
            logger.info("Scanning network for SeeStar telescope (mDNS only)...")
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
            
            self.progress_updated.emit(f"Connected to SeeStar at {ip}")
            logger.info(f"Connected to SeeStar at {ip}")
            self.progress_percent_updated.emit(10)
            
            # ...existing code for steps 2-6...
            
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
        self.telescope_list.setCurrentRow(0)
        self.telescope_list.setMaximumHeight(80)
        
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
        
        # Create and start worker thread
        self.worker = TelescopeDownloadWorker(telescope_type, hostname, network, target_directory, delete_files)
        self.worker.start()
    
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
