import os
import logging
import configparser
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QGroupBox, QLineEdit, QPushButton, QCheckBox, 
                               QComboBox, QSpinBox, QFileDialog, QMessageBox,
                               QApplication, QTabWidget)

logger = logging.getLogger(__name__)

class ConfigWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_settings()  # Load settings after UI is initialized

    def showEvent(self, event):
        """Handle show events to reload settings when widget becomes visible"""
        super().showEvent(event)
        logger.debug("Config widget shown - reloading settings from INI file")
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create individual tabs
        self.create_general_tab()
        self.create_cloud_sync_tab()
        self.create_calibration_tab()
        self.create_smart_telescopes_tab()
        
        # Add action buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Settings")
        self.save_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.setStyleSheet("QPushButton { font-size: 11px; }")

        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()

        layout.addWidget(self.tab_widget)
        layout.addLayout(button_layout)

        # Connect signals
        self.save_button.clicked.connect(self.save_settings)
        self.reset_button.clicked.connect(self.reset_settings)
        self.theme.currentTextChanged.connect(self.on_theme_changed)

    def create_general_tab(self):
        """Create the General tab with General Settings, Display Settings, External Tools, and Suppress Warnings."""
        general_tab = QWidget()
        layout = QVBoxLayout(general_tab)

        # General settings group
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout(general_group)

        # Source Path with directory picker
        source_path_layout = QHBoxLayout()
        self.source_path = QLineEdit()
        self.source_path_button = QPushButton("Browse...")
        self.source_path_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.source_path_button.clicked.connect(self.browse_source_path)
        source_path_layout.addWidget(self.source_path)
        source_path_layout.addWidget(self.source_path_button)

        # Repository Path with directory picker
        repo_path_layout = QHBoxLayout()
        self.repo_path = QLineEdit()
        self.repo_path_button = QPushButton("Browse...")
        self.repo_path_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.repo_path_button.clicked.connect(self.browse_repo_path)
        repo_path_layout.addWidget(self.repo_path)
        repo_path_layout.addWidget(self.repo_path_button)

        # Refresh on Startup (default checked)
        self.refresh_on_startup = QCheckBox()
        self.refresh_on_startup.setChecked(True)

        # Save modified headers (default unchecked)
        self.save_modified_headers = QCheckBox()
        self.save_modified_headers.setChecked(False)
        self.save_modified_headers.setToolTip("When enabled, AstroFiler will save any header modifications back to the FITS files")

        general_layout.addRow("Source Path:", source_path_layout)
        general_layout.addRow("Repository Path:", repo_path_layout)
        general_layout.addRow("Refresh on Startup:", self.refresh_on_startup)
        general_layout.addRow("Save Modified Headers:", self.save_modified_headers)

        # Display settings group
        display_group = QGroupBox("Display Settings")
        display_layout = QFormLayout(display_group)

        self.theme = QComboBox()
        self.theme.addItems(["Light", "Dark", "Auto"])
        self.theme.setCurrentText("Dark")
        self.font_size = QSpinBox()
        self.font_size.setMinimum(8)
        self.font_size.setMaximum(24)
        self.font_size.setValue(10)
        self.grid_size = QSpinBox()
        self.grid_size.setMinimum(16)
        self.grid_size.setMaximum(256)
        self.grid_size.setValue(64)

        display_layout.addRow("Theme:", self.theme)
        display_layout.addRow("Font Size:", self.font_size)
        display_layout.addRow("Grid Icon Size:", self.grid_size)

        # External Tools settings group
        tools_group = QGroupBox("External Tools")
        tools_layout = QFormLayout(tools_group)

        # FITS Viewer Path with file picker
        fits_viewer_layout = QHBoxLayout()
        self.fits_viewer_path = QLineEdit()
        self.fits_viewer_path.setPlaceholderText("Select external FITS file viewer...")
        self.fits_viewer_button = QPushButton("Browse...")
        self.fits_viewer_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.fits_viewer_button.clicked.connect(self.browse_fits_viewer)
        fits_viewer_layout.addWidget(self.fits_viewer_path)
        fits_viewer_layout.addWidget(self.fits_viewer_button)

        tools_layout.addRow("FITS Viewer:", fits_viewer_layout)

        # Siril CLI Path with file picker
        siril_cli_layout = QHBoxLayout()
        self.siril_cli_path = QLineEdit()
        self.siril_cli_path.setPlaceholderText("Select Siril CLI executable (siril-cli.exe)...")
        self.siril_cli_button = QPushButton("Browse...")
        self.siril_cli_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.siril_cli_button.clicked.connect(self.browse_siril_cli)
        siril_cli_layout.addWidget(self.siril_cli_path)
        siril_cli_layout.addWidget(self.siril_cli_button)

        tools_layout.addRow("Siril CLI:", siril_cli_layout)

        # Suppress Warnings settings group
        warnings_group = QGroupBox("Suppress Warnings")
        warnings_layout = QFormLayout(warnings_group)

        # Suppress delete warnings checkbox
        self.suppress_delete_warnings = QCheckBox()
        self.suppress_delete_warnings.setChecked(False)
        self.suppress_delete_warnings.setToolTip("When enabled, file deletion confirmations will be suppressed")

        warnings_layout.addRow("Suppress Delete Warnings:", self.suppress_delete_warnings)

        # Add groups to tab layout
        layout.addWidget(general_group)
        layout.addWidget(display_group)
        layout.addWidget(tools_group)
        layout.addWidget(warnings_group)
        layout.addStretch()

        self.tab_widget.addTab(general_tab, "General")

    def create_cloud_sync_tab(self):
        """Create the Cloud Sync tab."""
        cloud_tab = QWidget()
        layout = QVBoxLayout(cloud_tab)

        # Cloud Sync settings group
        cloud_sync_group = QGroupBox("Cloud Sync")
        cloud_sync_layout = QFormLayout(cloud_sync_group)

        # Cloud Vendor selection
        self.cloud_vendor = QComboBox()
        self.cloud_vendor.addItems(["Google Cloud Storage"])
        self.cloud_vendor.setCurrentText("Google Cloud Storage")

        # Bucket URL
        self.bucket_url = QLineEdit()
        self.bucket_url.setPlaceholderText("e.g., astrofiler-repository")
        self.bucket_url.setText("astrofiler-repository")
        self.bucket_url.setToolTip(
            "Google Cloud Storage bucket name.\n\n"
            "Create a bucket in Google Cloud Console:\n"
            "1. Go to Cloud Storage → Buckets\n"
            "2. Click 'Create Bucket'\n"
            "3. Choose a globally unique name\n"
            "4. Select location and storage class\n\n"
            "Bucket names must be globally unique across all of Google Cloud."
        )

        # Auth File Path with file picker
        auth_file_layout = QHBoxLayout()
        self.auth_file_path = QLineEdit()
        self.auth_file_path.setPlaceholderText("Select authentication file...")
        self.auth_file_path.setToolTip(
            "Path to Google Cloud Service Account JSON key file.\n\n"
            "To create an auth file:\n"
            "1. Go to Google Cloud Console\n"
            "2. Create a Service Account\n"
            "3. Grant 'Storage Object Admin' role\n"
            "4. Create and download JSON key\n\n"
            "See GCS_SETUP_GUIDE.md for detailed instructions."
        )
        self.auth_file_button = QPushButton("Browse...")
        self.auth_file_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.auth_file_button.clicked.connect(self.browse_auth_file)
        auth_file_layout.addWidget(self.auth_file_path)
        auth_file_layout.addWidget(self.auth_file_button)

        # Sync Profile selection
        self.sync_profile = QComboBox()
        self.sync_profile.addItem("Complete Sync", "complete")
        self.sync_profile.addItem("Backup Only", "backup")
        self.sync_profile.addItem("On Demand", "ondemand")
        self.sync_profile.setCurrentIndex(0)  # Default to Complete Sync
        self.sync_profile.setToolTip(
            "Complete Sync: All files kept both local and in the Cloud\n"
            "Backup Only: All files updated to the Cloud but do not download if missing\n"
            "On Demand: Download files if required"
        )

        # Auto-cleanup checkbox
        self.auto_cleanup_backed_files = QCheckBox()
        self.auto_cleanup_backed_files.setChecked(False)
        self.auto_cleanup_backed_files.setToolTip(
            "When enabled, calibration files and uncalibrated light files will be automatically deleted from local storage after they are successfully backed up to the cloud.\n\n"
            "This helps save local disk space while ensuring files are safely stored in the cloud.\n\n"
            "Only applies to:\n"
            "• Calibration files (bias, dark, flat)\n"
            "• Uncalibrated light frames\n\n"
            "Master calibration frames and processed/stacked images are never deleted."
        )

        cloud_sync_layout.addRow("Cloud Vendor:", self.cloud_vendor)
        cloud_sync_layout.addRow("Bucket URL:", self.bucket_url)
        cloud_sync_layout.addRow("Auth File:", auth_file_layout)
        cloud_sync_layout.addRow("Sync Profile:", self.sync_profile)
        cloud_sync_layout.addRow("Auto-cleanup Backed Files:", self.auto_cleanup_backed_files)

        layout.addWidget(cloud_sync_group)
        layout.addStretch()

        self.tab_widget.addTab(cloud_tab, "Cloud Sync")

    def create_calibration_tab(self):
        """Create the Calibration tab with Auto-Calibration settings."""
        calibration_tab = QWidget()
        layout = QVBoxLayout(calibration_tab)

        # Auto-Calibration settings group
        auto_cal_group = QGroupBox("Auto-Calibration")
        auto_cal_layout = QFormLayout(auto_cal_group)

        # Minimum files per master
        self.min_files_per_master = QSpinBox()
        self.min_files_per_master.setMinimum(2)
        self.min_files_per_master.setMaximum(100)
        self.min_files_per_master.setValue(3)
        self.min_files_per_master.setToolTip(
            "Minimum number of calibration files required to create a master frame.\n\n"
            "Higher numbers produce better quality masters but require more files.\n"
            "Recommended: 3-10 files per master."
        )

        # Auto-calibration progress
        self.auto_calibration_progress = QCheckBox()
        self.auto_calibration_progress.setChecked(True)
        self.auto_calibration_progress.setToolTip(
            "Show progress dialogs during automatic calibration operations.\n\n"
            "When enabled, progress windows will display master creation status.\n"
            "Disable for headless or automated processing environments."
        )

        auto_cal_layout.addRow("Min Files per Master:", self.min_files_per_master)
        auto_cal_layout.addRow("Show Progress Dialogs:", self.auto_calibration_progress)

        layout.addWidget(auto_cal_group)
        layout.addStretch()

        self.tab_widget.addTab(calibration_tab, "Calibration")

    def create_smart_telescopes_tab(self):
        """Create the Smart Telescopes tab with iTelescope Configuration."""
        smart_telescopes_tab = QWidget()
        layout = QVBoxLayout(smart_telescopes_tab)

        # iTelescope settings group
        itelescope_group = QGroupBox("iTelescope Configuration")
        itelescope_layout = QFormLayout(itelescope_group)

        # iTelescope Username
        self.itelescope_username = QLineEdit()
        self.itelescope_username.setPlaceholderText("Your iTelescope username")
        self.itelescope_username.setToolTip(
            "Username for your iTelescope account.\n\n"
            "This is required to connect to data.itelescope.net via FTPS\n"
            "and download calibrated files from your iTelescope sessions."
        )

        # iTelescope Password
        self.itelescope_password = QLineEdit()
        self.itelescope_password.setPlaceholderText("Your iTelescope password")
        self.itelescope_password.setEchoMode(QLineEdit.Password)
        self.itelescope_password.setToolTip(
            "Password for your iTelescope account.\n\n"
            "This is securely stored and used for FTPS authentication\n"
            "to download calibrated files from iTelescope."
        )

        itelescope_layout.addRow("Username:", self.itelescope_username)
        itelescope_layout.addRow("Password:", self.itelescope_password)

        layout.addWidget(itelescope_group)
        layout.addStretch()

        self.tab_widget.addTab(smart_telescopes_tab, "Smart Telescopes")
    
    def save_settings(self):
        """Save configuration settings to astrofiler.ini file"""
        try:
            config = configparser.ConfigParser()
            
            # Read existing config first to preserve any other settings
            config.read('astrofiler.ini')
            
            # Ensure DEFAULT section exists
            if 'DEFAULT' not in config:
                config.add_section('DEFAULT')
            
            # Get paths and ensure they end with a slash
            source_path = self.source_path.text().strip()
            repo_path = self.repo_path.text().strip()
            
            # Automatically append slash if not present
            if source_path and not source_path.endswith('/') and not source_path.endswith('\\'):
                source_path += '/'
            if repo_path and not repo_path.endswith('/') and not repo_path.endswith('\\'):
                repo_path += '/'
            
            # Update individual settings instead of replacing the entire DEFAULT section
            config.set('DEFAULT', 'source', source_path)
            config.set('DEFAULT', 'repo', repo_path)
            config.set('DEFAULT', 'refresh_on_startup', str(self.refresh_on_startup.isChecked()))
            config.set('DEFAULT', 'save_modified_headers', str(self.save_modified_headers.isChecked()))
            config.set('DEFAULT', 'theme', self.theme.currentText())
            config.set('DEFAULT', 'font_size', str(self.font_size.value()))
            config.set('DEFAULT', 'grid_size', str(self.grid_size.value()))
            config.set('DEFAULT', 'fits_viewer_path', self.fits_viewer_path.text().strip())
            config.set('DEFAULT', 'siril_cli_path', self.siril_cli_path.text().strip())
            config.set('DEFAULT', 'suppress_delete_warnings', str(self.suppress_delete_warnings.isChecked()))
            config.set('DEFAULT', 'cloud_vendor', self.cloud_vendor.currentText())
            config.set('DEFAULT', 'bucket_url', self.bucket_url.text().strip())
            config.set('DEFAULT', 'auth_file_path', self.auth_file_path.text().strip())
            config.set('DEFAULT', 'sync_profile', self.sync_profile.currentData())
            config.set('DEFAULT', 'auto_cleanup_backed_files', str(self.auto_cleanup_backed_files.isChecked()))
            
            # Auto-calibration settings
            config.set('DEFAULT', 'min_files_per_master', str(self.min_files_per_master.value()))
            config.set('DEFAULT', 'auto_calibration_progress', str(self.auto_calibration_progress.isChecked()))
            config.set('DEFAULT', 'auto_calibration_progress', str(self.auto_calibration_progress.isChecked()))
            
            # iTelescope settings
            config.set('DEFAULT', 'itelescope_username', self.itelescope_username.text().strip())
            config.set('DEFAULT', 'itelescope_password', self.itelescope_password.text().strip())
            
            # Write to the astrofiler.ini file
            with open('astrofiler.ini', 'w') as configfile:
                config.write(configfile)
            
            logger.info("Settings saved to astrofiler.ini!")
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save settings: {e}")
    
    def load_settings(self):
        """Load configuration settings from astrofiler.ini file"""
        try:
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            
            # Load path settings
            if config.has_option('DEFAULT', 'source'):
                self.source_path.setText(config.get('DEFAULT', 'source'))
            
            if config.has_option('DEFAULT', 'repo'):
                self.repo_path.setText(config.get('DEFAULT', 'repo'))
            
            # Load additional settings with defaults
            if config.has_option('DEFAULT', 'refresh_on_startup'):
                refresh_value = config.getboolean('DEFAULT', 'refresh_on_startup')
                self.refresh_on_startup.setChecked(refresh_value)
            
            if config.has_option('DEFAULT', 'save_modified_headers'):
                save_headers_value = config.getboolean('DEFAULT', 'save_modified_headers')
                self.save_modified_headers.setChecked(save_headers_value)
            
            if config.has_option('DEFAULT', 'theme'):
                theme_value = config.get('DEFAULT', 'theme')
                index = self.theme.findText(theme_value)
                if index >= 0:
                    self.theme.setCurrentIndex(index)
            
            if config.has_option('DEFAULT', 'font_size'):
                font_size = config.getint('DEFAULT', 'font_size')
                self.font_size.setValue(font_size)
            
            if config.has_option('DEFAULT', 'grid_size'):
                grid_size = config.getint('DEFAULT', 'grid_size')
                self.grid_size.setValue(grid_size)
            
            if config.has_option('DEFAULT', 'fits_viewer_path'):
                fits_viewer_path = config.get('DEFAULT', 'fits_viewer_path')
                self.fits_viewer_path.setText(fits_viewer_path)
            
            if config.has_option('DEFAULT', 'siril_cli_path'):
                siril_cli_path = config.get('DEFAULT', 'siril_cli_path')
                self.siril_cli_path.setText(siril_cli_path)
            
            if config.has_option('DEFAULT', 'suppress_delete_warnings'):
                suppress_value_str = config.get('DEFAULT', 'suppress_delete_warnings')
                logger.debug(f"Raw suppress_delete_warnings value from INI: '{suppress_value_str}'")
                
                # Convert to boolean
                if isinstance(suppress_value_str, str):
                    suppress_value = suppress_value_str.lower() in ('true', '1', 'yes', 'on')
                else:
                    suppress_value = bool(suppress_value_str)
                
                logger.debug(f"Converted suppress_delete_warnings value: {suppress_value}")
                
                if hasattr(self, 'suppress_delete_warnings'):
                    self.suppress_delete_warnings.setChecked(suppress_value)
                    logger.debug(f"Checkbox set to: {self.suppress_delete_warnings.isChecked()}")
            else:
                logger.debug("suppress_delete_warnings not found in INI file, setting to False")
                if hasattr(self, 'suppress_delete_warnings'):
                    self.suppress_delete_warnings.setChecked(False)

            # Load cloud sync settings
            if config.has_option('DEFAULT', 'cloud_vendor'):
                cloud_vendor = config.get('DEFAULT', 'cloud_vendor')
                index = self.cloud_vendor.findText(cloud_vendor)
                if index >= 0:
                    self.cloud_vendor.setCurrentIndex(index)
            
            if config.has_option('DEFAULT', 'bucket_url'):
                bucket_url = config.get('DEFAULT', 'bucket_url')
                self.bucket_url.setText(bucket_url)
            
            if config.has_option('DEFAULT', 'auth_file_path'):
                auth_file_path = config.get('DEFAULT', 'auth_file_path')
                self.auth_file_path.setText(auth_file_path)
            
            if config.has_option('DEFAULT', 'sync_profile'):
                sync_profile = config.get('DEFAULT', 'sync_profile')
                # Find the index by data value
                for i in range(self.sync_profile.count()):
                    if self.sync_profile.itemData(i) == sync_profile:
                        self.sync_profile.setCurrentIndex(i)
                        break
            
            if config.has_option('DEFAULT', 'auto_cleanup_backed_files'):
                auto_cleanup_str = config.get('DEFAULT', 'auto_cleanup_backed_files')
                # Convert to boolean
                if isinstance(auto_cleanup_str, str):
                    auto_cleanup_value = auto_cleanup_str.lower() in ('true', '1', 'yes', 'on')
                else:
                    auto_cleanup_value = bool(auto_cleanup_str)
                self.auto_cleanup_backed_files.setChecked(auto_cleanup_value)

            # Load auto-calibration settings
            if config.has_option('DEFAULT', 'min_files_per_master'):
                min_files = config.getint('DEFAULT', 'min_files_per_master', fallback=3)
                self.min_files_per_master.setValue(min_files)

            if config.has_option('DEFAULT', 'auto_calibration_progress'):
                progress_str = config.get('DEFAULT', 'auto_calibration_progress')
                progress_value = progress_str.lower() in ('true', '1', 'yes', 'on')
                self.auto_calibration_progress.setChecked(progress_value)
            
            # Load iTelescope settings
            if config.has_option('DEFAULT', 'itelescope_username'):
                itelescope_username = config.get('DEFAULT', 'itelescope_username')
                self.itelescope_username.setText(itelescope_username)
            
            if config.has_option('DEFAULT', 'itelescope_password'):
                itelescope_password = config.get('DEFAULT', 'itelescope_password')
                self.itelescope_password.setText(itelescope_password)
                
            logger.debug("Settings loaded from astrofiler.ini!")
            
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            # Use default values if loading fails
            self.reset_settings()
    
    def reset_settings(self):
        # Reset to default values
        self.source_path.setText("")
        self.repo_path.setText("")
        self.refresh_on_startup.setChecked(True)
        self.save_modified_headers.setChecked(False)
        self.theme.setCurrentIndex(0)
        self.font_size.setValue(10)
        self.grid_size.setValue(64)
        self.fits_viewer_path.setText("")
        self.siril_cli_path.setText("")
        self.suppress_delete_warnings.setChecked(False)
        self.cloud_vendor.setCurrentIndex(0)
        self.bucket_url.setText("astrofiler-repository")
        self.auth_file_path.setText("")
        self.sync_profile.setCurrentIndex(0)  # Default to Complete Sync
        self.auto_cleanup_backed_files.setChecked(False)
        
        # Auto-calibration defaults
        self.min_files_per_master.setValue(3)
        self.auto_calibration_progress.setChecked(True)
        self.auto_calibration_progress.setChecked(True)
        
        # iTelescope defaults
        self.itelescope_username.setText("")
        self.itelescope_password.setText("")
    
    def browse_source_path(self):
        """Open directory dialog for source path"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Source Directory", 
            self.source_path.text() or os.path.expanduser("~")
        )
        if directory:
            self.source_path.setText(directory)
    
    def browse_repo_path(self):
        """Open directory dialog for repository path"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Repository Directory", 
            self.repo_path.text() or os.path.expanduser("~")
        )
        if directory:
            self.repo_path.setText(directory)
    
    def browse_fits_viewer(self):
        """Open file dialog for FITS viewer executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FITS Viewer Executable",
            self.fits_viewer_path.text() or os.path.expanduser("~"),
            "Executable Files (*.exe);;All Files (*)" if os.name == 'nt' else "All Files (*)"
        )
        if file_path:
            self.fits_viewer_path.setText(file_path)

    def browse_siril_cli(self):
        """Open file dialog for Siril CLI executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Siril CLI Executable",
            self.siril_cli_path.text() or os.path.expanduser("~"),
            "Executable Files (*.exe);;All Files (*)" if os.name == 'nt' else "All Files (*)"
        )
        if file_path:
            self.siril_cli_path.setText(file_path)

    def browse_auth_file(self):
        """Open file dialog for cloud authentication file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Authentication File",
            self.auth_file_path.text() or os.path.expanduser("~"),
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.auth_file_path.setText(file_path)

    def get_cloud_config(self):
        """Get cloud configuration in format expected by astrofiler_cloud module"""
        return {
            'vendor': self.cloud_vendor.currentText(),
            'bucket_url': self.bucket_url.text().strip(),
            'sync_profile': self.sync_profile.currentData(),
            'auth_info': {
                'auth_string': self.auth_file_path.text().strip()
            } if self.auth_file_path.text().strip() else {}
        }
    
    def on_theme_changed(self, theme_name):
        """Handle theme changes"""
        from .main_window import get_dark_stylesheet, get_light_stylesheet, detect_system_theme
        
        app = QApplication.instance()
        if theme_name == "Dark":
            app.setStyleSheet(get_dark_stylesheet())
        elif theme_name == "Light":
            app.setStyleSheet(get_light_stylesheet())
        elif theme_name == "Auto":
            # Use system theme detection
            if detect_system_theme():
                app.setStyleSheet(get_dark_stylesheet())
            else:
                app.setStyleSheet(get_light_stylesheet())
