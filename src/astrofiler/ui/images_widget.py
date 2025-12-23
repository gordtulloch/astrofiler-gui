import os
import time
import logging
import configparser
from datetime import datetime

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QLineEdit, QComboBox, QTreeWidget, QTreeWidgetItem,
                               QCheckBox, QProgressDialog, QApplication, QMessageBox,
                               QMenu, QDialog, QDialogButtonBox)
from PySide6.QtGui import QFont, QDesktopServices, QTextCursor, QIcon

from astrofiler.core import fitsProcessing
from astrofiler.models import fitsFile as FitsFileModel, fitsSession as FitsSessionModel
from .download_dialog import SmartTelescopeDownloadDialog
from .mappings_dialog import MappingsDialog

logger = logging.getLogger(__name__)

class ImagesWidget(QWidget):
    """
    Images widget for viewing and managing FITS files with search.
    
    Features:
    - Text search functionality on object field
    - Sortable by Object (default) or Date
    - File loading and repository synchronization
    - Context menus and double-click actions
    """
    def __init__(self):
        super().__init__()
        self.search_term = ""
        
        # Setup icons for local and cloud status
        self.setup_icons()
        
        self.init_ui()
        # Load all items on startup
        self.load_fits_data()
    
    def setup_icons(self):
        """Setup icons for local and cloud file status"""
        # Get the application's style for standard icons
        style = self.style()
        
        # Hard disk icon for local files
        self.local_icon = style.standardIcon(style.StandardPixmap.SP_DriveHDIcon)
        
        # Cloud icon - using a network icon as substitute since there's no standard cloud icon
        self.cloud_icon = style.standardIcon(style.StandardPixmap.SP_DriveNetIcon)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Combined search and filter controls in single row
        controls_layout = QHBoxLayout()
        
        # Add regenerate button first
        self.regenerate_button = QPushButton("Regenerate")
        self.regenerate_button.setMaximumSize(100, 28)
        self.regenerate_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.regenerate_button.setToolTip("Regenerate repository database from existing files")
        self.regenerate_button.clicked.connect(self.sync_repo)
        
        # Add load new button after regenerate
        self.load_new_button = QPushButton("Load New")
        self.load_new_button.setMaximumSize(100, 28)
        self.load_new_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.load_new_button.setToolTip("Load new FITS and XISF files from incoming directory")
        self.load_new_button.clicked.connect(self.load_repo)
        
        # Add download button after load new
        self.download_button = QPushButton("Download")
        self.download_button.setMaximumSize(100, 28)
        self.download_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.download_button.setToolTip("Download files from telescope")
        self.download_button.clicked.connect(self.show_download_dialog)
        
        # Search controls
        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-weight: bold; margin-left: 15px; margin-right: 5px;")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search object names...")
        self.search_input.setMaximumWidth(250)
        self.search_button = QPushButton("Search")
        self.search_button.setMaximumSize(80, 28)
        self.search_button.setStyleSheet("QPushButton { font-size: 10px; }")
        self.clear_search_button = QPushButton("Clear")
        self.clear_search_button.setMaximumSize(60, 28)
        self.clear_search_button.setStyleSheet("QPushButton { font-size: 10px; }")
        
        # Add sort control
        sort_label = QLabel("Sort by:")
        sort_label.setStyleSheet("font-weight: bold; margin-left: 15px; margin-right: 5px;")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Object", "Date", "Filter"])
        self.sort_combo.setCurrentText("Object")
        self.sort_combo.setToolTip("Choose how to organize the file tree")
        
        # Add frame type filter control
        filter_label = QLabel("Show:")
        filter_label.setStyleSheet("font-weight: bold; margin-left: 15px; margin-right: 5px;")
        self.frame_filter_combo = QComboBox()
        self.frame_filter_combo.addItems(["Light Frames Only", "All Frames", "Calibration Frames Only"])
        self.frame_filter_combo.setCurrentText("Light Frames Only")
        
        # Add Show Deleted checkbox
        self.show_deleted_checkbox = QCheckBox("Show Deleted")
        self.show_deleted_checkbox.setToolTip("Show or hide soft-deleted frames")
        self.show_deleted_checkbox.setChecked(False)
        
        controls_layout.addWidget(self.regenerate_button)
        controls_layout.addWidget(self.load_new_button)
        controls_layout.addWidget(self.download_button)
        controls_layout.addWidget(search_label)
        controls_layout.addWidget(self.search_input)
        controls_layout.addWidget(self.search_button)
        controls_layout.addWidget(self.clear_search_button)
        controls_layout.addWidget(sort_label)
        controls_layout.addWidget(self.sort_combo)
        controls_layout.addWidget(filter_label)
        controls_layout.addWidget(self.frame_filter_combo)
        controls_layout.addWidget(self.show_deleted_checkbox)
        controls_layout.addStretch()
        
        # File list
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Object", "Type", "Date", "Exposure", "Filter", "Telescope", "Instrument", "Temperature", "Local", "Cloud", "Filename"])
        
        # Set column widths for better display
        self.file_tree.setColumnWidth(0, 120)  # Object
        self.file_tree.setColumnWidth(1, 80)   # Type
        self.file_tree.setColumnWidth(2, 150)  # Date
        self.file_tree.setColumnWidth(3, 80)   # Exposure
        self.file_tree.setColumnWidth(4, 80)   # Filter
        self.file_tree.setColumnWidth(5, 120)  # Telescope
        self.file_tree.setColumnWidth(6, 120)  # Instrument
        self.file_tree.setColumnWidth(7, 100)  # Temperature
        self.file_tree.setColumnWidth(8, 40)   # Local icon
        self.file_tree.setColumnWidth(9, 40)   # Cloud icon
        self.file_tree.setColumnWidth(10, 200) # Filename

        # Enable context menu
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_file_context_menu)
        
        # Add all layouts to main layout
        layout.addLayout(controls_layout)
        layout.addWidget(self.file_tree)
        
        # Connect signals
        self.search_input.returnPressed.connect(self.perform_search)
        self.search_button.clicked.connect(self.perform_search)
        self.clear_search_button.clicked.connect(self.clear_search)
        self.sort_combo.currentTextChanged.connect(self.load_fits_data)
        self.frame_filter_combo.currentTextChanged.connect(self.load_fits_data)
        self.show_deleted_checkbox.stateChanged.connect(self.load_fits_data)
        self.file_tree.itemDoubleClicked.connect(self.on_item_double_clicked)

    # ...existing code for other methods...
    
    def load_fits_data(self):
        """Load FITS file data from the database."""
        try:
            self.file_tree.clear()
            
            # Get sort method from combo box
            sort_method = self.sort_combo.currentText()
            
            # Show/hide Filter column based on sort method
            if sort_method == "Filter":
                self.file_tree.setColumnHidden(4, True)  # Hide Filter column when sorting by filter
            else:
                self.file_tree.setColumnHidden(4, False)  # Show Filter column for other sort methods
            
            # Load data based on sort method
            if sort_method == "Object":
                self._load_fits_data_by_object_paginated()
            elif sort_method == "Date":
                self._load_fits_data_by_date_paginated()
            elif sort_method == "Filter":
                self._load_fits_data_by_filter_paginated()
            else:
                self._load_fits_data_by_object_paginated()  # Default

            logger.debug(f"Loaded FITS data with {sort_method} sorting")
            
        except Exception as e:
            logger.error(f"Error loading FITS data: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load FITS data: {e}")

    def _get_fits_files_query(self, include_search=True):
        """Get the appropriate database query based on the frame filter selection and search term."""
        # Start with base query
        query = FitsFileModel.select()
        
        # Apply soft-delete filter (exclude soft-deleted by default unless checkbox is checked)
        if not self.show_deleted_checkbox.isChecked():
            query = query.where((FitsFileModel.fitsFileSoftDelete == False) | (FitsFileModel.fitsFileSoftDelete.is_null()))
        
        # Apply frame filter
        frame_filter = self.frame_filter_combo.currentText()
        if frame_filter == "Light Frames Only":
            query = query.where(FitsFileModel.fitsFileType.contains('Light'))
        elif frame_filter == "Calibration Frames Only":
            query = query.where(
                (FitsFileModel.fitsFileType.contains('Dark')) |
                (FitsFileModel.fitsFileType.contains('Bias')) |
                (FitsFileModel.fitsFileType.contains('Flat'))
            )
        # "All Frames" requires no additional filter
        
        # Apply search term if provided and requested
        if include_search and self.search_term:
            query = query.where(FitsFileModel.fitsFileObject.contains(self.search_term))
        
        return query

    def _load_fits_data_by_object_paginated(self):
        """Load FITS file data grouped by object name."""
        
        # Get unique objects with search and frame filter applied
        base_query = self._get_fits_files_query()
        objects_query = (base_query
                        .select(FitsFileModel.fitsFileObject)
                        .distinct()
                        .order_by(FitsFileModel.fitsFileObject))
        
        # Get all unique objects
        all_objects = [obj.fitsFileObject or "Unknown" for obj in objects_query]
        page_objects = all_objects
        
        # Load files for each object
        for object_name in page_objects:
            # Query files for this object
            if object_name == "Unknown":
                object_files = self._get_fits_files_query().where(FitsFileModel.fitsFileObject.is_null(True))
            else:
                object_files = self._get_fits_files_query().where(FitsFileModel.fitsFileObject == object_name)
            
            object_files = object_files.order_by(FitsFileModel.fitsFileDate.desc())
            
            # Create parent item for object
            parent_item = QTreeWidgetItem()
            parent_item.setText(0, object_name)
            parent_item.setText(1, "")  # Type
            parent_item.setText(2, "")  # Date  
            parent_item.setText(3, "")  # Exposure
            parent_item.setText(4, "")  # Filter
            parent_item.setText(5, "")  # Telescope
            parent_item.setText(6, "")  # Instrument
            parent_item.setText(7, "")  # Temperature
            parent_item.setText(8, "")  # Local icon column - empty for parent
            parent_item.setText(9, "")  # Cloud icon column - empty for parent
            parent_item.setText(10, f"({len(object_files)} files)")  # Filename shows count
            
            # Style parent item
            font = parent_item.font(0)
            font.setBold(True)
            parent_item.setFont(0, font)
            
            # Add child items for each file
            for fits_file in object_files:
                child_item = QTreeWidgetItem()
                child_item.setText(0, "")  # Empty object for child
                child_item.setText(1, fits_file.fitsFileType or "")
                child_item.setText(2, str(fits_file.fitsFileDate) if fits_file.fitsFileDate else "")
                child_item.setText(3, str(fits_file.fitsFileExpTime) if fits_file.fitsFileExpTime else "")
                child_item.setText(4, fits_file.fitsFileFilter or "")
                child_item.setText(5, fits_file.fitsFileTelescop or "")
                child_item.setText(6, fits_file.fitsFileInstrument or "")
                child_item.setText(7, str(fits_file.fitsFileCCDTemp) if fits_file.fitsFileCCDTemp else "")
                
                # Set icons for local and cloud status
                if fits_file.fitsFileName:
                    child_item.setIcon(8, self.local_icon)
                    child_item.setToolTip(8, f"Local file: {os.path.basename(fits_file.fitsFileName)}")
                    child_item.setText(10, fits_file.fitsFileName or "")  # Filename in column 10
                
                if fits_file.fitsFileCloudURL:
                    child_item.setIcon(9, self.cloud_icon)
                    child_item.setToolTip(9, f"Cloud file: {fits_file.fitsFileCloudURL}")
                
                parent_item.addChild(child_item)
            
            self.file_tree.addTopLevelItem(parent_item)
            parent_item.setExpanded(False)  # Start collapsed

    def _load_fits_data_by_date_paginated(self):
        """Load FITS file data grouped by date."""
        from peewee import fn
        
        # Get unique dates (date only, not time) with search and frame filter applied
        base_query = self._get_fits_files_query()
        dates_query = (base_query
                      .select(fn.DATE(FitsFileModel.fitsFileDate).alias('date_only'))
                      .distinct()
                      .order_by(fn.DATE(FitsFileModel.fitsFileDate).desc()))
        
        # Get all unique dates (date only)
        all_dates = [row.date_only for row in dates_query if row.date_only]
        page_dates = all_dates
        
        # Load files for each date
        for date_obj in page_dates:
            # Query files for this date (all files on this date regardless of time)
            date_files = self._get_fits_files_query().where(fn.DATE(FitsFileModel.fitsFileDate) == date_obj)
            date_files = date_files.order_by(FitsFileModel.fitsFileObject)
            
            # Create parent item for date (Date in first column as expandable section)
            parent_item = QTreeWidgetItem()
            parent_item.setText(0, str(date_obj))  # Date in first column (Object column)
            parent_item.setText(1, f"({len(date_files)} files)")  # File count in Type column
            parent_item.setText(2, "")  # Empty for child date column
            parent_item.setText(3, "")  # Exposure
            parent_item.setText(4, "")  # Filter
            parent_item.setText(5, "")  # Telescope
            parent_item.setText(6, "")  # Instrument
            parent_item.setText(7, "")  # Temperature
            parent_item.setText(8, "")  # Local icon column - empty for parent
            parent_item.setText(9, "")  # Cloud icon column - empty for parent
            parent_item.setText(10, "")  # Filename
            
            # Style parent item - make date bold in first column
            font = parent_item.font(0)  # First column (Object/Date)
            font.setBold(True)
            parent_item.setFont(0, font)
            
            # Add child items for each file
            for fits_file in date_files:
                child_item = QTreeWidgetItem()
                child_item.setText(0, fits_file.fitsFileObject or "")  # Object in first column
                child_item.setText(1, fits_file.fitsFileType or "")
                child_item.setText(2, "")  # Empty date for child (parent shows the date)
                child_item.setText(3, str(fits_file.fitsFileExpTime) if fits_file.fitsFileExpTime else "")
                child_item.setText(4, fits_file.fitsFileFilter or "")
                child_item.setText(5, fits_file.fitsFileTelescop or "")
                child_item.setText(6, fits_file.fitsFileInstrument or "")
                child_item.setText(7, str(fits_file.fitsFileCCDTemp) if fits_file.fitsFileCCDTemp else "")
                
                # Set icons for local and cloud status
                if fits_file.fitsFileName:
                    child_item.setIcon(8, self.local_icon)
                    child_item.setToolTip(8, f"Local file: {os.path.basename(fits_file.fitsFileName)}")
                    child_item.setText(10, fits_file.fitsFileName or "")  # Filename in column 10
                
                if fits_file.fitsFileCloudURL:
                    child_item.setIcon(9, self.cloud_icon)
                    child_item.setToolTip(9, f"Cloud file: {fits_file.fitsFileCloudURL}")
                
                parent_item.addChild(child_item)
            
            self.file_tree.addTopLevelItem(parent_item)
            parent_item.setExpanded(False)  # Start collapsed

    def _load_fits_data_by_filter_paginated(self):
        """Load FITS file data grouped by filter."""
        # Get unique filters with search and frame filter applied
        base_query = self._get_fits_files_query()
        filters_query = (base_query
                        .select(FitsFileModel.fitsFileFilter)
                        .distinct()
                        .order_by(FitsFileModel.fitsFileFilter))
        
        # Get all unique filters
        all_filters = [filt.fitsFileFilter or "No Filter" for filt in filters_query]
        page_filters = all_filters
        
        # Load files for each filter
        for filter_name in page_filters:
            # Query files for this filter
            if filter_name == "No Filter":
                filter_files = self._get_fits_files_query().where(FitsFileModel.fitsFileFilter.is_null(True))
            else:
                filter_files = self._get_fits_files_query().where(FitsFileModel.fitsFileFilter == filter_name)
            
            filter_files = filter_files.order_by(FitsFileModel.fitsFileDate.desc())
            
            # Create parent item for filter (Filter in first column as expandable section)
            parent_item = QTreeWidgetItem()
            parent_item.setText(0, filter_name)  # Filter in first column (Object column)
            parent_item.setText(1, f"({len(filter_files)} files)")  # File count in Type column
            parent_item.setText(2, "")  # Date
            parent_item.setText(3, "")  # Exposure
            parent_item.setText(4, "")  # Empty for child filter column
            parent_item.setText(5, "")  # Telescope
            parent_item.setText(6, "")  # Instrument
            parent_item.setText(7, "")  # Temperature
            parent_item.setText(8, "")  # Local icon column - empty for parent
            parent_item.setText(9, "")  # Cloud icon column - empty for parent
            parent_item.setText(10, "")  # Filename
            
            # Style parent item - make filter bold in first column
            font = parent_item.font(0)  # First column (Object/Filter)
            font.setBold(True)
            parent_item.setFont(0, font)
            
            # Add child items for each file
            for fits_file in filter_files:
                child_item = QTreeWidgetItem()
                child_item.setText(0, fits_file.fitsFileObject or "")  # Object in first column
                child_item.setText(1, fits_file.fitsFileType or "")
                child_item.setText(2, str(fits_file.fitsFileDate) if fits_file.fitsFileDate else "")
                child_item.setText(3, str(fits_file.fitsFileExpTime) if fits_file.fitsFileExpTime else "")
                child_item.setText(4, "")  # Empty filter for child (parent shows the filter)
                child_item.setText(5, fits_file.fitsFileTelescop or "")
                child_item.setText(6, fits_file.fitsFileInstrument or "")
                child_item.setText(7, str(fits_file.fitsFileCCDTemp) if fits_file.fitsFileCCDTemp else "")
                
                # Set icons for local and cloud status
                if fits_file.fitsFileName:
                    child_item.setIcon(8, self.local_icon)
                    child_item.setToolTip(8, f"Local file: {os.path.basename(fits_file.fitsFileName)}")
                    child_item.setText(10, fits_file.fitsFileName or "")  # Filename in column 10
                
                if fits_file.fitsFileCloudURL:
                    child_item.setIcon(9, self.cloud_icon)
                    child_item.setToolTip(9, f"Cloud file: {fits_file.fitsFileCloudURL}")
                
                parent_item.addChild(child_item)
            
            self.file_tree.addTopLevelItem(parent_item)
            parent_item.setExpanded(False)  # Start collapsed

    def show_file_context_menu(self, position):
        """Show context menu for file items"""
        item = self.file_tree.itemAt(position)
        if not item:
            return
        
        # Only show context menu for child items (actual files), not parent items
        if item.parent() is None:
            return
        
        # Get the filename from column 10
        filename = item.text(10)  # Filename is in column 10
        if not filename:
            return
        
        # Create context menu
        context_menu = QMenu(self)
        
        # Add View action
        view_action = context_menu.addAction("View")
        view_action.setToolTip("Open file with external viewer")
        view_action.triggered.connect(lambda: self._view_file(filename))
        
        # Add Delete action
        delete_action = context_menu.addAction("Delete")
        delete_action.setToolTip("Delete file from disk")
        delete_action.triggered.connect(lambda: self._delete_file(filename))
        
        # Show the context menu
        context_menu.exec(self.file_tree.mapToGlobal(position))

    def _view_file(self, filename):
        """View file with configured external viewer"""
        try:
            # Check if file exists
            if not os.path.exists(filename):
                QMessageBox.warning(self, "File Not Found", f"File not found: {filename}")
                return
            
            # Read configuration to get FITS viewer path
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            fits_viewer_path = config.get('DEFAULT', 'fits_viewer_path', fallback=None)
            
            # Try to open with configured FITS viewer first
            if fits_viewer_path and os.path.exists(fits_viewer_path):
                try:
                    import subprocess
                    subprocess.Popen([fits_viewer_path, filename])
                    logger.info(f"Opened file with configured viewer: {fits_viewer_path}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to open with configured viewer {fits_viewer_path}: {e}")
                    # Fall through to system default viewer
            
            # Try to open with default system viewer as fallback
            if os.name == 'nt':  # Windows
                os.startfile(filename)
            elif os.name == 'posix':  # macOS and Linux
                if os.uname().sysname == 'Darwin':  # macOS
                    os.system(f'open "{filename}"')
                else:  # Linux
                    os.system(f'xdg-open "{filename}"')
            else:
                QMessageBox.information(self, "Unsupported", "File viewing not supported on this platform")
                
        except Exception as e:
            logger.error(f"Error viewing file {filename}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")

    def _delete_file(self, filename):
        """Delete file from disk"""
        try:
            # Check if file exists
            if not os.path.exists(filename):
                QMessageBox.warning(self, "File Not Found", f"File not found: {filename}")
                return
            
            # Read configuration to check suppress_delete_warnings
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            suppress_warnings = config.getboolean('DEFAULT', 'suppress_delete_warnings', fallback=False)
            
            # Show confirmation dialog only if warnings are not suppressed
            if not suppress_warnings:
                # Create custom dialog with checkbox
                reply, dont_ask_again = self._show_delete_confirmation_with_checkbox(filename)
                
                # If user checked "Don't ask again", update config file
                if dont_ask_again:
                    config.set('DEFAULT', 'suppress_delete_warnings', 'True')
                    with open('astrofiler.ini', 'w') as configfile:
                        config.write(configfile)
                
                if not reply:
                    return
            # If warnings are suppressed, proceed directly without confirmation
            
            # Soft-delete the file (mark as deleted in database, don't remove from disk)
            try:
                # Update the database record to mark as soft-deleted
                update_count = (FitsFileModel
                               .update(fitsFileSoftDelete=True)
                               .where(FitsFileModel.fitsFileName == filename)
                               .execute())
                
                if update_count > 0:
                    logger.info(f"Soft-deleted file in database: {filename}")
                    
                    # Refresh the display
                    self.load_fits_data()
                    
                    QMessageBox.information(self, "File Soft-Deleted", 
                                          f"File marked as deleted:\n{os.path.basename(filename)}\n\n"
                                          f"The file remains on disk but is hidden from view.\n"
                                          f"Check 'Show Deleted' to see it again.")
                    logger.info(f"Successfully soft-deleted file: {filename}")
                else:
                    logger.warning(f"File not found in database: {filename}")
                    QMessageBox.warning(self, "File Not Found", f"File not found in database: {filename}")
                    
            except Exception as db_error:
                logger.error(f"Error soft-deleting file from database: {db_error}")
                QMessageBox.warning(self, "Database Error", f"Could not mark file as deleted:\n{str(db_error)}")
            
        except PermissionError:
            QMessageBox.critical(self, "Permission Error", f"Permission denied. Cannot delete file:\n{os.path.basename(filename)}")
            logger.error(f"Permission denied deleting file: {filename}")
        except FileNotFoundError:
            QMessageBox.warning(self, "File Not Found", f"File not found:\n{os.path.basename(filename)}")
            logger.warning(f"File not found for deletion: {filename}")
        except Exception as e:
            logger.error(f"Error deleting file {filename}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete file:\n{str(e)}")

    def _show_delete_confirmation_with_checkbox(self, filename):
        """Show delete confirmation dialog with 'Do not ask again' checkbox"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Delete File")
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        # Message label
        message = QLabel(f"Are you sure you want to delete this file?\n\n{os.path.basename(filename)}\n\nThe file will be marked as deleted but will remain on disk.\nYou can view deleted files using the 'Show Deleted' checkbox.")
        message.setWordWrap(True)
        layout.addWidget(message)
        
        # Checkbox
        checkbox = QCheckBox("Do not ask again")
        layout.addWidget(checkbox)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No, dialog)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Show dialog and get result
        result = dialog.exec()
        confirmed = (result == QDialog.Accepted)
        dont_ask_again = checkbox.isChecked()
        
        return confirmed, dont_ask_again
    
    def on_item_double_clicked(self, item, column):
        """Handle double-click on tree widget items"""
        # Only handle double-clicks on child items (actual files), not parent items
        if item.parent() is None:
            return
        
        # Get the filename from column 10
        filename = item.text(10)  # Filename is in column 10
        if filename:
            self._view_file(filename)
    
    def perform_search(self):
        """Perform search."""
        self.search_term = self.search_input.text().strip()
        self.load_fits_data()
    
    def clear_search(self):
        """Clear search."""
        self.search_input.clear()
        self.search_term = ""
        self.load_fits_data()
    
    def show_download_dialog(self):
        """Show the download dialog for smart telescopes."""
        try:
            dialog = SmartTelescopeDownloadDialog(self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening download dialog: {e}")
            QMessageBox.critical(self, "Error", f"Error opening download dialog: {e}")
    
    def load_repo(self):
        """Load the repository by running registerFitsImages with progress dialog."""
        try:
            from astrofiler.core import fitsProcessing
            
            # Show warning dialog first
            warning_msg = ("This function creates folders, renames files, and moves them into the folder structure.\n\n"
                          "This operation will:\n"
                          "• Scan your source directory for FITS and XISF files\n"
                          "• Convert XISF files to FITS format automatically\n"
                          "• Create an organized folder structure\n"
                          "• Move and rename files according to their metadata\n\n"
                          "Do you want to continue?")
            
            reply = QMessageBox.question(
                self,
                "Load Repository Warning",
                warning_msg,
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            
            if reply != QMessageBox.Ok:
                return
            
            progress_dialog = None
            was_cancelled = False
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Scanning for FITS and XISF files...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Loading Repository")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.setValue(0)  # Set initial value
            progress_dialog.show()
            QApplication.processEvents()  # Process events to show dialog
            
            # Small delay to ensure dialog is visible
            import time
            time.sleep(0.1)
            
            def update_progress(current, total, filename):
                """Progress callback function"""
                nonlocal was_cancelled
                try:
                    logger.debug(f"Progress callback called: {current}/{total} - {filename}")
                    
                    # Don't check cancellation if already cancelled
                    if was_cancelled:
                        logger.debug("Already cancelled, returning False")
                        return False
                    
                    # Check if dialog was cancelled before updating
                    if progress_dialog and progress_dialog.wasCanceled():
                        logger.debug("User cancelled the operation")
                        was_cancelled = True
                        return False  # Signal to stop processing
                    
                    if progress_dialog:
                        progress = int((current / total) * 100) if total > 0 else 0
                        progress_dialog.setValue(progress)
                        progress_dialog.setLabelText(f"Processing {current}/{total}: {os.path.basename(filename)}")
                        QApplication.processEvents()  # Keep UI responsive
                        
                        # Check again after processing events
                        if progress_dialog.wasCanceled():
                            logger.debug("User cancelled the operation during update")
                            was_cancelled = True
                            return False
                    
                    logger.debug(f"Progress callback returning True for {filename}")
                    return True  # Continue processing
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
                    return True  # Continue on callback errors
            
            # Create and run the FITS processing
            fits_processor = fitsProcessing()
            logger.debug("Starting registerFitsImages with progress callback")
            result = fits_processor.registerFitsImages(moveFiles=True, progress_callback=update_progress)
            
            # Handle the new tuple return format (registered_files, duplicate_count)
            if isinstance(result, tuple):
                registered_files, duplicate_count = result
            else:
                # Backward compatibility for old return format
                registered_files = result
                duplicate_count = 0
                
            logger.debug(f"registerFitsImages completed, registered {len(registered_files)} files, duplicates {duplicate_count}")
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled or completed normally
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Repository loading was cancelled by user.")
                logger.debug("Operation was cancelled by user")
            elif len(registered_files) == 0:
                if duplicate_count > 0:
                    QMessageBox.information(self, "No New Files", f"No new FITS files were processed. {duplicate_count} duplicate files were skipped.")
                else:
                    QMessageBox.information(self, "No Files", "No FITS files found to process in the source directory.")
                logger.info("No FITS files found to process")
            else:
                if duplicate_count > 0:
                    QMessageBox.information(self, "Success", f"Repository loading completed successfully! Processed {len(registered_files)} files, skipped {duplicate_count} duplicates.")
                else:
                    QMessageBox.information(self, "Success", f"Repository loading completed successfully! Processed {len(registered_files)} files.")
                self.load_fits_data()  # Refresh the display
                
                # Auto-regenerate sessions after new files are loaded
                try:
                    from .sessions_widget import SessionsWidget
                    # Get the main window and sessions widget
                    main_window = self.parent()
                    while main_window and not hasattr(main_window, 'sessions_widget'):
                        main_window = main_window.parent()
                    
                    if main_window and hasattr(main_window, 'sessions_widget'):
                        logger.info("Auto-regenerating sessions after Load New...")
                        if hasattr(main_window.sessions_widget, 'auto_regenerate_sessions'):
                            main_window.sessions_widget.auto_regenerate_sessions()
                        else:
                            logger.warning("auto_regenerate_sessions method not found on sessions widget")
                    else:
                        logger.warning("Could not find main window or sessions widget for auto-regeneration")
                        
                except Exception as e:
                    logger.error(f"Error auto-regenerating sessions after Load New: {e}")
                
                logger.info("Operation completed successfully")
                
        except ImportError:
            QMessageBox.warning(self, "Error", "Could not import core module. Please check your installation.")
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error in load_repo: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred while loading the repository:\n{str(e)}")

    def sync_repo(self):
        """Sync the repository by running registerFitsImages with moveFiles=False."""
        try:
            from astrofiler.core import fitsProcessing
            
            # Show information dialog first
            info_msg = ("This function will synchronize the repository database with existing files.\n\n"
                       "This operation will:\n"
                       "• Clear the current database\n"
                       "• Scan your repository directory for FITS files\n"
                       "• Update the database with file information\n"
                       "• Will NOT move or rename any files\n\n"
                       "Do you want to continue?")
            
            reply = QMessageBox.question(
                self,
                "Sync Repository",
                info_msg,
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            
            if reply != QMessageBox.Ok:
                return
            
            # Clear repository first before syncing
            try:
                # Clear the tree widget
                self.file_tree.clear()
                
                # Delete all fitsSession records from the database
                deleted_sessions = FitsSessionModel.delete().execute()
                
                # Delete all fitsFile records from the database
                deleted_files = FitsFileModel.delete().execute()
                
                logger.info(f"Cleared repository before sync: {deleted_sessions} sessions, {deleted_files} files")
            except Exception as e:
                logger.error(f"Error clearing repository before sync: {e}")
                QMessageBox.warning(self, "Error", f"Failed to clear repository before sync: {e}")
                return
            
            progress_dialog = None
            was_cancelled = False
            
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
            
            # Create and run the FITS processing
            fits_processor = fitsProcessing()
            # For regeneration, scan the repository folder instead of the source folder
            result = fits_processor.registerFitsImages(
                moveFiles=False, 
                progress_callback=update_progress, 
                source_folder=fits_processor.repoFolder
            )
            
            # Handle the new tuple return format (registered_files, duplicate_count)
            if isinstance(result, tuple):
                registered_files, duplicate_count = result
            else:
                # Backward compatibility for old return format
                registered_files = result
                duplicate_count = 0
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Check if operation was cancelled or completed normally
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", "Repository synchronization was cancelled by user.")
                logger.info("Repository synchronization was cancelled by user")
            elif len(registered_files) == 0:
                if duplicate_count > 0:
                    QMessageBox.information(self, "No New Files", f"No new FITS files were processed. {duplicate_count} duplicate files were skipped.")
                else:
                    QMessageBox.information(self, "No Files", "No FITS files found to process in the repository directory.")
                logger.info("No FITS files found to process")
            else:
                if duplicate_count > 0:
                    QMessageBox.information(self, "Success", f"Repository synchronization completed successfully! Processed {len(registered_files)} files, skipped {duplicate_count} duplicates.")
                else:
                    QMessageBox.information(self, "Success", f"Repository synchronization completed successfully! Processed {len(registered_files)} files.")
                self.load_fits_data()  # Refresh the display
                logger.info("Repository synchronization completed successfully")
                
        except ImportError:
            QMessageBox.warning(self, "Error", "Could not import core module. Please check your installation.")
        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error in sync_repo: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred while synchronizing the repository:\n{str(e)}")
    
    def clear_files(self):
        """Clear the file tree and delete all records from the database."""
        reply = QMessageBox.question(self, "Clear Repository", 
                                    "Are you sure you want to clear all files from the repository?\n\nThis will remove all database records but not delete physical files.",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                # Clear the tree widget
                self.file_tree.clear()
                
                # Delete all fitsSession records from the database
                deleted_sessions = FitsSessionModel.delete().execute()
                
                # Delete all fitsFile records from the database
                deleted_files = FitsFileModel.delete().execute()
                
                QMessageBox.information(self, "Repository Cleared", 
                                      f"Repository has been cleared.\n\nDeleted {deleted_sessions} sessions and {deleted_files} files from database.")
                logger.info(f"Clear repository completed: {deleted_sessions} sessions, {deleted_files} files")
                
            except Exception as e:
                logger.error(f"Error clearing repository: {e}")
                QMessageBox.critical(self, "Error", f"Failed to clear repository:\n{str(e)}")

    def open_mappings_dialog(self):
        """Open the mappings dialog"""
        try:
            from .mappings_dialog import MappingsDialog
            dialog = MappingsDialog(self)
            result = dialog.exec()
            
            # Refresh the Images view after the dialog closes
            # This ensures any applied mappings are reflected in the display
            if result == QDialog.DialogCode.Accepted or result == QDialog.DialogCode.Rejected:
                logger.debug("Refreshing Images view after mappings dialog closed")
                self.load_fits_data()
                
        except ImportError:
            QMessageBox.information(self, "Mappings", "Mappings dialog will be implemented.")
        except Exception as e:
            logger.error(f"Error opening mappings dialog: {e}")
            QMessageBox.critical(self, "Error", f"Error opening mappings dialog: {e}")

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
