import sys
import os
import shutil
import configparser
import datetime
from datetime import datetime

import logging
logger = logging.getLogger(__name__)

# Import necessary PySide6 modules
from PySide6.QtCore import Qt, QUrl, Q_ARG, QThread, Signal
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton, QVBoxLayout, 
                               QHBoxLayout, QWidget, QTabWidget, QListWidget, 
                               QTextEdit, QFormLayout, QLineEdit, QSpinBox, 
                               QCheckBox, QComboBox, QGroupBox, QFileDialog,
                               QSplitter, QTreeWidget, QTreeWidgetItem, QStackedLayout,
                               QMessageBox, QScrollArea,QMenu,QProgressDialog, QSizePolicy,
                               QDialog, QDialogButtonBox, QGridLayout)
from PySide6.QtGui import QPixmap, QFont, QTextCursor,QDesktopServices, QIcon
from astrofiler_file import fitsProcessing
from astrofiler_db import fitsFile as FitsFileModel, fitsSession as FitsSessionModel, Mapping as MappingModel
from astrofiler_smart import smart_telescope_manager

# Global version variable
VERSION = "1.1.0"

def load_stylesheet(filename):
    """Load stylesheet from a file"""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            logger.debug(f"Successfully loaded stylesheet: {filename}")
            return file.read()
    except FileNotFoundError:
        logger.warning(f"Stylesheet file '{filename}' not found. Using fallback styles.")
        return ""
    except Exception as e:
        logger.error(f"Error loading stylesheet '{filename}': {e}")
        return ""

def get_dark_stylesheet():
    """Return a dark theme stylesheet for the application"""
    return load_stylesheet("css/dark.css")

def get_light_stylesheet():
    """Return a light theme stylesheet for the application"""
    return load_stylesheet("css/light.css")

def detect_system_theme():
    """Detect if the system is using dark theme"""
    try:
        if os.name == 'nt':  # Windows
            import winreg
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0  # 0 means dark theme, 1 means light theme
        else:
            # For other systems, default to light theme
            return False
    except:
        return False

class ImagesTab(QWidget):
    """
    Images tab for viewing and managing FITS files.
    
    Features:
    - Hierarchical view of FITS files
    - Sortable by Object (default) or Date
    - File loading and repository synchronization
    - Context menus and double-click actions
    """
    def __init__(self):
        super().__init__()
        self.init_ui()        # Load existing data on startup
        self.load_fits_data()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # File controls
        controls_layout = QHBoxLayout()
        self.load_repo_button = QPushButton("Load Repo")
        self.sync_repo_button = QPushButton("Sync Repo")
        self.download_repo_button = QPushButton("Download Repo")
        self.clear_button = QPushButton("Clear Repo")
        self.mapping_button = QPushButton("Mapping")
        self.refresh_button = QPushButton("Refresh")
        
        # Add sort control
        sort_label = QLabel("Sort by:")
        sort_label.setStyleSheet("font-weight: bold; margin-right: 5px;")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Object", "Date"])
        self.sort_combo.setCurrentText("Object")  # Set default to Object
        self.sort_combo.setToolTip("Choose how to organize the file tree:\n• Object: Group by astronomical object, then by date\n• Date: Group by observation date, then by object")
        self.sort_combo.setMinimumWidth(80)
        self.sort_combo.setStyleSheet("QComboBox { padding: 3px; }")
        
        controls_layout.addWidget(self.load_repo_button)
        controls_layout.addWidget(self.sync_repo_button)
        controls_layout.addWidget(self.download_repo_button)
        controls_layout.addWidget(self.clear_button)
        controls_layout.addWidget(self.mapping_button)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addStretch()
        controls_layout.addWidget(sort_label)
        controls_layout.addWidget(self.sort_combo)
          # File list
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Object", "Type", "Date", "Exposure", "Filter", "Telescope", "Instrument", "Temperature", "Filename"])
        
        # Set column widths for better display
        self.file_tree.setColumnWidth(0, 120)  # Object
        self.file_tree.setColumnWidth(1, 80)   # Type
        self.file_tree.setColumnWidth(2, 150)  # Date
        self.file_tree.setColumnWidth(3, 80)   # Exposure
        self.file_tree.setColumnWidth(4, 80)   # Filter
        self.file_tree.setColumnWidth(5, 120)  # Telescope
        self.file_tree.setColumnWidth(6, 120)  # Instrument
        self.file_tree.setColumnWidth(7, 100)  # Temperature
        self.file_tree.setColumnWidth(8, 200)  # Filename
        
        layout.addLayout(controls_layout)
        layout.addWidget(self.file_tree)
        
        # Connect signals
        self.load_repo_button.clicked.connect(self.load_repo)
        self.sync_repo_button.clicked.connect(self.sync_repo)
        self.download_repo_button.clicked.connect(self.show_download_dialog)
        self.clear_button.clicked.connect(self.clear_files)
        self.mapping_button.clicked.connect(self.open_mappings_dialog)
        self.refresh_button.clicked.connect(self.load_fits_data)
        self.sort_combo.currentTextChanged.connect(self.load_fits_data)  # Reload data when sort changes
        self.file_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
    
    def load_repo(self):
        """Load the repository by running registerFitsImages with progress dialog."""
        from PySide6.QtWidgets import QProgressDialog, QMessageBox
        from PySide6.QtCore import Qt
        import time
        
        # Show warning dialog first
        warning_msg = ("This function creates folders, renames files, and moves them into the folder structure.\n\n"
                      "This operation will:\n"
                      "• Scan your source directory for FITS files\n"
                      "• Create an organized folder structure\n"
                      "• Move and rename files according to their metadata\n\n"
                      "Do you want to continue?")
        
        reply = QMessageBox.question(
            self,
            "Load Repository Warning",
            warning_msg,
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel  # Default to Cancel for safety
        )
        
        if reply != QMessageBox.Ok:
            return  # User cancelled, exit the function
        
        progress_dialog = None
        was_cancelled = False
        
        try:
            # Create progress dialog first
            progress_dialog = QProgressDialog("Scanning for FITS files...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Loading Repository")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.setValue(0)  # Set initial value
            progress_dialog.show()
            QApplication.processEvents()  # Process events to show dialog
            
            # Small delay to ensure dialog is visible
            time.sleep(0.1)
            
            self.fits_file_handler = fitsProcessing()
            
            def update_progress(current, total, filename):
                """Progress callback function"""
                nonlocal was_cancelled
                try:
                    logging.debug(f"Progress callback called: {current}/{total} - {filename}")
                    
                    # Don't check cancellation if already cancelled
                    if was_cancelled:
                        logging.debug("Already cancelled, returning False")
                        return False
                    
                    # Check if dialog was cancelled before updating
                    if progress_dialog and progress_dialog.wasCanceled():
                        logging.debug("User cancelled the operation")
                        was_cancelled = True
                        return False  # Signal to stop processing
                    
                    if progress_dialog:
                        progress = int((current / total) * 100) if total > 0 else 0
                        progress_dialog.setValue(progress)
                        progress_dialog.setLabelText(f"Processing {current}/{total}: {os.path.basename(filename)}")
                        QApplication.processEvents()  # Keep UI responsive
                        
                        # Check again after processing events
                        if progress_dialog.wasCanceled():
                            logging.debug("User cancelled the operation during update")
                            was_cancelled = True
                            return False
                    
                    logging.debug(f"Progress callback returning True for {filename}")
                    return True  # Continue processing
                except Exception as e:
                    logging.error(f"Error in progress callback: {e}")
                    return True  # Continue on callback errors
            
            # Run the processing with progress callback
            logging.debug("Starting registerFitsImages with progress callback")
            registered_files = self.fits_file_handler.registerFitsImages(moveFiles=True, progress_callback=update_progress)
            logging.debug(f"registerFitsImages completed, registered {len(registered_files)} files")
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled or completed normally
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Repository loading was cancelled by user.")
                logging.debug("Operation was cancelled by user")
            elif len(registered_files) == 0:
                QMessageBox.information(self, "No Files", "No FITS files found to process in the source directory.")
                logging.info("No FITS files found to process")
            else:
                self.load_fits_data()
                
                # Invalidate stats cache since new data was loaded
                parent_widget = self.parent()
                while parent_widget and not hasattr(parent_widget, 'invalidate_stats_cache'):
                    parent_widget = parent_widget.parent()
                if parent_widget:
                    parent_widget.invalidate_stats_cache()
                
                QMessageBox.information(self, "Success", f"Repository loaded successfully! Processed {len(registered_files)} files.")
                logging.info("Operation completed successfully")
                
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error loading repository: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load repository: {e}")

    def sync_repo(self):
        """Sync the repository by running registerFitsImages with moveFiles=False and progress dialog."""
        from PySide6.QtWidgets import QProgressDialog, QMessageBox
        from PySide6.QtCore import Qt
        
        # Show warning dialog first
        warning_msg = ("Sync Repo reloads the repository database with data from files in the specified Repository directory and does not change any data.\n\n"
                      "If you want to move files from Incoming to the Repository use Load Repo.\n\n"
                      "Do you want to continue with synchronization?")
        
        reply = QMessageBox.question(
            self,
            "Sync Repository Information",
            warning_msg,
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok  # Default to OK since this is informational
        )
        
        if reply != QMessageBox.Ok:
            return  # User cancelled, exit the function
        
        progress_dialog = None
        was_cancelled = False
        
        try:
            self.fits_file_handler = fitsProcessing()
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Synchronizing Repository")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.show()
            
            def update_progress(current, total, filename):
                """Progress callback function"""
                nonlocal was_cancelled
                
                # Don't check cancellation if already cancelled
                if was_cancelled:
                    return False
                
                # Check if dialog was cancelled before updating
                if progress_dialog and progress_dialog.wasCanceled():
                    was_cancelled = True
                    return False  # Signal to stop processing
                
                progress = int((current / total) * 100) if total > 0 else 0
                progress_dialog.setValue(progress)
                progress_dialog.setLabelText(f"Syncing {current}/{total}: {os.path.basename(filename)}")
                QApplication.processEvents()  # Keep UI responsive
                
                # Check again after processing events
                if progress_dialog and progress_dialog.wasCanceled():
                    was_cancelled = True
                    return False
                
                return True  # Continue processing
            
            # Run the processing with progress callback
            registered_files = self.fits_file_handler.registerFitsImages(moveFiles=False, progress_callback=update_progress)
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled or completed normally
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Repository synchronization was cancelled by user.")
                logger.info("Repository synchronization was cancelled by user")
            else:
                self.load_fits_data()
                
                # Invalidate stats cache since new data was synced
                parent_widget = self.parent()
                while parent_widget and not hasattr(parent_widget, 'invalidate_stats_cache'):
                    parent_widget = parent_widget.parent()
                if parent_widget:
                    parent_widget.invalidate_stats_cache()
                
                QMessageBox.information(self, "Success", f"Repository synchronized successfully! Processed {len(registered_files)} files.")
                logger.info("Repository synchronization completed successfully")
                
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error syncing repository: {e}")
            QMessageBox.warning(self, "Error", f"Failed to sync repository: {e}")

    def load_fits_data(self):
        """Load FITS file data from the database and populate the tree widget based on selected sort criteria."""
        try:
            self.file_tree.clear()

            # Get the current sort criteria (default to Object if UI not yet initialized)
            sort_by = getattr(self, 'sort_combo', None)
            if sort_by is not None:
                sort_by = self.sort_combo.currentText()
            else:
                sort_by = "Object"  # Default when UI isn't ready yet
            
            if sort_by == "Object":
                self._load_fits_data_by_object()
            else:  # Date
                self._load_fits_data_by_date()
            
            logger.debug(f"FITS data loaded and organized by {sort_by}")
                
        except Exception as e:
            logger.error(f"Error loading FITS data: {e}")
            if "no such table" not in str(e).lower():
                QMessageBox.warning(self, "Error", f"Failed to load FITS data: {e}")

    def _load_fits_data_by_object(self):
        """Load FITS file data grouped by object name, then by date."""
        # Query all FITS files from the database where fitsFileType contains "Light"
        fits_files = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains("Light")).order_by(FitsFileModel.fitsFileObject, FitsFileModel.fitsFileDate)

        # Group files by object name and date
        objects_dict = {}
        for fits_file in fits_files:
            object_name = fits_file.fitsFileObject or "Unknown"
            date_str = str(fits_file.fitsFileDate)[:10] if fits_file.fitsFileDate else "Unknown Date"

            if object_name not in objects_dict:
                objects_dict[object_name] = {}
            if date_str not in objects_dict[object_name]:
                objects_dict[object_name][date_str] = []

            objects_dict[object_name][date_str].append(fits_file)

        # Create parent items for each object (sorted alphabetically)
        for object_name in sorted(objects_dict.keys()):
            dates_dict = objects_dict[object_name]
            # Create parent item for the object
            parent_item = QTreeWidgetItem()
            parent_item.setText(0, object_name)  # Object name in first column
            parent_item.setText(1, f"({sum(len(files) for files in dates_dict.values())} files)")  # File count in Type column
            parent_item.setText(2, "")  # Empty other columns for parent
            parent_item.setText(3, "")
            parent_item.setText(4, "")
            parent_item.setText(5, "")
            parent_item.setText(6, "")
            parent_item.setText(7, "")
            parent_item.setText(8, "")

            # Make parent item bold and slightly different color
            font = parent_item.font(0)
            font.setBold(True)
            for col in range(9):
                parent_item.setFont(col, font)

            # Add sub-parent items for each date (sorted by date)
            for date_str in sorted(dates_dict.keys(), reverse=True):  # Most recent dates first
                files = dates_dict[date_str]
                date_item = QTreeWidgetItem()
                date_item.setText(0, date_str)  # Date in first column
                date_item.setText(1, f"({len(files)} files)")  # File count in Type column
                date_item.setText(2, "")  # Empty other columns for date
                date_item.setText(3, "")
                date_item.setText(4, "")
                date_item.setText(5, "")
                date_item.setText(6, "")
                date_item.setText(7, "")
                date_item.setText(8, "")

                # Add child items for each file
                for fits_file in files:
                    self._add_file_item(date_item, fits_file)

                # Add date item to parent
                parent_item.addChild(date_item)

                # Keep the date item collapsed by default
                date_item.setExpanded(False)

            # Add parent item to tree
            self.file_tree.addTopLevelItem(parent_item)

            # Keep the parent item collapsed by default
            parent_item.setExpanded(False)

        total_files = len(fits_files)
        total_objects = len(objects_dict)
        if total_files > 0:
            logger.debug(f"Loaded {total_files} FITS files from {total_objects} objects into the display (sorted by object)")
        else:
            logger.info("No FITS files found in database")

    def _load_fits_data_by_date(self):
        """Load FITS file data grouped by date, then by object."""
        # Query all FITS files from the database where fitsFileType contains "Light"
        fits_files = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains("Light")).order_by(FitsFileModel.fitsFileDate.desc(), FitsFileModel.fitsFileObject)

        # Group files by date and object
        dates_dict = {}
        for fits_file in fits_files:
            object_name = fits_file.fitsFileObject or "Unknown"
            date_str = str(fits_file.fitsFileDate)[:10] if fits_file.fitsFileDate else "Unknown Date"

            if date_str not in dates_dict:
                dates_dict[date_str] = {}
            if object_name not in dates_dict[date_str]:
                dates_dict[date_str][object_name] = []

            dates_dict[date_str][object_name].append(fits_file)

        # Create parent items for each date (sorted by date, newest first)
        for date_str in sorted(dates_dict.keys(), reverse=True):
            objects_dict = dates_dict[date_str]
            # Create parent item for the date
            parent_item = QTreeWidgetItem()
            parent_item.setText(0, date_str)  # Date in first column
            parent_item.setText(1, f"({sum(len(files) for files in objects_dict.values())} files)")  # File count in Type column
            parent_item.setText(2, "")  # Empty other columns for parent
            parent_item.setText(3, "")
            parent_item.setText(4, "")
            parent_item.setText(5, "")
            parent_item.setText(6, "")
            parent_item.setText(7, "")
            parent_item.setText(8, "")

            # Make parent item bold and slightly different color
            font = parent_item.font(0)
            font.setBold(True)
            for col in range(9):
                parent_item.setFont(col, font)

            # Add sub-parent items for each object (sorted alphabetically)
            for object_name in sorted(objects_dict.keys()):
                files = objects_dict[object_name]
                object_item = QTreeWidgetItem()
                object_item.setText(0, object_name)  # Object name in first column
                object_item.setText(1, f"({len(files)} files)")  # File count in Type column
                object_item.setText(2, "")  # Empty other columns for object
                object_item.setText(3, "")
                object_item.setText(4, "")
                object_item.setText(5, "")
                object_item.setText(6, "")
                object_item.setText(7, "")
                object_item.setText(8, "")

                # Add child items for each file
                for fits_file in files:
                    self._add_file_item(object_item, fits_file)

                # Add object item to parent
                parent_item.addChild(object_item)

                # Keep the object item collapsed by default
                object_item.setExpanded(False)

            # Add parent item to tree
            self.file_tree.addTopLevelItem(parent_item)

            # Keep the parent item collapsed by default
            parent_item.setExpanded(False)

        total_files = len(fits_files)
        total_dates = len(dates_dict)
        if total_files > 0:
            logger.debug(f"Loaded {total_files} FITS files from {total_dates} dates into the display (sorted by date)")
        else:
            logger.debug("No FITS files found in database")

    def _add_file_item(self, parent_item, fits_file):
        """Helper method to add a file item to a parent tree widget item."""
        child_item = QTreeWidgetItem()

        # Populate the child item with database fields
        child_item.setText(0, "")  # Empty object column for child (parent shows object/date)
        child_item.setText(1, fits_file.fitsFileType or "N/A")    # Type

        # Format date to be more readable
        date_str = str(fits_file.fitsFileDate) if fits_file.fitsFileDate else "N/A"
        if date_str != "N/A" and "T" in date_str:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass  # Keep original format if parsing fails
        child_item.setText(2, date_str)  # Date

        # Format exposure time
        exp_time = fits_file.fitsFileExpTime or ""
        if exp_time:
            child_item.setText(3, f"{exp_time}s")  # Exposure
        else:
            child_item.setText(3, "N/A")

        child_item.setText(4, fits_file.fitsFileFilter or "N/A")  # Filter
        child_item.setText(5, fits_file.fitsFileTelescop or "N/A")  # Telescope
        child_item.setText(6, fits_file.fitsFileInstrument or "N/A")  # Instrument

        # Format temperature
        temp = fits_file.fitsFileCCDTemp or ""
        if temp:
            child_item.setText(7, f"{temp}°C")  # Temperature
        else:
            child_item.setText(7, "N/A")

        # Extract just the filename from the full path for display
        filename = fits_file.fitsFileName or ""
        if filename:
            filename = os.path.basename(filename)
            child_item.setText(8, filename)  # Filename
        else:
            child_item.setText(8, "N/A")

        # Store the full database record for potential future use
        child_item.setData(0, Qt.UserRole, fits_file.fitsFileId)

        # Add child to parent item
        parent_item.addChild(child_item)

    def clear_files(self):
        """Clear the file tree and delete all fitsSession and fitsFile records from the database."""
        try:
            # Clear the tree widget
            self.file_tree.clear()
            
            # Delete all fitsSession records from the database
            deleted_sessions = FitsSessionModel.delete().execute()
            
            # Delete all fitsFile records from the database
            deleted_files = FitsFileModel.delete().execute()
            
            # Invalidate stats cache since all data was cleared
            parent_widget = self.parent()
            while parent_widget and not hasattr(parent_widget, 'invalidate_stats_cache'):
                parent_widget = parent_widget.parent()
            if parent_widget:
                parent_widget.invalidate_stats_cache()
            
            logger.info(f"Deleted {deleted_sessions} session records and {deleted_files} file records from database")
            QMessageBox.information(self, "Success", f"Repository cleared! Deleted {deleted_sessions} session records and {deleted_files} file records from database.")
            
        except Exception as e:
            logger.error(f"Error clearing repository: {e}")
            QMessageBox.warning(self, "Error", f"Failed to clear repository: {e}")

    def on_item_double_clicked(self, item, column):
        """Handle double-click on tree widget items"""
        # Check if the item has a stored file ID (indicating it's a FITS file, not a parent/date item)
        file_id = item.data(0, Qt.UserRole)
        if file_id is not None:
            try:
                # Get the FITS file record from the database
                fits_file = FitsFileModel.get_by_id(file_id)
                if fits_file and fits_file.fitsFileName:
                    logger.info(f"Launching external viewer for file: {fits_file.fitsFileName}")
                    self.launch_external_viewer(fits_file.fitsFileName)
                else:
                    QMessageBox.warning(self, "File Not Found", "The FITS file path is not available.")
            except Exception as e:
                logger.error(f"Error retrieving FITS file: {e}")
                QMessageBox.warning(self, "Error", f"Failed to retrieve file information: {e}")
    
    def launch_external_viewer(self, file_path):
        """Launch external FITS viewer with the specified file"""
        # Get the main GUI instance to access config settings
        main_window = self.window()
        if hasattr(main_window, 'config_tab') and hasattr(main_window.config_tab, 'fits_viewer_path'):
            viewer_path = main_window.config_tab.fits_viewer_path.text().strip()
            
            if not viewer_path:
                QMessageBox.warning(self, "No Viewer Configured", 
                                  "Please configure an external FITS viewer in the Config tab.")
                return
            logger.info(f"Launching external FITS viewer: {viewer_path} with file {file_path}")            
            try:
                import subprocess
                import shlex
                
                # Check if viewer_path contains spaces or multiple arguments
                if ' ' in viewer_path:
                    # Parse command with arguments using shlex for proper shell-like parsing
                    # This handles quoted arguments, escaping, etc.
                    try:
                        cmd_parts = shlex.split(viewer_path)
                        cmd_args = cmd_parts + [file_path]
                    except ValueError as e:
                        # If shlex parsing fails (malformed quotes, etc.), fall back to simple split
                        logger.warning(f"shlex parsing failed for '{viewer_path}', using simple split: {e}")
                        cmd_parts = viewer_path.split()
                        cmd_args = cmd_parts + [file_path]
                else:
                    # Single executable path with no arguments
                    cmd_args = [viewer_path, file_path]
                
                # Launch the external viewer with the file path as argument
                subprocess.Popen(cmd_args)
                logger.info(f"Launched external FITS viewer: {cmd_args}")
            except Exception as e:
                logger.error(f"Error launching external viewer: {e}")
                QMessageBox.warning(self, "Launch Error", 
                                  f"Failed to launch external viewer: {str(e)}")
        else:
            QMessageBox.warning(self, "Configuration Error", 
                              "Unable to access FITS viewer configuration.")
    
    def show_download_dialog(self):
        """Show the download dialog for smart telescopes."""
        try:
            dialog = SmartTelescopeDownloadDialog(self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening download dialog: {e}")
            QMessageBox.critical(self, "Error", f"Error opening download dialog: {e}")
    
    def open_mappings_dialog(self):
        """Open the mappings dialog"""
        try:
            dialog = MappingsDialog(self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening mappings dialog: {e}")
            QMessageBox.critical(self, "Error", f"Error opening mappings dialog: {e}")



class TelescopeDownloadWorker(QThread):
    """Worker thread for downloading files from smart telescopes."""
    
    # Signals for thread-safe communication
    progress_updated = Signal(str)
    progress_percent_updated = Signal(int)  # New signal for progress percentage
    download_completed = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, telescope_type, hostname, network, delete_files=False):
        super().__init__()
        self.telescope_type = telescope_type
        self.hostname = hostname
        self.network = network
        self.delete_files = delete_files
        self._stop_requested = False
    
    def _modify_fits_headers(self, fits_path, folder_name):
        """Modify FITS headers based on folder name."""
        try:
            from astropy.io import fits
            
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
        import tempfile
        
        try:
            # Step 1: Find the telescope (10% of progress)
            if self._stop_requested:
                return
            
            self.progress_updated.emit("Scanning network for SEESTAR telescope...")
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
                return
            
            self.progress_updated.emit(f"Connected to SEESTAR at {ip}")
            self.progress_percent_updated.emit(10)
            
            # Step 2: Connect and get FITS files (20% of progress)
            if self._stop_requested:
                return
            
            self.progress_updated.emit("Scanning SEESTAR for FITS files...")
            self.progress_percent_updated.emit(15)
            
            fits_files, error = smart_telescope_manager.get_fits_files(self.telescope_type, ip)
            
            if self._stop_requested:
                return
            
            if error:
                self.error_occurred.emit(f"Failed to get FITS files: {error}")
                return
            
            if not fits_files:
                self.download_completed.emit("No FITS files found on telescope.")
                return
            
            self.progress_updated.emit(f"Found {len(fits_files)} FITS files to download")
            self.progress_percent_updated.emit(20)
            
            # Step 3: Create temp directory
            if self._stop_requested:
                return
            
            temp_dir = tempfile.mkdtemp(prefix="astrofiler_download_")
            
            # Step 4: Download and process each file (20-100% of progress)
            successful_downloads = 0
            failed_downloads = 0
            processed_files = 0
            
            fits_processor = fitsProcessing()
            
            for i, file_info in enumerate(fits_files):
                if self._stop_requested:
                    logger.debug("Stop requested - breaking out of download loop")
                    break
                
                file_name = file_info['name']
                file_size = smart_telescope_manager.format_file_size(file_info['size'])
                
                # Calculate progress: 20% base + 80% for files (each file gets equal share)
                base_progress = 20
                file_progress_range = 80
                current_file_start = base_progress + (i * file_progress_range // len(fits_files))
                next_file_start = base_progress + ((i + 1) * file_progress_range // len(fits_files))
                
                self.progress_updated.emit(f"Downloading {file_name} ({file_size}) - {i+1} of {len(fits_files)}")
                self.progress_percent_updated.emit(current_file_start)
                
                # Download file to temp directory
                local_path = os.path.join(temp_dir, file_name)
                
                def download_progress_callback(progress):
                    if self._stop_requested:
                        return False  # Signal to stop the download
                    # Update progress within this file's range
                    file_percent = current_file_start + int((progress / 100) * (next_file_start - current_file_start) * 0.8)
                    self.progress_percent_updated.emit(file_percent)
                    self.progress_updated.emit(f"Downloading {file_name}: {progress:.1f}%")
                    return True  # Continue downloading
                
                success, error = smart_telescope_manager.download_file(
                    self.telescope_type, ip, file_info, local_path,
                    progress_callback=download_progress_callback
                )
                
                if self._stop_requested:
                    break
                
                if not success:
                    if "cancelled by user" in str(error).lower():
                        # Download was cancelled, break out of loop
                        self.progress_updated.emit("Download cancelled by user")
                        break
                    else:
                        self.progress_updated.emit(f"Failed to download {file_name}: {error}")
                        failed_downloads += 1
                        continue
                
                successful_downloads += 1
                
                # Check for cancellation immediately after download
                if self._stop_requested:
                    self.progress_updated.emit("Download cancelled")
                    break
                
                # Processing phase (remaining 20% of this file's progress range)
                processing_progress = current_file_start + int((next_file_start - current_file_start) * 0.8)
                self.progress_updated.emit(f"Processing {file_name}...")
                self.progress_percent_updated.emit(processing_progress)
                
                # Process the file with registerFitsImage
                try:
                    if self._stop_requested:
                        self.progress_updated.emit("Download cancelled")
                        break
                    
                    # Modify FITS headers before processing
                    self._modify_fits_headers(local_path, file_info.get('folder_name', ''))
                    
                    if self._stop_requested:
                        self.progress_updated.emit("Download cancelled")
                        break
                    
                    # Process file (this might take time, but we can't easily interrupt it)
                    self.progress_updated.emit(f"Adding {file_name} to repository...")
                    result = fits_processor.registerFitsImage(
                        os.path.dirname(local_path), 
                        file_name, 
                        moveFiles=True
                    )
                    
                    if self._stop_requested:
                        self.progress_updated.emit("Download cancelled")
                        break
                    
                    if result:
                        processed_files += 1
                        self.progress_updated.emit(f"Successfully processed {file_name}")
                        
                        # Delete file from host if requested
                        if self.delete_files:
                            if self._stop_requested:
                                self.progress_updated.emit("Download cancelled")
                                break
                            
                            self.progress_updated.emit(f"Deleting {file_name} from telescope...")
                            delete_success, delete_error = smart_telescope_manager.delete_file(
                                self.telescope_type, ip, file_info
                            )
                            
                            if delete_success:
                                self.progress_updated.emit(f"Successfully deleted {file_name} from telescope")
                            else:
                                self.progress_updated.emit(f"Warning: Failed to delete {file_name} from telescope: {delete_error}")
                    else:
                        self.progress_updated.emit(f"Failed to process {file_name} (file may be invalid)")
                        
                except Exception as e:
                    if self._stop_requested:
                        self.progress_updated.emit("Download cancelled")
                        break
                    self.progress_updated.emit(f"Error processing {file_name}: {str(e)}")
                
                # Update progress to next file start
                self.progress_percent_updated.emit(next_file_start)
                
                # Clean up downloaded file (since moveFiles=True should have moved it)
                try:
                    if os.path.exists(local_path):
                        os.remove(local_path)
                except:
                    pass
            
            # Final completion
            if self._stop_requested:
                self.progress_updated.emit("Download cancelled")
                return
            
            self.progress_updated.emit("Download complete!")
            self.progress_percent_updated.emit(100)
            
            # Step 5: Clean up temp directory
            try:
                os.rmdir(temp_dir)
            except:
                pass
            
            # Step 6: Show final status
            if not self._stop_requested:
                message = (f"Download complete!\n\n"
                          f"Files found: {len(fits_files)}\n"
                          f"Successfully downloaded: {successful_downloads}\n"
                          f"Failed downloads: {failed_downloads}\n"
                          f"Successfully processed: {processed_files}\n\n"
                          f"Files have been moved to your repository and registered in the database.")
                
                self.download_completed.emit(message)
            
        except Exception as e:
            if not self._stop_requested:
                self.error_occurred.emit(f"Unexpected error during download: {str(e)}")


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
        self.telescope_list.setCurrentRow(0)  # Select first item by default
        self.telescope_list.setMaximumHeight(80)
        
        telescope_layout.addRow("Telescope Type:", self.telescope_list)
        
        # Connection settings
        connection_group = QGroupBox("Connection Settings")
        connection_layout = QFormLayout(connection_group)
        
        self.hostname_edit = QLineEdit("SEESTAR.local")
        self.hostname_edit.setToolTip("Hostname or IP address of the telescope")
        
        self.network_edit = QLineEdit()
        # Set default network
        default_network = smart_telescope_manager.get_local_network()
        self.network_edit.setText(default_network)
        self.network_edit.setToolTip("Network range to scan (e.g., 10.0.0.0/24)")
        
        connection_layout.addRow("Hostname:", self.hostname_edit)
        connection_layout.addRow("Network:", self.network_edit)
        
        # Delete files option
        self.delete_files_checkbox = QCheckBox("Delete files on host after download")
        self.delete_files_checkbox.setChecked(False)  # Default to False
        self.delete_files_checkbox.setToolTip("WARNING: This will permanently delete files from the telescope after successful download")
        connection_layout.addRow("", self.delete_files_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.download_button = QPushButton("Download")
        self.cancel_button = QPushButton("Cancel")
        
        button_layout.addStretch()
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)
        
        # Add to main layout
        layout.addWidget(telescope_group)
        layout.addWidget(connection_group)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        # Connect signals
        self.telescope_list.currentTextChanged.connect(self.on_telescope_changed)
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button.clicked.connect(self.reject)
        
        # Update initial state
        self.on_telescope_changed()
    
    def closeEvent(self, event):
        """Handle dialog close event to ensure worker thread is stopped."""
        if hasattr(self, 'worker') and self.worker.isRunning():
            # Stop the worker thread before closing
            self.worker.stop()
            if not self.worker.wait(3000):  # Wait up to 3 seconds
                self.worker.terminate()
                self.worker.wait(1000)
        
        # Close progress dialog if it exists
        self.close_progress_dialog()
        
        # Accept the close event
        event.accept()
    
    def reject(self):
        """Handle dialog rejection (ESC key, X button, etc.)."""
        if hasattr(self, 'worker') and self.worker.isRunning():
            # Stop the worker thread before rejecting
            self.worker.stop()
            if not self.worker.wait(3000):  # Wait up to 3 seconds
                self.worker.terminate()
                self.worker.wait(1000)
        
        # Close progress dialog if it exists
        self.close_progress_dialog()
        
        # Call parent reject
        super().reject()
    
    def on_telescope_changed(self):
        """Handle telescope selection change."""
        current_telescope = self.telescope_list.currentItem()
        if current_telescope:
            telescope_type = current_telescope.text()
            if telescope_type == "SeeStar":
                self.hostname_edit.setText("SEESTAR.local")
    
    def start_download(self):
        """Start the download process."""
        current_telescope = self.telescope_list.currentItem()
        if not current_telescope:
            QMessageBox.warning(self, "Warning", "Please select a telescope type.")
            return
        
        telescope_type = current_telescope.text()
        hostname = self.hostname_edit.text().strip()
        network = self.network_edit.text().strip()
        delete_files = self.delete_files_checkbox.isChecked()
        
        if not network:
            QMessageBox.warning(self, "Warning", "Please enter a network range.")
            return
        
        # Confirmation dialog for file deletion
        if delete_files:
            reply = QMessageBox.question(
                self, 
                "Confirm File Deletion",
                "WARNING: You have selected to delete files from the telescope after download.\n\n"
                "This will PERMANENTLY DELETE the original files from the telescope's storage "
                "after they are successfully downloaded and processed.\n\n"
                "Are you sure you want to proceed?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
        
        # Don't hide the main dialog yet - keep it alive for signal handling
        # self.hide()  # Comment this out for now
        
        # Create and show progress dialog with proper parent
        self.progress_dialog = QProgressDialog("Connecting to SEESTAR...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Downloading from Smart Telescope")
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)  # Changed to ApplicationModal
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.setAutoClose(False)  # Prevent auto-close
        self.progress_dialog.setAutoReset(False)  # Prevent auto-reset
        
        # Center the progress dialog
        if self.parent():
            parent_center = self.parent().geometry().center()
            dialog_size = self.progress_dialog.sizeHint()
            self.progress_dialog.move(
                parent_center.x() - dialog_size.width() // 2,
                parent_center.y() - dialog_size.height() // 2
            )
        
        self.progress_dialog.show()
        
        # Create and start worker thread with delete_files parameter
        self.worker = TelescopeDownloadWorker(telescope_type, hostname, network, delete_files)
        
        # Connect signals
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.progress_percent_updated.connect(self.on_progress_percent_updated)
        self.worker.download_completed.connect(self.on_download_completed)
        self.worker.error_occurred.connect(self.on_error_occurred)
        self.worker.finished.connect(self.on_worker_finished)
        
        # Connect cancel button
        self.progress_dialog.canceled.connect(self.on_cancel_download)
        
        # Start the worker
        self.worker.start()
    
    def on_progress_updated(self, message):
        """Update progress dialog with new message."""
        logger.debug(f"Progress update: {message}")
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setLabelText(message)
            # Force update
            self.progress_dialog.repaint()
    
    def on_progress_percent_updated(self, percent):
        """Update progress dialog with percentage."""
        logger.debug(f"Progress percent: {percent}%")
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setValue(percent)
            # Force update
            self.progress_dialog.repaint()
    
    def on_download_completed(self, message):
        """Handle successful download completion."""
        logger.info("Download completed successfully")
        self.close_progress_dialog()
        self.accept()  # Close the main dialog now
        QMessageBox.information(self.parent(), "Download Complete", message)
    
    def on_error_occurred(self, error_message):
        """Handle download error."""
        logger.error(f"Download error occurred: {error_message}")
        self.close_progress_dialog()
        self.show()  # Show the main dialog again for retry
        QMessageBox.critical(self, "Download Error", error_message)
    
    def on_worker_finished(self):
        """Handle worker thread completion."""
        logger.debug("Worker thread finished")
        if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
            self.close_progress_dialog()
    
    def on_cancel_download(self):
        """Handle download cancellation."""
        logger.debug("Cancel button clicked!")
        
        if hasattr(self, 'worker') and self.worker.isRunning():
            logger.debug("Stopping worker thread...")
            self.progress_dialog.setLabelText("Cancelling download...")
            self.progress_dialog.setValue(0)
            
            # Request graceful stop
            self.worker.stop()
            
            # Give worker time to stop gracefully
            if not self.worker.wait(3000):  # Wait up to 3 seconds
                logger.debug("Force terminating worker thread")
                self.progress_dialog.setLabelText("Forcing cancellation...")
                self.worker.terminate()  # Force termination if needed
                self.worker.wait(2000)   # Wait up to 2 more seconds
            
            # Ensure worker is fully stopped before proceeding
            if self.worker.isRunning():
                logger.debug("Final termination of worker thread")
                self.worker.terminate()
                self.worker.wait()
        
        logger.debug("Closing progress dialog...")
        self.close_progress_dialog()
        self.show()  # Show the main dialog again
    
    def close_progress_dialog(self):
        """Close the progress dialog safely."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
            self.progress_dialog.close()
            self.progress_dialog = None


class SessionsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        # Load existing data on startup
        self.load_sessions_data()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.regenerate_button = QPushButton("Regenerate")
        self.regenerate_button.setToolTip("Clear all sessions and regenerate: Update Lights → Update Calibrations → Link Sessions")
        
        controls_layout.addWidget(self.regenerate_button)
        controls_layout.addStretch()
        
        # Sessions list
        self.sessions_tree = QTreeWidget()
        self.sessions_tree.setHeaderLabels(["Object Name", "Date", "Telescope", "Imager"])
        
        # Set column widths for better display
        self.sessions_tree.setColumnWidth(0, 200)  # Object Name
        self.sessions_tree.setColumnWidth(1, 150)  # Date
        self.sessions_tree.setColumnWidth(2, 150)  # Telescope
        self.sessions_tree.setColumnWidth(3, 150)  # Imager
        
        # Enable context menu
        self.sessions_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sessions_tree.customContextMenuRequested.connect(self.show_context_menu)

        layout.addLayout(controls_layout)
        layout.addWidget(self.sessions_tree)
        
        # Connect signals
        self.regenerate_button.clicked.connect(self.regenerate_sessions)
    
    def show_context_menu(self, position):
        """Show context menu for session items"""
        item = self.sessions_tree.itemAt(position)
        if not item:
            return
            
        # Determine if this is a session item (child of an object)
        parent = item.parent()
        if not parent:
            return  # This is a parent item (object name), not a session
            
        # Create context menu
        context_menu = QMenu(self)
        checkout_action = context_menu.addAction("Check out")
        # don't really need delete action but maybe later
        #delete_action = context_menu.addAction("Delete Session")

        # Show the menu and get the selected action
        action = context_menu.exec_(self.sessions_tree.viewport().mapToGlobal(position))
        
        if action == checkout_action:
            logging.info(f"Checking out session: {item.text(0)} on {item.text(1)}")
            self.checkout_session(item)
        #elif action == delete_action:
        #    logging.info(f"Deleting session: {item.text(0)} on {item.text(1)}")
        #    self.delete_session(item)

    def checkout_session(self, item):
        """Create symbolic links for session files in a Siril-friendly format"""
        try:
            # Get session information from the tree item
            session_date = item.text(1)
            object_name = item.parent().text(0)
            
            # Get the session from database
            session = FitsSessionModel.select().where(
                (FitsSessionModel.fitsSessionObjectName == object_name) & 
                (FitsSessionModel.fitsSessionDate == session_date)
            ).first()
            
            if not session:
                QMessageBox.warning(self, "Error", f"Session not found in database")
                return
            else:
                logging.info(f"Found session: {object_name} on {session_date}")
            # Get light files
            light_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsSessionId)

            # Get calibration files if this is a light session
            dark_files = []
            bias_files = []
            flat_files = []

            if object_name not in ['Bias', 'Dark', 'Flat']:
                # Get linked calibration files
                if session.fitsBiasSession:
                    bias_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsBiasSession)
                    logging.info(f"Found {bias_files.count()} bias files")

                if session.fitsDarkSession:
                    dark_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsDarkSession)
                    logging.info(f"Found {dark_files.count()} dark files")

                # Get all unique filters used in light frames
                filters = set([lf.fitsFileFilter for lf in light_files if lf.fitsFileFilter])
                logging.info(f"Filters used in light frames: {filters}")
                from astrofiler_db import fitsSession as FitsSessionModel, fitsFile as FitsFileModel
                for filter_name in filters:
                    # Find flat session(s) matching this filter and other session parameters
                    flat_sessions = FitsSessionModel.select().where(
                        (FitsSessionModel.fitsSessionObjectName == 'Flat') &
                        (FitsSessionModel.fitsSessionTelescope == session.fitsSessionTelescope) &
                        (FitsSessionModel.fitsSessionImager == session.fitsSessionImager) &
                        (FitsSessionModel.fitsSessionBinningX == session.fitsSessionBinningX) &
                        (FitsSessionModel.fitsSessionBinningY == session.fitsSessionBinningY) &
                        (FitsSessionModel.fitsSessionFilter == filter_name)
                    )
                    for flat_session in flat_sessions:
                        these_flats = FitsFileModel.select().where(FitsFileModel.fitsFileSession == flat_session.fitsSessionId)
                        flat_files.extend(list(these_flats))
                        logging.info(f"Found {these_flats.count()} flat files for filter {filter_name}")

            # Combine all files for progress tracking
            all_files = list(light_files) + list(dark_files) + list(bias_files) + list(flat_files)
            total_files = len(all_files)
            
            if total_files == 0:
                QMessageBox.information(self, "Information", "No files found for this session")
                return
            logging.info(f"Found {total_files} files for session {object_name} on {session_date}")

            # Ask user for destination directory
            dest_dir = QFileDialog.getExistingDirectory(
                self, 
                "Select Destination Directory",
                os.path.expanduser("~"),
                QFileDialog.ShowDirsOnly
            )
            
            if not dest_dir:
                return  # User cancelled
                    
            # Create destination directory structure
            session_dir = os.path.join(dest_dir, f"{object_name}_{session_date.replace(':', '-')}")
            light_dir = os.path.join(session_dir, "lights")
            dark_dir = os.path.join(session_dir, "darks")
            flat_dir = os.path.join(session_dir, "flats")
            bias_dir = os.path.join(session_dir, "bias")
            process_dir = os.path.join(session_dir, "process")
            
            # Create directories if they don't exist
            os.makedirs(light_dir, exist_ok=True)
            os.makedirs(dark_dir, exist_ok=True)
            os.makedirs(flat_dir, exist_ok=True)
            os.makedirs(bias_dir, exist_ok=True)
            os.makedirs(process_dir, exist_ok=True)
            logging.info(f"Created session directory structure at {session_dir}")  

            # Progress dialog
            progress = QProgressDialog("Creating symbolic links...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)

            # Create symbolic links for each file
            created_links = 0
            for i, file in enumerate(all_files):
                # Update progress
                progress.setValue(int(i * 100 / total_files))
                if progress.wasCanceled():
                    break
                    
                # Determine destination directory based on file type
                if "LIGHT" in file.fitsFileType.upper():
                    dest_folder = light_dir
                elif "DARK" in file.fitsFileType.upper():
                    dest_folder = dark_dir
                elif "FLAT" in file.fitsFileType.upper():
                    dest_folder = flat_dir
                elif "BIAS" in file.fitsFileType.upper():
                    dest_folder = bias_dir
                else:
                    logging.warning(f"Unknown file type for {file.fitsFileName}, skipping")
                    continue  # Skip unknown file types
                    
                # Extract filename from path
                logging.info(f"Processing file: {file.fitsFileName} of type {file.fitsFileType}")
                filename = os.path.basename(file.fitsFileName)
                
                # Create destination path
                dest_path = os.path.join(dest_folder, filename)
                
                # Create symbolic link based on platform
                try:
                    if os.path.exists(dest_path):
                        continue  # Skip if link already exists
                        
                    if sys.platform == "win32":
                        # Windows - use directory junction or symlink (requires admin privileges)
                        import subprocess
                        subprocess.run(["mklink", dest_path, file.fitsFileName], shell=True)
                    else:
                        # Mac/Linux - use symbolic link
                        os.symlink(file.fitsFileName, dest_path)
                    created_links += 1
                    logging.info(f"Created link for {file.fitsFileName} -> {dest_path}")
                except Exception as e:
                    logging.error(f"Error creating link for {file.fitsFileName}: {e}")
            
            # Close progress dialog
            progress.setValue(100)
            
            # Create a simple Siril script
            script_path = os.path.join(session_dir, "process.ssf")
            with open(script_path, "w") as f:
                f.write(f"# Siril processing script for {object_name} {session_date}\n")
                f.write("requires 1.0.0\n\n")
                f.write("# Convert to .fit files\n")
                f.write("cd lights\n")
                f.write("convert fits\n")
                f.write("cd ../darks\n")
                f.write("convert fits\n")
                f.write("cd ../flats\n")
                f.write("convert fits\n")
                f.write("cd ../bias\n")
                f.write("convert fits\n")
                f.write("cd ..\n\n")
                f.write("# Stack calibration frames\n")
                f.write("stack darks rej 3 3 -nonorm\n")
                f.write("stack bias rej 3 3 -nonorm\n")
                f.write("stack flats rej 3 3 -norm=mul\n\n")
                f.write("# Calibrate light frames\n")
                f.write("calibrate lights bias=bias_stacked flat=flat_stacked dark=dark_stacked\n\n")
                f.write("# Register light frames\n")
                f.write("register pp_lights\n\n")
                f.write("# Stack registered light frames\n")
                f.write("stack r_pp_lights rej 3 3 -norm=addscale\n")
            
            # Display success message
            QMessageBox.information(
                self, 
                "Success", 
                f"Created {created_links} symbolic links and Siril script in {session_dir}"
            )
            
            # Open the directory
            QDesktopServices.openUrl(QUrl.fromLocalFile(session_dir))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create symbolic links: {str(e)}")
            logging.error(f"Error in checkout_session: {str(e)}")

    def update_sessions(self):
        """Update light sessions by running createLightSessions method with progress dialog."""
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        
        progress_dialog = None
        was_cancelled = False
        
        try:
            self.fits_file_handler = fitsProcessing()
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Creating Light Sessions")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.show()
            
            def update_progress(current, total, filename):
                """Progress callback function"""
                nonlocal was_cancelled
                try:
                    # Don't check cancellation if already cancelled
                    if was_cancelled:
                        logging.info("Already cancelled, returning False")
                        return False
                    
                    # Check if dialog was cancelled before updating
                    if progress_dialog and progress_dialog.wasCanceled():
                        logging.info("User cancelled the light session creation")
                        was_cancelled = True
                        return False  # Signal to stop processing
                    
                    if progress_dialog:
                        progress = int((current / total) * 100) if total > 0 else 0
                        progress_dialog.setValue(progress)
                        progress_dialog.setLabelText(f"Creating sessions {current}/{total}: {os.path.basename(filename)}")
                        QApplication.processEvents()  # Keep UI responsive
                        
                        # Check again after processing events
                        if progress_dialog.wasCanceled():
                            logging.info("User cancelled the light session creation during update")
                            was_cancelled = True
                            return False
                    
                    return True  # Continue processing
                except Exception as e:
                    logging.error(f"Error in progress callback: {e}")
                    return True  # Continue on callback errors
            
            # Run the processing with progress callback
            created_sessions = self.fits_file_handler.createLightSessions(progress_callback=update_progress)
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled or completed normally
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Light session creation was cancelled by user.")
                logging.info("Light session creation was cancelled by user")
            else:
                self.load_sessions_data()
                
                # Invalidate stats cache since session data was updated
                parent_widget = self.parent()
                while parent_widget and not hasattr(parent_widget, 'invalidate_stats_cache'):
                    parent_widget = parent_widget.parent()
                if parent_widget:
                    parent_widget.invalidate_stats_cache()
                
                QMessageBox.information(self, "Success", f"Light sessions updated successfully! Created {len(created_sessions)} sessions.")
                logging.info("Light session creation completed successfully")
                
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error updating light Sessions: {e}")
            QMessageBox.warning(self, "Error", f"Failed to update light Sessions: {e}")

    def update_calibration_sessions(self):
        """Update calibration Sessions by running createCalibrationSessions method with progress dialog."""
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        
        progress_dialog = None
        was_cancelled = False
        
        try:
            self.fits_file_handler = fitsProcessing()
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Creating Calibration Sessions")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.show()
            
            def update_progress(current, total, filename):
                """Progress callback function"""
                nonlocal was_cancelled
                try:
                    # Don't check cancellation if already cancelled
                    if was_cancelled:
                        logging.info("Already cancelled, returning False")
                        return False
                    
                    # Check if dialog was cancelled before updating
                    if progress_dialog and progress_dialog.wasCanceled():
                        logging.info("User cancelled the calibration Session creation")
                        was_cancelled = True
                        return False  # Signal to stop processing
                    
                    if progress_dialog:
                        progress = int((current / total) * 100) if total > 0 else 0
                        progress_dialog.setValue(progress)
                        progress_dialog.setLabelText(f"Creating calibration sessions {current}/{total}: {os.path.basename(filename)}")
                        QApplication.processEvents()  # Keep UI responsive
                        
                        # Check again after processing events
                        if progress_dialog.wasCanceled():
                            logging.info("User cancelled the calibration session creation during update")
                            was_cancelled = True
                            return False
                    
                    return True  # Continue processing
                except Exception as e:
                    logging.error(f"Error in progress callback: {e}")
                    return True  # Continue on callback errors
            
            # Run the processing with progress callback
            created_sessions = self.fits_file_handler.createCalibrationSessions(progress_callback=update_progress)
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled or completed normally
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Calibration session creation was cancelled by user.")
                logging.info("Calibration session creation was cancelled by user")
            else:
                self.load_sessions_data()
                
                # Invalidate stats cache since calibration session data was updated
                parent_widget = self.parent()
                while parent_widget and not hasattr(parent_widget, 'invalidate_stats_cache'):
                    parent_widget = parent_widget.parent()
                if parent_widget:
                    parent_widget.invalidate_stats_cache()
                
                QMessageBox.information(self, "Success", f"Calibration sessions updated successfully! Created {len(created_sessions)} sessions.")
                logging.info("Calibration session creation completed successfully")
                
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error updating calibration Sessions: {e}")
            QMessageBox.warning(self, "Error", f"Failed to update calibration Sessions: {e}")

    def load_sessions_data(self):
        """Load session data from the database and populate the tree widget with hierarchical structure."""
        try:
            self.sessions_tree.clear()
            
            # Query all sessions from the database
            sessions = FitsSessionModel.select()
            
            # Group sessions by object name
            sessions_by_object = {}
            for session in sessions:
                object_name = session.fitsSessionObjectName or "Unknown"
                if object_name not in sessions_by_object:
                    sessions_by_object[object_name] = []
                sessions_by_object[object_name].append(session)
            
            # Create hierarchical tree structure - sort objects alphabetically
            for object_name in sorted(sessions_by_object.keys()):
                object_sessions = sessions_by_object[object_name]
                # Create parent item for each object
                parent_item = QTreeWidgetItem()
                parent_item.setText(0, object_name)
                parent_item.setText(1, "")  # No date for parent
                parent_item.setText(2, "")  # No telescope for parent
                parent_item.setText(3, "")  # No imager for parent
                
                # Style parent item differently
                font = parent_item.font(0)
                font.setBold(True)
                parent_item.setFont(0, font)
                
                # Sort sessions by date (newest first)
                sorted_sessions = sorted(object_sessions, 
                                       key=lambda x: x.fitsSessionDate if x.fitsSessionDate else datetime.date.min, 
                                       reverse=True)
                
                # Add child items for each session
                for session in sorted_sessions:
                    child_item = QTreeWidgetItem()
                    child_item.setText(0, "")  # Empty object name for child (parent shows it)
                    child_item.setText(1, str(session.fitsSessionDate) if session.fitsSessionDate else "N/A")
                    child_item.setText(2, session.fitsSessionTelescope or "N/A")
                    child_item.setText(3, session.fitsSessionImager or "N/A")
                    
                    # Store session ID for future use
                    child_item.setData(0, Qt.UserRole, session.fitsSessionId)
                    
                    # Add linked calibration sessions as sub-children for light sessions
                    if object_name not in ['Bias', 'Dark', 'Flat']:
                        # This is a light session, show linked calibration sessions
                        if session.fitsBiasSession:
                            try:
                                bias_session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session.fitsBiasSession)
                                bias_child = QTreeWidgetItem()
                                bias_child.setText(0, f"  → Bias")
                                bias_child.setText(1, str(bias_session.fitsSessionDate) if bias_session.fitsSessionDate else "N/A")
                                bias_child.setText(2, bias_session.fitsSessionTelescope or "N/A")
                                bias_child.setText(3, bias_session.fitsSessionImager or "N/A")
                                child_item.addChild(bias_child)
                            except FitsSessionModel.DoesNotExist:
                                pass
                        
                        if session.fitsDarkSession:
                            try:
                                dark_session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session.fitsDarkSession)
                                dark_child = QTreeWidgetItem()
                                dark_child.setText(0, f"  → Dark")
                                dark_child.setText(1, str(dark_session.fitsSessionDate) if dark_session.fitsSessionDate else "N/A")
                                dark_child.setText(2, dark_session.fitsSessionTelescope or "N/A")
                                dark_child.setText(3, dark_session.fitsSessionImager or "N/A")
                                child_item.addChild(dark_child)
                            except FitsSessionModel.DoesNotExist:
                                pass
                        
                        if session.fitsFlatSession:
                            try:
                                flat_session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session.fitsFlatSession)
                                flat_child = QTreeWidgetItem()
                                flat_child.setText(0, f"  → Flat")
                                flat_child.setText(1, str(flat_session.fitsSessionDate) if flat_session.fitsSessionDate else "N/A")
                                flat_child.setText(2, flat_session.fitsSessionTelescope or "N/A")
                                flat_child.setText(3, flat_session.fitsSessionImager or "N/A")
                                child_item.addChild(flat_child)
                            except FitsSessionModel.DoesNotExist:
                                pass
                    
                    parent_item.addChild(child_item)
                
                # Only add parent item if it has children
                if parent_item.childCount() > 0:
                    self.sessions_tree.addTopLevelItem(parent_item)
                    # Collapse parent item by default
                    parent_item.setExpanded(False)
            
            count = len(sessions)
            if count > 0:
                logger.debug(f"Loaded {count} sessions into hierarchical display")
            else:
                logger.debug("No sessions found in database")
            
        except Exception as e:
            logger.error(f"Error loading Sessions data: {e}")
            # Don't show error dialog on startup if database is just empty
            if "no such table" not in str(e).lower():
                QMessageBox.warning(self, "Error", f"Failed to load Sessions data: {e}")

    def clear_sessions(self):
        """Clear all Session records from the database and refresh the display."""
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            "Confirm Clear Sessions", 
            "This will permanently delete all Session records from the database.\n"
            "This will NOT delete the actual FITS files, only the Session groupings.\n"
            "Individual FITS files will become unassigned to Sessions.\n\n"
            "Are you sure you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            # Clear the tree widget first
            self.sessions_tree.clear()
            
            # Delete all fitsSession records from the database
            deleted_sessions = FitsSessionModel.delete().execute()
            
            # Also clear the session assignments from FITS files
            from astrofiler_db import fitsFile as FitsFileModel
            FitsFileModel.update(fitsFileSession=None).execute()
            
            logger.info(f"Deleted {deleted_sessions} session records from database and cleared session assignments")
            QMessageBox.information(
                self, 
                "Success", 
                f"Successfully cleared {deleted_sessions} session records from database.\n"
                f"All FITS files are now unassigned to sessions."
            )
            
            # Refresh the display (should be empty now)
            self.load_sessions_data()
            
            # Invalidate stats cache since session data was cleared
            parent_widget = self.parent()
            while parent_widget and not hasattr(parent_widget, 'invalidate_stats_cache'):
                parent_widget = parent_widget.parent()
            if parent_widget:
                parent_widget.invalidate_stats_cache()
            
        except Exception as e:
            logger.error(f"Error clearing Sessions: {e}")
            QMessageBox.warning(self, "Error", f"Failed to clear Sessions: {e}")

    def link_sessions(self):
        """Link calibration sessions to light sessions with progress dialog."""
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        
        progress_dialog = None
        was_cancelled = False
        
        try:
            self.fits_file_handler = fitsProcessing()
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Linking Sessions")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.show()
            
            # Progress callback function
            def update_progress(current, total, session_name):
                nonlocal was_cancelled
                
                try:
                    # Don't check cancellation if already cancelled
                    if was_cancelled:
                        logging.info("Already cancelled, returning False")
                        return False
                    
                    # Check if dialog was cancelled before updating
                    if progress_dialog and progress_dialog.wasCanceled():
                        logging.info("User cancelled session linking")
                        was_cancelled = True
                        return False  # Signal to stop processing
                    
                    if progress_dialog:
                        progress = int((current / total) * 100) if total > 0 else 0
                        progress_dialog.setValue(progress)
                        progress_dialog.setLabelText(f"Linking sessions {current}/{total}: {session_name}")
                        QApplication.processEvents()  # Keep UI responsive
                        
                        # Check again after processing events
                        if progress_dialog.wasCanceled():
                            logging.info("User cancelled session linking during update")
                            was_cancelled = True
                            return False
                    
                    return True  # Continue processing
                except Exception as e:
                    logging.error(f"Error in progress callback: {e}")
                    return True  # Continue on callback errors
            
            # Run the processing with progress callback
            updated_sessions = self.fits_file_handler.linkSessions(progress_callback=update_progress)
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled or completed normally
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Session linking was cancelled by user.")
                logging.info("Session linking was cancelled by user")
            else:
                self.load_sessions_data()
                QMessageBox.information(self, "Success", f"Session linking completed successfully! Updated {len(updated_sessions)} light sessions with calibration links.")
                logging.info("Session linking completed successfully")
                
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error linking sessions: {e}")
            QMessageBox.warning(self, "Error", f"Failed to link sessions: {e}")

    def regenerate_sessions(self):
        """Regenerate all sessions: Clear → Update Lights → Update Calibrations → Link Sessions"""
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        
        # Confirm regeneration
        reply = QMessageBox.question(
            self, 
            "Confirm Regenerate Sessions", 
            "This will:\n"
            "1. Clear all existing session records\n"
            "2. Create new light sessions\n"
            "3. Create new calibration sessions\n"
            "4. Link calibration sessions to light sessions\n\n"
            "This will NOT delete actual FITS files, only session groupings.\n"
            "Are you sure you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        progress_dialog = None
        was_cancelled = False
        operation_results = {
            'cleared_sessions': 0,
            'light_sessions': 0,
            'calibration_sessions': 0,
            'linked_sessions': 0
        }
        
        try:
            # Create overall progress dialog
            progress_dialog = QProgressDialog("Initializing regeneration...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Regenerating Sessions")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()
            
            # Step 1: Clear existing sessions (25% of progress)
            progress_dialog.setLabelText("Step 1/4: Clearing existing sessions...")
            progress_dialog.setValue(0)
            QApplication.processEvents()
            
            if progress_dialog.wasCanceled():
                return
            
            logger.info("Regenerate Sessions: Starting step 1 - clearing existing sessions")
            try:
                # Clear the tree widget first
                self.sessions_tree.clear()
                
                # Delete all fitsSession records from the database
                deleted_sessions = FitsSessionModel.delete().execute()
                operation_results['cleared_sessions'] = deleted_sessions
                
                # Also clear the session assignments from FITS files
                from astrofiler_db import fitsFile as FitsFileModel
                FitsFileModel.update(fitsFileSession=None).execute()
                
                logger.info(f"Regenerate Sessions: Cleared {deleted_sessions} existing sessions")
                progress_dialog.setValue(25)
                QApplication.processEvents()
                
            except Exception as e:
                logger.error(f"Error in step 1 (clear sessions): {e}")
                if progress_dialog:
                    progress_dialog.close()
                QMessageBox.warning(self, "Error", f"Failed to clear existing sessions: {e}")
                return
            
            if progress_dialog.wasCanceled():
                return
            
            # Step 2: Create light sessions (25-50% of progress)
            progress_dialog.setLabelText("Step 2/4: Creating light sessions...")
            QApplication.processEvents()
            
            logger.info("Regenerate Sessions: Starting step 2 - creating light sessions")
            try:
                self.fits_file_handler = fitsProcessing()
                
                def light_progress_callback(current, total, filename):
                    nonlocal was_cancelled
                    if was_cancelled or (progress_dialog and progress_dialog.wasCanceled()):
                        was_cancelled = True
                        return False
                    
                    if progress_dialog:
                        # Light sessions take 25% of total progress (25-50%)
                        step_progress = int((current / total) * 25) if total > 0 else 0
                        overall_progress = 25 + step_progress
                        progress_dialog.setValue(overall_progress)
                        progress_dialog.setLabelText(f"Step 2/4: Creating light sessions {current}/{total}: {os.path.basename(filename)}")
                        QApplication.processEvents()
                    
                    return not was_cancelled
                
                created_light_sessions = self.fits_file_handler.createLightSessions(progress_callback=light_progress_callback)
                if was_cancelled:
                    return
                
                operation_results['light_sessions'] = len(created_light_sessions)
                logger.info(f"Regenerate Sessions: Created {len(created_light_sessions)} light sessions")
                progress_dialog.setValue(50)
                QApplication.processEvents()
                
            except Exception as e:
                logger.error(f"Error in step 2 (create light sessions): {e}")
                if progress_dialog:
                    progress_dialog.close()
                QMessageBox.warning(self, "Error", f"Failed to create light sessions: {e}")
                return
            
            if progress_dialog.wasCanceled():
                return
            
            # Step 3: Create calibration sessions (50-75% of progress)
            progress_dialog.setLabelText("Step 3/4: Creating calibration sessions...")
            QApplication.processEvents()
            
            logger.info("Regenerate Sessions: Starting step 3 - creating calibration sessions")
            try:
                def calibration_progress_callback(current, total, filename):
                    nonlocal was_cancelled
                    if was_cancelled or (progress_dialog and progress_dialog.wasCanceled()):
                        was_cancelled = True
                        return False
                    
                    if progress_dialog:
                        # Calibration sessions take 25% of total progress (50-75%)
                        step_progress = int((current / total) * 25) if total > 0 else 0
                        overall_progress = 50 + step_progress
                        progress_dialog.setValue(overall_progress)
                        progress_dialog.setLabelText(f"Step 3/4: Creating calibration sessions {current}/{total}: {filename}")
                        QApplication.processEvents()
                    
                    return not was_cancelled
                
                created_calibration_sessions = self.fits_file_handler.createCalibrationSessions(progress_callback=calibration_progress_callback)
                if was_cancelled:
                    return
                
                operation_results['calibration_sessions'] = len(created_calibration_sessions)
                logger.info(f"Regenerate Sessions: Created {len(created_calibration_sessions)} calibration sessions")
                progress_dialog.setValue(75)
                QApplication.processEvents()
                
            except Exception as e:
                logger.error(f"Error in step 3 (create calibration sessions): {e}")
                if progress_dialog:
                    progress_dialog.close()
                QMessageBox.warning(self, "Error", f"Failed to create calibration sessions: {e}")
                return
            
            if progress_dialog.wasCanceled():
                return
            
            # Step 4: Link sessions (75-100% of progress)
            progress_dialog.setLabelText("Step 4/4: Linking sessions...")
            QApplication.processEvents()
            
            logger.info("Regenerate Sessions: Starting step 4 - linking sessions")
            try:
                def link_progress_callback(current, total, session_name):
                    nonlocal was_cancelled
                    if was_cancelled or (progress_dialog and progress_dialog.wasCanceled()):
                        was_cancelled = True
                        return False
                    
                    if progress_dialog:
                        # Linking takes 25% of total progress (75-100%)
                        step_progress = int((current / total) * 25) if total > 0 else 0
                        overall_progress = 75 + step_progress
                        progress_dialog.setValue(overall_progress)
                        progress_dialog.setLabelText(f"Step 4/4: Linking sessions {current}/{total}: {session_name}")
                        QApplication.processEvents()
                    
                    return not was_cancelled
                
                updated_sessions = self.fits_file_handler.linkSessions(progress_callback=link_progress_callback)
                if was_cancelled:
                    return
                
                operation_results['linked_sessions'] = len(updated_sessions)
                logger.info(f"Regenerate Sessions: Linked {len(updated_sessions)} sessions")
                progress_dialog.setValue(100)
                QApplication.processEvents()
                
            except Exception as e:
                logger.error(f"Error in step 4 (link sessions): {e}")
                if progress_dialog:
                    progress_dialog.close()
                QMessageBox.warning(self, "Error", f"Failed to link sessions: {e}")
                return
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Session regeneration was cancelled by user.")
                logger.info("Session regeneration was cancelled by user")
            else:
                # Refresh the display
                self.load_sessions_data()
                
                # Invalidate stats cache since session data was updated
                parent_widget = self.parent()
                while parent_widget and not hasattr(parent_widget, 'invalidate_stats_cache'):
                    parent_widget = parent_widget.parent()
                if parent_widget:
                    parent_widget.invalidate_stats_cache()
                
                # Show success message with detailed results
                result_message = (
                    f"Session regeneration completed successfully!\n\n"
                    f"• Cleared: {operation_results['cleared_sessions']} existing sessions\n"
                    f"• Created: {operation_results['light_sessions']} light sessions\n"
                    f"• Created: {operation_results['calibration_sessions']} calibration sessions\n"
                    f"• Linked: {operation_results['linked_sessions']} sessions with calibration frames"
                )
                
                QMessageBox.information(self, "Success", result_message)
                logger.info(f"Session regeneration completed successfully: {operation_results}")
                
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error during session regeneration: {e}")
            QMessageBox.warning(self, "Error", f"Failed to regenerate sessions: {e}")

class MappingsDialog(QDialog):
    """Dialog for managing FITS header mappings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mappings")
        self.setModal(True)
        self.resize(800, 600)
        
        # Store mapping rows for dynamic management
        self.mapping_rows = []
        
        self.init_ui()
        self.load_existing_mappings()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Add button at the top
        add_button = QPushButton("Add Mapping")
        add_button.clicked.connect(lambda: self.add_mapping_row())
        layout.addWidget(add_button)
        
        # Scroll area for mappings
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setAlignment(Qt.AlignTop)  # Top-justify the mapping rows
        self.scroll_layout.setSpacing(5)  # Add consistent spacing between rows
        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area)
        
        # Bottom checkboxes and buttons
        bottom_layout = QVBoxLayout()
        
        # Checkboxes
        checkbox_layout = QHBoxLayout()
        self.apply_current_checkbox = QCheckBox("Apply to Database")
        
        # Get save_modified_headers setting from ini file
        import configparser
        config = configparser.ConfigParser()
        try:
            config.read('astrofiler.ini')
            save_headers_default = config.getboolean('DEFAULT', 'save_modified_headers', fallback=True)
        except:
            save_headers_default = True
        
        self.update_files_checkbox = QCheckBox("Update Files on Disk")
        self.update_files_checkbox.setChecked(save_headers_default)
        
        checkbox_layout.addWidget(self.apply_current_checkbox)
        checkbox_layout.addWidget(self.update_files_checkbox)
        bottom_layout.addLayout(checkbox_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_mappings)
        button_box.rejected.connect(self.reject)
        bottom_layout.addWidget(button_box)
        
        layout.addLayout(bottom_layout)
    
    def get_current_values_for_card(self, card):
        """Get all current values in the database for a given card"""
        try:
            values = set()
            
            # Map card names to database fields
            field_mapping = {
                'TELESCOP': 'fitsFileTelescop',
                'INSTRUME': 'fitsFileInstrument', 
                'OBSERVER': None,  # Not currently in database
                'NOTES': None,     # Not currently in database
                'FILTER': 'fitsFileFilter'
            }
            
            field_name = field_mapping.get(card)
            if field_name:
                # Query the database for distinct values
                query = FitsFileModel.select(getattr(FitsFileModel, field_name)).distinct()
                for record in query:
                    value = getattr(record, field_name)
                    if value is not None:
                        values.add(str(value))
            
            # Always add blank option
            values.add("")
            
            return sorted(list(values))
        except Exception as e:
            logger.error(f"Error getting current values for {card}: {e}")
            return [""]
    
    def add_mapping_row(self, card="TELESCOP", current="", replace="", is_default=False):
        """Add a new mapping row to the dialog"""
        row_widget = QWidget()
        row_layout = QGridLayout(row_widget)
        
        # Card dropdown
        card_combo = QComboBox()
        card_combo.addItems(["TELESCOP", "INSTRUME", "OBSERVER", "NOTES"])
        card_combo.setCurrentText(card)
        card_combo.currentTextChanged.connect(lambda: self.update_current_values(row_widget))
        
        # Current dropdown
        current_combo = QComboBox()
        current_combo.setEditable(True)
        
        # Replace text field
        replace_edit = QLineEdit()
        replace_edit.setText(replace)
              
        # Delete button (trash icon)
        delete_button = QPushButton("🗑")
        delete_button.setMaximumWidth(30)
        delete_button.setToolTip("Delete this mapping")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #ff4444;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 14px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #ff6666;
                border: 1px solid #ff4444;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
                color: #ff2222;
            }
        """)
        delete_button.clicked.connect(lambda: self.delete_mapping_row(row_widget))
        
        # Add to layout
        row_layout.addWidget(QLabel("Card:"), 0, 0)
        row_layout.addWidget(card_combo, 0, 1)
        row_layout.addWidget(QLabel("Current:"), 0, 2)
        row_layout.addWidget(current_combo, 0, 3)
        row_layout.addWidget(QLabel("Replace:"), 0, 4)
        row_layout.addWidget(replace_edit, 0, 5)
        row_layout.addWidget(delete_button, 0, 8)
        
        # Store references
        row_widget.card_combo = card_combo
        row_widget.current_combo = current_combo
        row_widget.replace_edit = replace_edit
        
        # Update current values for initial card
        self.update_current_values(row_widget)
        current_combo.setCurrentText(current)
        
        # Add to scroll layout
        self.scroll_layout.addWidget(row_widget)
        self.mapping_rows.append(row_widget)

    def add_mapping_row(self, card="TELESCOP", current="", replace=""):
        """Add a new mapping row to the dialog"""
        row_widget = QWidget()
        row_layout = QGridLayout(row_widget)

        # Card dropdown
        card_combo = QComboBox()
        card_combo.addItems(["TELESCOP", "INSTRUME", "OBSERVER", "NOTES", "FILTER"])
        card_combo.setCurrentText(card)
        card_combo.currentTextChanged.connect(lambda: self.update_current_values(row_widget))

        # Current dropdown
        current_combo = QComboBox()
        current_combo.setEditable(True)

        # Replace text field
        replace_edit = QLineEdit()
        replace_edit.setText(replace)

        # Apply button for this row
        apply_button = QPushButton("✓")
        apply_button.setMaximumWidth(30)
        apply_button.setToolTip("Apply this mapping to database and files")
        apply_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #44aa44;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 14px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #66cc66;
                border: 1px solid #44aa44;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
                color: #22aa22;
            }
        """)
        apply_button.clicked.connect(lambda: self.apply_single_mapping(row_widget))

        # Delete button (trash icon)
        delete_button = QPushButton("🗑")
        delete_button.setMaximumWidth(30)
        delete_button.setToolTip("Delete this mapping")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #ff4444;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 14px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #ff6666;
                border: 1px solid #ff4444;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
                color: #ff2222;
            }
        """)
        delete_button.clicked.connect(lambda: self.delete_mapping_row(row_widget))

        # Add to layout
        row_layout.addWidget(QLabel("Card:"), 0, 0)
        row_layout.addWidget(card_combo, 0, 1)
        row_layout.addWidget(QLabel("Current:"), 0, 2)
        row_layout.addWidget(current_combo, 0, 3)
        row_layout.addWidget(QLabel("Replace:"), 0, 4)
        row_layout.addWidget(replace_edit, 0, 5)
        row_layout.addWidget(apply_button, 0, 6)
        row_layout.addWidget(delete_button, 0, 7)

        # Store references
        row_widget.card_combo = card_combo
        row_widget.current_combo = current_combo
        row_widget.replace_edit = replace_edit

        # Update current values for initial card
        self.update_current_values(row_widget)
        current_combo.setCurrentText(current)

        # Add to scroll layout
        self.scroll_layout.addWidget(row_widget)
        self.mapping_rows.append(row_widget)

    def apply_single_mapping(self, row_widget):
        """Apply the mapping in this row to the database and files"""
        card = row_widget.card_combo.currentText()
        current = row_widget.current_combo.currentText()
        replace = row_widget.replace_edit.text()

        # Validate inputs
        if not current or not replace:
            QMessageBox.warning(self, "Invalid Mapping", "Both 'Current' and 'Replace' values must be provided.")
            return

        # Count affected records
        field_mapping = {
            'TELESCOP': 'fitsFileTelescop',
            'INSTRUME': 'fitsFileInstrument',
            'OBSERVER': None,
            'NOTES': None,
            'FILTER': 'fitsFileFilter'
        }
        field_name = field_mapping.get(card)
        
        affected_count = 0
        if field_name:
            from astrofiler_db import fitsFile as FitsFileModel
            query = FitsFileModel.select().where(getattr(FitsFileModel, field_name) == current)
            affected_count = query.count()

        if affected_count == 0:
            QMessageBox.information(self, "No Records Found", f"No records found with {card} = '{current}'")
            return

        # Show confirmation dialog
        actions = []
        actions.append(f"Database Updates: {affected_count} records")
        
        if self.update_files_checkbox.isChecked():
            actions.append(f"File Header Updates: {affected_count} files")
            if card == 'FILTER':
                actions.append(f"File/Folder Rename Updates: {affected_count} files (filter paths and filenames)")

        confirmation_text = f"Apply mapping: {card} '{current}' → '{replace}'\n\n"
        confirmation_text += "Actions to be performed:\n"
        confirmation_text += "\n".join(f"• {action}" for action in actions)
        if card == 'FILTER' and self.update_files_checkbox.isChecked():
            confirmation_text += f"\n\nNote: FILTER mapping will rename files and move them to new filter-specific folders."
        confirmation_text += f"\n\nProceed with these changes?"

        reply = QMessageBox.question(
            self, 
            "Confirm Mapping Application",
            confirmation_text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Create progress dialog
        progress_dialog = QProgressDialog("Applying mapping...", "Cancel", 0, 100, self)
        progress_dialog.setWindowTitle("Applying Mapping")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.show()

        try:
            total_steps = 1  # Database updates
            if self.update_files_checkbox.isChecked():
                total_steps += 1  # File header updates
                if card == 'FILTER':
                    total_steps += 1  # File/folder rename updates for FILTER

            current_step = 0
            
            # Step 1: Database Updates
            progress_dialog.setLabelText(f"Database Updates: 0/{affected_count}")
            progress_dialog.setValue(0)
            QApplication.processEvents()

            if field_name:
                query = FitsFileModel.select().where(getattr(FitsFileModel, field_name) == current)
                updated_count = 0
                for i, record in enumerate(query):
                    if progress_dialog.wasCanceled():
                        break
                    
                    setattr(record, field_name, replace)
                    record.save()
                    updated_count += 1
                    
                    # Update progress
                    step_progress = int((i + 1) / affected_count * 100 / total_steps)
                    overall_progress = int(current_step / total_steps * 100) + step_progress
                    progress_dialog.setValue(overall_progress)
                    progress_dialog.setLabelText(f"Database Updates: {updated_count}/{affected_count}")
                    QApplication.processEvents()

                logger.info(f"Applied mapping: {card} '{current}' → '{replace}' to {updated_count} database records.")

            current_step += 1

            # Step 2: File Header Updates (if enabled)
            if self.update_files_checkbox.isChecked() and not progress_dialog.wasCanceled():
                progress_dialog.setLabelText(f"File Header Updates: 0/{affected_count}")
                QApplication.processEvents()

                # Get the files to update
                if field_name:
                    query = FitsFileModel.select().where(getattr(FitsFileModel, field_name) == current)
                    updated_files = 0
                    
                    for i, record in enumerate(query):
                        if progress_dialog.wasCanceled():
                            break
                        
                        try:
                            # Update the FITS file header
                            file_path = record.fitsFileName
                            if os.path.exists(file_path):
                                # Open FITS file and update header
                                from astropy.io import fits
                                with fits.open(file_path, mode='update') as hdul:
                                    hdr = hdul[0].header
                                    if card in hdr:
                                        old_value = hdr[card]
                                        if str(old_value).strip() == current:
                                            hdr[card] = replace
                                            hdul.flush()
                                            logger.info(f"Updated {card} in {file_path}: '{current}' → '{replace}'")
                                            updated_files += 1
                            else:
                                logger.warning(f"File not found for header update: {file_path}")
                                
                        except Exception as e:
                            logger.error(f"Error updating file header for {record.fitsFileName}: {e}")
                        
                        # Update progress
                        step_progress = int((i + 1) / affected_count * 100 / total_steps)
                        overall_progress = int(current_step / total_steps * 100) + step_progress
                        progress_dialog.setValue(overall_progress)
                        progress_dialog.setLabelText(f"File Header Updates: {i + 1}/{affected_count}")
                        QApplication.processEvents()

                    logger.info(f"Updated file headers for mapping: {card} '{current}' → '{replace}' on {updated_files} files")
                else:
                    logger.info(f"No file header updates needed for {card} field (not stored in database)")

            # Step 3: File and Folder Rename Updates (if FILTER mapping affects filenames/paths)
            if (self.update_files_checkbox.isChecked() and 
                not progress_dialog.wasCanceled() and 
                card == 'FILTER' and field_name):
                
                current_step += 1
                progress_dialog.setLabelText(f"File/Folder Rename Updates: 0/{affected_count}")
                QApplication.processEvents()

                # Get the files that need renaming
                query = FitsFileModel.select().where(getattr(FitsFileModel, field_name) == replace)  # Files now have the new value
                renamed_files = 0
                
                for i, record in enumerate(query):
                    if progress_dialog.wasCanceled():
                        break
                    
                    try:
                        old_path = record.fitsFileName
                        if os.path.exists(old_path):
                            # Update filename and folder path for FILTER changes
                            old_dir = os.path.dirname(old_path)
                            old_filename = os.path.basename(old_path)
                            
                            # Replace old filter in folder path
                            new_dir = old_dir.replace(f"/{current}/", f"/{replace}/")
                            
                            # Replace old filter in filename
                            new_filename = old_filename.replace(f"-{current}-", f"-{replace}-")
                            
                            new_path = os.path.join(new_dir, new_filename)
                            
                            # Only rename if path actually changed
                            if new_path != old_path:
                                # Create new directory if needed
                                os.makedirs(new_dir, exist_ok=True)
                                
                                # Move file
                                shutil.move(old_path, new_path)
                                
                                # Update database with new path
                                record.fitsFileName = new_path
                                record.save()
                                
                                logger.info(f"Renamed file: {old_path} → {new_path}")
                                renamed_files += 1
                                
                                # Clean up empty directories
                                try:
                                    if os.path.isdir(old_dir) and not os.listdir(old_dir):
                                        os.rmdir(old_dir)
                                        logger.info(f"Removed empty directory: {old_dir}")
                                except OSError:
                                    pass  # Directory not empty or other issue
                        else:
                            logger.warning(f"File not found for rename: {old_path}")
                            
                    except Exception as e:
                        logger.error(f"Error renaming file {record.fitsFileName}: {e}")
                    
                    # Update progress
                    step_progress = int((i + 1) / affected_count * 100 / total_steps)
                    overall_progress = int(current_step / total_steps * 100) + step_progress
                    progress_dialog.setValue(overall_progress)
                    progress_dialog.setLabelText(f"File/Folder Rename Updates: {i + 1}/{affected_count}")
                    QApplication.processEvents()

                logger.info(f"Renamed {renamed_files} files/folders for FILTER mapping: '{current}' → '{replace}'")

            # Complete
            if not progress_dialog.wasCanceled():
                progress_dialog.setValue(100)
                progress_dialog.setLabelText("Mapping application complete!")
                QApplication.processEvents()
                
                QMessageBox.information(self, "Success", f"Mapping applied successfully!\n\nUpdated {affected_count} records.")

        except Exception as e:
            logger.error(f"Error applying mapping: {e}")
            QMessageBox.critical(self, "Error", f"Error applying mapping: {str(e)}")
        
        finally:
            progress_dialog.close()
    
    def update_current_values(self, row_widget):
        """Update the current values dropdown when card changes"""
        card = row_widget.card_combo.currentText()
        current_values = self.get_current_values_for_card(card)
        
        # Remember current selection
        current_text = row_widget.current_combo.currentText()
        
        # Update combo box
        row_widget.current_combo.clear()
        row_widget.current_combo.addItems(current_values)
        
        # Restore selection if it still exists
        if current_text in current_values:
            row_widget.current_combo.setCurrentText(current_text)
    
    def delete_mapping_row(self, row_widget):
        """Delete a mapping row"""
        if row_widget in self.mapping_rows:
            self.mapping_rows.remove(row_widget)
            self.scroll_layout.removeWidget(row_widget)
            row_widget.deleteLater()
    
    def load_existing_mappings(self):
        """Load existing mappings from the database"""
        try:
            mappings = MappingModel.select()
            for mapping in mappings:
                self.add_mapping_row(
                    card=mapping.card,
                    current=mapping.current or "",
                    replace=mapping.replace or ""
                )
        except Exception as e:
            logger.error(f"Error loading existing mappings: {e}")
    
    def accept_mappings(self):
        """Save mappings and apply if requested"""
        try:
            # Clear existing mappings
            MappingModel.delete().execute()
            
            # Save new mappings
            mappings_to_apply = []
            for row_widget in self.mapping_rows:
                card = row_widget.card_combo.currentText()
                current = row_widget.current_combo.currentText()
                replace = row_widget.replace_edit.text()
                
                MappingModel.create(
                    card=card,
                    current=current if current else None,
                    replace=replace if replace else None
                )
                
                # Store mapping for application
                mappings_to_apply.append({
                    'card': card,
                    'current': current,
                    'replace': replace
                })
            
            # Clear the mapping cache so file processing picks up new mappings
            try:
                from astrofiler_file import clearMappingCache
                clearMappingCache()
            except ImportError:
                pass  # Function might not be available in older versions
            
            # Always apply database updates
            self.apply_database_mappings(mappings_to_apply)
            
            # Apply file/folder changes if requested
            if self.apply_current_checkbox.isChecked():
                self.apply_file_folder_mappings(mappings_to_apply)
            
            self.accept()
            
        except Exception as e:
            logger.error(f"Error saving mappings: {e}")
            QMessageBox.critical(self, "Error", f"Error saving mappings: {e}")
    
    def apply_database_mappings(self, mappings):
        """Apply mappings to database records"""
        try:
            update_files = self.update_files_checkbox.isChecked()
            total_updates = 0
            
            # Create progress dialog
            from PySide6.QtWidgets import QProgressDialog
            from PySide6.QtCore import Qt
            
            progress = QProgressDialog("Updating database records...", "Cancel", 0, len(mappings), self)
            progress.setWindowTitle("Applying Mappings")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            for i, mapping in enumerate(mappings):
                if progress.wasCanceled():
                    break
                    
                progress.setValue(i)
                progress.setLabelText(f"Processing {mapping['card']} mapping: '{mapping['current']}' → '{mapping['replace']}'")
                QApplication.processEvents()
                
                if mapping['card'] in ['TELESCOP', 'INSTRUME']:
                    field_name = 'fitsFileTelescop' if mapping['card'] == 'TELESCOP' else 'fitsFileInstrument'
                    
                    # Find files that match the current value
                    if mapping['current']:
                        # Specific value mapping
                        query = FitsFileModel.select().where(getattr(FitsFileModel, field_name) == mapping['current'])
                    else:
                        # Default mapping for null/empty values
                        query = FitsFileModel.select().where(
                            (getattr(FitsFileModel, field_name).is_null()) |
                            (getattr(FitsFileModel, field_name) == '')
                        )
                    
                    # Update matching files
                    for fits_file in query:
                        if mapping['replace']:
                            setattr(fits_file, field_name, mapping['replace'])
                            fits_file.save()
                            total_updates += 1
                            
                            # Update FITS header if requested
                            if update_files and fits_file.fitsFileName and os.path.exists(fits_file.fitsFileName):
                                try:
                                    from astropy.io import fits
                                    with fits.open(fits_file.fitsFileName, mode='update') as hdul:
                                        hdul[0].header[mapping['card']] = mapping['replace']
                                        hdul[0].header.comments[mapping['card']] = 'Updated via Astrofiler mapping'
                                        hdul.flush()
                                except Exception as e:
                                    logger.error(f"Error updating FITS header for {fits_file.fitsFileName}: {e}")
            
            progress.setValue(len(mappings))
            progress.close()
            
            if total_updates > 0:
                QMessageBox.information(self, "Database Updated", 
                                      f"Successfully updated {total_updates} database records.")
            
        except Exception as e:
            logger.error(f"Error applying database mappings: {e}")
            QMessageBox.critical(self, "Error", f"Error applying database mappings: {e}")
    
    def apply_file_folder_mappings(self, mappings):
        """Apply mappings to filenames and folder names on disk"""
        try:
            # Get repository folder from config
            import configparser
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            repo_folder = config.get('DEFAULT', 'repo', fallback='.')
            if not repo_folder.endswith('/') and not repo_folder.endswith('\\'):
                repo_folder += os.sep
            
            # Create progress dialog
            from PySide6.QtWidgets import QProgressDialog
            from PySide6.QtCore import Qt
            
            progress = QProgressDialog("Scanning files and folders...", "Cancel", 0, 100, self)
            progress.setWindowTitle("Renaming Files and Folders")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            renamed_files = 0
            renamed_folders = 0
            errors = []
            
            # Process each mapping
            for mapping_idx, mapping in enumerate(mappings):
                if progress.wasCanceled():
                    break
                
                if not mapping['current'] or not mapping['replace']:
                    continue
                
                current_text = mapping['current']
                replace_text = mapping['replace']
                
                progress.setLabelText(f"Processing mapping {mapping_idx + 1}/{len(mappings)}: '{current_text}' → '{replace_text}'")
                QApplication.processEvents()
                
                # Walk through the repository directory
                try:
                    for root, dirs, files in os.walk(repo_folder):
                        # Update progress
                        progress.setValue(int((mapping_idx / len(mappings)) * 100))
                        QApplication.processEvents()
                        
                        if progress.wasCanceled():
                            break
                        
                        # Rename files containing the current text
                        for filename in files:
                            if current_text in filename:
                                old_path = os.path.join(root, filename)
                                new_filename = filename.replace(current_text, replace_text)
                                new_path = os.path.join(root, new_filename)
                                
                                try:
                                    if not os.path.exists(new_path):
                                        os.rename(old_path, new_path)
                                        renamed_files += 1
                                        
                                        # Update database record if it exists
                                        try:
                                            fits_file = FitsFileModel.get(FitsFileModel.fitsFileName == old_path)
                                            fits_file.fitsFileName = new_path
                                            fits_file.save()
                                        except FitsFileModel.DoesNotExist:
                                            pass  # File not in database
                                        
                                        logger.info(f"Renamed file: {old_path} → {new_path}")
                                    else:
                                        error_msg = f"Cannot rename {old_path} - target exists: {new_path}"
                                        errors.append(error_msg)
                                        logger.warning(error_msg)
                                except Exception as e:
                                    error_msg = f"Error renaming file {old_path}: {str(e)}"
                                    errors.append(error_msg)
                                    logger.error(error_msg)
                        
                        # Rename directories containing the current text
                        # Process in reverse order to handle nested directories correctly
                        for dirname in reversed(dirs):
                            if current_text in dirname:
                                old_dir_path = os.path.join(root, dirname)
                                new_dirname = dirname.replace(current_text, replace_text)
                                new_dir_path = os.path.join(root, new_dirname)
                                
                                try:
                                    if not os.path.exists(new_dir_path):
                                        os.rename(old_dir_path, new_dir_path)
                                        renamed_folders += 1
                                        
                                        # Update database records with paths in this directory
                                        old_prefix = old_dir_path + os.sep
                                        new_prefix = new_dir_path + os.sep
                                        
                                        fits_files = FitsFileModel.select().where(
                                            FitsFileModel.fitsFileName.startswith(old_prefix)
                                        )
                                        for fits_file in fits_files:
                                            fits_file.fitsFileName = fits_file.fitsFileName.replace(old_prefix, new_prefix)
                                            fits_file.save()
                                        
                                        logger.info(f"Renamed folder: {old_dir_path} → {new_dir_path}")
                                    else:
                                        error_msg = f"Cannot rename {old_dir_path} - target exists: {new_dir_path}"
                                        errors.append(error_msg)
                                        logger.warning(error_msg)
                                except Exception as e:
                                    error_msg = f"Error renaming folder {old_dir_path}: {str(e)}"
                                    errors.append(error_msg)
                                    logger.error(error_msg)
                
                except Exception as e:
                    error_msg = f"Error processing mapping '{current_text}' → '{replace_text}': {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            progress.setValue(100)
            progress.close()
            
            # Show results
            result_message = f"File and folder renaming completed:\n\n"
            result_message += f"• Files renamed: {renamed_files}\n"
            result_message += f"• Folders renamed: {renamed_folders}\n"
            
            if errors:
                result_message += f"\n{len(errors)} errors encountered:\n"
                result_message += "\n".join(errors[:10])  # Show first 10 errors
                if len(errors) > 10:
                    result_message += f"\n... and {len(errors) - 10} more errors (see log for details)"
                
                QMessageBox.warning(self, "Renaming Completed with Errors", result_message)
            else:
                QMessageBox.information(self, "Renaming Successful", result_message)
            
        except Exception as e:
            logger.error(f"Error applying file/folder mappings: {e}")
            QMessageBox.critical(self, "Error", f"Error applying file/folder mappings: {e}")

    def apply_mappings(self):
        """Legacy method - redirects to new implementation"""
        # This method is kept for compatibility but shouldn't be called anymore
        # since the new accept_mappings method handles everything
        pass

class MergeTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Main content area
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Title
        title_label = QLabel("Object Name Merge/Rename Tool")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Instructions
        instructions = QLabel(
            "This tool allows you to merge object names in the database. "
            "All instances of the 'From' object name will be changed to the 'To' object name. "
            "If the 'To' object name does not exist, it will be created, if necessary. "
            "Optionally, you can also rename and move the actual files on disk. The FITS header will also be updated"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 10px; background-color: rgba(255, 255, 255, 0.1); border-radius: 5px; margin: 10px 0px;")
        main_layout.addWidget(instructions)
        
        # Form group
        form_group = QGroupBox("Merge Settings")
        form_layout = QFormLayout(form_group)
        
        # From field
        self.from_field = QLineEdit()
        self.from_field.setPlaceholderText("Enter the object name to change from...")
        form_layout.addRow("From Object:", self.from_field)
        
        # To field
        self.to_field = QLineEdit()
        self.to_field.setPlaceholderText("Enter the object name to change to...")
        form_layout.addRow("To Object:", self.to_field)
        
        # Change filenames checkbox
        self.change_filenames = QCheckBox("Change/Move filenames on disk")
        self.change_filenames.setChecked(True)  # Default to true
        self.change_filenames.setToolTip("If checked, actual files on disk will be renamed to match the new object name")
        form_layout.addRow("", self.change_filenames)
        
        main_layout.addWidget(form_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.preview_button = QPushButton("Preview Changes")
        self.merge_button = QPushButton("Execute Merge")
        self.clear_button = QPushButton("Clear Fields")
        
        self.preview_button.clicked.connect(self.preview_merge)
        self.merge_button.clicked.connect(self.execute_merge)
        self.clear_button.clicked.connect(self.clear_fields)
        
        button_layout.addWidget(self.preview_button)
        button_layout.addWidget(self.merge_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        # Results area
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(200)
        self.results_text.setPlaceholderText("Results and status messages will appear here...")
        main_layout.addWidget(self.results_text)
        
        main_layout.addStretch()
        layout.addWidget(main_widget)
    
    def clear_fields(self):
        """Clear all input fields and results"""
        self.from_field.clear()
        self.to_field.clear()
        self.change_filenames.setChecked(False)
        self.results_text.clear()
    
    def preview_merge(self):
        """Preview what changes would be made without executing them"""
        from_object = self.from_field.text().strip()
        to_object = self.to_field.text().strip()
        
        if not from_object or not to_object:
            QMessageBox.warning(self, "Input Error", "Please enter both From and To object names.")
            return
        
        if from_object == to_object:
            QMessageBox.information(self, "No Changes", "From and To object names are identical. No changes needed.")
            return
        
        try:
            # Check if From object exists
            from_files = FitsFileModel.select().where(FitsFileModel.fitsFileObject == from_object)
            from_count = len(from_files)
            
            if from_count == 0:
                QMessageBox.warning(self, "Object Not Found", f"No files found with object name '{from_object}'.")
                return
            
            # Check if To object exists
            to_files = FitsFileModel.select().where(FitsFileModel.fitsFileObject == to_object)
            to_count = len(to_files)
            
            # Display preview
            preview_text = f"PREVIEW - No changes will be made:\n\n"
            preview_text += f"From Object: '{from_object}' ({from_count} files)\n"
            preview_text += f"To Object: '{to_object}' ({to_count} files)\n\n"
            
            if to_count > 0:
                preview_text += f"After merge: '{to_object}' will have {from_count + to_count} files total\n\n"
            else:
                preview_text += f"After merge: '{to_object}' will be created with {from_count} files\n\n"
            
            preview_text += "Database changes:\n"
            preview_text += f"- {from_count} FITS file records will have their object name changed\n"
            
            if self.change_filenames.isChecked():
                preview_text += f"- {from_count} files on disk will be renamed\n"
            else:
                preview_text += "- Files on disk will NOT be renamed\n"
            
            self.results_text.setPlainText(preview_text)
            
        except Exception as e:
            logger.error(f"Error during preview: {e}")
            QMessageBox.warning(self, "Preview Error", f"Error during preview: {e}")
    
    def execute_merge(self):
        """Execute the actual merge operation"""
        from_object = self.from_field.text().strip()
        to_object = self.to_field.text().strip()
        change_files = self.change_filenames.isChecked()
        
        if not from_object or not to_object:
            QMessageBox.warning(self, "Input Error", "Please enter both From and To object names.")
            return
        
        if from_object == to_object:
            QMessageBox.information(self, "No Changes", "From and To object names are identical. No changes needed.")
            return
        
        # Confirm with user
        msg = f"Are you sure you want to merge '{from_object}' into '{to_object}'?\n\n"
        if change_files:
            msg += "This will change database records AND rename/move files on disk.\n"
        else:
            msg += "This will change database records only.\n"
        msg += "\nThis action cannot be undone!"
        
        reply = QMessageBox.question(self, "Confirm Merge", msg, 
                                   QMessageBox.Yes | QMessageBox.No, 
                                   QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            # Get repository folder from config
            import configparser
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            repo_folder = config.get('DEFAULT', 'repo', fallback='.')
            if not repo_folder.endswith('/'):
                repo_folder += '/'
            
            # Get files to merge
            files_to_merge = FitsFileModel.select().where(FitsFileModel.fitsFileObject == from_object)
            
            if len(files_to_merge) == 0:
                QMessageBox.warning(self, "Object Not Found", f"No files found with object name '{from_object}'.")
                return
            
            merged_count = 0
            renamed_count = 0
            moved_count = 0
            header_updated_count = 0
            errors = []
            
            # Import FITS handling for header updates
            from astropy.io import fits
            
            result_text = f"MERGE EXECUTION RESULTS:\n\n"
            result_text += f"From: '{from_object}' → To: '{to_object}'\n"
            result_text += f"Change filenames: {'Yes' if change_files else 'No'}\n\n"
            
            for fits_file in files_to_merge:
                try:
                    old_filename = fits_file.fitsFileName
                    new_full_path = None
                    file_operation_successful = True
                    
                    # If changing filenames, perform file operations first before updating database
                    if change_files and old_filename and os.path.exists(old_filename):
                        # Parse the current file path to extract metadata
                        # Expected path structure: {repo}/Light/{OBJECT}/{TELESCOPE}/{INSTRUMENT}/{DATE}/filename
                        path_parts = old_filename.split('/')
                        filename = path_parts[-1]  # Get just the filename
                        
                        # Try to extract directory structure info
                        if len(path_parts) >= 5 and 'Light' in old_filename:
                            # Extract metadata from path
                            old_object = path_parts[-5] if path_parts[-6] == 'Light' else None
                            telescope = path_parts[-4] if old_object else None
                            instrument = path_parts[-3] if telescope else None
                            date_dir = path_parts[-2] if instrument else None
                            
                            if old_object and telescope and instrument and date_dir:
                                # Create new directory structure with new object name
                                new_object_clean = to_object.replace(" ", "").replace("-", "")
                                new_dir_path = f"{repo_folder}Light/{new_object_clean}/{telescope}/{instrument}/{date_dir}/"
                                
                                # Parse filename to update object name in filename
                                filename_parts = filename.split('-')
                                if len(filename_parts) >= 2:
                                    # Replace the first part (object name) with the new object name
                                    filename_parts[0] = new_object_clean
                                    new_filename = '-'.join(filename_parts)
                                    new_full_path = new_dir_path + new_filename
                                    
                                    # Create new directory if it doesn't exist
                                    if not os.path.exists(new_dir_path):
                                        try:
                                            os.makedirs(new_dir_path, exist_ok=True)
                                            logger.info(f"Created directory: {new_dir_path}")
                                        except OSError as e:
                                            error_msg = f"Cannot create directory {new_dir_path}: {str(e)}"
                                            errors.append(error_msg)
                                            logger.error(error_msg)
                                            continue
                                    
                                    # Move and rename the file
                                    if old_filename != new_full_path:
                                        if not os.path.exists(new_full_path):
                                            try:
                                                os.rename(old_filename, new_full_path)
                                                # Verify the file was actually moved/renamed
                                                if not os.path.exists(new_full_path):
                                                    error_msg = f"File move verification failed: {new_full_path} does not exist after rename"
                                                    errors.append(error_msg)
                                                    logger.error(error_msg)
                                                    file_operation_successful = False
                                                    continue
                                                elif os.path.exists(old_filename):
                                                    error_msg = f"File move verification failed: {old_filename} still exists after rename"
                                                    errors.append(error_msg)
                                                    logger.error(error_msg)
                                                    file_operation_successful = False
                                                    continue
                                                
                                                # File move successful, now update FITS header
                                                renamed_count += 1
                                                moved_count += 1
                                                logger.info(f"Moved and renamed file: {old_filename} → {new_full_path}")
                                                
                                                # Update FITS header with new object name
                                                try:
                                                    with fits.open(new_full_path, mode='update') as hdul:
                                                        if 'OBJECT' in hdul[0].header:
                                                            old_object_name = hdul[0].header['OBJECT']
                                                            hdul[0].header['OBJECT'] = to_object
                                                            # Add comment about the change
                                                            hdul[0].header.comments['OBJECT'] = f'Updated from {old_object_name} via Astrofiler merge'
                                                            hdul.flush()
                                                            header_updated_count += 1
                                                            logger.info(f"Updated OBJECT header from '{old_object_name}' to '{to_object}' in {new_full_path}")
                                                        else:
                                                            # Add OBJECT header if it doesn't exist
                                                            hdul[0].header['OBJECT'] = to_object
                                                            hdul[0].header.comments['OBJECT'] = 'Added via Astrofiler merge'
                                                            hdul.flush()
                                                            header_updated_count += 1
                                                            logger.info(f"Added OBJECT header '{to_object}' to {new_full_path}")
                                                except Exception as fits_error:
                                                    error_msg = f"FITS header update failed for {new_full_path}: {str(fits_error)}"
                                                    errors.append(error_msg)
                                                    logger.error(error_msg)
                                                    # Header update failure doesn't fail the file operation
                                                    
                                            except OSError as e:
                                                error_msg = f"Cannot move/rename {old_filename}: {str(e)}"
                                                errors.append(error_msg)
                                                logger.error(error_msg)
                                                file_operation_successful = False
                                                continue
                                        else:
                                            error_msg = f"Cannot move {old_filename} - target file already exists: {new_full_path}"
                                            errors.append(error_msg)
                                            logger.warning(error_msg)
                                            file_operation_successful = False
                                    else:
                                        logger.debug(f"No move needed for {old_filename} (already in correct location)")
                                else:
                                    error_msg = f"Cannot parse filename format for {filename}"
                                    errors.append(error_msg)
                                    logger.error(error_msg)
                            else:
                                # Fallback to simple rename without moving directories
                                filename_parts = filename.split('-')
                                if len(filename_parts) >= 2:
                                    new_object_name = to_object.replace(" ", "_").replace("-", "")
                                    filename_parts[0] = new_object_name
                                    new_filename = '-'.join(filename_parts)
                                    new_full_path = '/'.join(path_parts[:-1] + [new_filename])
                                    
                                    if old_filename != new_full_path:
                                        if not os.path.exists(new_full_path):
                                            try:
                                                os.rename(old_filename, new_full_path)
                                                # Verify the file was actually renamed
                                                if not os.path.exists(new_full_path):
                                                    error_msg = f"File rename verification failed: {new_full_path} does not exist after rename"
                                                    errors.append(error_msg)
                                                    logger.error(error_msg)
                                                    file_operation_successful = False
                                                    continue
                                                elif os.path.exists(old_filename):
                                                    error_msg = f"File rename verification failed: {old_filename} still exists after rename"
                                                    errors.append(error_msg)
                                                    logger.error(error_msg)
                                                    file_operation_successful = False
                                                    continue
                                                
                                                # File rename successful
                                                renamed_count += 1
                                                logger.info(f"Renamed file: {old_filename} → {new_full_path}")
                                                
                                                # Update FITS header with new object name
                                                try:
                                                    with fits.open(new_full_path, mode='update') as hdul:
                                                        if 'OBJECT' in hdul[0].header:
                                                            old_object_name = hdul[0].header['OBJECT']
                                                            hdul[0].header['OBJECT'] = to_object
                                                            # Add comment about the change
                                                            hdul[0].header.comments['OBJECT'] = f'Updated from {old_object_name} via Astrofiler merge'
                                                            hdul.flush()
                                                            header_updated_count += 1
                                                            logger.info(f"Updated OBJECT header from '{old_object_name}' to '{to_object}' in {new_full_path}")
                                                        else:
                                                            # Add OBJECT header if it doesn't exist
                                                            hdul[0].header['OBJECT'] = to_object
                                                            hdul[0].header.comments['OBJECT'] = 'Added via Astrofiler merge'
                                                            hdul.flush()
                                                            header_updated_count += 1
                                                            logger.info(f"Added OBJECT header '{to_object}' to {new_full_path}")
                                                except Exception as fits_error:
                                                    error_msg = f"FITS header update failed for {new_full_path}: {str(fits_error)}"
                                                    errors.append(error_msg)
                                                    logger.error(error_msg)
                                                    # Header update failure doesn't fail the file operation
                                                    
                                            except OSError as e:
                                                error_msg = f"Cannot rename {old_filename}: {str(e)}"
                                                errors.append(error_msg)
                                                logger.error(error_msg)
                                                file_operation_successful = False
                                                continue
                                        else:
                                            error_msg = f"Cannot rename {old_filename} - target file already exists: {new_full_path}"
                                            errors.append(error_msg)
                                            logger.warning(error_msg)
                                            file_operation_successful = False
                                else:
                                    error_msg = f"Cannot parse filename format for {filename}"
                                    errors.append(error_msg)
                                    logger.error(error_msg)
                        else:
                            # Handle non-standard path structure with simple rename
                            filename_parts = filename.split('-')
                            if len(filename_parts) >= 2:
                                new_object_name = to_object.replace(" ", "_").replace("-", "")
                                filename_parts[0] = new_object_name
                                new_filename = '-'.join(filename_parts)
                                new_full_path = '/'.join(path_parts[:-1] + [new_filename])
                                
                                if old_filename != new_full_path:
                                    if not os.path.exists(new_full_path):
                                        try:
                                            os.rename(old_filename, new_full_path)
                                            # Verify the file was actually renamed
                                            if not os.path.exists(new_full_path):
                                                error_msg = f"File rename verification failed: {new_full_path} does not exist after rename"
                                                errors.append(error_msg)
                                                logger.error(error_msg)
                                                file_operation_successful = False
                                                continue
                                            elif os.path.exists(old_filename):
                                                error_msg = f"File rename verification failed: {old_filename} still exists after rename"
                                                errors.append(error_msg)
                                                logger.error(error_msg)
                                                file_operation_successful = False
                                                continue
                                            
                                            # File rename successful
                                            renamed_count += 1
                                            logger.info(f"Renamed file: {old_filename} → {new_full_path}")
                                            
                                            # Update FITS header with new object name
                                            try:
                                                with fits.open(new_full_path, mode='update') as hdul:
                                                    if 'OBJECT' in hdul[0].header:
                                                        old_object_name = hdul[0].header['OBJECT']
                                                        hdul[0].header['OBJECT'] = to_object
                                                        # Add comment about the change
                                                        hdul[0].header.comments['OBJECT'] = f'Updated from {old_object_name} via Astrofiler merge'
                                                        hdul.flush()
                                                        header_updated_count += 1
                                                        logger.info(f"Updated OBJECT header from '{old_object_name}' to '{to_object}' in {new_full_path}")
                                                    else:
                                                        # Add OBJECT header if it doesn't exist
                                                        hdul[0].header['OBJECT'] = to_object
                                                        hdul[0].header.comments['OBJECT'] = 'Added via Astrofiler merge'
                                                        hdul.flush()
                                                        header_updated_count += 1
                                                        logger.info(f"Added OBJECT header '{to_object}' to {new_full_path}")
                                            except Exception as fits_error:
                                                error_msg = f"FITS header update failed for {new_full_path}: {str(fits_error)}"
                                                errors.append(error_msg)
                                                logger.error(error_msg)
                                                # Header update failure doesn't fail the file operation
                                                
                                        except OSError as e:
                                            error_msg = f"Cannot rename {old_filename}: {str(e)}"
                                            errors.append(error_msg)
                                            logger.error(error_msg)
                                            file_operation_successful = False
                                            continue
                                    else:
                                        error_msg = f"Cannot rename {old_filename} - target file already exists: {new_full_path}"
                                        errors.append(error_msg)
                                        logger.warning(error_msg)
                                        file_operation_successful = False
                            else:
                                error_msg = f"Cannot parse filename format for {filename}"
                                errors.append(error_msg)
                                logger.error(error_msg)
                                file_operation_successful = False
                    elif change_files and old_filename and not os.path.exists(old_filename):
                        error_msg = f"File not found on disk: {old_filename}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        file_operation_successful = False
                    elif not change_files:
                        # Database-only operation, no file operations needed
                        logger.debug(f"Database-only merge for {old_filename}")
                    
                    # Only update database if file operations were successful (or if not changing files)
                    if file_operation_successful:
                        # Update database record with new object name
                        fits_file.fitsFileObject = to_object
                        
                        # Update filename in database if file was actually moved/renamed
                        if new_full_path and change_files:
                            fits_file.fitsFileName = new_full_path
                        
                        fits_file.save()
                        merged_count += 1
                        logger.debug(f"Database updated for file: {fits_file.fitsFileName}")
                    else:
                        logger.warning(f"Skipping database update for {old_filename} due to file operation failure")
                    
                except Exception as e:
                    error_msg = f"Error processing {fits_file.fitsFileName}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    logger.exception("Full exception details for merge error:")  # This logs the full stack trace
            
            # Update Sessions that reference the old object name
            Sessions_updated = 0
            try:
                from astrofiler_db import fitsSession as FitsSessionModel
                Sessions = FitsSessionModel.select().where(FitsSessionModel.fitsSessionObjectName == from_object)
                for Session in Sessions:
                    try:
                        Session.fitsSessionObjectName = to_object
                        Session.save()
                        Sessions_updated += 1
                        logger.debug(f"Updated session {Session.fitsSessionId} object name from '{from_object}' to '{to_object}'")
                    except Exception as e:
                        error_msg = f"Error updating session {Session.fitsSessionId}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
            except Exception as e:
                error_msg = f"Error querying/updating Sessions: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                logger.exception("Full exception details for session update error:")
            
            # Log summary of operation
            logger.info(f"Merge operation summary: {merged_count} records processed, {renamed_count} files renamed, {moved_count} files moved, {header_updated_count} FITS headers updated, {Sessions_updated} sessions updated, {len(errors)} errors encountered")
            
            # Log all errors for debugging
            if errors:
                logger.error(f"Merge operation completed with {len(errors)} errors:")
                for i, error in enumerate(errors, 1):
                    logger.error(f"Error {i}: {error}")
            
            result_text += f"Database records updated: {merged_count}\n"
            if change_files:
                result_text += f"Files renamed on disk: {renamed_count}\n"
                result_text += f"Files moved to new directory structure: {moved_count}\n"
                if header_updated_count > 0:
                    result_text += f"FITS headers updated: {header_updated_count}\n"
            result_text += f"Sessions updated: {Sessions_updated}\n"
            
            if errors:
                result_text += f"\nErrors encountered ({len(errors)} total):\n"
                for error in errors:
                    result_text += f"- {error}\n"
            
            result_text += f"\nMerge completed!"
            
            self.results_text.setPlainText(result_text)
            
            # Show success message
            if errors:
                QMessageBox.warning(self, "Merge Completed with Errors", 
                                  f"Merge completed but {len(errors)} errors occurred. Check results and log for details.")
                logger.warning(f"Merge operation completed with {len(errors)} errors. User notified.")
            else:
                QMessageBox.information(self, "Merge Successful", 
                                      f"Successfully merged {merged_count} records from '{from_object}' to '{to_object}'.")
                logger.info(f"Merge operation completed successfully without errors.")
            
        except Exception as e:
            error_msg = f"Critical error during merge execution: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full exception details for critical merge error:")
            QMessageBox.critical(self, "Merge Error", f"A critical error occurred during merge: {str(e)}\n\nCheck the log file for detailed error information.")
            self.results_text.setPlainText(f"CRITICAL ERROR: {error_msg}\n\nPlease check the log file for detailed error information.")
    
    def open_mappings_dialog(self):
        """Open the mappings dialog"""
        try:
            dialog = MappingsDialog(self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening mappings dialog: {e}")
            QMessageBox.critical(self, "Error", f"Error opening mappings dialog: {e}")


class ConfigTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_settings()  # Load settings after UI is initialized
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # General settings group
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout(general_group)
        
        # Source Path with directory picker
        source_path_layout = QHBoxLayout()
        self.source_path = QLineEdit()
        self.source_path_button = QPushButton("Browse...")
        self.source_path_button.clicked.connect(self.browse_source_path)
        source_path_layout.addWidget(self.source_path)
        source_path_layout.addWidget(self.source_path_button)
        
        # Repository Path with directory picker
        repo_path_layout = QHBoxLayout()
        self.repo_path = QLineEdit()
        self.repo_path_button = QPushButton("Browse...")
        self.repo_path_button.clicked.connect(self.browse_repo_path)
        repo_path_layout.addWidget(self.repo_path)
        repo_path_layout.addWidget(self.repo_path_button)
        
        # Refresh on Startup (default checked)
        self.refresh_on_startup = QCheckBox()
        self.refresh_on_startup.setChecked(True)  # Default to true
        
        # Save modified headers (default unchecked)
        self.save_modified_headers = QCheckBox()
        self.save_modified_headers.setChecked(False)  # Default to false for safety
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
        self.theme.setCurrentText("Dark")  # Default to dark theme
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
        self.fits_viewer_button.clicked.connect(self.browse_fits_viewer)
        fits_viewer_layout.addWidget(self.fits_viewer_path)
        fits_viewer_layout.addWidget(self.fits_viewer_button)
        
        tools_layout.addRow("FITS Viewer:", fits_viewer_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Settings")
        self.reset_button = QPushButton("Reset to Defaults")
        self.import_button = QPushButton("Import Config")
        self.export_button = QPushButton("Export Config")
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.import_button)
        button_layout.addWidget(self.export_button)
        button_layout.addStretch()
        
        layout.addWidget(general_group)
        layout.addWidget(display_group)
        layout.addWidget(tools_group)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        # Connect signals
        self.save_button.clicked.connect(self.save_settings)
        self.reset_button.clicked.connect(self.reset_settings)
        self.theme.currentTextChanged.connect(self.on_theme_changed)
    
    def save_settings(self):
        """Save configuration settings to astrofiler.ini file"""
        try:
            config = configparser.ConfigParser()
            
            # Get paths and ensure they end with a slash
            source_path = self.source_path.text().strip()
            repo_path = self.repo_path.text().strip()
            
            # Automatically append slash if not present
            if source_path and not source_path.endswith('/') and not source_path.endswith('\\'):
                source_path += '/'
            if repo_path and not repo_path.endswith('/') and not repo_path.endswith('\\'):
                repo_path += '/'
            
            # Update the GUI fields with the corrected paths
            self.source_path.setText(source_path)
            self.repo_path.setText(repo_path)
            
            # Validate that source and repository paths are different
            if source_path and repo_path and os.path.abspath(source_path) == os.path.abspath(repo_path):
                QMessageBox.warning(self, "Invalid Configuration", 
                                  "Source and Repository paths cannot be the same.\n\n"
                                  "The source path is for incoming files, while the repository "
                                  "path is for organized storage. They must be different directories.")
                return
            
            # Save the path settings directly to DEFAULT section
            config['DEFAULT'] = {
                'source': source_path,
                'repo': repo_path,
                'refresh_on_startup': str(self.refresh_on_startup.isChecked()),
                'save_modified_headers': str(self.save_modified_headers.isChecked()),
                'theme': self.theme.currentText(),
                'font_size': str(self.font_size.value()),
                'grid_size': str(self.grid_size.value()),
                'fits_viewer_path': self.fits_viewer_path.text().strip()
            }
            
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
    
    def on_theme_changed(self, theme_name):
        """Handle theme changes"""
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


class AboutTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a container widget that will hold both background and text
        self.container = QWidget()
        self.container.setMinimumSize(800, 600)
        
        # Create background label
        self.background_label = QLabel(self.container)
        self.background_label.setAlignment(Qt.AlignCenter)
        self.background_label.setGeometry(0, 0, 800, 600)
        
        # Create text overlay widget with transparent background
        self.text_widget = QWidget(self.container)
        self.text_widget.setStyleSheet("background-color: transparent;")
        text_layout = QVBoxLayout(self.text_widget)
        text_layout.setAlignment(Qt.AlignCenter)
        
        # Main title
        self.title_label = QLabel(f"AstroFiler Version {VERSION}")
        title_font = QFont()
        title_font.setPointSize(32)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 120);
                padding: 20px;
                border-radius: 10px;
                margin: 10px;
            }
        """)
        
        # Subtitle
        self.subtitle_label = QLabel("By Gord Tulloch\nJuly 2025\n\nQuestions to:\nEmail: gord.tulloch@gmail.com\nGithub: https://github.com/gordtulloch/astrofiler-gui\n\nContributions gratefully accepted via\nPaypal to the above email address.")
        subtitle_font = QFont()
        subtitle_font.setPointSize(16)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 120);
                padding: 15px;
                border-radius: 10px;
                margin: 10px;
            }
        """)
        
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)
        
        layout.addWidget(self.container)
        
        # Set default background first
        self.set_default_background()
        
        # Then try to load the actual background image
        self.load_background_image()
    
    def load_background_image(self):
        """Load the background image from local images/background.jpg file"""
        try:
            # Try to load the image from the images directory
            pixmap = QPixmap("images/background.jpg")
            
            if not pixmap.isNull():
                # Get the size of the container
                container_size = self.container.size()
                if container_size.width() <= 0:
                    # Use minimum size if widget not yet properly sized
                    container_size = self.container.minimumSize()
                
                # Scale the image to fit the container while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    container_size, 
                    Qt.KeepAspectRatioByExpanding, 
                    Qt.SmoothTransformation
                )
                
                self.background_label.setPixmap(scaled_pixmap)
                self.background_label.setScaledContents(True)
                logger.debug("Successfully loaded images/background.jpg as background")
            else:
                # If image loading fails, use the default background
                logger.warning("Failed to load images/background.jpg, using default background")
                self.set_default_background()
        except Exception as e:
            logger.error(f"Error loading background image: {e}")
            self.set_default_background()
    
    def set_default_background(self):
        """Set a default starry background if image download fails"""
        self.background_label.setStyleSheet("""
            QLabel {
                background: qradialgradient(cx:0.5, cy:0.5, radius:1.0,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1.0 #0f0f23);
            }
        """)
    
    def resizeEvent(self, event):
        """Handle resize events to reposition text overlay and reload background"""
        super().resizeEvent(event)
        if hasattr(self, 'container') and hasattr(self, 'background_label') and hasattr(self, 'text_widget'):
            # Resize container and its children
            container_size = self.container.size()
            self.background_label.resize(container_size)
            self.text_widget.resize(container_size)
            # Reload the background image with new size
            self.load_background_image()
    
    def showEvent(self, event):
        """Handle show events to ensure background loads when tab is visible"""
        super().showEvent(event)
        # Load background when tab becomes visible and ensure text positioning
        if hasattr(self, 'container') and hasattr(self, 'background_label') and hasattr(self, 'text_widget'):
            container_size = self.container.size()
            self.background_label.resize(container_size)
            self.text_widget.resize(container_size)
        self.load_background_image()


class LogTab(QWidget):
    """Tab for displaying and managing log files"""
    
    def __init__(self):
        super().__init__()
        self.log_file_path = "astrofiler.log"
        self.init_ui()
        self.load_log_content()
    
    def init_ui(self):
        """Initialize the log tab UI"""
        layout = QVBoxLayout(self)
        
        # Controls layout with Clear button
        controls_layout = QHBoxLayout()
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_log)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_log_content)
        
        controls_layout.addWidget(self.clear_button)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addStretch()  # Push buttons to the left
        
        # Log display area with horizontal and vertical scrolling
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)  # Enable horizontal scrolling
        self.log_text.setFont(QFont("Courier", 9))  # Monospace font for logs
        
        layout.addLayout(controls_layout)
        layout.addWidget(self.log_text)
    
    def load_log_content(self):
        """Load the current log file content into the text area"""
        try:
            if os.path.exists(self.log_file_path):
                with open(self.log_file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    self.log_text.setPlainText(content)
                    # Scroll to the bottom to show latest entries
                    cursor = self.log_text.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    self.log_text.setTextCursor(cursor)
                    logger.debug("Log content loaded successfully")
            else:
                self.log_text.setPlainText("Log file not found.")
                logger.warning(f"Log file not found: {self.log_file_path}")
        except Exception as e:
            self.log_text.setPlainText(f"Error loading log file: {str(e)}")
            logger.error(f"Error loading log file: {e}")
    
    def clear_log(self):
        """Clear the log file by deleting it and creating an empty file"""
        try:
            if os.path.exists(self.log_file_path):
                os.remove(self.log_file_path)
            
            # Create an empty log file
            with open(self.log_file_path, 'w', encoding='utf-8') as file:
                pass
            
            # Clear the display
            self.log_text.clear()
            
            # Log this action (this will recreate the log file with the first entry)
            logger.info("Log file cleared by user")
            
            # Reload to show the new log entry
            self.load_log_content()
            
            QMessageBox.information(self, "Success", "Log file cleared successfully!")
            
        except Exception as e:
            logger.error(f"Error clearing log file: {e}")
            QMessageBox.warning(self, "Error", f"Failed to clear log file: {str(e)}")


class DuplicatesTab(QWidget):
    """Tab for managing duplicate FITS files"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.refresh_duplicates()
    
    def init_ui(self):
        """Initialize the duplicates tab UI"""
        layout = QVBoxLayout(self)
        
        # Title and description
        title_label = QLabel("Duplicate Files Management")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        description = QLabel("Files with identical content (same hash) are considered duplicates.\n"
                           "You can safely remove all but one copy of each duplicate group.")
        description.setAlignment(Qt.AlignCenter)
        description.setStyleSheet("margin: 5px;")
        layout.addWidget(description)
        
        # Refresh button
        refresh_button = QPushButton("Refresh Duplicates")
        refresh_button.clicked.connect(self.refresh_duplicates)
        layout.addWidget(refresh_button)
        
        # Duplicates tree widget
        self.duplicates_tree = QTreeWidget()
        self.duplicates_tree.setHeaderLabels(["File", "Object", "Date", "Filter", "Exposure", "Type"])
        self.duplicates_tree.setAlternatingRowColors(True)
        self.duplicates_tree.setSortingEnabled(True)
        layout.addWidget(self.duplicates_tree)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Delete duplicates button
        self.delete_button = QPushButton("Delete Duplicate Files")
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #cccccc;
            }
        """)
        self.delete_button.clicked.connect(self.delete_duplicates)
        self.delete_button.setEnabled(False)
        
        # Info label
        self.info_label = QLabel("No duplicates found.")
        self.info_label.setAlignment(Qt.AlignLeft)
        
        button_layout.addWidget(self.info_label)
        button_layout.addStretch()
        button_layout.addWidget(self.delete_button)
        
        layout.addLayout(button_layout)
    
    def refresh_duplicates(self):
        """Refresh the list of duplicate files"""
        from astrofiler_db import fitsFile
        
        self.duplicates_tree.clear()
        duplicate_groups = []
        
        try:
            # Query for files with duplicate hashes
            query = """
            SELECT fitsFileHash, COUNT(*) as count
            FROM fitsfile 
            WHERE fitsFileHash IS NOT NULL 
            GROUP BY fitsFileHash 
            HAVING COUNT(*) > 1
            """
            
            import sqlite3
            conn = sqlite3.connect('astrofiler.db')
            cursor = conn.cursor()
            cursor.execute(query)
            duplicate_hashes = cursor.fetchall()
            conn.close()
            
            total_duplicates = 0
            
            for hash_value, count in duplicate_hashes:
                # Get all files with this hash
                files_with_hash = fitsFile.select().where(fitsFile.fitsFileHash == hash_value)
                
                if files_with_hash.count() > 1:
                    # Create a parent item for this duplicate group
                    group_item = QTreeWidgetItem(self.duplicates_tree)
                    group_item.setText(0, f"Duplicate Group (Hash: {hash_value[:16]}...)")
                    group_item.setText(1, f"{count} files")
                    group_item.setExpanded(True)
                    
                    # Style the group item
                    font = group_item.font(0)
                    font.setBold(True)
                    for i in range(6):
                        group_item.setFont(i, font)
                    
                    # Add individual files as children
                    for fits_file in files_with_hash:
                        file_item = QTreeWidgetItem(group_item)
                        file_item.setText(0, os.path.basename(fits_file.fitsFileName or "Unknown"))
                        file_item.setText(1, fits_file.fitsFileObject or "Unknown")
                        file_item.setText(2, str(fits_file.fitsFileDate) if fits_file.fitsFileDate else "Unknown")
                        file_item.setText(3, fits_file.fitsFileFilter or "Unknown")
                        file_item.setText(4, str(fits_file.fitsFileExpTime) if fits_file.fitsFileExpTime else "Unknown")
                        file_item.setText(5, fits_file.fitsFileType or "Unknown")
                        
                        # Store the file object for deletion
                        file_item.setData(0, Qt.UserRole, fits_file)
                    
                    duplicate_groups.append((hash_value, count))
                    total_duplicates += count - 1  # count - 1 because we keep one copy
            
            # Update info label and button state
            if duplicate_groups:
                self.info_label.setText(f"Found {len(duplicate_groups)} duplicate groups with {total_duplicates} files that can be removed.")
                self.delete_button.setEnabled(True)
            else:
                self.info_label.setText("No duplicate files found.")
                self.delete_button.setEnabled(False)
                
        except Exception as e:
            logging.error(f"Error refreshing duplicates: {str(e)}")
            self.info_label.setText(f"Error loading duplicates: {str(e)}")
            self.delete_button.setEnabled(False)
    
    def delete_duplicates(self):
        """Delete duplicate files, keeping only one copy of each"""
        from astrofiler_db import fitsFile
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            "This will permanently delete duplicate files from both the database and disk.\n"
            "One copy of each file will be kept. This action cannot be undone.\n\n"
            "Are you sure you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        deleted_count = 0
        error_count = 0
        
        try:
            # Get all duplicate groups
            query = """
            SELECT fitsFileHash
            FROM fitsfile 
            WHERE fitsFileHash IS NOT NULL 
            GROUP BY fitsFileHash 
            HAVING COUNT(*) > 1
            """
            
            import sqlite3
            conn = sqlite3.connect('astrofiler.db')
            cursor = conn.cursor()
            cursor.execute(query)
            duplicate_hashes = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            for hash_value in duplicate_hashes:
                # Get all files with this hash, ordered by date (keep the earliest)
                files_with_hash = fitsFile.select().where(fitsFile.fitsFileHash == hash_value).order_by(fitsFile.fitsFileDate)
                files_list = list(files_with_hash)
                
                if len(files_list) > 1:
                    # Keep the first file, delete the rest
                    files_to_delete = files_list[1:]
                    
                    for fits_file in files_to_delete:
                        try:
                            # Delete the physical file if it exists
                            if fits_file.fitsFileName and os.path.exists(fits_file.fitsFileName):
                                os.remove(fits_file.fitsFileName)
                                logging.info(f"Deleted file: {fits_file.fitsFileName}")
                            
                            # Delete from database
                            fits_file.delete_instance()
                            deleted_count += 1
                            
                        except Exception as e:
                            logging.error(f"Error deleting file {fits_file.fitsFileName}: {str(e)}")
                            error_count += 1
            
            # Show results
            if error_count == 0:
                QMessageBox.information(
                    self, 
                    "Deletion Complete", 
                    f"Successfully deleted {deleted_count} duplicate files."
                )
            else:
                QMessageBox.warning(
                    self, 
                    "Deletion Complete with Errors", 
                    f"Deleted {deleted_count} files successfully.\n"
                    f"Failed to delete {error_count} files. Check the log for details."
                )
            
            # Refresh the display
            self.refresh_duplicates()
            
        except Exception as e:
            logging.error(f"Error during duplicate deletion: {str(e)}")
            QMessageBox.critical(
                self, 
                "Deletion Error", 
                f"An error occurred during deletion: {str(e)}"
            )


class StatsTab(QWidget):
    def __init__(self):
        super().__init__()
        # Initialize cache variables
        self._stats_cache = {}
        self._cache_timestamp = None
        self._cache_validity_seconds = 300  # Cache valid for 5 minutes
        
        self.init_ui()
        self.load_stats_data()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 10)  # Reduce top margin from default
        layout.setSpacing(5)  # Reduce spacing between elements
        
        # Refresh button
        refresh_layout = QHBoxLayout()
        refresh_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins around button layout
        self.refresh_button = QPushButton("Refresh Stats")
        self.refresh_button.clicked.connect(self.force_refresh_stats)
        self.refresh_button.setToolTip("Force refresh of statistics (clears cache)")
        
        # Add cache status label
        self.cache_status_label = QLabel("")
        self.cache_status_label.setStyleSheet("color: gray; font-size: 10px;")
        
        refresh_layout.addWidget(self.refresh_button)
        refresh_layout.addWidget(self.cache_status_label)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # Main content area with horizontal splitter for two columns
        splitter = QSplitter(Qt.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Left column
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 0, 5, 5)  # Reduce margins
        left_layout.setSpacing(10)  # Reduce spacing between sections
        
        # Last 10 Objects Observed section
        recent_objects_label = QLabel("Last 10 Objects Observed")
        recent_objects_label.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(recent_objects_label)
        
        # Recent objects table - provide adequate space for 10 entries
        self.recent_objects_table = QTreeWidget()
        self.recent_objects_table.setMinimumHeight(280)  # Ensure space for 10 entries plus header
        self.recent_objects_table.setMaximumHeight(320)  # Limit to prevent excessive growth
        self.recent_objects_table.setHeaderLabels(["Rank", "Object Name", "Last Observed"])
        self.recent_objects_table.setRootIsDecorated(False)
        self.recent_objects_table.setAlternatingRowColors(True)
        
        # Set column widths for recent objects table
        self.recent_objects_table.setColumnWidth(0, 50)   # Rank
        self.recent_objects_table.setColumnWidth(1, 220)  # Object Name - increased width
        self.recent_objects_table.setColumnWidth(2, 120)  # Last Observed
        
        # Set header alignment
        self.recent_objects_table.headerItem().setTextAlignment(0, Qt.AlignCenter)  # Rank
        self.recent_objects_table.headerItem().setTextAlignment(2, Qt.AlignRight)   # Last Observed
        
        left_layout.addWidget(self.recent_objects_table)
        
        # Add spacing
        left_layout.addSpacing(10)  # Reduce spacing between sections
        
        # Summary Statistics section
        summary_label = QLabel("Summary Statistics")
        summary_label.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(summary_label)
        
        self.summary_table = QTreeWidget()
        self.summary_table.setMinimumHeight(160)   # Ensure adequate space for summary data
        self.summary_table.setMaximumHeight(200)   # Increased slightly for better visibility
        self.summary_table.setHeaderLabels(["Item", "Count"])
        self.summary_table.setRootIsDecorated(False)
        self.summary_table.setAlternatingRowColors(True)
        
        # Set column widths for summary table
        self.summary_table.setColumnWidth(0, 220)  # Item - increased width to match object name
        self.summary_table.setColumnWidth(1, 100)  # Count
        
        # Set header alignment for "Count" column
        self.summary_table.headerItem().setTextAlignment(1, Qt.AlignRight)
        
        left_layout.addWidget(self.summary_table)
        
        # Don't add stretch - let content naturally fill the space
        # left_layout.addStretch()  # Removed to prevent excessive spacing in fullscreen
        
        splitter.addWidget(left_widget)
        
        # Right column
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 5, 5)  # Reduce margins
        right_layout.setSpacing(10)  # Reduce spacing between sections
        
        # Top 10 Objects section
        objects_label = QLabel("Top 10 Objects by Total Integration Time")
        objects_label.setFont(QFont("Arial", 12, QFont.Bold))
        right_layout.addWidget(objects_label)
        
        # Objects table with columns - give it more dedicated space
        self.objects_table = QTreeWidget()
        self.objects_table.setMinimumHeight(280)  # Increased minimum height
        self.objects_table.setMaximumHeight(350)  # Increased maximum height for better space
        self.objects_table.setHeaderLabels(["Rank", "Object Name", "Total Seconds"])
        self.objects_table.setRootIsDecorated(False)
        self.objects_table.setAlternatingRowColors(True)
        
        # Set column widths - make object name column wider
        self.objects_table.setColumnWidth(0, 50)   # Rank
        self.objects_table.setColumnWidth(1, 220)  # Object Name - increased width
        self.objects_table.setColumnWidth(2, 120)  # Total Seconds
        
        # Set header alignment for "Total Seconds" column
        self.objects_table.headerItem().setTextAlignment(0, Qt.AlignCenter)  # Rank
        self.objects_table.headerItem().setTextAlignment(2, Qt.AlignRight)   # Total Seconds
        
        right_layout.addWidget(self.objects_table)
        
        # Add spacing
        right_layout.addSpacing(10)  # Reduce spacing between sections
        
        # Filter Chart section
        chart_label = QLabel("Total Imaging Time by Filter")
        chart_label.setFont(QFont("Arial", 12, QFont.Bold))
        right_layout.addWidget(chart_label)
        
        # Chart area - responsive sizing that scales with window
        self.chart_label = QLabel()
        self.chart_label.setMinimumSize(300, 250)  # Minimum size to ensure readability
        self.chart_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Allow expansion
        self.chart_label.setAlignment(Qt.AlignCenter)
        self.chart_label.setStyleSheet("border: 1px solid gray; background-color: white;")
        right_layout.addWidget(self.chart_label)
        
        # Don't add stretch - let content naturally fill the space  
        # right_layout.addStretch()  # Removed to prevent excessive spacing in fullscreen
        
        splitter.addWidget(right_widget)
        
        # Set splitter proportions - give right side slightly more space for the data table
        splitter.setSizes([380, 450])
        
        # Add the splitter to the main layout
        layout.addWidget(splitter)
        
        # Add stretch at the bottom to push content to top in fullscreen mode
        layout.addStretch(1)  # Use factor of 1 to control expansion
    
    def _is_cache_valid(self):
        """Check if the stats cache is still valid"""
        if self._cache_timestamp is None:
            return False
        
        import time
        current_time = time.time()
        cache_age = current_time - self._cache_timestamp
        
        return cache_age < self._cache_validity_seconds
    
    def _update_cache_status(self):
        """Update the cache status label"""
        if self._cache_timestamp is None:
            self.cache_status_label.setText("")
        else:
            import time
            cache_age = int(time.time() - self._cache_timestamp)
            if cache_age < 60:
                self.cache_status_label.setText(f"Cache: {cache_age}s ago")
            else:
                minutes = cache_age // 60
                self.cache_status_label.setText(f"Cache: {minutes}m ago")
    
    def _invalidate_cache(self):
        """Invalidate the stats cache"""
        self._stats_cache.clear()
        self._cache_timestamp = None
        self.cache_status_label.setText("")
        logger.debug("Stats cache invalidated")
    
    def force_refresh_stats(self):
        """Force refresh statistics by clearing cache first"""
        self._invalidate_cache()
        self.load_stats_data()
    
    def invalidate_stats_cache(self):
        """Public method to invalidate stats cache when data changes"""
        self._invalidate_cache()
        logger.debug("Stats cache invalidated due to data changes")
    
    def set_cache_validity_duration(self, seconds):
        """Set how long the cache remains valid (in seconds)"""
        self._cache_validity_seconds = seconds
        logger.debug(f"Stats cache validity duration set to {seconds} seconds")
    
    def load_stats_data(self):
        """Load and display statistics data with caching"""
        try:
            # Check if we can use cached data
            if self._is_cache_valid():
                logger.debug("Using cached statistics data")
                self._load_from_cache()
                self._update_cache_status()
                return
            
            # Cache is invalid, load fresh data
            logger.debug("Loading fresh statistics data")
            
            # Load last 10 objects observed
            self.load_recent_objects()
            
            # Load summary statistics
            self.load_summary_stats()
            
            # Load top 10 objects by integration time
            self.load_top_objects()
            
            # Load and create pie chart for filters
            self.create_filter_pie_chart()
            
            # Update cache timestamp
            import time
            self._cache_timestamp = time.time()
            self._update_cache_status()
            
            logger.debug("Statistics data loaded and cached")
            
        except Exception as e:
            logging.error(f"Error loading stats data: {str(e)}")
            QMessageBox.warning(self, "Stats Error", f"Error loading statistics: {str(e)}")
    
    def _load_from_cache(self):
        """Load statistics from cache if available"""
        # Note: Since the data is displayed in Qt widgets, we don't need to cache the actual data
        # The widgets retain their state, so we just need to avoid requerying the database
        # This method exists for completeness and future enhancements
        pass
    
    def load_recent_objects(self):
        """Load last 10 objects observed based on most recent sessions"""
        try:
            self.recent_objects_table.clear()
            
            # Query to get the 10 most recent light sessions with their objects and dates
            # We need to get unique objects from the most recent sessions
            from peewee import fn
            
            query = (FitsSessionModel
                    .select(FitsSessionModel.fitsSessionObjectName, 
                           fn.MAX(FitsSessionModel.fitsSessionDate).alias('last_observed'))
                    .where(FitsSessionModel.fitsSessionObjectName.is_null(False),
                           FitsSessionModel.fitsSessionObjectName != 'Bias',
                           FitsSessionModel.fitsSessionObjectName != 'Dark',
                           FitsSessionModel.fitsSessionObjectName != 'Flat')
                    .group_by(FitsSessionModel.fitsSessionObjectName)
                    .order_by(fn.MAX(FitsSessionModel.fitsSessionDate).desc())
                    .limit(10))
            
            for i, session in enumerate(query, 1):
                # Format the date for display
                last_observed_str = str(session.last_observed) if session.last_observed else "Unknown"
                
                # Create table row
                item = QTreeWidgetItem([
                    str(i),                          # Rank
                    session.fitsSessionObjectName,  # Object Name
                    last_observed_str                # Last Observed
                ])
                
                # Center-align rank column, right-align date column
                item.setTextAlignment(0, Qt.AlignCenter)  # Rank
                item.setTextAlignment(2, Qt.AlignRight)   # Last Observed
                
                self.recent_objects_table.addTopLevelItem(item)
                
        except Exception as e:
            logging.error(f"Error loading recent objects: {str(e)}")
            # Add error item to table
            error_item = QTreeWidgetItem([
                "Error",
                f"Failed to load data: {str(e)}",
                ""
            ])
            self.recent_objects_table.addTopLevelItem(error_item)
    
    def load_summary_stats(self):
        """Load summary statistics for FITS files and sessions"""
        try:
            self.summary_table.clear()
            
            # Count different types of FITS files
            total_lights = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains('Light')).count()
            total_darks = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains('Dark')).count()
            total_biases = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains('Bias')).count()
            total_flats = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains('Flat')).count()
            
            # Count total sessions
            total_sessions = FitsSessionModel.select().count()
            
            # Count unique nights of imaging (using 12-hour period definition)
            from peewee import fn
            try:
                # Get all distinct dates from light frames, then group by 12-hour periods
                light_files = (FitsFileModel
                             .select(FitsFileModel.fitsFileDate)
                             .where(FitsFileModel.fitsFileType.contains('Light'),
                                   FitsFileModel.fitsFileDate.is_null(False))
                             .distinct())
                
                # Convert to list and process dates to group by astronomical nights
                dates = [file.fitsFileDate for file in light_files]
                if dates:
                    total_nights = self._count_astronomical_nights(dates)
                else:
                    total_nights = 0
            except Exception as date_error:
                logging.warning(f"Error calculating unique nights: {str(date_error)}")
                total_nights = 0
            
            # Create summary items
            summary_items = [
                ("Total Lights", total_lights),
                ("Total Darks", total_darks),
                ("Total Biases", total_biases),
                ("Total Flats", total_flats),
                ("Total Sessions", total_sessions),
                ("Total Nights Imaging", total_nights)
            ]
            
            for item_name, count in summary_items:
                item = QTreeWidgetItem([
                    item_name,
                    f"{count:,}"  # Format with commas for large numbers
                ])
                
                # Right-align the count column
                item.setTextAlignment(1, Qt.AlignRight)
                
                self.summary_table.addTopLevelItem(item)
                
        except Exception as e:
            logging.error(f"Error loading summary stats: {str(e)}")
            # Add error item to table
            error_item = QTreeWidgetItem([
                "Error loading summary",
                "N/A"
            ])
            self.summary_table.addTopLevelItem(error_item)
    
    def _count_astronomical_nights(self, dates):
        """
        Count unique astronomical nights from a list of dates.
        An astronomical night is defined as a 12-hour period surrounding midnight.
        Two dates belong to the same night if they are within 12 hours of each other.
        """
        if not dates:
            return 0
        
        # Convert all dates to datetime objects for proper comparison
        datetime_objects = []
        for date in dates:
            if date is None:
                continue
                
            try:
                # Handle different date formats
                if isinstance(date, str):
                    # Try parsing different date string formats
                    if 'T' in date:
                        # ISO format with time: 2023-07-15T03:26:15
                        dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    elif ' ' in date and len(date) > 10:
                        # Space-separated format: 2023-07-15 03:26:15
                        dt = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                    else:
                        # Just date: 2023-07-15
                        dt = datetime.strptime(date, '%Y-%m-%d')
                elif hasattr(date, 'strftime'):
                    # It's already a datetime or date object
                    if hasattr(date, 'hour'):
                        dt = date  # It's a datetime
                    else:
                        dt = datetime.combine(date, datetime.min.time())  # It's a date
                else:
                    continue
                    
                datetime_objects.append(dt)
            except (ValueError, TypeError) as e:
                logging.warning(f"Could not parse date: {date}, error: {e}")
                continue
        
        if not datetime_objects:
            return 0
        
        # Sort dates for easier processing
        datetime_objects.sort()
        
        # Group dates into astronomical nights
        nights = []
        
        for dt in datetime_objects:
            # Find if this datetime belongs to an existing night
            found_night = False
            
            for night_group in nights:
                # Check if any date in this night group is within 12 hours
                for night_dt in night_group:
                    time_diff = abs((dt - night_dt).total_seconds() / 3600)  # Convert to hours
                    if time_diff <= 12:
                        night_group.append(dt)
                        found_night = True
                        break
                if found_night:
                    break
            
            # If no existing night found, create a new night
            if not found_night:
                nights.append([dt])
        
        return len(nights)
    
    def load_top_objects(self):
        """Load top 10 objects by total integration time"""
        try:
            self.objects_table.clear()
            
            # Query to get total integration time per object for Light frames only
            from peewee import fn
            
            query = (FitsFileModel
                    .select(FitsFileModel.fitsFileObject, 
                           fn.SUM(FitsFileModel.fitsFileExpTime.cast('float')).alias('total_time'))
                    .where(FitsFileModel.fitsFileType.contains('Light'))
                    .group_by(FitsFileModel.fitsFileObject)
                    .order_by(fn.SUM(FitsFileModel.fitsFileExpTime.cast('float')).desc())
                    .limit(10))
            
            for i, obj in enumerate(query, 1):
                total_seconds = float(obj.total_time)
                
                # Create table row with only 3 columns
                item = QTreeWidgetItem([
                    str(i),                          # Rank
                    obj.fitsFileObject,              # Object Name
                    f"{total_seconds:,.0f}s"         # Total Seconds
                ])
                
                # Right-align numeric columns
                item.setTextAlignment(0, Qt.AlignCenter)  # Rank - center
                item.setTextAlignment(2, Qt.AlignRight)   # Total Seconds - right
                
                self.objects_table.addTopLevelItem(item)
                
        except Exception as e:
            logging.error(f"Error loading top objects: {str(e)}")
            # Add error item to table
            error_item = QTreeWidgetItem([
                "Error",
                f"Failed to load data: {str(e)}",
                ""
            ])
            self.objects_table.addTopLevelItem(error_item)
    
    def create_filter_pie_chart(self):
        """Create and display pie chart for filter usage"""
        try:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            from matplotlib.figure import Figure
            import io
            from PySide6.QtGui import QPixmap
            
            # Query to get total time per filter for Light frames only
            from peewee import fn
            
            query = (FitsFileModel
                    .select(FitsFileModel.fitsFileFilter, 
                           fn.SUM(FitsFileModel.fitsFileExpTime.cast('float')).alias('total_time'))
                    .where(FitsFileModel.fitsFileType.contains('Light'))
                    .group_by(FitsFileModel.fitsFileFilter)
                    .order_by(fn.SUM(FitsFileModel.fitsFileExpTime.cast('float')).desc()))
            
            filters = []
            times = []
            
            for result in query:
                filter_name = result.fitsFileFilter if result.fitsFileFilter else 'Unknown'
                total_seconds = float(result.total_time)
                
                filters.append(filter_name)
                times.append(total_seconds)
            
            if not filters:
                self.chart_label.setText("No light frame data available")
                return
            
            # Get the current size of the chart label to determine optimal figure size
            label_width = max(300, self.chart_label.width())  # Ensure minimum width
            label_height = max(250, self.chart_label.height())  # Ensure minimum height
            
            # Calculate figure size based on available space (convert pixels to inches, assuming 100 DPI)
            fig_width = max(4, min(12, label_width / 100))   # Between 4-12 inches wide
            fig_height = max(3, min(10, label_height / 100))  # Between 3-10 inches tall
            
            logging.debug(f"Chart label size: {label_width}x{label_height}, figure size: {fig_width:.1f}x{fig_height:.1f}")
            
            # Create matplotlib figure - dynamically sized
            fig = Figure(figsize=(fig_width, fig_height), dpi=100)
            ax = fig.add_subplot(111)
            
            # Convert times to hours for display
            times_hours = [t / 3600 for t in times]
            
            # Define colors for better visibility
            colors = plt.cm.Set3(range(len(filters)))
            
            # Calculate appropriate font sizes based on figure size
            title_font_size = max(10, min(16, int(fig_width * 2)))
            label_font_size = max(7, min(12, int(fig_width * 1.5)))
            percent_font_size = max(8, min(14, int(fig_width * 1.5)))
            
            # Create pie chart with improved spacing
            wedges, texts, autotexts = ax.pie(times_hours, labels=filters, autopct='%1.1f%%', 
                                            startangle=90, colors=colors, 
                                            pctdistance=0.85)  # Move percentages closer to edge
            
            # Customize the chart with dynamic font sizes
            ax.set_title('Total Imaging Time by Filter', fontsize=title_font_size, fontweight='bold', pad=15)
            
            # Make text more readable with scaled fonts
            for autotext in autotexts:
                autotext.set_color('black')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(percent_font_size)
            
            for text in texts:
                text.set_fontsize(label_font_size)
            
            # Add summary text positioned appropriately for chart size
            total_hours = sum(times_hours)
            summary_text = f"Total: {total_hours:.1f} hours"
            summary_font_size = max(9, min(14, int(fig_width * 1.8)))
            ax.text(0, -1.25, summary_text, ha='center', fontsize=summary_font_size, fontweight='bold')
            
            # Save to buffer and display
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', bbox_inches='tight', facecolor='white', dpi=100)
            buffer.seek(0)
            
            # Convert to QPixmap and display
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())
            
            # Scale pixmap to fit label while maintaining aspect ratio
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.chart_label.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.chart_label.setPixmap(scaled_pixmap)
            else:
                self.chart_label.setText("Error loading chart image")
            
            plt.close(fig)  # Clean up the figure
            buffer.close()
            
        except ImportError as e:
            self.chart_label.setText("Matplotlib not available for charts\nInstall matplotlib to view charts")
            logging.warning(f"Matplotlib import error: {str(e)}")
        except Exception as e:
            logging.error(f"Error creating pie chart: {str(e)}")
            self.chart_label.setText(f"Error creating chart:\n{str(e)}")

    def showEvent(self, event):
        """Handle show events to reload data when tab becomes visible"""
        super().showEvent(event)
        # Only reload stats data if cache is invalid
        if not self._is_cache_valid():
            self.load_stats_data()
        else:
            logger.debug("Stats tab shown - using cached data")
            self._update_cache_status()
    
    def resizeEvent(self, event):
        """Handle resize events to update chart size"""
        super().resizeEvent(event)
        # Only regenerate chart if the size change is significant (more than 50 pixels)
        if hasattr(self, '_last_size'):
            width_diff = abs(event.size().width() - self._last_size.width())
            height_diff = abs(event.size().height() - self._last_size.height())
            if width_diff > 50 or height_diff > 50:
                # Regenerate the chart with new size after a short delay
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self.create_filter_pie_chart)
        
        self._last_size = event.size()


class AstroFilerGUI(QWidget):
    """Main GUI class that encapsulates the entire AstroFiler application interface"""
    
    def __init__(self):
        super().__init__()
        self.current_theme = "Dark"
        self.init_ui()
        self.apply_initial_theme()
    
    def init_ui(self):
        """Initialize the user interface"""
        # Set window properties
        self.setWindowTitle("AstroFiler - Astronomy File Management Tool")
        self.resize(1000, 700)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create and add tabs
        self.images_tab = ImagesTab()
        self.sessions_tab = SessionsTab()
        self.merge_tab = MergeTab()
        self.stats_tab = StatsTab()
        self.config_tab = ConfigTab()
        self.duplicates_tab = DuplicatesTab()
        self.log_tab = LogTab()
        self.about_tab = AboutTab()
        
        self.tab_widget.addTab(self.stats_tab, "Stats")
        self.tab_widget.addTab(self.images_tab, "Images")
        self.tab_widget.addTab(self.sessions_tab, "Sessions")
        self.tab_widget.addTab(self.merge_tab, "Merge")
        self.tab_widget.addTab(self.duplicates_tab, "Duplicates")
        self.tab_widget.addTab(self.log_tab, "Log")
        self.tab_widget.addTab(self.config_tab, "Config")
        self.tab_widget.addTab(self.about_tab, "About")
        # Set the default tab to be the Stats tab
        self.tab_widget.setCurrentWidget(self.stats_tab)
        
        layout.addWidget(self.tab_widget)
    
    def invalidate_stats_cache(self):
        """Helper method to invalidate stats cache from any tab"""
        if hasattr(self, 'stats_tab'):
            self.stats_tab.invalidate_stats_cache()
    
    def apply_initial_theme(self):
        """Apply dark theme as default"""
        app = QApplication.instance()
        app.setStyleSheet(get_dark_stylesheet())
        self.current_theme = "Dark"
        self.config_tab.theme.setCurrentText("Dark")
    
    def get_config_settings(self):
        """Get current configuration settings from the GUI"""
        return {
            'source_path': self.config_tab.source_path.text(),
            'repo_path': self.config_tab.repo_path.text(),
            'refresh_on_startup': self.config_tab.refresh_on_startup.isChecked(),
            'theme': self.config_tab.theme.currentText(),
            'font_size': self.config_tab.font_size.value(),
            'grid_size': self.config_tab.grid_size.value()
        }
    
    def set_config_settings(self, settings):
        """Set configuration settings in the GUI"""
        if 'source_path' in settings:
            self.config_tab.source_path.setText(settings['source_path'])
        if 'repo_path' in settings:
            self.config_tab.repo_path.setText(settings['repo_path'])
        if 'refresh_on_startup' in settings:
            self.config_tab.refresh_on_startup.setChecked(settings['refresh_on_startup'])
        if 'theme' in settings:
            index = self.config_tab.theme.findText(settings['theme'])
            if index >= 0:
                self.config_tab.theme.setCurrentIndex(index)
        if 'font_size' in settings:
            self.config_tab.font_size.setValue(settings['font_size'])
        if 'grid_size' in settings:
            self.config_tab.grid_size.setValue(settings['grid_size'])

    def showEvent(self, event):
        """Handle show events to reload data when tab regains focus"""
        super().showEvent(event)
        # Reload FITS data when tab becomes visible
        self.images_tab.load_fits_data()
