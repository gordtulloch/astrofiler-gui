import sys
import os
import configparser
import logging
import datetime
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='astrofiler.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# Import necessary PySide6 modules
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton, QVBoxLayout, 
                               QHBoxLayout, QWidget, QTabWidget, QListWidget, 
                               QTextEdit, QFormLayout, QLineEdit, QSpinBox, 
                               QCheckBox, QComboBox, QGroupBox, QFileDialog,
                               QSplitter, QTreeWidget, QTreeWidgetItem, QStackedLayout,
                               QMessageBox, QScrollArea, QDialog)
from PySide6.QtGui import QPixmap, QFont, QTextCursor
from astrofiler_file import fitsProcessing
from astrofiler_db import fitsFile as FitsFileModel, fitsSession as FitsSessionModel

# Global version variable
VERSION = "1.0.0 alpha"

def load_stylesheet(filename):
    """Load stylesheet from a file"""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            logger.info(f"Successfully loaded stylesheet: {filename}")
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
        self.clear_button = QPushButton("Clear Repo")
        self.refresh_button = QPushButton("Refresh")
        
        controls_layout.addWidget(self.load_repo_button)
        controls_layout.addWidget(self.sync_repo_button)
        controls_layout.addWidget(self.clear_button)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addStretch()
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
        self.clear_button.clicked.connect(self.clear_files)
        self.refresh_button.clicked.connect(self.load_fits_data)
        self.file_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
    
    def load_repo(self):
        """Load the repository by running registerFitsImages with progress dialog."""
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        import time
        
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
                    logging.info(f"Progress callback called: {current}/{total} - {filename}")
                    
                    # Don't check cancellation if already cancelled
                    if was_cancelled:
                        logging.info("Already cancelled, returning False")
                        return False
                    
                    # Check if dialog was cancelled before updating
                    if progress_dialog and progress_dialog.wasCanceled():
                        logging.info("User cancelled the operation")
                        was_cancelled = True
                        return False  # Signal to stop processing
                    
                    if progress_dialog:
                        progress = int((current / total) * 100) if total > 0 else 0
                        progress_dialog.setValue(progress)
                        progress_dialog.setLabelText(f"Processing {current}/{total}: {os.path.basename(filename)}")
                        QApplication.processEvents()  # Keep UI responsive
                        
                        # Check again after processing events
                        if progress_dialog.wasCanceled():
                            logging.info("User cancelled the operation during update")
                            was_cancelled = True
                            return False
                    
                    logging.info(f"Progress callback returning True for {filename}")
                    return True  # Continue processing
                except Exception as e:
                    logging.error(f"Error in progress callback: {e}")
                    return True  # Continue on callback errors
            
            # Run the processing with progress callback
            logging.info("Starting registerFitsImages with progress callback")
            registered_files = self.fits_file_handler.registerFitsImages(moveFiles=True, progress_callback=update_progress)
            logging.info(f"registerFitsImages completed, registered {len(registered_files)} files")
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled or completed normally
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Repository loading was cancelled by user.")
                logging.info("Operation was cancelled by user")
            elif len(registered_files) == 0:
                QMessageBox.information(self, "No Files", "No FITS files found to process in the source directory.")
                logging.info("No FITS files found to process")
            else:
                self.load_fits_data()
                QMessageBox.information(self, "Success", f"Repository loaded successfully! Processed {len(registered_files)} files.")
                logging.info("Operation completed successfully")
                
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error loading repository: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load repository: {e}")

    def sync_repo(self):
        """Sync the repository by running registerFitsImages with moveFiles=False and progress dialog."""
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        
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
                try:
                    # Don't check cancellation if already cancelled
                    if was_cancelled:
                        logging.info("Already cancelled, returning False")
                        return False
                    
                    # Check if dialog was cancelled before updating
                    if progress_dialog and progress_dialog.wasCanceled():
                        logging.info("User cancelled the repository synchronization")
                        was_cancelled = True
                        return False  # Signal to stop processing
                    
                    if progress_dialog:
                        progress = int((current / total) * 100) if total > 0 else 0
                        progress_dialog.setValue(progress)
                        progress_dialog.setLabelText(f"Syncing {current}/{total}: {os.path.basename(filename)}")
                        QApplication.processEvents()  # Keep UI responsive
                        
                        # Check again after processing events
                        if progress_dialog.wasCanceled():
                            logging.info("User cancelled the repository synchronization during update")
                            was_cancelled = True
                            return False
                    
                    return True  # Continue processing
                except Exception as e:
                    logging.error(f"Error in progress callback: {e}")
                    return True  # Continue on callback errors
            
            # Run the processing with progress callback
            registered_files = self.fits_file_handler.registerFitsImages(moveFiles=False, progress_callback=update_progress)
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled or completed normally
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Repository synchronization was cancelled by user.")
                logging.info("Repository synchronization was cancelled by user")
            else:
                self.load_fits_data()
                QMessageBox.information(self, "Success", f"Repository synchronized successfully! Processed {len(registered_files)} files.")
                logging.info("Repository synchronization completed successfully")
                
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error syncing repository: {e}")
            QMessageBox.warning(self, "Error", f"Failed to sync repository: {e}")

    def load_fits_data(self):
        """Load FITS file data from the database and populate the tree widget categorized by object name and date."""
        try:
            self.file_tree.clear()

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

            # Create parent items for each object
            for object_name, dates_dict in objects_dict.items():
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

                # Make parent item bold and slightly different color
                font = parent_item.font(0)
                font.setBold(True)
                for col in range(9):
                    parent_item.setFont(col, font)

                # Add sub-parent items for each date
                for date_str, files in dates_dict.items():
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
                        child_item = QTreeWidgetItem()

                        # Populate the child item with database fields
                        child_item.setText(0, "")  # Empty object column for child (parent shows object)
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

                        # Add child to date item
                        date_item.addChild(child_item)

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
                logger.info(f"Loaded {total_files} FITS files from {total_objects} objects into the display")
            else:
                logger.info("No FITS files found in database")

        except Exception as e:
            logger.error(f"Error loading FITS data: {e}")
            if "no such table" not in str(e).lower():
                QMessageBox.warning(self, "Error", f"Failed to load FITS data: {e}")

    def clear_files(self):
        """Clear the file tree and delete all fitsSession and fitsFile records from the database."""
        try:
            # Clear the tree widget
            self.file_tree.clear()
            
            # Delete all fitsSession records from the database
            deleted_sessions = FitsSessionModel.delete().execute()
            
            # Delete all fitsFile records from the database
            deleted_files = FitsFileModel.delete().execute()
            
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
            
            if not os.path.exists(viewer_path):
                QMessageBox.warning(self, "Viewer Not Found", 
                                  f"The configured FITS viewer was not found: {viewer_path}")
                return
            
            if not os.path.exists(file_path):
                QMessageBox.warning(self, "File Not Found", 
                                  f"The FITS file was not found: {file_path}")
                return
            
            try:
                import subprocess
                # Launch the external viewer with the file path as argument
                subprocess.Popen([viewer_path, file_path])
                logger.info(f"Launched external FITS viewer: {viewer_path} with file: {file_path}")
            except Exception as e:
                logger.error(f"Error launching external viewer: {e}")
                QMessageBox.warning(self, "Launch Error", 
                                  f"Failed to launch external viewer: {str(e)}")
        else:
            QMessageBox.warning(self, "Configuration Error", 
                              "Unable to access FITS viewer configuration.")


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
        self.update_button = QPushButton("Update Lights")
        self.update_calibrations_button = QPushButton("Update Calibrations")
        self.link_sessions_button = QPushButton("Link Sessions")
        self.clear_sessions_button = QPushButton("Clear Sessions")
        
        controls_layout.addWidget(self.update_button)
        controls_layout.addWidget(self.update_calibrations_button)
        controls_layout.addWidget(self.link_sessions_button)
        controls_layout.addWidget(self.clear_sessions_button)
        controls_layout.addStretch()
        
        # Sessions list
        self.sessions_tree = QTreeWidget()
        self.sessions_tree.setHeaderLabels(["Object Name", "Date", "Telescope", "Imager", "Bias Date", "Dark Date", "Flat Date"])
        
        # Set column widths for better display
        self.sessions_tree.setColumnWidth(0, 200)  # Object Name
        self.sessions_tree.setColumnWidth(1, 150)  # Date
        self.sessions_tree.setColumnWidth(2, 150)  # Telescope
        self.sessions_tree.setColumnWidth(3, 150)  # Imager
        self.sessions_tree.setColumnWidth(4, 120)  # Bias Date
        self.sessions_tree.setColumnWidth(5, 120)  # Dark Date
        self.sessions_tree.setColumnWidth(6, 120)  # Flat Date
        
        layout.addLayout(controls_layout)
        layout.addWidget(self.sessions_tree)
        
        # Connect signals
        self.update_button.clicked.connect(self.update_sessions)
        self.update_calibrations_button.clicked.connect(self.update_calibration_sessions)
        self.link_sessions_button.clicked.connect(self.link_sessions)
        self.clear_sessions_button.clicked.connect(self.clear_sessions)
        self.sessions_tree.itemDoubleClicked.connect(self.on_session_double_click)
    
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
            
            # Create hierarchical tree structure, sorted by object name
            for object_name in sorted(sessions_by_object.keys()):
                object_sessions = sessions_by_object[object_name]
                # Create parent item for each object
                parent_item = QTreeWidgetItem()
                parent_item.setText(0, object_name)
                parent_item.setText(1, "")  # No date for parent
                parent_item.setText(2, "")  # No telescope for parent
                parent_item.setText(3, "")  # No imager for parent
                parent_item.setText(4, "")  # No bias date for parent
                parent_item.setText(5, "")  # No dark date for parent
                parent_item.setText(6, "")  # No flat date for parent
                
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
                    
                    # Initialize calibration date columns
                    bias_date = "N/A"
                    dark_date = "N/A"
                    flat_date = "N/A"
                    
                    # For light sessions, get calibration dates
                    if object_name not in ['Bias', 'Dark', 'Flat']:
                        # Get bias date
                        if session.fitsBiasSession:
                            try:
                                bias_session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session.fitsBiasSession)
                                bias_date = str(bias_session.fitsSessionDate) if bias_session.fitsSessionDate else "N/A"
                            except FitsSessionModel.DoesNotExist:
                                bias_date = "N/A"
                        
                        # Get dark date
                        if session.fitsDarkSession:
                            try:
                                dark_session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session.fitsDarkSession)
                                dark_date = str(dark_session.fitsSessionDate) if dark_session.fitsSessionDate else "N/A"
                            except FitsSessionModel.DoesNotExist:
                                dark_date = "N/A"
                        
                        # Get flat date
                        if session.fitsFlatSession:
                            try:
                                flat_session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session.fitsFlatSession)
                                flat_date = str(flat_session.fitsSessionDate) if flat_session.fitsSessionDate else "N/A"
                            except FitsSessionModel.DoesNotExist:
                                flat_date = "N/A"
                    
                    # Set the calibration date columns
                    child_item.setText(4, bias_date)
                    child_item.setText(5, dark_date)
                    child_item.setText(6, flat_date)
                    
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
                                bias_child.setText(4, "")  # Empty for sub-child
                                bias_child.setText(5, "")  # Empty for sub-child
                                bias_child.setText(6, "")  # Empty for sub-child
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
                                dark_child.setText(4, "")  # Empty for sub-child
                                dark_child.setText(5, "")  # Empty for sub-child
                                dark_child.setText(6, "")  # Empty for sub-child
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
                                flat_child.setText(4, "")  # Empty for sub-child
                                flat_child.setText(5, "")  # Empty for sub-child
                                flat_child.setText(6, "")  # Empty for sub-child
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
                logger.info(f"Loaded {count} sessions into hierarchical display")
            else:
                logger.info("No sessions found in database")
            
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

    def on_session_double_click(self, item, column):
        """Handle double-click on session tree items."""
        try:
            # Check if this is a parent item (object name)
            if item.parent() is None:
                # This is a top-level item (object name), don't do anything
                return
            
            # Check if this is a session item or a sub-item (calibration detail)
            if item.parent().parent() is None:
                # This is a session item (child of object name)
                session_id = item.data(0, Qt.UserRole)
                if session_id:
                    self.show_session_export_dialog(session_id)
                return
            
            # This is a sub-item (calibration detail), check if it represents a file
            # For now, we'll implement file opening in a future update
            # as sub-items show calibration session details, not individual files
            
        except Exception as e:
            logger.error(f"Error handling session double-click: {e}")
            QMessageBox.warning(self, "Error", f"Error handling double-click: {e}")

    def show_session_export_dialog(self, session_id):
        """Show dialog for exporting session files."""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                     QFormLayout, QLineEdit, QPushButton, 
                                     QComboBox, QFileDialog, QLabel)
        
        try:
            # Get session details
            session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session_id)
            
            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Export Session: {session.fitsSessionObjectName}")
            dialog.setModal(True)
            dialog.resize(500, 200)
            
            layout = QVBoxLayout(dialog)
            form_layout = QFormLayout()
            
            # Session info
            info_label = QLabel(f"Object: {session.fitsSessionObjectName or 'N/A'}\n"
                               f"Date: {session.fitsSessionDate or 'N/A'}\n"
                               f"Telescope: {session.fitsSessionTelescope or 'N/A'}\n"
                               f"Imager: {session.fitsSessionImager or 'N/A'}")
            layout.addWidget(info_label)
            
            # Destination folder
            dest_layout = QHBoxLayout()
            self.dest_folder_edit = QLineEdit()
            self.dest_folder_edit.setPlaceholderText("Select destination folder...")
            browse_button = QPushButton("Browse")
            browse_button.clicked.connect(lambda: self.browse_destination_folder(dialog))
            dest_layout.addWidget(self.dest_folder_edit)
            dest_layout.addWidget(browse_button)
            form_layout.addRow("Destination Folder:", dest_layout)
            
            # Format selection (currently only FITS)
            format_combo = QComboBox()
            format_combo.addItem("FITS")
            # Future formats can be added here: format_combo.addItem("TIFF")
            form_layout.addRow("Format:", format_combo)
            
            # Folder structure selection
            structure_combo = QComboBox()
            structure_combo.addItem("Siril")
            # Future structures can be added here: structure_combo.addItem("PixInsight")
            form_layout.addRow("Folder Structure:", structure_combo)
            
            layout.addLayout(form_layout)
            
            # Buttons
            button_layout = QHBoxLayout()
            ok_button = QPushButton("OK")
            cancel_button = QPushButton("Cancel")
            
            ok_button.clicked.connect(lambda: self.export_session_files(
                dialog, session_id, self.dest_folder_edit.text(), 
                format_combo.currentText(), structure_combo.currentText()))
            cancel_button.clicked.connect(dialog.reject)
            
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            dialog.exec()
            
        except FitsSessionModel.DoesNotExist:
            QMessageBox.warning(self, "Error", "Session not found in database.")
        except Exception as e:
            logger.error(f"Error showing session export dialog: {e}")
            QMessageBox.warning(self, "Error", f"Error showing export dialog: {e}")

    def browse_destination_folder(self, dialog):
        """Browse for destination folder."""
        folder = QFileDialog.getExistingDirectory(dialog, "Select Destination Folder")
        if folder:
            self.dest_folder_edit.setText(folder)

    def export_session_files(self, dialog, session_id, dest_folder, format_type, structure_type):
        """Export session files to destination folder."""
        import os
        import shutil
        
        if not dest_folder:
            QMessageBox.warning(dialog, "Error", "Please select a destination folder.")
            return
            
        if not os.path.exists(dest_folder):
            QMessageBox.warning(dialog, "Error", "Destination folder does not exist.")
            return
            
        try:
            # Get session details
            session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session_id)
            
            # Create folder structure based on selected type
            if structure_type == "Siril":
                folders = ["lights", "darks", "biases", "flats", "process"]
                for folder in folders:
                    folder_path = os.path.join(dest_folder, folder)
                    os.makedirs(folder_path, exist_ok=True)
                
                # Get light files for this session
                light_files = FitsFileModel.select().where(
                    FitsFileModel.fitsFileSession == session_id,
                    FitsFileModel.fitsFileType == "Light"
                )
                
                # Create symbolic links for light files
                for file_record in light_files:
                    if file_record.fitsFileName and os.path.exists(file_record.fitsFileName):
                        dest_path = os.path.join(dest_folder, "lights", os.path.basename(file_record.fitsFileName))
                        try:
                            os.symlink(file_record.fitsFileName, dest_path)
                        except FileExistsError:
                            pass  # Link already exists
                
                # Handle calibration files
                calibration_sessions = []
                if session.fitsBiasSession:
                    calibration_sessions.append((session.fitsBiasSession, "Bias", "biases"))
                if session.fitsDarkSession:
                    calibration_sessions.append((session.fitsDarkSession, "Dark", "darks"))
                if session.fitsFlatSession:
                    calibration_sessions.append((session.fitsFlatSession, "Flat", "flats"))
                
                for cal_session_id, cal_type, folder_name in calibration_sessions:
                    cal_files = FitsFileModel.select().where(
                        FitsFileModel.fitsFileSession == cal_session_id,
                        FitsFileModel.fitsFileType == cal_type
                    )
                    
                    for file_record in cal_files:
                        if file_record.fitsFileName and os.path.exists(file_record.fitsFileName):
                            dest_path = os.path.join(dest_folder, folder_name, os.path.basename(file_record.fitsFileName))
                            try:
                                os.symlink(file_record.fitsFileName, dest_path)
                            except FileExistsError:
                                pass  # Link already exists
                
                dialog.accept()
                QMessageBox.information(self, "Success", 
                                      f"Session files exported successfully to:\n{dest_folder}\n\n"
                                      f"Folder structure: {structure_type}\n"
                                      f"Format: {format_type}")
            
            else:
                QMessageBox.warning(dialog, "Error", f"Folder structure '{structure_type}' not implemented yet.")
                
        except Exception as e:
            logger.error(f"Error exporting session files: {e}")
            QMessageBox.warning(dialog, "Error", f"Failed to export session files: {e}")
