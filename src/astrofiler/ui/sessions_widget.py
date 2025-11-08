import os
import sys
import logging
import datetime
from datetime import datetime as dt
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTreeWidget, QTreeWidgetItem, QAbstractItemView,
                               QMenu, QProgressDialog, QApplication, QMessageBox,
                               QFileDialog, QLabel, QProgressBar)
from PySide6.QtGui import QFont, QDesktopServices, QIcon, QPixmap, QPainter, QColor, QBrush
from PySide6.QtCore import QUrl

from astrofiler.core import fitsProcessing
from astrofiler.models import fitsFile as FitsFileModel, fitsSession as FitsSessionModel

logger = logging.getLogger(__name__)

class SessionsWidget(QWidget):
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
        self.regenerate_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.regenerate_button.setToolTip("Clear all sessions and regenerate: Update Lights → Update Calibrations → Link Sessions")
        
        self.auto_calibration_button = QPushButton("Auto-Calibration")
        self.auto_calibration_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.auto_calibration_button.setToolTip("Analyze sessions and automatically create master calibration frames")
        
        controls_layout.addWidget(self.regenerate_button)
        controls_layout.addWidget(self.auto_calibration_button)
        controls_layout.addStretch()
        
        # Sessions list
        self.sessions_tree = QTreeWidget()
        self.sessions_tree.setHeaderLabels(["Object Name", "Date", "Telescope", "Imager", "Filter", "Images", "Resources"])
        
        # Enable multi-selection
        self.sessions_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # Set column widths for better display
        self.sessions_tree.setColumnWidth(0, 200)  # Object Name
        self.sessions_tree.setColumnWidth(1, 150)  # Date
        self.sessions_tree.setColumnWidth(2, 150)  # Telescope
        self.sessions_tree.setColumnWidth(3, 150)  # Imager
        self.sessions_tree.setColumnWidth(4, 100)  # Filter
        self.sessions_tree.setColumnWidth(5, 80)   # Images
        self.sessions_tree.setColumnWidth(6, 140)  # Resources
        
        # Enable context menu
        self.sessions_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sessions_tree.customContextMenuRequested.connect(self.show_context_menu)

        layout.addLayout(controls_layout)
        layout.addWidget(self.sessions_tree)
        
        # Connect signals
        self.regenerate_button.clicked.connect(self.regenerate_sessions)
        self.auto_calibration_button.clicked.connect(self.run_auto_calibration)
    
    def show_context_menu(self, position):
        """Show context menu for session items with master frame management"""
        item = self.sessions_tree.itemAt(position)
        if not item:
            return
            
        # Get all selected items
        selected_items = self.sessions_tree.selectedItems()
        if not selected_items:
            return
        
        # Analyze selected items to determine menu options
        light_sessions = []
        calibration_sessions = []
        parent_objects = []
        
        for selected_item in selected_items:
            parent = selected_item.parent()
            if not parent:
                # This is a parent item (object name)
                parent_objects.append(selected_item)
                continue
                
            # This is a session item
            object_name = parent.text(0)
            if object_name in ['Bias', 'Dark', 'Flat']:
                calibration_sessions.append(selected_item)
            else:
                light_sessions.append(selected_item)
        
        # Create context menu based on selection
        context_menu = QMenu(self)
        
        # === CHECKOUT OPTIONS ===
        if light_sessions:
            if len(light_sessions) == 1:
                checkout_action = context_menu.addAction("📂 Check out")
                checkout_action.setToolTip("Create symbolic links for this session's files")
            else:
                checkout_action = context_menu.addAction(f"📂 Check out ({len(light_sessions)} sessions)")
                checkout_action.setToolTip("Create symbolic links for selected light sessions")
        else:
            checkout_action = None
        
        # === SESSION MANAGEMENT ===
        if light_sessions or calibration_sessions:
            if len(selected_items) == 1:
                properties_action = context_menu.addAction("🔍 Properties")
                properties_action.setToolTip("View detailed session properties and metadata")

        # Show the menu and handle selected action
        if context_menu.isEmpty():
            return
            
        action = context_menu.exec(self.sessions_tree.viewport().mapToGlobal(position))
        
        if not action:
            return
            
        # === HANDLE ACTIONS ===
        # Checkout actions
        if action == checkout_action:
            if len(light_sessions) == 1:
                logger.info(f"Checking out session: {light_sessions[0].parent().text(0)} on {light_sessions[0].text(1)}")
                self.checkout_session(light_sessions[0])
            else:
                logger.info(f"Checking out {len(light_sessions)} sessions")
                self.checkout_multiple_sessions(light_sessions)
        
        # Session management actions        
        elif action.text().startswith("🔍 Properties"):
            self.show_session_properties(selected_items[0])
    
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
                logger.info(f"Found session: {object_name} on {session_date}")
                
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
                    logger.info(f"Found {bias_files.count()} bias files")

                if session.fitsDarkSession:
                    dark_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsDarkSession)
                    logger.info(f"Found {dark_files.count()} dark files")

                # Get all unique filters used in light frames
                filters = set([lf.fitsFileFilter for lf in light_files if lf.fitsFileFilter])
                logger.info(f"Filters used in light frames: {filters}")
                
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
                        logger.info(f"Found {these_flats.count()} flat files for filter {filter_name}")

            # Combine all files for progress tracking
            all_files = list(light_files) + list(dark_files) + list(bias_files) + list(flat_files)
            total_files = len(all_files)
            
            if total_files == 0:
                QMessageBox.information(self, "Information", "No files found for this session")
                return
            logger.info(f"Found {total_files} files for session {object_name} on {session_date}")

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
            logger.info(f"Created session directory structure at {session_dir}")  

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
                    logger.warning(f"Unknown file type for {file.fitsFileName}, skipping")
                    continue  # Skip unknown file types
                    
                # Extract filename from path
                logger.info(f"Processing file: {file.fitsFileName} of type {file.fitsFileType}")
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
                    logger.info(f"Created link for {file.fitsFileName} -> {dest_path}")
                except Exception as e:
                    logger.error(f"Error creating link for {file.fitsFileName}: {e}")
            
            # Close progress dialog
            progress.setValue(100)
            
            # Display success message
            QMessageBox.information(
                self, 
                "Success", 
                f"Created {created_links} symbolic links in {session_dir}"
            )
            
            # Open the directory
            QDesktopServices.openUrl(QUrl.fromLocalFile(session_dir))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create symbolic links: {str(e)}")
            logger.error(f"Error in checkout_session: {str(e)}")

    def checkout_multiple_sessions(self, session_items):
        """Create symbolic links for multiple sessions in a common directory structure"""
        try:
            # Ask user for destination directory
            dest_dir = QFileDialog.getExistingDirectory(
                self, 
                "Select Destination Directory for Multiple Sessions",
                os.path.expanduser("~"),
                QFileDialog.ShowDirsOnly
            )
            
            if not dest_dir:
                return  # User cancelled
            
            # Create main checkout directory
            checkout_dir = os.path.join(dest_dir, f"Sessions_Checkout_{dt.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(checkout_dir, exist_ok=True)
            
            # Calculate total work for progress tracking
            total_sessions = len(session_items)
            current_session = 0
            
            # Progress dialog for overall operation
            overall_progress = QProgressDialog("Processing sessions...", "Cancel", 0, total_sessions, self)
            overall_progress.setWindowModality(Qt.WindowModal)
            overall_progress.setWindowTitle("Checking Out Multiple Sessions")
            
            successful_sessions = 0
            failed_sessions = []
            
            for session_item in session_items:
                if overall_progress.wasCanceled():
                    break
                    
                try:
                    # Get session information
                    session_date = session_item.text(1)
                    object_name = session_item.parent().text(0)
                    
                    overall_progress.setLabelText(f"Processing {object_name} - {session_date}...")
                    overall_progress.setValue(current_session)
                    
                    # Get the session from database
                    session = FitsSessionModel.select().where(
                        (FitsSessionModel.fitsSessionObjectName == object_name) & 
                        (FitsSessionModel.fitsSessionDate == session_date)
                    ).first()
                    
                    if not session:
                        failed_sessions.append(f"{object_name} - {session_date}: Not found in database")
                        continue
                    
                    # Create session-specific directory
                    session_dir = os.path.join(checkout_dir, f"{object_name}_{session_date.replace(':', '-')}")
                    light_dir = os.path.join(session_dir, "lights")
                    dark_dir = os.path.join(session_dir, "darks")
                    flat_dir = os.path.join(session_dir, "flats")
                    bias_dir = os.path.join(session_dir, "bias")
                    process_dir = os.path.join(session_dir, "process")
                    
                    # Create directories
                    os.makedirs(light_dir, exist_ok=True)
                    os.makedirs(dark_dir, exist_ok=True)
                    os.makedirs(flat_dir, exist_ok=True)
                    os.makedirs(bias_dir, exist_ok=True)
                    os.makedirs(process_dir, exist_ok=True)
                    
                    # Get files
                    light_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsSessionId)
                    dark_files = []
                    bias_files = []
                    flat_files = []
                    
                    # Get calibration files
                    if session.fitsBiasSession:
                        bias_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsBiasSession)
                    if session.fitsDarkSession:
                        dark_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsDarkSession)
                    
                    # Get flats for each filter
                    filters = set([lf.fitsFileFilter for lf in light_files if lf.fitsFileFilter])
                    for filter_name in filters:
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
                    
                    # Create symbolic links
                    all_files = list(light_files) + list(dark_files) + list(bias_files) + list(flat_files)
                    session_links = 0
                    
                    for file in all_files:
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
                            continue
                        
                        filename = os.path.basename(file.fitsFileName)
                        dest_path = os.path.join(dest_folder, filename)
                        
                        try:
                            if not os.path.exists(dest_path):
                                if sys.platform == "win32":
                                    import subprocess
                                    subprocess.run(["mklink", dest_path, file.fitsFileName], shell=True)
                                else:
                                    os.symlink(file.fitsFileName, dest_path)
                                session_links += 1
                        except Exception as e:
                            logger.error(f"Error creating link for {file.fitsFileName}: {e}")
                    
                    # Create Siril script
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
                    
                    successful_sessions += 1
                    logger.info(f"Successfully processed session {object_name} - {session_date} with {session_links} links")
                    
                except Exception as e:
                    failed_sessions.append(f"{object_name} - {session_date}: {str(e)}")
                    logger.error(f"Error processing session {object_name} - {session_date}: {e}")
                
                current_session += 1
            
            overall_progress.setValue(total_sessions)
            
            # Show results
            message = f"Successfully processed {successful_sessions} out of {total_sessions} sessions."
            if failed_sessions:
                message += f"\n\nFailed sessions:\n" + "\n".join(failed_sessions)
            
            if successful_sessions > 0:
                message += f"\n\nFiles created in: {checkout_dir}"
                QMessageBox.information(self, "Multiple Sessions Checkout Complete", message)
                # Open the directory
                QDesktopServices.openUrl(QUrl.fromLocalFile(checkout_dir))
            else:
                QMessageBox.warning(self, "Multiple Sessions Checkout Failed", message)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to checkout multiple sessions: {str(e)}")
            logger.error(f"Error in checkout_multiple_sessions: {str(e)}")

        # === SESSION MANAGEMENT METHODS ===

    def show_session_properties(self, session_item):
        """Show detailed properties for a session"""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QTabWidget, QWidget, QTableWidget, QTableWidgetItem, QHeaderView
            
            parent = session_item.parent()
            if not parent:
                QMessageBox.information(self, "Properties", "Properties view is only available for individual sessions.")
                return
            
            # Get session information
            object_name = parent.text(0)
            session_date = session_item.text(1)
            
            # Find session in database
            session = FitsSessionModel.select().where(
                (FitsSessionModel.fitsSessionObjectName == object_name) & 
                (FitsSessionModel.fitsSessionDate == session_date)
            ).first()
            
            if not session:
                QMessageBox.warning(self, "Error", "Session not found in database")
                return
            
            # Create properties dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Session Properties: {object_name} - {session_date}")
            dialog.setMinimumSize(700, 500)
            layout = QVBoxLayout(dialog)
            
            # Create tab widget
            tabs = QTabWidget()
            
            # === SESSION INFO TAB ===
            session_tab = QWidget()
            session_layout = QVBoxLayout(session_tab)
            
            session_info = QTextEdit()
            session_info.setReadOnly(True)
            
            info_content = f"Session Properties\n"
            info_content += f"=" * 50 + "\n\n"
            info_content += f"Session ID: {session.fitsSessionId}\n"
            info_content += f"Object Name: {session.fitsSessionObjectName}\n"
            info_content += f"Date: {session.fitsSessionDate}\n"
            info_content += f"Telescope: {session.fitsSessionTelescope or 'Unknown'}\n"
            info_content += f"Imager: {session.fitsSessionImager or 'Unknown'}\n"
            info_content += f"Exposure: {session.fitsSessionExposure or 'Unknown'}s\n"
            info_content += f"Binning: {session.fitsSessionBinningX or '?'}x{session.fitsSessionBinningY or '?'}\n"
            info_content += f"CCD Temperature: {session.fitsSessionCCDTemp or 'Unknown'}°C\n"
            info_content += f"Gain: {session.fitsSessionGain or 'Unknown'}\n"
            info_content += f"Offset: {session.fitsSessionOffset or 'Unknown'}\n"
            info_content += f"Filter: {session.fitsSessionFilter or 'Unknown'}\n\n"
            
            info_content += f"Calibration Links:\n"
            info_content += f"Bias Session: {session.fitsBiasSession or 'Not linked'}\n"
            info_content += f"Dark Session: {session.fitsDarkSession or 'Not linked'}\n"
            info_content += f"Flat Session: {session.fitsFlatSession or 'Not linked'}\n\n"
            
            info_content += f"Master Frames:\n"
            info_content += f"Bias Master: {session.fitsBiasMaster or 'Not available'}\n"
            info_content += f"Dark Master: {session.fitsDarkMaster or 'Not available'}\n"
            info_content += f"Flat Master: {session.fitsFlatMaster or 'Not available'}\n"
            
            session_info.setPlainText(info_content)
            session_layout.addWidget(session_info)
            tabs.addTab(session_tab, "Session Info")
            
            # === FILES TAB ===
            files_tab = QWidget()
            files_layout = QVBoxLayout(files_tab)
            
            files_table = QTableWidget()
            files_table.setColumnCount(6)
            files_table.setHorizontalHeaderLabels([
                "Filename", "Type", "Date", "Calibrated", "Hash", "Size"
            ])
            
            # Get session files
            session_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsSessionId)
            files_table.setRowCount(session_files.count())
            
            for i, file in enumerate(session_files):
                files_table.setItem(i, 0, QTableWidgetItem(os.path.basename(file.fitsFileName or '')))
                files_table.setItem(i, 1, QTableWidgetItem(file.fitsFileType or 'Unknown'))
                files_table.setItem(i, 2, QTableWidgetItem(str(file.fitsFileDate or 'Unknown')))
                files_table.setItem(i, 3, QTableWidgetItem('Yes' if file.fitsFileCalibrated else 'No'))
                files_table.setItem(i, 4, QTableWidgetItem(file.fitsFileHash or 'Unknown'))
                
                # Get file size
                if file.fitsFileName and os.path.exists(file.fitsFileName):
                    size = os.path.getsize(file.fitsFileName)
                    size_str = f"{size:,} bytes"
                else:
                    size_str = "File not found"
                files_table.setItem(i, 5, QTableWidgetItem(size_str))
            
            # Configure files table
            header = files_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(QHeaderView.ResizeToContents)
            files_table.setAlternatingRowColors(True)
            files_table.setSelectionBehavior(QTableWidget.SelectRows)
            
            files_layout.addWidget(files_table)
            tabs.addTab(files_tab, f"Files ({session_files.count()})")
            
            layout.addWidget(tabs)
            
            # Buttons
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Error showing session properties: {e}")
            QMessageBox.critical(self, "Error", f"Failed to show session properties:\n\n{e}")

    def update_sessions(self):
        """Update light sessions by running createLightSessions method with progress dialog."""
        try:
            logger.info("Starting light sessions creation")
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Creating Light Sessions")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            # Create the processor
            processor = fitsProcessing()
            
            # Define progress callback
            def progress_callback(current, total, description):
                if progress_dialog.wasCanceled():
                    return False
                
                if total > 0:
                    progress = int((current / total) * 100)
                    progress_dialog.setValue(progress)
                    progress_dialog.setLabelText(f"Creating sessions {current}/{total}: {description}")
                else:
                    progress_dialog.setLabelText(f"Processing: {description}")
                
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Run the light sessions creation
            created_sessions = processor.createLightSessions(progress_callback)
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                logger.info("Light sessions creation cancelled by user")
                QMessageBox.information(self, "Cancelled", "Light sessions creation was cancelled.")
                return
            
            # Refresh the display
            self.load_sessions_data()
            
            logger.info(f"Created {len(created_sessions)} light sessions")
            QMessageBox.information(self, "Sessions Created", 
                                  f"Successfully created {len(created_sessions)} light sessions.")
            
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            logger.error(f"Error creating light sessions: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create light sessions: {e}")

    def update_calibration_sessions(self):
        """Update calibration Sessions by running createCalibrationSessions method with progress dialog."""
        try:
            logger.info("Starting calibration sessions creation")
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Creating Calibration Sessions")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            # Create the processor
            processor = fitsProcessing()
            
            # Define progress callback
            def progress_callback(current, total, description):
                if progress_dialog.wasCanceled():
                    return False
                
                if total > 0:
                    progress = int((current / total) * 100)
                    progress_dialog.setValue(progress)
                    progress_dialog.setLabelText(f"Creating calibration sessions {current}/{total}: {description}")
                else:
                    progress_dialog.setLabelText(f"Processing: {description}")
                
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Run the calibration sessions creation
            created_sessions = processor.createCalibrationSessions(progress_callback)
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                logger.info("Calibration sessions creation cancelled by user")
                QMessageBox.information(self, "Cancelled", "Calibration sessions creation was cancelled.")
                return
            
            # Refresh the display
            self.load_sessions_data()
            
            logger.info(f"Created {len(created_sessions)} calibration sessions")
            QMessageBox.information(self, "Sessions Created", 
                                  f"Successfully created {len(created_sessions)} calibration sessions.")
            
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            logger.error(f"Error creating calibration sessions: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create calibration sessions: {e}")

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
                
                # Calculate total image count for this object across all sessions
                total_images = 0
                for session in object_sessions:
                    session_image_count = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsSessionId).count()
                    total_images += session_image_count
                
                # Calculate overall calibration statistics for this object
                calibrated_sessions = 0
                total_light_sessions = 0
                
                for session in object_sessions:
                    if session.fitsSessionObjectName not in ['Bias', 'Dark', 'Flat']:
                        total_light_sessions += 1
                        calibration_info = self._build_resources_status(session)
                        if calibration_info["percentage"] > 0:
                            calibrated_sessions += 1
                
                # Create parent item for each object
                parent_item = QTreeWidgetItem()
                parent_item.setText(0, object_name)
                parent_item.setText(1, "")  # No date for parent
                parent_item.setText(2, "")  # No telescope for parent
                parent_item.setText(3, "")  # No imager for parent
                parent_item.setText(4, "")  # No filter for parent
                parent_item.setText(5, str(total_images))  # Total images for this object
                
                # Show resource summary for parent
                if total_light_sessions > 0:
                    cal_percentage = (calibrated_sessions / total_light_sessions) * 100
                    cal_summary = f"{calibrated_sessions}/{total_light_sessions} ({cal_percentage:.0f}%)"
                    parent_item.setText(6, cal_summary)
                    parent_item.setToolTip(6, f"Resource Coverage: {calibrated_sessions} of {total_light_sessions} sessions have calibration resources")
                else:
                    parent_item.setText(6, "")
                
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
                    # Get the image count for this specific session
                    session_image_count = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsSessionId).count()
                    
                    # Build enhanced resources status
                    calibration_info = self._build_resources_status(session)
                    
                    child_item = QTreeWidgetItem()
                    child_item.setText(0, "")  # Empty object name for child
                    child_item.setText(1, str(session.fitsSessionDate) if session.fitsSessionDate else "Unknown Date")
                    child_item.setText(2, session.fitsSessionTelescope or "Unknown")
                    child_item.setText(3, session.fitsSessionImager or "Unknown")
                    child_item.setText(4, session.fitsSessionFilter or "Unknown")
                    child_item.setText(5, str(session_image_count))  # Image count for this session
                    
                    # Set resources status as simple text only
                    if calibration_info["text"]:
                        child_item.setText(6, calibration_info["text"])
                        child_item.setToolTip(6, calibration_info["tooltip"])
                    else:
                        child_item.setText(6, "")
                    
                    parent_item.addChild(child_item)
                
                # Only add parent item if it has children
                if parent_item.childCount() > 0:
                    self.sessions_tree.addTopLevelItem(parent_item)
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

    def _create_status_icon(self, icon_type, available=True):
        """Create a colored icon for calibration status."""
        size = 12
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Define colors and shapes for different calibration types
        if icon_type == 'B':  # Bias
            color = QColor(0, 150, 255) if available else QColor(128, 128, 128)  # Blue or gray
            painter.setBrush(QBrush(color))
            painter.setPen(color)
            painter.drawEllipse(1, 1, size-2, size-2)
        elif icon_type == 'D':  # Dark
            color = QColor(80, 80, 80) if available else QColor(180, 180, 180)  # Dark gray or light gray
            painter.setBrush(QBrush(color))
            painter.setPen(color)
            painter.drawRect(1, 1, size-2, size-2)
        elif icon_type == 'F':  # Flat
            color = QColor(255, 165, 0) if available else QColor(200, 200, 200)  # Orange or gray
            painter.setBrush(QBrush(color))
            painter.setPen(color)
            # Draw triangle
            points = [
                Qt.QPoint(size//2, 1),
                Qt.QPoint(size-1, size-1),
                Qt.QPoint(1, size-1)
            ]
            painter.drawPolygon(points)
        elif icon_type == 'M':  # Master frame indicator
            color = QColor(0, 200, 0) if available else QColor(150, 150, 150)  # Green or gray
            painter.setBrush(QBrush(color))
            painter.setPen(color)
            painter.drawEllipse(3, 3, size-6, size-6)  # Small filled circle
            
        painter.end()
        return QIcon(pixmap)
    
    def _build_resources_status(self, session):
        """Build resources status showing frame counts or Master availability for light sessions."""
        if session.fitsSessionObjectName in ['Bias', 'Dark', 'Flat']:
            # This is a calibration session, don't show resources status
            return {"text": "", "tooltip": "", "percentage": 0}
        
        # Check if this is a precalibrated telescope/instrument (iTelescope or SeeStar)
        if session.fitsSessionTelescope or session.fitsSessionImager:
            telescope = session.fitsSessionTelescope or ""
            instrument = session.fitsSessionImager or ""
            
            if 'itelescope' in telescope.lower() or 'seestar' in instrument.lower():
                source_name = ""
                if 'itelescope' in telescope.lower():
                    source_name = session.fitsSessionTelescope
                else:
                    source_name = session.fitsSessionImager
                
                return {
                    "text": "Precalibrated",
                    "tooltip": f"Pre-calibrated images from {source_name}",
                    "percentage": 100,
                    "has_bias": True,
                    "has_dark": True,
                    "has_flat": True,
                    "has_masters": True
                }
        
        # Check for master frames first
        has_bias_master = hasattr(session, 'fitsBiasMaster') and session.fitsBiasMaster
        has_dark_master = hasattr(session, 'fitsDarkMaster') and session.fitsDarkMaster
        has_flat_master = hasattr(session, 'fitsFlatMaster') and session.fitsFlatMaster
        
        # Check calibration sessions availability
        has_bias_session = bool(session.fitsBiasSession)
        has_dark_session = bool(session.fitsDarkSession)
        has_flat_session = bool(session.fitsFlatSession)
        
        # Build status parts
        status_parts = []
        tooltip_parts = []
        
        # Dark
        if has_dark_master:
            status_parts.append("Dark: Master")
            tooltip_parts.append("✓ Dark master frame available")
        elif has_dark_session:
            # Count dark frames in the session
            try:
                dark_session = FitsSessionModel.get_by_id(session.fitsDarkSession)
                dark_count = FitsFileModel.select().where(
                    FitsFileModel.fitsFileSession == dark_session.fitsSessionId
                ).count()
                status_parts.append(f"Dark: {dark_count}")
                tooltip_parts.append(f"✓ {dark_count} dark frames available")
            except:
                status_parts.append("Dark: Available")
                tooltip_parts.append("✓ Dark frames available")
        else:
            status_parts.append("Dark: None")
            tooltip_parts.append("✗ No dark frames available")
            
        # Flat
        if has_flat_master:
            status_parts.append("Flat: Master")
            tooltip_parts.append("✓ Flat master frame available")
        elif has_flat_session:
            # Count flat frames in the session
            try:
                flat_session = FitsSessionModel.get_by_id(session.fitsFlatSession)
                flat_count = FitsFileModel.select().where(
                    FitsFileModel.fitsFileSession == flat_session.fitsSessionId
                ).count()
                status_parts.append(f"Flat: {flat_count}")
                tooltip_parts.append(f"✓ {flat_count} flat frames available")
            except:
                status_parts.append("Flat: Available")
                tooltip_parts.append("✓ Flat frames available")
        else:
            status_parts.append("Flat: None")
            tooltip_parts.append("✗ No flat frames available")
            
        # Bias
        if has_bias_master:
            status_parts.append("Bias: Master")
            tooltip_parts.append("✓ Bias master frame available")
        elif has_bias_session:
            # Count bias frames in the session
            try:
                bias_session = FitsSessionModel.get_by_id(session.fitsBiasSession)
                bias_count = FitsFileModel.select().where(
                    FitsFileModel.fitsFileSession == bias_session.fitsSessionId
                ).count()
                status_parts.append(f"Bias: {bias_count}")
                tooltip_parts.append(f"✓ {bias_count} bias frames available")
            except:
                status_parts.append("Bias: Available")
                tooltip_parts.append("✓ Bias frames available")
        else:
            status_parts.append("Bias: None")
            tooltip_parts.append("✗ No bias frames available")
        
        # Calculate readiness percentage (for color coding)
        available_count = sum([
            has_dark_master or has_dark_session,
            has_flat_master or has_flat_session,
            has_bias_master or has_bias_session
        ])
        readiness_percentage = (available_count / 3.0) * 100
        
        # Create comprehensive tooltip
        tooltip = f"Calibration Resources ({readiness_percentage:.0f}% ready):\n" + "\n".join(tooltip_parts)
        
        # Build display text - combine all status parts with commas
        if status_parts:
            text = ", ".join(status_parts)
        else:
            text = "No resources"
            
        return {
            "text": text,
            "tooltip": tooltip,
            "percentage": readiness_percentage,
            "has_bias": has_bias_session or has_bias_master,
            "has_dark": has_dark_session or has_dark_master,
            "has_flat": has_flat_session or has_flat_master,
            "has_masters": any([has_bias_master, has_dark_master, has_flat_master])
        }

    def _create_calibration_progress_widget(self, percentage, has_bias, has_dark, has_flat):
        """Create a compact progress widget showing calibration status."""
        widget = QLabel()
        
        # Create a mini progress representation
        progress_text = "["
        
        # Add indicators for each calibration type
        progress_text += "●" if has_bias else "○"  # Bias
        progress_text += "●" if has_dark else "○"   # Dark  
        progress_text += "●" if has_flat else "○"   # Flat
        
        progress_text += f"] {percentage:.0f}%"
        
        widget.setText(progress_text)
        
        # Color code the text based on completion
        if percentage >= 100:
            widget.setStyleSheet("color: green; font-weight: bold;")
        elif percentage >= 67:
            widget.setStyleSheet("color: orange; font-weight: bold;")
        elif percentage >= 33:
            widget.setStyleSheet("color: #CC8800; font-weight: bold;")
        else:
            widget.setStyleSheet("color: red; font-weight: bold;")
            
        return widget
    
    def _get_calibration_status_icon(self, session):
        """Get an overall calibration status icon for the session."""
        calibration_info = self._build_resources_status(session)
        
        if calibration_info["text"] == "":
            return None
            
        percentage = calibration_info["percentage"]
        
        if percentage >= 100:
            return self._create_status_icon('M', True)  # Master/complete indicator
        elif percentage >= 67:
            return self._create_status_icon('B', True)  # Good status
        elif percentage >= 33:
            return self._create_status_icon('D', True)  # Partial status
        else:
            return self._create_status_icon('F', False)  # Poor status
    def clear_sessions(self):
        """Clear all Session records from the database and refresh the display."""
        try:
            logger.info("Clearing all sessions from database")
            
            # Clear session references in files first to avoid foreign key constraints
            FitsFileModel.update(fitsFileSession=None).execute()
            
            # Delete all sessions
            deleted_count = FitsSessionModel.delete().execute()
            
            logger.info(f"Cleared {deleted_count} sessions from database")
            
            # Refresh the display
            self.load_sessions_data()
            
            QMessageBox.information(self, "Sessions Cleared", 
                                  f"Successfully cleared {deleted_count} sessions from the database.")
            
        except Exception as e:
            logger.error(f"Error clearing sessions: {e}")
            QMessageBox.critical(self, "Error", f"Failed to clear sessions: {e}")

    def link_sessions(self):
        """Link calibration sessions to light sessions with progress dialog."""
        try:
            logger.info("Starting session linking")
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Linking Sessions")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            # Create the processor
            processor = fitsProcessing()
            
            # Define progress callback
            def progress_callback(current, total, description):
                if progress_dialog.wasCanceled():
                    return False
                
                if total > 0:
                    progress = int((current / total) * 100)
                    progress_dialog.setValue(progress)
                    progress_dialog.setLabelText(f"Linking sessions {current}/{total}: {description}")
                else:
                    progress_dialog.setLabelText(f"Processing: {description}")
                
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Run the session linking
            updated_sessions = processor.linkSessions(progress_callback)
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                logger.info("Session linking cancelled by user")
                QMessageBox.information(self, "Cancelled", "Session linking was cancelled.")
                return
            
            # Refresh the display
            self.load_sessions_data()
            
            logger.info(f"Linked {len(updated_sessions)} sessions")
            QMessageBox.information(self, "Sessions Linked", 
                                  f"Successfully linked {len(updated_sessions)} light sessions with calibration sessions.")
            
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            logger.error(f"Error linking sessions: {e}")
            QMessageBox.critical(self, "Error", f"Failed to link sessions: {e}")

    def run_auto_calibration(self):
        """Run the auto-calibration workflow with progress tracking"""
        try:
            # Ask for confirmation before proceeding
            reply = QMessageBox.question(self, "Auto-Calibration Workflow", 
                                       "This will analyze calibration sessions and automatically create master frames.\n\n"
                                       "The process includes:\n"
                                       "• Analyzing calibration sessions\n"
                                       "• Creating master bias/dark/flat frames\n"
                                       "• Detecting auto-calibration opportunities\n"
                                       "• Preparing for light frame calibration\n\n"
                                       "Are you sure you want to continue?",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.No)
            
            if reply != QMessageBox.Yes:
                return
            
            # Set up progress tracking
            was_cancelled = False
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing auto-calibration workflow...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Auto-Calibration Workflow")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.show()
            QApplication.processEvents()
            
            def update_progress(current, total, message):
                """Progress callback function"""
                nonlocal was_cancelled
                
                # Don't check cancellation if already cancelled
                if was_cancelled:
                    return False
                
                # Check if dialog was cancelled before updating
                if progress_dialog and progress_dialog.wasCanceled():
                    was_cancelled = True
                    return False  # Signal to stop processing
                
                if progress_dialog:
                    progress_dialog.setValue(current)
                    progress_dialog.setLabelText(f"{message}")
                    QApplication.processEvents()  # Keep UI responsive
                    
                    # Check again after processing events
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                
                return True  # Continue processing
            
            # Create and run the auto-calibration workflow
            fits_processor = fitsProcessing()
            results = fits_processor.runAutoCalibrationWorkflow(progress_callback=update_progress)
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Handle results
            if was_cancelled:
                QMessageBox.information(self, "Auto-Calibration", "Auto-calibration workflow was cancelled.")
            elif results.get("status") == "error":
                error_message = results.get("message", "Unknown error occurred")
                QMessageBox.critical(self, "Auto-Calibration Error", f"Auto-calibration failed:\n\n{error_message}")
            else:
                # Show success summary
                sessions_analyzed = results.get("sessions_analyzed", 0)
                masters_created = results.get("masters_created", 0)
                opportunities = results.get("calibration_opportunities", 0)
                light_sessions = results.get("light_frames_calibrated", 0)
                errors = results.get("errors", [])
                
                status_text = results.get("status", "unknown")
                success_msg = f"Auto-calibration workflow completed ({status_text})!\n\n"
                success_msg += f"• Sessions analyzed: {sessions_analyzed}\n"
                success_msg += f"• Master frames created: {masters_created}\n"
                success_msg += f"• Calibration opportunities found: {opportunities}\n"
                success_msg += f"• Light sessions ready for calibration: {light_sessions}\n"
                
                if errors:
                    success_msg += f"\n⚠️ Warnings/Errors ({len(errors)}):\n"
                    for i, error in enumerate(errors[:3]):  # Show first 3 errors
                        success_msg += f"  {i+1}. {error}\n"
                    if len(errors) > 3:
                        success_msg += f"  ... and {len(errors)-3} more issues\n"
                
                if status_text == "success":
                    QMessageBox.information(self, "Auto-Calibration Complete", success_msg)
                else:
                    QMessageBox.warning(self, "Auto-Calibration Partial Success", success_msg)
                
                # Refresh the sessions display
                self.load_sessions_data()
            
        except Exception as e:
            logger.error(f"Error running auto-calibration workflow: {e}")
            QMessageBox.critical(self, "Error", f"Failed to run auto-calibration workflow:\n\n{e}")

    def regenerate_sessions(self):
        """Regenerate all sessions: Clear → Update Lights → Update Calibrations → Link Sessions"""
        try:
            # Ask user to choose regeneration mode
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Regenerate Sessions")
            msg_box.setText("Choose session regeneration mode:")
            msg_box.setDetailedText(
                "All Sessions: Clear all existing sessions and recreate them from all FITS files.\n\n"
                "New Only: Only create sessions for FITS files that don't currently have a session assigned."
            )
            
            all_button = msg_box.addButton("All Sessions", QMessageBox.AcceptRole)
            new_only_button = msg_box.addButton("New Only", QMessageBox.AcceptRole)
            cancel_button = msg_box.addButton("Cancel", QMessageBox.RejectRole)
            
            msg_box.setDefaultButton(new_only_button)
            msg_box.exec()
            
            clicked_button = msg_box.clickedButton()
            
            if clicked_button == cancel_button:
                return
            elif clicked_button == all_button:
                # Confirm the destructive operation
                reply = QMessageBox.question(self, "Confirm Regenerate All", 
                                           "This will clear ALL existing sessions and recreate them from FITS files.\n\n"
                                           "Are you sure you want to continue?",
                                           QMessageBox.Yes | QMessageBox.No,
                                           QMessageBox.No)
                
                if reply != QMessageBox.Yes:
                    return
                
                # Call the full regeneration method (existing behavior)
                self._do_regenerate_sessions()
            elif clicked_button == new_only_button:
                # Call the new-only regeneration method
                self._do_regenerate_sessions_new_only()
            
        except Exception as e:
            logger.error(f"Error in regenerate_sessions: {e}")
            QMessageBox.critical(self, "Error", f"Session regeneration failed: {e}")
    
    def _do_regenerate_sessions(self):
        """Internal method that performs the actual session regeneration without confirmation dialog"""
        try:
            logger.info("Starting complete session regeneration")
            
            # Step 1: Clear all existing sessions
            logger.info("Step 1: Clearing existing sessions")
            try:
                # Clear session references in files first to avoid foreign key constraints
                FitsFileModel.update(fitsFileSession=None).execute()
                
                # Delete all sessions
                deleted_count = FitsSessionModel.delete().execute()
                logger.info(f"Cleared {deleted_count} existing sessions")
                
                # Refresh display immediately to show empty sessions
                self.load_sessions_data()
                QApplication.processEvents()
                
            except Exception as e:
                logger.error(f"Error clearing sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to clear existing sessions: {e}")
                return
            
            # Step 2: Create light sessions
            logger.info("Step 2: Creating light sessions")
            light_sessions = []
            try:
                progress_dialog = QProgressDialog("Creating light sessions...", "Cancel", 0, 100, self)
                progress_dialog.setWindowTitle("Regenerating Sessions - Step 2/4")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QApplication.processEvents()
                
                processor = fitsProcessing()
                
                # Track if operation was cancelled
                was_cancelled = False
                
                def light_progress_callback(current, total, description):
                    nonlocal was_cancelled
                    if was_cancelled:
                        return False
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                    if total > 0:
                        progress = int((current / total) * 100)
                        progress_dialog.setValue(progress)
                        # Extract filename from full path in description
                        filename = os.path.basename(description) if description else ""
                        progress_dialog.setLabelText(f"Light sessions {current}/{total}: {filename}")
                    QApplication.processEvents()
                    return True
                
                light_sessions = processor.createLightSessions(light_progress_callback)
                progress_dialog.close()
                
                if was_cancelled:
                    logger.info("Session regeneration cancelled during light sessions creation")
                    QMessageBox.information(self, "Cancelled", "Session regeneration was cancelled.")
                    return
                    
                logger.info(f"Created {len(light_sessions)} light sessions")
                
            except Exception as e:
                if 'progress_dialog' in locals():
                    progress_dialog.close()
                logger.error(f"Error creating light sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to create light sessions: {e}")
                return
            
            # Step 3: Create calibration sessions
            logger.info("Step 3: Creating calibration sessions")
            cal_sessions = []
            try:
                progress_dialog = QProgressDialog("Creating calibration sessions...", "Cancel", 0, 100, self)
                progress_dialog.setWindowTitle("Regenerating Sessions - Step 3/4")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QApplication.processEvents()
                
                # Track if operation was cancelled
                was_cancelled = False
                
                def cal_progress_callback(current, total, description):
                    nonlocal was_cancelled
                    if was_cancelled:
                        return False
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                    if total > 0:
                        progress = int((current / total) * 100)
                        progress_dialog.setValue(progress)
                        # Extract filename from description (format: "Type: /path/to/file")
                        if ": " in description:
                            file_type, file_path = description.split(": ", 1)
                            filename = os.path.basename(file_path)
                            display_text = f"{file_type}: {filename}"
                        else:
                            display_text = os.path.basename(description) if description else ""
                        progress_dialog.setLabelText(f"Calibration sessions {current}/{total}: {display_text}")
                    QApplication.processEvents()
                    return True
                
                cal_sessions = processor.createCalibrationSessions(cal_progress_callback)
                progress_dialog.close()
                
                if was_cancelled:
                    logger.info("Session regeneration cancelled during calibration sessions creation")
                    QMessageBox.information(self, "Cancelled", "Session regeneration was cancelled.")
                    return
                    
                logger.info(f"Created {len(cal_sessions)} calibration sessions")
                
            except Exception as e:
                if 'progress_dialog' in locals():
                    progress_dialog.close()
                logger.error(f"Error creating calibration sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to create calibration sessions: {e}")
                return
            
            # Step 4: Link sessions
            logger.info("Step 4: Linking Master sessions")
            linked_sessions = []
            try:
                progress_dialog = QProgressDialog("Linking Master sessions...", "Cancel", 0, 100, self)
                progress_dialog.setWindowTitle("Regenerating Sessions - Step 4/4")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QApplication.processEvents()
                
                # Track if operation was cancelled
                was_cancelled = False
                
                def link_progress_callback(current, total, description):
                    nonlocal was_cancelled
                    if was_cancelled:
                        return False
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                    if total > 0:
                        progress = int((current / total) * 100)
                        progress_dialog.setValue(progress)
                        # For linking, description should be object names, but handle file paths just in case
                        display_text = os.path.basename(description) if description and os.path.sep in description else description
                        progress_dialog.setLabelText(f"Linking {current}/{total}: {display_text}")
                    QApplication.processEvents()
                    return True
                
                linked_sessions = processor.linkSessions(link_progress_callback)
                progress_dialog.close()
                
                if was_cancelled:
                    logger.info("Session regeneration cancelled during linking")
                    QMessageBox.information(self, "Cancelled", "Session regeneration was cancelled.")
                    return
                    
                logger.info(f"Linked {len(linked_sessions)} sessions")
                
            except Exception as e:
                if 'progress_dialog' in locals():
                    progress_dialog.close()
                logger.error(f"Error linking sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to link sessions: {e}")
                return
            
            # Final step: Refresh the display
            self.load_sessions_data()
            
            # Show completion message
            total_light = len(light_sessions) if 'light_sessions' in locals() else 0
            total_cal = len(cal_sessions) if 'cal_sessions' in locals() else 0
            total_linked = len(linked_sessions) if 'linked_sessions' in locals() else 0
            
            logger.info(f"Session regeneration complete: {total_light} light, {total_cal} calibration, {total_linked} linked")
            
        except Exception as e:
            logger.error(f"Unexpected error during session regeneration: {e}")
            QMessageBox.critical(self, "Error", f"Unexpected error during session regeneration: {e}")
    
    def _do_regenerate_sessions_new_only(self):
        """Regenerate sessions only for files without sessions assigned"""
        try:
            logger.info("Starting new-only session regeneration (files without sessions)")
            
            # Count unassigned files first
            unassigned_light_count = FitsFileModel.select().where(
                FitsFileModel.fitsFileSession.is_null(), 
                FitsFileModel.fitsFileType == 'LIGHT FRAME',
                FitsFileModel.fitsFileSoftDelete == False
            ).count()
            
            unassigned_cal_count = FitsFileModel.select().where(
                FitsFileModel.fitsFileSession.is_null(),
                FitsFileModel.fitsFileType.in_(['BIAS FRAME', 'DARK FRAME', 'FLAT FIELD']),
                FitsFileModel.fitsFileSoftDelete == False
            ).count()
            
            total_unassigned = unassigned_light_count + unassigned_cal_count
            
            if total_unassigned == 0:
                QMessageBox.information(self, "No Unassigned Files", 
                                      "All FITS files already have sessions assigned.\n\n"
                                      "No new sessions need to be created.")
                return
            
            logger.info(f"Found {unassigned_light_count} unassigned light files and {unassigned_cal_count} unassigned calibration files")
            
            # Step 1: Create light sessions for unassigned files
            logger.info("Step 1: Creating light sessions for unassigned files")
            light_sessions = []
            try:
                progress_dialog = QProgressDialog("Creating light sessions for unassigned files...", "Cancel", 0, 100, self)
                progress_dialog.setWindowTitle("Creating Sessions - Step 1/3")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QApplication.processEvents()
                
                processor = fitsProcessing()
                
                # Track if operation was cancelled
                was_cancelled = False
                
                def light_progress_callback(current, total, description):
                    nonlocal was_cancelled
                    if was_cancelled:
                        return False
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                    if total > 0:
                        progress = int((current / total) * 100)
                        progress_dialog.setValue(progress)
                        filename = os.path.basename(description) if description else ""
                        progress_dialog.setLabelText(f"Light sessions {current}/{total}: {filename}")
                    QApplication.processEvents()
                    return True
                
                light_sessions = processor.createLightSessions(light_progress_callback)
                progress_dialog.close()
                
                if was_cancelled:
                    logger.info("New-only session regeneration cancelled during light sessions creation")
                    QMessageBox.information(self, "Cancelled", "Session creation was cancelled.")
                    return
                    
                logger.info(f"Created {len(light_sessions)} light sessions for unassigned files")
                
            except Exception as e:
                if 'progress_dialog' in locals():
                    progress_dialog.close()
                logger.error(f"Error creating light sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to create light sessions: {e}")
                return
            
            # Step 2: Create calibration sessions for unassigned files
            logger.info("Step 2: Creating calibration sessions for unassigned files")
            cal_sessions = []
            try:
                progress_dialog = QProgressDialog("Creating calibration sessions for unassigned files...", "Cancel", 0, 100, self)
                progress_dialog.setWindowTitle("Creating Sessions - Step 2/3")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QApplication.processEvents()
                
                was_cancelled = False
                
                def cal_progress_callback(current, total, description):
                    nonlocal was_cancelled
                    if was_cancelled:
                        return False
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                    if total > 0:
                        progress = int((current / total) * 100)
                        progress_dialog.setValue(progress)
                        if ": " in description:
                            file_type, file_path = description.split(": ", 1)
                            filename = os.path.basename(file_path)
                            display_text = f"{file_type}: {filename}"
                        else:
                            display_text = os.path.basename(description) if description else ""
                        progress_dialog.setLabelText(f"Calibration sessions {current}/{total}: {display_text}")
                    QApplication.processEvents()
                    return True
                
                cal_sessions = processor.createCalibrationSessions(cal_progress_callback)
                progress_dialog.close()
                
                if was_cancelled:
                    logger.info("New-only session regeneration cancelled during calibration sessions creation")
                    QMessageBox.information(self, "Cancelled", "Session creation was cancelled.")
                    return
                    
                logger.info(f"Created {len(cal_sessions)} calibration sessions for unassigned files")
                
            except Exception as e:
                if 'progress_dialog' in locals():
                    progress_dialog.close()
                logger.error(f"Error creating calibration sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to create calibration sessions: {e}")
                return
            
            # Step 3: Link sessions
            logger.info("Step 3: Linking calibration sessions to light sessions")
            linked_sessions = []
            try:
                progress_dialog = QProgressDialog("Linking calibration sessions...", "Cancel", 0, 100, self)
                progress_dialog.setWindowTitle("Creating Sessions - Step 3/3")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QApplication.processEvents()
                
                was_cancelled = False
                
                def link_progress_callback(current, total, description):
                    nonlocal was_cancelled
                    if was_cancelled:
                        return False
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                    if total > 0:
                        progress = int((current / total) * 100)
                        progress_dialog.setValue(progress)
                        progress_dialog.setLabelText(f"Linking sessions {current}/{total}")
                    QApplication.processEvents()
                    return True
                
                linked_sessions = processor.linkSessions(link_progress_callback)
                progress_dialog.close()
                
                if was_cancelled:
                    logger.info("New-only session regeneration cancelled during linking")
                    QMessageBox.information(self, "Cancelled", "Session creation was cancelled.")
                    return
                    
                logger.info(f"Linked {len(linked_sessions)} sessions")
                
            except Exception as e:
                if 'progress_dialog' in locals():
                    progress_dialog.close()
                logger.error(f"Error linking sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to link sessions: {e}")
                return
            
            # Final step: Refresh the display
            self.load_sessions_data()
            
            # Show completion message
            total_light = len(light_sessions) if 'light_sessions' in locals() else 0
            total_cal = len(cal_sessions) if 'cal_sessions' in locals() else 0
            total_linked = len(linked_sessions) if 'linked_sessions' in locals() else 0
            
            completion_message = (f"Session creation completed successfully!\n\n"
                                f"Created {total_light} new light sessions\n"
                                f"Created {total_cal} new calibration sessions\n"
                                f"Linked {total_linked} light sessions with calibrations\n\n"
                                f"Only files without existing sessions were processed.")
            
            QMessageBox.information(self, "Session Creation Complete", completion_message)
            logger.info(f"New-only session creation complete: {total_light} light, {total_cal} calibration, {total_linked} linked")
            
        except Exception as e:
            logger.error(f"Unexpected error during new-only session regeneration: {e}")
            QMessageBox.critical(self, "Error", f"Unexpected error during session creation: {e}")

    def auto_regenerate_sessions(self):
        """Auto-regenerate sessions without user confirmation (for use after file imports)"""
        try:
            logger.info("Auto-regenerating sessions after file import")
            
            # Create a progress dialog for auto-regeneration
            progress_dialog = QProgressDialog("Auto-regenerating sessions...", None, 0, 100, self)
            progress_dialog.setWindowTitle("Updating Sessions")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            # Call the internal regeneration method
            self._do_regenerate_sessions()
            
            # Close the progress dialog
            progress_dialog.close()
            
            logger.info("Auto-regeneration completed")
            
        except Exception as e:
            logger.error(f"Error in auto_regenerate_sessions: {e}")
            if 'progress_dialog' in locals():
                progress_dialog.close()
            
            # Step 2: Create light sessions
            logger.info("Step 2: Creating light sessions")
            light_sessions = []
            try:
                progress_dialog = QProgressDialog("Creating light sessions...", "Cancel", 0, 100, self)
                progress_dialog.setWindowTitle("Regenerating Sessions - Step 2/4")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QApplication.processEvents()
                
                processor = fitsProcessing()
                
                # Track if operation was cancelled
                was_cancelled = False
                
                def light_progress_callback(current, total, description):
                    nonlocal was_cancelled
                    if was_cancelled:
                        return False
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                    if total > 0:
                        progress = int((current / total) * 100)
                        progress_dialog.setValue(progress)
                        # Extract filename from full path in description
                        filename = os.path.basename(description) if description else ""
                        progress_dialog.setLabelText(f"Light sessions {current}/{total}: {filename}")
                    QApplication.processEvents()
                    return True
                
                light_sessions = processor.createLightSessions(light_progress_callback)
                progress_dialog.close()
                
                if was_cancelled:
                    logger.info("Session regeneration cancelled during light sessions creation")
                    QMessageBox.information(self, "Cancelled", "Session regeneration was cancelled.")
                    return
                    
                logger.info(f"Created {len(light_sessions)} light sessions")
                
            except Exception as e:
                if 'progress_dialog' in locals():
                    progress_dialog.close()
                logger.error(f"Error creating light sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to create light sessions: {e}")
                return
            
            # Step 3: Create calibration sessions
            logger.info("Step 3: Creating calibration sessions")
            cal_sessions = []
            try:
                progress_dialog = QProgressDialog("Creating calibration sessions...", "Cancel", 0, 100, self)
                progress_dialog.setWindowTitle("Regenerating Sessions - Step 3/4")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QApplication.processEvents()
                
                # Track if operation was cancelled
                was_cancelled = False
                
                def cal_progress_callback(current, total, description):
                    nonlocal was_cancelled
                    if was_cancelled:
                        return False
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                    if total > 0:
                        progress = int((current / total) * 100)
                        progress_dialog.setValue(progress)
                        # Extract filename from description (format: "Type: /path/to/file")
                        if ": " in description:
                            file_type, file_path = description.split(": ", 1)
                            filename = os.path.basename(file_path)
                            display_text = f"{file_type}: {filename}"
                        else:
                            display_text = os.path.basename(description) if description else ""
                        progress_dialog.setLabelText(f"Calibration sessions {current}/{total}: {display_text}")
                    QApplication.processEvents()
                    return True
                
                cal_sessions = processor.createCalibrationSessions(cal_progress_callback)
                progress_dialog.close()
                
                if was_cancelled:
                    logger.info("Session regeneration cancelled during calibration sessions creation")
                    QMessageBox.information(self, "Cancelled", "Session regeneration was cancelled.")
                    return
                    
                logger.info(f"Created {len(cal_sessions)} calibration sessions")
                
            except Exception as e:
                if 'progress_dialog' in locals():
                    progress_dialog.close()
                logger.error(f"Error creating calibration sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to create calibration sessions: {e}")
                return
            
            # Step 4: Link sessions
            logger.info("Step 4: Linking Master sessions")
            linked_sessions = []
            try:
                progress_dialog = QProgressDialog("Linking Master sessions...", "Cancel", 0, 100, self)
                progress_dialog.setWindowTitle("Regenerating Sessions - Step 4/4")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QApplication.processEvents()
                
                # Track if operation was cancelled
                was_cancelled = False
                
                def link_progress_callback(current, total, description):
                    nonlocal was_cancelled
                    if was_cancelled:
                        return False
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                    if total > 0:
                        progress = int((current / total) * 100)
                        progress_dialog.setValue(progress)
                        # For linking, description should be object names, but handle file paths just in case
                        display_text = os.path.basename(description) if description and os.path.sep in description else description
                        progress_dialog.setLabelText(f"Linking Masters {current}/{total}: {display_text}")
                    QApplication.processEvents()
                    return True
                
                linked_sessions = processor.linkSessions(link_progress_callback)
                progress_dialog.close()
                
                if was_cancelled:
                    logger.info("Session regeneration cancelled during linking")
                    QMessageBox.information(self, "Cancelled", "Session regeneration was cancelled.")
                    return
                    
                logger.info(f"Linked {len(linked_sessions)} sessions")
                
            except Exception as e:
                if 'progress_dialog' in locals():
                    progress_dialog.close()
                logger.error(f"Error linking sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to link sessions: {e}")
                return
            
            # Final step: Refresh the display
            self.load_sessions_data()
            
            # Show completion message
            total_light = len(light_sessions) if 'light_sessions' in locals() else 0
            total_cal = len(cal_sessions) if 'cal_sessions' in locals() else 0
            total_linked = len(linked_sessions) if 'linked_sessions' in locals() else 0
            
            completion_message = (f"Session regeneration completed successfully!\n\n"
                                f"Created {total_light} light sessions\n"
                                f"Created {total_cal} calibration sessions\n"
                                f"Linked {total_linked} light sessions with calibrations")
            
            QMessageBox.information(self, "Regeneration Complete", completion_message)
            logger.info(f"Session regeneration complete: {total_light} light, {total_cal} calibration, {total_linked} linked")
            
        except Exception as e:
            logger.error(f"Unexpected error during session regeneration: {e}")
            QMessageBox.critical(self, "Error", f"Unexpected error during session regeneration: {e}")