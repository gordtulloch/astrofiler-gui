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
                               QMessageBox)
from PySide6.QtGui import QPixmap, QFont
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
        
        controls_layout.addWidget(self.load_repo_button)
        controls_layout.addWidget(self.sync_repo_button)
        controls_layout.addWidget(self.clear_button)
        controls_layout.addStretch()
          # File list
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Object", "Type", "Date", "Exposure", "Telescope", "Instrument", "Temperature", "Filename"])
        
        # Set column widths for better display
        self.file_tree.setColumnWidth(0, 120)  # Object
        self.file_tree.setColumnWidth(1, 80)   # Type
        self.file_tree.setColumnWidth(2, 150)  # Date
        self.file_tree.setColumnWidth(3, 80)   # Exposure
        self.file_tree.setColumnWidth(4, 120)  # Telescope
        self.file_tree.setColumnWidth(5, 120)  # Instrument
        self.file_tree.setColumnWidth(6, 100)  # Temperature
        self.file_tree.setColumnWidth(7, 200)  # Filename
        
        layout.addLayout(controls_layout)
        layout.addWidget(self.file_tree)
        
        # Connect signals
        self.load_repo_button.clicked.connect(self.load_repo)
        self.sync_repo_button.clicked.connect(self.sync_repo)
        self.clear_button.clicked.connect(self.clear_files)
    
    def load_repo(self):
        """Load the repository by running registerFitsImages."""
        try:
            self.fits_file_handler = fitsProcessing()
            self.fits_file_handler.registerFitsImages(moveFiles=True)
            self.load_fits_data()
            QMessageBox.information(self, "Success", "Repository loaded successfully!")
        except Exception as e:
            logger.error(f"Error loading repository: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load repository: {e}")

    def sync_repo(self):
        """Sync the repository by running registerFitsImages with moveFiles=False."""
        try:
            self.fits_file_handler = fitsProcessing()
            registered_files = self.fits_file_handler.registerFitsImages(moveFiles=False)
            self.load_fits_data()
            QMessageBox.information(self, "Success", f"Repository synchronized successfully! Processed {len(registered_files)} files.")
        except Exception as e:
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
                for col in range(8):
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

                        child_item.setText(4, fits_file.fitsFileTelescop or "N/A")  # Telescope
                        child_item.setText(5, fits_file.fitsFileInstrument or "N/A")  # Instrument

                        # Format temperature
                        temp = fits_file.fitsFileCCDTemp or ""
                        if temp:
                            child_item.setText(6, f"{temp}°C")  # Temperature
                        else:
                            child_item.setText(6, "N/A")

                        # Extract just the filename from the full path for display
                        filename = fits_file.fitsFileName or ""
                        if filename:
                            filename = os.path.basename(filename)
                            child_item.setText(7, filename)  # Filename
                        else:
                            child_item.setText(7, "N/A")

                        # Store the full database record for potential future use
                        child_item.setData(0, Qt.UserRole, fits_file.fitsFileId)

                        # Add child to date item
                        date_item.addChild(child_item)

                    # Add date item to parent
                    parent_item.addChild(date_item)

                    # Expand the date item to show children by default
                    date_item.setExpanded(True)

                # Add parent item to tree
                self.file_tree.addTopLevelItem(parent_item)

                # Expand the parent item to show children by default
                parent_item.setExpanded(True)

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
        self.file_tree.clear()


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
        self.update_button = QPushButton("Update")
        
        controls_layout.addWidget(self.update_button)
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
    
    def update_sequences(self):
        """Update sequences by running createSequences method."""
        try:
            self.fits_file_handler = fitsProcessing()
            self.fits_file_handler.createSequences()
            self.load_sequences_data()
            QMessageBox.information(self, "Success", "Sequences updated successfully!")
        except Exception as e:
            logger.error(f"Error updating sequences: {e}")
            QMessageBox.warning(self, "Error", f"Failed to update sequences: {e}")

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


class ViewsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # View controls
        controls_layout = QHBoxLayout()
        self.view_type = QComboBox()
        self.view_type.addItems(["List View", "Grid View", "Detail View"])
        self.filter_button = QPushButton("Apply Filter")
        self.export_button = QPushButton("Export View")
        
        controls_layout.addWidget(QLabel("View Type:"))
        controls_layout.addWidget(self.view_type)
        controls_layout.addWidget(self.filter_button)
        controls_layout.addWidget(self.export_button)
        controls_layout.addStretch()
        
        # Main view area with splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - filters/options
        filter_widget = QWidget()
        filter_layout = QVBoxLayout(filter_widget)
        filter_group = QGroupBox("Filters")
        filter_form = QFormLayout(filter_group)
        
        self.name_filter = QLineEdit()
        self.size_filter = QSpinBox()
        self.size_filter.setMaximum(999999)
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Images", "Documents", "Videos"])
        
        filter_form.addRow("Name contains:", self.name_filter)
        filter_form.addRow("Min size (KB):", self.size_filter)
        filter_form.addRow("File type:", self.type_filter)
        
        filter_layout.addWidget(filter_group)
        filter_layout.addStretch()
        
        # Right panel - main view
        self.main_view = QListWidget()
        self.main_view.addItem("No files loaded")
        
        splitter.addWidget(filter_widget)
        splitter.addWidget(self.main_view)
        splitter.setSizes([200, 600])  # Set initial sizes
        
        layout.addLayout(controls_layout)
        layout.addWidget(splitter)


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
            
            # Save the path settings directly to DEFAULT section
            config['DEFAULT'] = {
                'source': self.source_path.text(),
                'repo': self.repo_path.text(),
                'refresh_on_startup': str(self.refresh_on_startup.isChecked()),
                'theme': self.theme.currentText(),
                'font_size': str(self.font_size.value()),
                'grid_size': str(self.grid_size.value())
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
        self.subtitle_label = QLabel("By Gord Tulloch\ngord.tulloch@gmail.com\nJune 27, 2025")
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
        self.views_tab = ViewsTab()
        self.config_tab = ConfigTab()
        self.about_tab = AboutTab()
        
        self.tab_widget.addTab(self.images_tab, "Images")
        self.tab_widget.addTab(self.sequences_tab, "Sequences")
        self.tab_widget.addTab(self.views_tab, "Views")
        self.tab_widget.addTab(self.config_tab, "Config")
        self.tab_widget.addTab(self.about_tab, "About")
        
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
