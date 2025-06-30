import sys
import os
import configparser
import logging
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
                               QMessageBox, QScrollArea)
from PySide6.QtGui import QPixmap, QFont, QTextCursor
from astrofiler_file import fitsProcessing
from astrofiler_db import fitsFile as FitsFileModel, fitsSequence as FitsSequenceModel

# Global version variable
VERSION = "1.0.0"

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
                if progress_dialog.wasCanceled():
                    return False  # Signal to stop processing
                
                progress = int((current / total) * 100) if total > 0 else 0
                progress_dialog.setValue(progress)
                progress_dialog.setLabelText(f"Syncing {current}/{total}: {os.path.basename(filename)}")
                QApplication.processEvents()  # Keep UI responsive
                return True  # Continue processing
            
            # Run the processing with progress callback
            registered_files = self.fits_file_handler.registerFitsImages(moveFiles=False, progress_callback=update_progress)
            
            # Close progress dialog
            progress_dialog.close()
            
            # Check if operation was cancelled
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", "Repository synchronization was cancelled by user.")
            else:
                self.load_fits_data()
                QMessageBox.information(self, "Success", f"Repository synchronized successfully! Processed {len(registered_files)} files.")
                
        except Exception as e:
            if 'progress_dialog' in locals():
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
        """Clear the file tree and delete all fitsSequence and fitsFile records from the database."""
        try:
            # Clear the tree widget
            self.file_tree.clear()
            
            # Delete all fitsSequence records from the database
            deleted_sequences = FitsSequenceModel.delete().execute()
            
            # Delete all fitsFile records from the database
            deleted_files = FitsFileModel.delete().execute()
            
            logger.info(f"Deleted {deleted_sequences} sequence records and {deleted_files} file records from database")
            QMessageBox.information(self, "Success", f"Repository cleared! Deleted {deleted_sequences} sequence records and {deleted_files} file records from database.")
            
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


class SequencesTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        # Load existing data on startup
        self.load_sequences_data()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.update_button = QPushButton("Update Lights")
        self.update_calibrations_button = QPushButton("Update Calibrations")
        
        controls_layout.addWidget(self.update_button)
        controls_layout.addWidget(self.update_calibrations_button)
        controls_layout.addStretch()
        
        # Sequences list
        self.sequences_tree = QTreeWidget()
        self.sequences_tree.setHeaderLabels(["Sequence ID", "Object Name", "Date", "Telescope", "Imager", "Master Bias", "Master Dark", "Master Flat"])
        
        # Set column widths for better display
        self.sequences_tree.setColumnWidth(0, 250)  # Sequence ID
        self.sequences_tree.setColumnWidth(1, 120)  # Object Name
        self.sequences_tree.setColumnWidth(2, 150)  # Date
        self.sequences_tree.setColumnWidth(3, 120)  # Telescope
        self.sequences_tree.setColumnWidth(4, 120)  # Imager
        self.sequences_tree.setColumnWidth(5, 100)  # Master Bias
        self.sequences_tree.setColumnWidth(6, 100)  # Master Dark
        self.sequences_tree.setColumnWidth(7, 100)  # Master Flat
        
        layout.addLayout(controls_layout)
        layout.addWidget(self.sequences_tree)
        
        # Connect signals
        self.update_button.clicked.connect(self.update_sequences)
        self.update_calibrations_button.clicked.connect(self.update_calibration_sequences)
    
    def update_sequences(self):
        """Update light sequences by running createLightSequences method with progress dialog."""
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        
        try:
            self.fits_file_handler = fitsProcessing()
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Creating Light Sequences")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.show()
            
            def update_progress(current, total, filename):
                """Progress callback function"""
                if progress_dialog.wasCanceled():
                    return False  # Signal to stop processing
                
                progress = int((current / total) * 100) if total > 0 else 0
                progress_dialog.setValue(progress)
                progress_dialog.setLabelText(f"Creating sequences {current}/{total}: {os.path.basename(filename)}")
                QApplication.processEvents()  # Keep UI responsive
                return True  # Continue processing
            
            # Run the processing with progress callback
            created_sequences = self.fits_file_handler.createLightSequences(progress_callback=update_progress)
            
            # Close progress dialog
            progress_dialog.close()
            
            # Check if operation was cancelled
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", "Light sequence creation was cancelled by user.")
            else:
                self.load_sequences_data()
                QMessageBox.information(self, "Success", f"Light sequences updated successfully! Created {len(created_sequences)} sequences.")
                
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            logger.error(f"Error updating light sequences: {e}")
            QMessageBox.warning(self, "Error", f"Failed to update light sequences: {e}")

    def update_calibration_sequences(self):
        """Update calibration sequences by running createCalibrationSequences method."""
        try:
            self.fits_file_handler = fitsProcessing()
            created_sequences = self.fits_file_handler.createCalibrationSequences()
            self.load_sequences_data()
            QMessageBox.information(self, "Success", f"Calibration sequences updated successfully! Created {len(created_sequences)} sequences.")
        except Exception as e:
            logger.error(f"Error updating calibration sequences: {e}")
            QMessageBox.warning(self, "Error", f"Failed to update calibration sequences: {e}")

    def load_sequences_data(self):
        """Load sequence data from the database and populate the tree widget."""
        try:
            self.sequences_tree.clear()
            
            # Query all sequences from the database
            sequences = FitsSequenceModel.select()
            
            for sequence in sequences:
                item = QTreeWidgetItem()
                
                # Populate the tree item with database fields
                item.setText(0, str(sequence.fitsSequenceId) or "N/A")  # Sequence ID
                item.setText(1, sequence.fitsSequenceObjectName or "N/A")  # Object Name
                item.setText(2, str(sequence.fitsSequenceDate) or "N/A")  # Date
                item.setText(3, sequence.fitsSequenceTelescope or "N/A")  # Telescope
                item.setText(4, sequence.fitsSequenceImager or "N/A")  # Imager
                item.setText(5, sequence.fitsMasterBias or "N/A")  # Master Bias
                item.setText(6, sequence.fitsMasterDark or "N/A")  # Master Dark
                item.setText(7, sequence.fitsMasterFlat or "N/A")  # Master Flat
                
                # Store the full database record for potential future use
                item.setData(0, Qt.UserRole, sequence.fitsSequenceId)
                
                self.sequences_tree.addTopLevelItem(item)
                
            count = len(sequences)
            if count > 0:
                logger.info(f"Loaded {count} sequences into the display")
            else:
                logger.info("No sequences found in database")
            
        except Exception as e:
            logger.error(f"Error loading sequences data: {e}")
            # Don't show error dialog on startup if database is just empty
            if "no such table" not in str(e).lower():
                QMessageBox.warning(self, "Error", f"Failed to load sequences data: {e}")


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
        title_label = QLabel("Object Name Merge Tool")
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
            "Optionally, you can also rename the actual files on disk."
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
        self.change_filenames = QCheckBox("Change filenames on disk")
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
            msg += "This will change database records AND rename files on disk.\n"
        else:
            msg += "This will change database records only.\n"
        msg += "\nThis action cannot be undone!"
        
        reply = QMessageBox.question(self, "Confirm Merge", msg, 
                                   QMessageBox.Yes | QMessageBox.No, 
                                   QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            # Get files to merge
            files_to_merge = FitsFileModel.select().where(FitsFileModel.fitsFileObject == from_object)
            
            if len(files_to_merge) == 0:
                QMessageBox.warning(self, "Object Not Found", f"No files found with object name '{from_object}'.")
                return
            
            merged_count = 0
            renamed_count = 0
            errors = []
            
            result_text = f"MERGE EXECUTION RESULTS:\n\n"
            result_text += f"From: '{from_object}' → To: '{to_object}'\n"
            result_text += f"Change filenames: {'Yes' if change_files else 'No'}\n\n"
            
            for fits_file in files_to_merge:
                try:
                    old_filename = fits_file.fitsFileName
                    
                    # Update database record
                    fits_file.fitsFileObject = to_object
                    
                    # If changing filenames, update the filename in database and rename actual file
                    if change_files and old_filename and os.path.exists(old_filename):
                        # Create new filename by replacing the object name
                        path_parts = old_filename.split('/')
                        old_file_part = path_parts[-1]  # Get just the filename
                        
                        # Replace the from_object with to_object in the filename
                        new_file_part = old_file_part.replace(from_object.replace(" ", "_"), to_object.replace(" ", "_"))
                        new_filename = '/'.join(path_parts[:-1] + [new_file_part])
                        
                        # Rename the actual file
                        if old_filename != new_filename:
                            if not os.path.exists(new_filename):
                                os.rename(old_filename, new_filename)
                                fits_file.fitsFileName = new_filename
                                renamed_count += 1
                            else:
                                errors.append(f"Cannot rename {old_filename} - target file already exists")
                    
                    fits_file.save()
                    merged_count += 1
                    
                except Exception as e:
                    errors.append(f"Error processing {fits_file.fitsFileName}: {str(e)}")
            
            # Update sequences that reference the old object name
            sequences_updated = 0
            try:
                from astrofiler_db import fitsSequence as FitsSequenceModel
                sequences = FitsSequenceModel.select().where(FitsSequenceModel.fitsSequenceObjectName == from_object)
                for sequence in sequences:
                    sequence.fitsSequenceObjectName = to_object
                    sequence.save()
                    sequences_updated += 1
            except Exception as e:
                errors.append(f"Error updating sequences: {str(e)}")
            
            result_text += f"Database records updated: {merged_count}\n"
            if change_files:
                result_text += f"Files renamed on disk: {renamed_count}\n"
            result_text += f"Sequences updated: {sequences_updated}\n"
            
            if errors:
                result_text += f"\nErrors encountered:\n"
                for error in errors:
                    result_text += f"- {error}\n"
            
            result_text += f"\nMerge completed successfully!"
            
            self.results_text.setPlainText(result_text)
            
            # Show success message
            if errors:
                QMessageBox.warning(self, "Merge Completed with Errors", 
                                  f"Merge completed but {len(errors)} errors occurred. Check results for details.")
            else:
                QMessageBox.information(self, "Merge Successful", 
                                      f"Successfully merged {merged_count} records from '{from_object}' to '{to_object}'.")
            
            logger.info(f"Object merge completed: {from_object} → {to_object}, {merged_count} records, {renamed_count} files renamed")
            
        except Exception as e:
            error_msg = f"Error during merge execution: {e}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Merge Error", error_msg)
            self.results_text.setPlainText(f"ERROR: {error_msg}")


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
        
        general_layout.addRow("Source Path:", source_path_layout)
        general_layout.addRow("Repository Path:", repo_path_layout)
        general_layout.addRow("Refresh on Startup:", self.refresh_on_startup)
        
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
            
            # Save the path settings directly to DEFAULT section
            config['DEFAULT'] = {
                'source': source_path,
                'repo': repo_path,
                'refresh_on_startup': str(self.refresh_on_startup.isChecked()),
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
                
            logger.info("Settings loaded from astrofiler.ini!")
            
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            # Use default values if loading fails
            self.reset_settings()
    
    def reset_settings(self):
        # Reset to default values
        self.source_path.setText("")
        self.repo_path.setText("")
        self.refresh_on_startup.setChecked(True)
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
                logger.info("Successfully loaded images/background.jpg as background")
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
                    logger.info("Log content loaded successfully")
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
        self.sequences_tab = SequencesTab()
        self.merge_tab = MergeTab()
        self.config_tab = ConfigTab()
        self.duplicates_tab = DuplicatesTab()
        self.log_tab = LogTab()
        self.about_tab = AboutTab()
        
        self.tab_widget.addTab(self.images_tab, "Images")
        self.tab_widget.addTab(self.sequences_tab, "Sequences")
        self.tab_widget.addTab(self.merge_tab, "Merge")
        self.tab_widget.addTab(self.config_tab, "Config")
        self.tab_widget.addTab(self.duplicates_tab, "Duplicates")
        self.tab_widget.addTab(self.log_tab, "Log")
        self.tab_widget.addTab(self.about_tab, "About")
        # Set the default tab to be the Images tab
        self.tab_widget.setCurrentWidget(self.images_tab)
        
        layout.addWidget(self.tab_widget)
    
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
