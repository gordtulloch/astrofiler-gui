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

from astrofiler_file import fitsProcessing
from astrofiler_db import fitsFile as FitsFileModel, fitsSession as FitsSessionModel

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
        
        self.master_maintenance_button = QPushButton("Master Maintenance")
        self.master_maintenance_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.master_maintenance_button.setToolTip("Validate and maintain master calibration files")
        
        self.register_existing_button = QPushButton("Register Existing")
        self.register_existing_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.register_existing_button.setToolTip("Scan repository for existing calibrated files and master frames to avoid duplicate work")
        
        controls_layout.addWidget(self.regenerate_button)
        controls_layout.addWidget(self.auto_calibration_button)
        controls_layout.addWidget(self.master_maintenance_button)
        controls_layout.addWidget(self.register_existing_button)
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
        self.master_maintenance_button.clicked.connect(self.run_master_maintenance)
        self.register_existing_button.clicked.connect(self.run_register_existing)
    
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
        
        # === MASTER FRAME MANAGEMENT ===
        if calibration_sessions or light_sessions:
            context_menu.addSeparator()
            master_menu = context_menu.addMenu("🎯 Master Frames")
            
            # Master frame actions for calibration sessions
            if calibration_sessions:
                if len(calibration_sessions) == 1:
                    cal_session = calibration_sessions[0]
                    object_name = cal_session.parent().text(0)
                    
                    create_master_action = master_menu.addAction(f"🔨 Create {object_name} Master")
                    create_master_action.setToolTip(f"Create master {object_name.lower()} frame from this session")
                    
                    view_master_action = master_menu.addAction(f"👁️ View Master Info")
                    view_master_action.setToolTip("View information about the master frame for this session")
                    
                    validate_master_action = master_menu.addAction(f"✅ Validate Master")
                    validate_master_action.setToolTip("Validate master frame integrity and links")
                    
                else:
                    create_masters_action = master_menu.addAction(f"🔨 Create Masters ({len(calibration_sessions)})")
                    create_masters_action.setToolTip("Create master frames from selected calibration sessions")
                    
                    validate_masters_action = master_menu.addAction(f"✅ Validate Masters")
                    validate_masters_action.setToolTip("Validate master frames for selected sessions")
                
                master_menu.addSeparator()
            
            # Master frame actions for light sessions
            if light_sessions:
                link_masters_action = master_menu.addAction("🔗 Link to Masters")
                link_masters_action.setToolTip("Find and link appropriate master calibration frames")
                
                view_calibration_action = master_menu.addAction("📊 View Calibration Status")
                view_calibration_action.setToolTip("View detailed calibration status and master frame links")
                
                master_menu.addSeparator()
                
                if len(light_sessions) == 1:
                    calibrate_action = master_menu.addAction("🌟 Calibrate Light Frames")
                    calibrate_action.setToolTip("Apply calibration using linked master frames")
                else:
                    calibrate_action = master_menu.addAction(f"🌟 Calibrate Light Frames ({len(light_sessions)})")
                    calibrate_action.setToolTip("Apply calibration to selected light sessions")
            
            # General master frame actions
            master_menu.addSeparator()
            browse_masters_action = master_menu.addAction("📁 Browse Master Files")
            browse_masters_action.setToolTip("Open master frames directory in file explorer")
            
            cleanup_masters_action = master_menu.addAction("🧹 Clean up Masters")
            cleanup_masters_action.setToolTip("Clean up orphaned and invalid master frame references")
        
        # === SESSION MANAGEMENT ===
        if light_sessions or calibration_sessions:
            context_menu.addSeparator()
            session_menu = context_menu.addMenu("⚙️ Session Tools")
            
            refresh_links_action = session_menu.addAction("🔄 Refresh Calibration Links")
            refresh_links_action.setToolTip("Refresh calibration session links for selected sessions")
            
            export_session_action = session_menu.addAction("📤 Export Session Info")
            export_session_action.setToolTip("Export session information to file")
            
            if len(selected_items) == 1:
                session_menu.addSeparator()
                properties_action = session_menu.addAction("🔍 Properties")
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
        
        # Master frame actions
        elif calibration_sessions and action.text().startswith("🔨 Create"):
            if len(calibration_sessions) == 1:
                self.create_master_for_session(calibration_sessions[0])
            else:
                self.create_masters_for_sessions(calibration_sessions)
        
        elif action.text().startswith("👁️ View Master Info"):
            self.view_master_info(calibration_sessions[0])
        
        elif action.text().startswith("✅ Validate Master"):
            if len(calibration_sessions) == 1:
                self.validate_master_for_session(calibration_sessions[0])
            else:
                self.validate_masters_for_sessions(calibration_sessions)
        
        elif action.text().startswith("🔗 Link to Masters"):
            self.link_sessions_to_masters(light_sessions)
        
        elif action.text().startswith("📊 View Calibration Status"):
            self.view_calibration_status_detail(light_sessions)
        
        elif action.text().startswith("🌟 Calibrate Light Frames"):
            self.calibrate_light_sessions(light_sessions)
        
        elif action.text().startswith("📁 Browse Master Files"):
            self.browse_master_files()
        
        elif action.text().startswith("🧹 Clean up Masters"):
            self.cleanup_master_files()
        
        # Session management actions
        elif action.text().startswith("🔄 Refresh Calibration Links"):
            self.refresh_calibration_links(selected_items)
        
        elif action.text().startswith("📤 Export Session Info"):
            self.export_session_info(selected_items)
        
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

    # === MASTER FRAME MANAGEMENT METHODS ===
    
    def create_master_for_session(self, session_item):
        """Create master frame for a single calibration session"""
        try:
            # Get session information
            session_date = session_item.text(1)
            object_name = session_item.parent().text(0)
            
            # Find the session in database
            session = FitsSessionModel.select().where(
                (FitsSessionModel.fitsSessionObjectName == object_name) & 
                (FitsSessionModel.fitsSessionDate == session_date)
            ).first()
            
            if not session:
                QMessageBox.warning(self, "Error", f"Session not found in database")
                return
            
            # Confirm action
            reply = QMessageBox.question(self, "Create Master Frame", 
                                       f"Create master {object_name.lower()} frame for session on {session_date}?\n\n"
                                       f"This will combine all {object_name.lower()} frames in this session into a single master frame.",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.Yes)
            
            if reply != QMessageBox.Yes:
                return
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Creating master frame...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Master Frame Creation")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            def update_progress(current, total, message):
                if progress_dialog.wasCanceled():
                    return False
                if total > 0:
                    progress_dialog.setValue(int((current / total) * 100))
                progress_dialog.setLabelText(message)
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Create master frame
            processor = fitsProcessing()
            results = processor.createMasterCalibrationFrames(progress_callback=update_progress)
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", "Master frame creation was cancelled.")
                return
            
            # Check results
            master_type = object_name.lower()
            masters_created = results.get(f'{master_type}_masters', 0)
            
            if masters_created > 0:
                QMessageBox.information(self, "Success", 
                                      f"Successfully created {masters_created} {object_name.lower()} master frame(s)!")
                self.load_sessions_data()  # Refresh display
            else:
                QMessageBox.warning(self, "No Masters Created", 
                                  f"No {object_name.lower()} master frames were created. "
                                  f"Check that the session has enough files and meets requirements.")
            
        except Exception as e:
            logger.error(f"Error creating master for session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create master frame:\n\n{e}")

    def create_masters_for_sessions(self, session_items):
        """Create master frames for multiple calibration sessions"""
        try:
            session_count = len(session_items)
            session_info = []
            
            for item in session_items:
                object_name = item.parent().text(0)
                session_date = item.text(1)
                session_info.append(f"• {object_name} on {session_date}")
            
            # Confirm action
            reply = QMessageBox.question(self, "Create Master Frames", 
                                       f"Create master frames for {session_count} sessions?\n\n" +
                                       "\n".join(session_info[:5]) +
                                       (f"\n... and {session_count-5} more" if session_count > 5 else ""),
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.Yes)
            
            if reply != QMessageBox.Yes:
                return
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Creating master frames...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Batch Master Frame Creation")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            def update_progress(current, total, message):
                if progress_dialog.wasCanceled():
                    return False
                if total > 0:
                    progress_dialog.setValue(int((current / total) * 100))
                progress_dialog.setLabelText(message)
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Create master frames
            processor = fitsProcessing()
            results = processor.createMasterCalibrationFrames(progress_callback=update_progress)
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", "Master frame creation was cancelled.")
                return
            
            # Show results
            total_masters = (results.get('bias_masters', 0) + 
                           results.get('dark_masters', 0) + 
                           results.get('flat_masters', 0))
            
            result_msg = f"Master frame creation completed!\n\n"
            result_msg += f"Created {total_masters} master frames:\n"
            result_msg += f"• Bias masters: {results.get('bias_masters', 0)}\n"
            result_msg += f"• Dark masters: {results.get('dark_masters', 0)}\n"
            result_msg += f"• Flat masters: {results.get('flat_masters', 0)}"
            
            QMessageBox.information(self, "Master Creation Complete", result_msg)
            self.load_sessions_data()  # Refresh display
            
        except Exception as e:
            logger.error(f"Error creating masters for sessions: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create master frames:\n\n{e}")

    def view_master_info(self, session_item):
        """View detailed information about a master frame"""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QPushButton, QHBoxLayout
            
            # Get session information
            session_date = session_item.text(1)
            object_name = session_item.parent().text(0)
            
            # Find the session in database
            session = FitsSessionModel.select().where(
                (FitsSessionModel.fitsSessionObjectName == object_name) & 
                (FitsSessionModel.fitsSessionDate == session_date)
            ).first()
            
            if not session:
                QMessageBox.warning(self, "Error", f"Session not found in database")
                return
            
            # Get master frame path based on type
            master_path = None
            if object_name.lower() == 'bias':
                master_path = session.fitsBiasMaster
            elif object_name.lower() == 'dark':
                master_path = session.fitsDarkMaster
            elif object_name.lower() == 'flat':
                master_path = session.fitsFlatMaster
            
            # Create info dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"{object_name} Master Frame Information")
            dialog.setMinimumSize(600, 400)
            layout = QVBoxLayout(dialog)
            
            # Info text
            info_text = QTextEdit()
            info_text.setReadOnly(True)
            
            info_content = f"Master Frame Information\n"
            info_content += f"=" * 50 + "\n\n"
            info_content += f"Session: {object_name} on {session_date}\n"
            info_content += f"Session ID: {session.fitsSessionId}\n"
            info_content += f"Telescope: {session.fitsSessionTelescope or 'Unknown'}\n"
            info_content += f"Imager: {session.fitsSessionImager or 'Unknown'}\n"
            info_content += f"Binning: {session.fitsSessionBinningX or '?'}x{session.fitsSessionBinningY or '?'}\n"
            
            if object_name.lower() == 'dark':
                info_content += f"Exposure: {session.fitsSessionExposure or 'Unknown'}s\n"
                info_content += f"CCD Temp: {session.fitsSessionCCDTemp or 'Unknown'}°C\n"
            elif object_name.lower() == 'flat':
                info_content += f"Filter: {session.fitsSessionFilter or 'Unknown'}\n"
            
            info_content += f"\nMaster Frame Status:\n"
            if master_path:
                info_content += f"Path: {master_path}\n"
                info_content += f"Exists: {'Yes' if os.path.exists(master_path) else 'No (Missing!)'}\n"
                
                if os.path.exists(master_path):
                    stat = os.stat(master_path)
                    info_content += f"Size: {stat.st_size:,} bytes\n"
                    info_content += f"Created: {datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    info_content += f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    
                    # Try to read FITS headers
                    try:
                        from astropy.io import fits
                        with fits.open(master_path) as hdul:
                            header = hdul[0].header
                            info_content += f"\nFITS Header Information:\n"
                            info_content += f"NAXIS1: {header.get('NAXIS1', 'Unknown')} pixels\n"
                            info_content += f"NAXIS2: {header.get('NAXIS2', 'Unknown')} pixels\n"
                            info_content += f"BITPIX: {header.get('BITPIX', 'Unknown')}\n"
                            info_content += f"IMAGETYP: {header.get('IMAGETYP', 'Unknown')}\n"
                            if 'NFRAMES' in header:
                                info_content += f"Source Frames: {header['NFRAMES']}\n"
                            if 'CREATED' in header:
                                info_content += f"Created: {header['CREATED']}\n"
                    except Exception as e:
                        info_content += f"\nError reading FITS headers: {e}\n"
            else:
                info_content += f"No master frame reference found\n"
            
            # Get source files count
            source_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsSessionId)
            info_content += f"\nSource Files: {source_files.count()} files in session\n"
            
            info_text.setPlainText(info_content)
            layout.addWidget(info_text)
            
            # Buttons
            button_layout = QHBoxLayout()
            
            if master_path and os.path.exists(master_path):
                open_button = QPushButton("Open File Location")
                open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(master_path))))
                button_layout.addWidget(open_button)
            
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.reject)
            button_layout.addWidget(buttons)
            
            layout.addLayout(button_layout)
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Error viewing master info: {e}")
            QMessageBox.critical(self, "Error", f"Failed to view master frame information:\n\n{e}")

    def validate_master_for_session(self, session_item):
        """Validate master frame for a single session"""
        try:
            # Get session information
            session_date = session_item.text(1)
            object_name = session_item.parent().text(0)
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Validating master frame...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Master Frame Validation")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            def update_progress(current, total, message):
                if progress_dialog.wasCanceled():
                    return False
                if total > 0:
                    progress_dialog.setValue(int((current / total) * 100))
                progress_dialog.setLabelText(message)
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Validate master
            processor = fitsProcessing()
            results = processor.validateMasterFiles(progress_callback=update_progress, fix_issues=True)
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", "Master validation was cancelled.")
                return
            
            # Show results
            valid_count = len(results.get('valid_masters', []))
            missing_count = len(results.get('missing_masters', []))
            invalid_count = len(results.get('invalid_masters', []))
            fixes_count = results.get('fixes_applied', 0)
            
            result_msg = f"Master frame validation completed!\n\n"
            result_msg += f"• Valid masters: {valid_count}\n"
            result_msg += f"• Missing masters: {missing_count}\n"
            result_msg += f"• Invalid masters: {invalid_count}\n"
            result_msg += f"• Issues fixed: {fixes_count}\n"
            
            if missing_count > 0 or invalid_count > 0:
                QMessageBox.warning(self, "Validation Issues Found", result_msg)
            else:
                QMessageBox.information(self, "Validation Complete", result_msg)
            
            if fixes_count > 0:
                self.load_sessions_data()  # Refresh display if fixes were applied
            
        except Exception as e:
            logger.error(f"Error validating master: {e}")
            QMessageBox.critical(self, "Error", f"Failed to validate master frame:\n\n{e}")

    def validate_masters_for_sessions(self, session_items):
        """Validate master frames for multiple sessions"""
        # This can reuse the single session validation since validateMasterFiles
        # validates all masters at once
        self.validate_master_for_session(session_items[0])

    def link_sessions_to_masters(self, session_items):
        """Link light sessions to appropriate master frames"""
        try:
            session_count = len(session_items)
            
            # Confirm action
            reply = QMessageBox.question(self, "Link to Master Frames", 
                                       f"Search for and link appropriate master calibration frames "
                                       f"for {session_count} light session(s)?\n\n"
                                       f"This will find matching bias, dark, and flat masters based on "
                                       f"telescope, instrument, binning, and other parameters.",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.Yes)
            
            if reply != QMessageBox.Yes:
                return
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Linking to master frames...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Master Frame Linking")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            def update_progress(current, total, message):
                if progress_dialog.wasCanceled():
                    return False
                if total > 0:
                    progress_dialog.setValue(int((current / total) * 100))
                progress_dialog.setLabelText(message)
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Link sessions
            processor = fitsProcessing()
            
            linked_count = 0
            for i, session_item in enumerate(session_items):
                if update_progress(i, len(session_items), f"Linking session {i+1}/{len(session_items)}"):
                    # Get session from database
                    session_date = session_item.text(1)
                    object_name = session_item.parent().text(0)
                    
                    session = FitsSessionModel.select().where(
                        (FitsSessionModel.fitsSessionObjectName == object_name) & 
                        (FitsSessionModel.fitsSessionDate == session_date)
                    ).first()
                    
                    if session:
                        # Link this session to masters
                        processor.linkSessionWithMasterPreference(session)
                        linked_count += 1
                else:
                    break  # Cancelled
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", "Master linking was cancelled.")
                return
            
            QMessageBox.information(self, "Linking Complete", 
                                  f"Processed {linked_count} sessions for master frame linking!")
            self.load_sessions_data()  # Refresh display
            
        except Exception as e:
            logger.error(f"Error linking sessions to masters: {e}")
            QMessageBox.critical(self, "Error", f"Failed to link sessions to master frames:\n\n{e}")

    def view_calibration_status_detail(self, session_items):
        """Show detailed calibration status for selected sessions"""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QDialogButtonBox, QHeaderView
            
            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Detailed Calibration Status")
            dialog.setMinimumSize(800, 600)
            layout = QVBoxLayout(dialog)
            
            # Create table
            table = QTableWidget()
            table.setColumnCount(8)
            table.setHorizontalHeaderLabels([
                "Session", "Date", "Telescope", "Imager", "Filter", 
                "Bias Master", "Dark Master", "Flat Master"
            ])
            table.setRowCount(len(session_items))
            
            # Populate table
            for i, session_item in enumerate(session_items):
                session_date = session_item.text(1)
                object_name = session_item.parent().text(0)
                telescope = session_item.text(2)
                imager = session_item.text(3)
                filter_name = session_item.text(4)
                
                # Get session from database
                session = FitsSessionModel.select().where(
                    (FitsSessionModel.fitsSessionObjectName == object_name) & 
                    (FitsSessionModel.fitsSessionDate == session_date)
                ).first()
                
                table.setItem(i, 0, QTableWidgetItem(object_name))
                table.setItem(i, 1, QTableWidgetItem(session_date))
                table.setItem(i, 2, QTableWidgetItem(telescope))
                table.setItem(i, 3, QTableWidgetItem(imager))
                table.setItem(i, 4, QTableWidgetItem(filter_name))
                
                if session:
                    # Check master frame status
                    bias_status = "✅ Linked" if session.fitsBiasMaster and os.path.exists(session.fitsBiasMaster) else "❌ Missing"
                    dark_status = "✅ Linked" if session.fitsDarkMaster and os.path.exists(session.fitsDarkMaster) else "❌ Missing"
                    flat_status = "✅ Linked" if session.fitsFlatMaster and os.path.exists(session.fitsFlatMaster) else "❌ Missing"
                    
                    table.setItem(i, 5, QTableWidgetItem(bias_status))
                    table.setItem(i, 6, QTableWidgetItem(dark_status))
                    table.setItem(i, 7, QTableWidgetItem(flat_status))
                else:
                    for j in range(5, 8):
                        table.setItem(i, j, QTableWidgetItem("❓ Unknown"))
            
            # Configure table
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QTableWidget.SelectRows)
            
            layout.addWidget(table)
            
            # Buttons
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Error viewing calibration status: {e}")
            QMessageBox.critical(self, "Error", f"Failed to view calibration status:\n\n{e}")

    def calibrate_light_sessions(self, session_items):
        """Calibrate light frames for selected sessions"""
        try:
            session_count = len(session_items)
            
            # Confirm action
            reply = QMessageBox.question(self, "Calibrate Light Frames", 
                                       f"Apply calibration to light frames in {session_count} session(s)?\n\n"
                                       f"This will use linked master frames (bias, dark, flat) to "
                                       f"calibrate all light frames in the selected sessions.\n\n"
                                       f"Note: This operation may take a considerable amount of time.",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.Yes)
            
            if reply != QMessageBox.Yes:
                return
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Calibrating light frames...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Light Frame Calibration")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            def update_progress(current, total, message):
                if progress_dialog.wasCanceled():
                    return False
                if total > 0:
                    progress_dialog.setValue(int((current / total) * 100))
                progress_dialog.setLabelText(message)
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Calibrate sessions
            from astrofiler_smart import calibrate_session_lights
            
            calibrated_sessions = 0
            total_frames = 0
            
            for i, session_item in enumerate(session_items):
                if not update_progress(i, len(session_items), f"Calibrating session {i+1}/{len(session_items)}"):
                    break  # Cancelled
                
                # Get session from database
                session_date = session_item.text(1)
                object_name = session_item.parent().text(0)
                
                session = FitsSessionModel.select().where(
                    (FitsSessionModel.fitsSessionObjectName == object_name) & 
                    (FitsSessionModel.fitsSessionDate == session_date)
                ).first()
                
                if session:
                    try:
                        # Calibrate this session's light frames
                        result = calibrate_session_lights(
                            session.fitsSessionId, 
                            progress_callback=lambda msg: update_progress(i, len(session_items), msg)
                        )
                        
                        if result and result.get('status') == 'success':
                            calibrated_sessions += 1
                            total_frames += result.get('calibrated_files', 0)
                            
                    except Exception as e:
                        logger.warning(f"Error calibrating session {session.fitsSessionId}: {e}")
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", "Light frame calibration was cancelled.")
                return
            
            # Show results
            result_msg = f"Light frame calibration completed!\n\n"
            result_msg += f"• Sessions processed: {calibrated_sessions}/{len(session_items)}\n"
            result_msg += f"• Total frames calibrated: {total_frames}\n"
            
            if calibrated_sessions > 0:
                QMessageBox.information(self, "Calibration Complete", result_msg)
                self.load_sessions_data()  # Refresh display
            else:
                QMessageBox.warning(self, "No Calibration Applied", 
                                  result_msg + "\nNo frames were calibrated. Check that master frames are available.")
            
        except Exception as e:
            logger.error(f"Error calibrating light sessions: {e}")
            QMessageBox.critical(self, "Error", f"Failed to calibrate light frames:\n\n{e}")

    def browse_master_files(self):
        """Open the master frames directory in file explorer"""
        try:
            # Get the master frames directory
            processor = fitsProcessing()
            masters_dir = os.path.join(processor.repoFolder, 'Masters')
            
            if not os.path.exists(masters_dir):
                reply = QMessageBox.question(self, "Create Master Directory", 
                                           f"Master frames directory does not exist:\n{masters_dir}\n\n"
                                           f"Would you like to create it?",
                                           QMessageBox.Yes | QMessageBox.No,
                                           QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    os.makedirs(masters_dir, exist_ok=True)
                else:
                    return
            
            # Open in file explorer
            QDesktopServices.openUrl(QUrl.fromLocalFile(masters_dir))
            
        except Exception as e:
            logger.error(f"Error opening master files directory: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open master files directory:\n\n{e}")

    def cleanup_master_files(self):
        """Clean up orphaned and invalid master frame references"""
        try:
            # Confirm action
            reply = QMessageBox.question(self, "Clean up Master Files", 
                                       f"Clean up orphaned and invalid master frame references?\n\n"
                                       f"This operation will:\n"
                                       f"• Remove references to missing master files\n"
                                       f"• Identify orphaned master files not referenced in database\n"
                                       f"• Validate master file integrity\n"
                                       f"• Move invalid files to quarantine\n\n"
                                       f"This operation is safe and recommended for maintenance.",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.Yes)
            
            if reply != QMessageBox.Yes:
                return
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Cleaning up master files...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Master File Cleanup")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            def update_progress(current, total, message):
                if progress_dialog.wasCanceled():
                    return False
                if total > 0:
                    progress_dialog.setValue(int((current / total) * 100))
                progress_dialog.setLabelText(message)
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Run cleanup
            processor = fitsProcessing()
            results = processor.runMasterMaintenanceWorkflow(
                progress_callback=update_progress,
                include_cleanup=True,
                fix_issues=True
            )
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", "Master file cleanup was cancelled.")
                return
            
            # Show results
            result_msg = f"Master file cleanup completed!\n\n"
            if 'validation_results' in results:
                validation = results['validation_results']
                result_msg += f"• Valid masters: {len(validation.get('valid_masters', []))}\n"
                result_msg += f"• Missing masters: {len(validation.get('missing_masters', []))}\n"
                result_msg += f"• Orphaned files: {len(validation.get('orphaned_files', []))}\n"
                result_msg += f"• Issues fixed: {validation.get('fixes_applied', 0)}\n"
            
            QMessageBox.information(self, "Cleanup Complete", result_msg)
            self.load_sessions_data()  # Refresh display
            
        except Exception as e:
            logger.error(f"Error cleaning up master files: {e}")
            QMessageBox.critical(self, "Error", f"Failed to clean up master files:\n\n{e}")

    # === SESSION MANAGEMENT METHODS ===

    def refresh_calibration_links(self, session_items):
        """Refresh calibration links for selected sessions"""
        try:
            # Create progress dialog
            progress_dialog = QProgressDialog("Refreshing calibration links...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Refresh Calibration Links")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            def update_progress(current, total, message):
                if progress_dialog.wasCanceled():
                    return False
                if total > 0:
                    progress_dialog.setValue(int((current / total) * 100))
                progress_dialog.setLabelText(message)
                QApplication.processEvents()
                return not progress_dialog.wasCanceled()
            
            # Refresh links
            processor = fitsProcessing()
            updated_count = processor.linkSessions(progress_callback=update_progress)
            
            progress_dialog.close()
            
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", "Calibration link refresh was cancelled.")
                return
            
            QMessageBox.information(self, "Links Refreshed", 
                                  f"Updated calibration links for {updated_count} sessions!")
            self.load_sessions_data()  # Refresh display
            
        except Exception as e:
            logger.error(f"Error refreshing calibration links: {e}")
            QMessageBox.critical(self, "Error", f"Failed to refresh calibration links:\n\n{e}")

    def export_session_info(self, session_items):
        """Export session information to a file"""
        try:
            from PySide6.QtWidgets import QFileDialog
            import csv
            from datetime import datetime
            
            # Ask user for export file location
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Session Information",
                f"session_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
            )
            
            if not filename:
                return
            
            # Collect session data
            session_data = []
            for session_item in session_items:
                parent = session_item.parent()
                if parent:  # Regular session
                    object_name = parent.text(0)
                    session_date = session_item.text(1)
                    telescope = session_item.text(2)
                    imager = session_item.text(3)
                    filter_name = session_item.text(4)
                    image_count = session_item.text(5)
                    calibration_status = session_item.text(6)
                    
                    # Get detailed session info from database
                    session = FitsSessionModel.select().where(
                        (FitsSessionModel.fitsSessionObjectName == object_name) & 
                        (FitsSessionModel.fitsSessionDate == session_date)
                    ).first()
                    
                    session_data.append({
                        'Object': object_name,
                        'Date': session_date,
                        'Telescope': telescope,
                        'Imager': imager,
                        'Filter': filter_name,
                        'Image_Count': image_count,
                        'Calibration_Status': calibration_status,
                        'Session_ID': session.fitsSessionId if session else 'Unknown',
                        'Binning': f"{session.fitsSessionBinningX or '?'}x{session.fitsSessionBinningY or '?'}" if session else 'Unknown',
                        'Gain': session.fitsSessionGain if session else 'Unknown',
                        'Offset': session.fitsSessionOffset if session else 'Unknown',
                        'Exposure': session.fitsSessionExposure if session else 'Unknown',
                        'CCD_Temp': session.fitsSessionCCDTemp if session else 'Unknown',
                        'Bias_Master': session.fitsBiasMaster if session else '',
                        'Dark_Master': session.fitsDarkMaster if session else '',
                        'Flat_Master': session.fitsFlatMaster if session else ''
                    })
                else:  # Parent object
                    object_name = session_item.text(0)
                    session_data.append({
                        'Object': object_name,
                        'Date': 'PARENT_OBJECT',
                        'Telescope': '',
                        'Imager': '',
                        'Filter': '',
                        'Image_Count': session_item.text(5),
                        'Calibration_Status': session_item.text(6),
                        'Session_ID': '',
                        'Binning': '',
                        'Gain': '',
                        'Offset': '',
                        'Exposure': '',
                        'CCD_Temp': '',
                        'Bias_Master': '',
                        'Dark_Master': '',
                        'Flat_Master': ''
                    })
            
            # Write to file
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                if session_data:
                    fieldnames = session_data[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(session_data)
            
            QMessageBox.information(self, "Export Complete", 
                                  f"Session information exported to:\n{filename}")
            
        except Exception as e:
            logger.error(f"Error exporting session info: {e}")
            QMessageBox.critical(self, "Error", f"Failed to export session information:\n\n{e}")

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
            # Check if auto-calibration is enabled in config
            from configparser import ConfigParser
            config = ConfigParser()
            config.read('astrofiler.ini')
            
            auto_calibration_enabled = config.getboolean('Settings', 'enable_auto_calibration', fallback=False)
            if not auto_calibration_enabled:
                QMessageBox.information(self, "Auto-Calibration", 
                    "Auto-calibration is disabled. Please enable it in the Config tab first.")
                return
            
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

    def run_register_existing(self):
        """Register existing calibrated files and master frames to avoid duplicate work"""
        try:
            # Ask for confirmation and options
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QDialogButtonBox, QLabel
            
            class RegisterExistingDialog(QDialog):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Register Existing Files Options")
                    self.setModal(True)
                    self.setMinimumWidth(450)
                    
                    layout = QVBoxLayout(self)
                    
                    # Description
                    desc_label = QLabel("Scan repository for existing calibrated files and master frames to avoid duplicate processing.\n\n"
                                      "This process will:")
                    layout.addWidget(desc_label)
                    
                    info_label = QLabel("• Identify existing master calibration frames\n"
                                      "• Find already calibrated light frames\n" 
                                      "• Update database records with calibration status\n"
                                      "• Link master frames to appropriate sessions\n"
                                      "• Validate file consistency and fix issues\n")
                    info_label.setStyleSheet("margin-left: 20px; color: #666;")
                    layout.addWidget(info_label)
                    
                    # Options
                    self.scan_subdirs_check = QCheckBox("Scan subdirectories recursively")
                    self.scan_subdirs_check.setChecked(True)
                    self.scan_subdirs_check.setToolTip("Search all subdirectories for calibrated files and masters")
                    layout.addWidget(self.scan_subdirs_check)
                    
                    self.verify_headers_check = QCheckBox("Verify FITS headers for calibration metadata")
                    self.verify_headers_check.setChecked(True)
                    self.verify_headers_check.setToolTip("Read FITS headers to confirm calibration status (recommended)")
                    layout.addWidget(self.verify_headers_check)
                    
                    # Buttons
                    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    buttons.accepted.connect(self.accept)
                    buttons.rejected.connect(self.reject)
                    layout.addWidget(buttons)
            
            # Show options dialog
            options_dialog = RegisterExistingDialog(self)
            if options_dialog.exec() != QDialog.Accepted:
                return
                
            scan_subdirectories = options_dialog.scan_subdirs_check.isChecked()
            verify_headers = options_dialog.verify_headers_check.isChecked()
            
            # Set up progress tracking
            was_cancelled = False
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing existing file registration...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Register Existing Files")
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
                
                if progress_dialog and total > 0:
                    percentage = int((current / total) * 100)
                    progress_dialog.setValue(percentage)
                    progress_dialog.setLabelText(f"{message}")
                    QApplication.processEvents()  # Keep UI responsive
                    
                    # Check again after processing events
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        return False
                
                return True  # Continue processing
            
            # Run the registration process
            fits_processor = fitsProcessing()
            results = fits_processor.registerExistingFiles(
                progress_callback=update_progress,
                scan_subdirectories=scan_subdirectories,
                verify_headers=verify_headers
            )
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Handle results
            if was_cancelled:
                QMessageBox.information(self, "Registration Cancelled", "Existing file registration was cancelled.")
            else:
                # Show success summary
                summary = results.get('summary', {})
                master_info = summary.get('master_frames', {})
                calibrated_info = summary.get('calibrated_lights', {})
                errors = results.get('errors', [])
                
                success_msg = f"Existing file registration completed!\n\n"
                success_msg += f"📁 Total files processed: {summary.get('total_files_processed', 0)}\n\n"
                success_msg += f"🎯 Master Frames:\n"
                success_msg += f"  • Found: {master_info.get('found', 0)}\n"
                success_msg += f"  • Already linked: {master_info.get('already_linked', 0)}\n" 
                success_msg += f"  • Newly linked: {master_info.get('newly_linked', 0)}\n\n"
                success_msg += f"⭐ Calibrated Light Frames:\n"
                success_msg += f"  • Found: {calibrated_info.get('found', 0)}\n"
                success_msg += f"  • Database updated: {calibrated_info.get('updated', 0)}\n"
                success_msg += f"  • Verification errors: {calibrated_info.get('verification_errors', 0)}\n\n"
                success_msg += f"💾 Database changes: {summary.get('database_changes', 0)}\n"
                
                if errors:
                    success_msg += f"\n⚠️ Errors encountered ({len(errors)}):\n"
                    for i, error in enumerate(errors[:3]):  # Show first 3 errors
                        success_msg += f"  {i+1}. {error}\n"
                    if len(errors) > 3:
                        success_msg += f"  ... and {len(errors)-3} more errors\n"
                
                if len(errors) == 0:
                    QMessageBox.information(self, "Registration Complete", success_msg)
                else:
                    QMessageBox.warning(self, "Registration Complete with Warnings", success_msg)
                
                # Refresh the sessions display to show updated calibration status
                self.load_sessions_data()
            
        except Exception as e:
            logger.error(f"Error registering existing files: {e}")
            QMessageBox.critical(self, "Error", f"Failed to register existing files:\n\n{e}")

    def run_master_maintenance(self):
        """Run the master maintenance workflow with progress tracking"""
        try:
            # Ask for confirmation and options
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QDialogButtonBox, QLabel
            
            class MaintenanceOptionsDialog(QDialog):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Master Maintenance Options")
                    self.setModal(True)
                    
                    layout = QVBoxLayout(self)
                    
                    # Description
                    desc_label = QLabel("Master maintenance will validate and repair master calibration files.\n\n"
                                      "Operations include:")
                    layout.addWidget(desc_label)
                    
                    # Options
                    self.validate_check = QCheckBox("Validate master file integrity and references")
                    self.validate_check.setChecked(True)
                    self.validate_check.setEnabled(False)  # Always required
                    layout.addWidget(self.validate_check)
                    
                    self.repair_check = QCheckBox("Repair broken database associations")
                    self.repair_check.setChecked(True)
                    self.repair_check.setEnabled(False)  # Always included
                    layout.addWidget(self.repair_check)
                    
                    self.fix_issues_check = QCheckBox("Automatically fix detected issues")
                    self.fix_issues_check.setChecked(True)
                    layout.addWidget(self.fix_issues_check)
                    
                    self.cleanup_check = QCheckBox("Clean up old/orphaned master files (moves to quarantine)")
                    self.cleanup_check.setChecked(False)
                    layout.addWidget(self.cleanup_check)
                    
                    # Warning
                    warning_label = QLabel("\n⚠️ This operation may modify the database and move files.\n"
                                         "Consider backing up your data before proceeding.")
                    warning_label.setStyleSheet("QLabel { color: orange; }")
                    layout.addWidget(warning_label)
                    
                    # Buttons
                    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    button_box.accepted.connect(self.accept)
                    button_box.rejected.connect(self.reject)
                    layout.addWidget(button_box)
            
            # Show options dialog
            options_dialog = MaintenanceOptionsDialog(self)
            if options_dialog.exec() != QDialog.Accepted:
                return
            
            include_cleanup = options_dialog.cleanup_check.isChecked()
            fix_issues = options_dialog.fix_issues_check.isChecked()
            
            # Set up progress tracking
            was_cancelled = False
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Initializing master maintenance...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Master Maintenance")
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
            
            # Create and run the master maintenance workflow
            fits_processor = fitsProcessing()
            results = fits_processor.runMasterMaintenanceWorkflow(
                progress_callback=update_progress,
                include_cleanup=include_cleanup,
                fix_issues=fix_issues
            )
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Handle results
            if was_cancelled:
                QMessageBox.information(self, "Master Maintenance", "Master maintenance workflow was cancelled.")
            elif results.get("status") == "error":
                error_message = results.get("message", "Unknown error occurred")
                QMessageBox.critical(self, "Master Maintenance Error", f"Master maintenance failed:\n\n{error_message}")
            else:
                # Show success summary with detailed results
                status_text = results.get("status", "unknown")
                
                # Build detailed summary
                summary_lines = []
                summary_lines.append(f"Master maintenance completed ({status_text})!")
                
                if results.get("validation_results"):
                    v_results = results["validation_results"]
                    summary_lines.append(f"\n📋 Validation Results:")
                    summary_lines.append(f"  • Masters checked: {v_results.get('total_masters_checked', 0)}")
                    summary_lines.append(f"  • Missing files: {len(v_results.get('missing_files', []))}")
                    summary_lines.append(f"  • Corrupted files: {len(v_results.get('corrupted_files', []))}")
                    summary_lines.append(f"  • Orphaned files: {len(v_results.get('orphaned_files', []))}")
                    summary_lines.append(f"  • Database issues: {len(v_results.get('database_issues', []))}")
                
                if results.get("repair_results"):
                    r_results = results["repair_results"]
                    summary_lines.append(f"\n🔧 Repair Results:")
                    summary_lines.append(f"  • Sessions processed: {r_results.get('sessions_processed', 0)}")
                    summary_lines.append(f"  • Masters relinked: {r_results.get('masters_relinked', 0)}")
                    summary_lines.append(f"  • Broken refs cleared: {r_results.get('broken_refs_cleared', 0)}")
                
                if results.get("cleanup_results", {}).get("status") != "skipped":
                    c_results = results["cleanup_results"]
                    summary_lines.append(f"\n🧹 Cleanup Results:")
                    summary_lines.append(f"  • Files processed: {c_results.get('files_processed', 0)}")
                    summary_lines.append(f"  • Files moved to quarantine: {c_results.get('files_deleted', 0)}")
                    space_mb = c_results.get('space_reclaimed', 0) / (1024*1024)
                    summary_lines.append(f"  • Space reclaimed: {space_mb:.1f} MB")
                
                summary_lines.append(f"\n📊 Summary:")
                summary_lines.append(f"  • Total issues found: {results.get('total_issues_found', 0)}")
                summary_lines.append(f"  • Total fixes applied: {results.get('total_fixes_applied', 0)}")
                
                errors = []
                for result_type in ['validation_results', 'repair_results', 'cleanup_results']:
                    if results.get(result_type, {}).get('errors'):
                        errors.extend(results[result_type]['errors'])
                
                if errors:
                    summary_lines.append(f"\n⚠️ Warnings/Errors ({len(errors)}):")
                    for i, error in enumerate(errors[:3]):  # Show first 3 errors
                        summary_lines.append(f"  {i+1}. {error}")
                    if len(errors) > 3:
                        summary_lines.append(f"  ... and {len(errors)-3} more issues")
                
                success_msg = "\n".join(summary_lines)
                
                if status_text == "success":
                    QMessageBox.information(self, "Master Maintenance Complete", success_msg)
                else:
                    QMessageBox.warning(self, "Master Maintenance Partial Success", success_msg)
                
                # Refresh the sessions display if fixes were applied
                if results.get('total_fixes_applied', 0) > 0:
                    self.load_sessions_data()
            
        except Exception as e:
            logger.error(f"Error running master maintenance: {e}")
            QMessageBox.critical(self, "Error", f"Failed to run master maintenance:\n\n{e}")

    def regenerate_sessions(self):
        """Regenerate all sessions: Clear → Update Lights → Update Calibrations → Link Sessions"""
        try:
            # Ask for confirmation before proceeding
            reply = QMessageBox.question(self, "Regenerate Sessions", 
                                       "This will clear all existing sessions and recreate them from FITS files.\n\n"
                                       "Are you sure you want to continue?",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.No)
            
            if reply != QMessageBox.Yes:
                return
            
            # Call the actual regeneration method
            self._do_regenerate_sessions()
            
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
            logger.info("Step 4: Linking sessions")
            linked_sessions = []
            try:
                progress_dialog = QProgressDialog("Linking sessions...", "Cancel", 0, 100, self)
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
            logger.info("Step 4: Linking sessions")
            linked_sessions = []
            try:
                progress_dialog = QProgressDialog("Linking sessions...", "Cancel", 0, 100, self)
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
            
            completion_message = (f"Session regeneration completed successfully!\n\n"
                                f"Created {total_light} light sessions\n"
                                f"Created {total_cal} calibration sessions\n"
                                f"Linked {total_linked} light sessions with calibrations")
            
            QMessageBox.information(self, "Regeneration Complete", completion_message)
            logger.info(f"Session regeneration complete: {total_light} light, {total_cal} calibration, {total_linked} linked")
            
        except Exception as e:
            logger.error(f"Unexpected error during session regeneration: {e}")
            QMessageBox.critical(self, "Error", f"Unexpected error during session regeneration: {e}")