import os
import sys
import glob
import logging
import datetime
from datetime import datetime as dt
from PySide6.QtCore import Qt
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTreeWidget, QTreeWidgetItem, QAbstractItemView,
                               QMenu, QProgressDialog, QApplication, QMessageBox,
                               QFileDialog, QLabel, QProgressBar)
from PySide6.QtGui import QFont, QDesktopServices, QIcon, QPixmap, QPainter, QColor, QBrush
from PySide6.QtCore import QUrl

from astrofiler.core import fitsProcessing
from astrofiler.models import fitsFile as FitsFileModel, fitsSession as FitsSessionModel, Masters

logger = logging.getLogger(__name__)

class SessionsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

        # Caches used to speed up sessions rendering
        self._session_file_counts = {}
        self._master_source_session_ids = set()

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
        self.sessions_tree.setHeaderLabels(["Object Name", "Thumbnail", "Date", "Telescope", "Imager", "Filter", "Images", "Resources"])
        self.sessions_tree.setIconSize(QSize(150, 150))
        
        # Enable multi-selection
        self.sessions_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # Set column widths for better display
        self.sessions_tree.setColumnWidth(0, 200)  # Object Name
        self.sessions_tree.setColumnWidth(1, 160)  # Thumbnail
        self.sessions_tree.setColumnWidth(2, 150)  # Date
        self.sessions_tree.setColumnWidth(3, 150)  # Telescope
        self.sessions_tree.setColumnWidth(4, 150)  # Imager
        self.sessions_tree.setColumnWidth(5, 100)  # Filter
        self.sessions_tree.setColumnWidth(6, 80)   # Images
        self.sessions_tree.setColumnWidth(7, 140)  # Resources
        
        # Enable context menu
        self.sessions_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sessions_tree.customContextMenuRequested.connect(self.show_context_menu)

        # Double-click behavior (e.g., open stack from thumbnail)
        self.sessions_tree.itemDoubleClicked.connect(self.on_item_double_clicked)

        layout.addLayout(controls_layout)
        layout.addWidget(self.sessions_tree)
        
        # Connect signals
        self.regenerate_button.clicked.connect(self.regenerate_sessions)
        self.auto_calibration_button.clicked.connect(self.run_auto_calibration)

    def on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle double-clicks in the sessions tree.

        Requirement: double-clicking the Thumbnail column opens the stacked image
        for that light session (if available) in the external viewer.
        """
        try:
            THUMBNAIL_COLUMN = 1
            if column != THUMBNAIL_COLUMN:
                return

            parent = item.parent()
            if not parent:
                return  # ignore parent object rows

            session_id = item.data(0, Qt.UserRole)
            if not session_id:
                return

            # Only respond if a thumbnail exists for this session
            thumb_path = self._get_thumbnail_path(str(session_id))
            if not (thumb_path and os.path.exists(thumb_path)):
                return

            # Resolve session + find best matching stack output
            try:
                session = FitsSessionModel.get_by_id(str(session_id))
            except Exception:
                session = None
            if not session:
                QMessageBox.warning(self, "Error", "Session not found in database")
                return

            object_name = parent.text(0) or (session.fitsSessionObjectName or "Unknown")
            if object_name in ['Bias', 'Dark', 'Flat']:
                return

            out_dir = self._get_session_stack_output_dir(session)
            if not out_dir:
                QMessageBox.information(self, "No Stack", "No stack location found for this session.")
                return

            stack_path = self._find_best_stack_for_session(session=session, object_name=object_name, out_dir=out_dir)
            if not stack_path:
                QMessageBox.information(self, "No Stack", "No stacked FITS file found for this session.")
                return

            self._open_path_in_external_viewer(stack_path)

        except Exception as e:
            logger.error(f"Error handling thumbnail double-click: {e}")

    def _get_session_stack_output_dir(self, session: FitsSessionModel) -> str:
        """Best-effort directory where stack outputs are expected to be written."""
        try:
            telescope = getattr(session, 'fitsSessionTelescope', None) or ''
            instrument = getattr(session, 'fitsSessionImager', None) or ''
            is_precalibrated_session = (
                ('itelescope' in telescope.lower()) or
                ('seestar' in instrument.lower())
            )

            base = (
                (FitsFileModel.fitsFileSession == session.fitsSessionId)
                & (FitsFileModel.fitsFileSoftDelete == False)
                & (FitsFileModel.fitsFileType.in_(['LIGHT', 'LIGHT FRAME', 'Light Frame']))
            )

            if is_precalibrated_session:
                candidates = list(FitsFileModel.select().where(base))
            else:
                candidates = list(FitsFileModel.select().where(base & (FitsFileModel.fitsFileCalibrated == 1)))

            for f in candidates:
                p = getattr(f, 'fitsFileName', None)
                if p and os.path.exists(p):
                    return os.path.dirname(p)

        except Exception:
            pass

        return ''

    def _find_best_stack_for_session(self, session: FitsSessionModel, object_name: str, out_dir: str) -> str:
        """Find the most likely stack FITS file for a session.

        Preference order:
          1) photometric stacks
          2) deep stacks (stack_*)
          3) sample stacks
        If multiple matches exist, choose the newest by mtime.
        """
        try:
            from astrofiler.core.utils import sanitize_filesystem_name

            safe_object = sanitize_filesystem_name(object_name or 'Unknown')
            date_str = str(session.fitsSessionDate) if session.fitsSessionDate else 'unknown_date'
            session_id = str(session.fitsSessionId)

            patterns = [
                os.path.join(out_dir, f"photometric_stack_{safe_object}_{date_str}*.fits"),
                os.path.join(out_dir, f"stack_{safe_object}_{date_str}_{session_id}*.fits"),
                os.path.join(out_dir, f"stack_{safe_object}_{date_str}*.fits"),
                os.path.join(out_dir, f"sample_stack_{safe_object}_{date_str}*.fits"),
                os.path.join(out_dir, f"*stack*{session_id}*.fits"),
            ]

            matches = []
            for pat in patterns:
                matches.extend([p for p in glob.glob(pat) if os.path.isfile(p)])

            # De-dupe while preserving order
            seen = set()
            unique = []
            for p in matches:
                if p not in seen:
                    seen.add(p)
                    unique.append(p)

            if not unique:
                return ''

            # Pick newest mtime
            best = max(unique, key=lambda p: os.path.getmtime(p))
            return best if os.path.exists(best) else ''

        except Exception:
            return ''
    
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

        # Session ID clipboard helper
        session_items_for_clipboard = [si for si in selected_items if si.parent() is not None]
        session_ids_for_clipboard = [str(si.data(0, Qt.UserRole)) for si in session_items_for_clipboard if si.data(0, Qt.UserRole)]
        if session_ids_for_clipboard:
            label = "📋 Copy Session ID" if len(session_ids_for_clipboard) == 1 else f"📋 Copy Session IDs ({len(session_ids_for_clipboard)})"
            copy_session_id_action = context_menu.addAction(label)
            copy_session_id_action.setToolTip("Copy the selected session ID(s) to the clipboard")
        else:
            copy_session_id_action = None
        
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
        
        # === CALIBRATION OPTIONS ===
        if light_sessions and len(light_sessions) == 1:
            calibrate_action = context_menu.addAction("⚙️ Calibrate")
            calibrate_action.setToolTip("Calibrate light frames in this session using available master frames")

            sample_stack_action = context_menu.addAction("📚 Stack")
            sample_stack_action.setToolTip(
                "Stack light frames and open the result in the external FITS viewer. If the session is not precalibrated, calibration runs automatically if needed."
            )

            photometric_stack_action = context_menu.addAction("📚 Stack (photometric)")
            photometric_stack_action.setToolTip(
                "Create a photometry-safe stack (registered mean, no sigma clipping) and open the result in the external FITS viewer. If the session is not precalibrated, calibration runs automatically if needed."
            )

            regenerate_thumbnail_action = context_menu.addAction("🖼️ Regenerate Thumbnail")
            regenerate_thumbnail_action.setToolTip(
                "Recreate the session thumbnail from the most recent stack file (photometric/deep/sample) if available."
            )
        else:
            calibrate_action = None
            sample_stack_action = None
            photometric_stack_action = None
            regenerate_thumbnail_action = None
        
        # === MASTER FRAME OPTIONS ===
        view_master_action = None
        if len(selected_items) == 1 and not parent_objects:
            # Check if this session has a master frame
            session_id = selected_items[0].data(0, Qt.UserRole)
            if session_id:
                try:
                    master = Masters.select().where(
                        Masters.source_session_id == session_id,
                        Masters.soft_delete == False
                    ).first()
                    if master:
                        view_master_action = context_menu.addAction("🔍 View Master")
                        view_master_action.setToolTip(f"Open master {master.master_type} frame in external FITS viewer")
                        logger.debug(f"Found master for session {session_id}: {master.master_path}")
                    else:
                        logger.debug(f"No master found for session {session_id}")
                except Exception as e:
                    logger.error(f"Error checking for master: {e}")

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
                logger.info(f"Checking out session: {light_sessions[0].parent().text(0)} on {light_sessions[0].text(2)}")
                self.checkout_session(light_sessions[0])
            else:
                logger.info(f"Checking out {len(light_sessions)} sessions")
                self.checkout_multiple_sessions(light_sessions)
        
        # Calibrate action
        elif action == calibrate_action:
            logger.info(f"Calibrating session: {light_sessions[0].parent().text(0)} on {light_sessions[0].text(2)}")
            self.calibrate_session(light_sessions[0])

        # Stack action
        elif action == sample_stack_action:
            logger.info(f"Stacking session: {light_sessions[0].parent().text(0)} on {light_sessions[0].text(2)}")
            self.sample_stack_session(light_sessions[0])

        # Photometric stack action
        elif action == photometric_stack_action:
            logger.info(f"Photometric stacking session: {light_sessions[0].parent().text(0)} on {light_sessions[0].text(2)}")
            self.photometric_stack_session(light_sessions[0])

        # Regenerate thumbnail action
        elif action == regenerate_thumbnail_action:
            try:
                item = light_sessions[0]
                session_id = item.data(0, Qt.UserRole)
                if not session_id:
                    QMessageBox.warning(self, "Error", "Session ID not found")
                    return

                parent_item = item.parent()
                object_name = parent_item.text(0) if parent_item else "Unknown"
                if object_name in ['Bias', 'Dark', 'Flat']:
                    QMessageBox.information(self, "Not Applicable", "Thumbnails are only generated for light sessions.")
                    return

                try:
                    session = FitsSessionModel.get_by_id(str(session_id))
                except Exception:
                    session = None
                if not session:
                    QMessageBox.warning(self, "Error", "Session not found in database")
                    return

                out_dir = self._get_session_stack_output_dir(session)
                if not out_dir:
                    QMessageBox.information(self, "No Stack", "No stack location found for this session.")
                    return

                stack_path = self._find_best_stack_for_session(session=session, object_name=object_name, out_dir=out_dir)
                if not stack_path:
                    QMessageBox.information(self, "No Stack", "No stacked FITS file found for this session.")
                    return

                from astrofiler.core.master_manager import get_master_manager
                master_manager = get_master_manager()
                out_thumb = master_manager._write_light_session_thumbnail(
                    stacked_fits_path=stack_path,
                    session_id=str(session_id),
                    width_px=150,
                )

                if not out_thumb or not os.path.exists(out_thumb):
                    QMessageBox.warning(self, "Thumbnail Failed", "Failed to regenerate thumbnail.")
                    return

                logger.info(f"Thumbnail regenerated for session {session_id}: {out_thumb}")
                self.load_sessions_data()

            except Exception as e:
                logger.error(f"Error regenerating thumbnail: {e}")
                QMessageBox.critical(self, "Error", f"Failed to regenerate thumbnail:\n{str(e)}")
        
        # View master action
        elif action == view_master_action:
            session_id = selected_items[0].data(0, Qt.UserRole)
            self.view_master_frame(session_id)

        # Copy Session ID(s)
        elif action == copy_session_id_action:
            try:
                ids = session_ids_for_clipboard
                if not ids:
                    return
                text = "\n".join(ids)
                QApplication.clipboard().setText(text)
                logger.info(f"Copied {len(ids)} session id(s) to clipboard")
            except Exception as e:
                logger.error(f"Failed to copy session id(s) to clipboard: {e}")
    
    def view_master_frame(self, session_id):
        """Open master frame in external FITS viewer"""
        try:
            # Get the master frame for this session
            master = Masters.select().where(
                Masters.source_session_id == session_id,
                Masters.soft_delete == False
            ).first()
            
            if not master:
                QMessageBox.warning(self, "No Master", "No master frame found for this session.")
                return
            
            master_path = master.master_path
            
            # Check if file exists
            if not os.path.exists(master_path):
                QMessageBox.warning(self, "File Not Found", f"Master file not found:\n{master_path}")
                return
            
            self._open_path_in_external_viewer(master_path)
                
        except Exception as e:
            logger.error(f"Error viewing master frame: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open master frame:\n{str(e)}")

    def _open_path_in_external_viewer(self, file_path: str) -> None:
        """Open a file path in the configured external FITS viewer (or OS default)."""
        if not file_path:
            return
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found", f"File not found:\n{file_path}")
            return

        # Read configuration to get FITS viewer path
        import configparser
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        fits_viewer_path = config.get('DEFAULT', 'fits_viewer_path', fallback=None)

        # Try to open with configured FITS viewer first
        if fits_viewer_path and os.path.exists(fits_viewer_path):
            try:
                import subprocess
                subprocess.Popen([fits_viewer_path, file_path])
                logger.info(f"Opened file with configured viewer: {fits_viewer_path}")
                return
            except Exception as e:
                logger.warning(f"Failed to open with configured viewer {fits_viewer_path}: {e}")

        # Fall back to OS default viewer
        try:
            if os.name == 'nt':
                os.startfile(file_path)
            elif os.name == 'posix':
                if hasattr(os, 'uname') and os.uname().sysname == 'Darwin':
                    os.system(f'open "{file_path}"')
                else:
                    os.system(f'xdg-open "{file_path}"')
            else:
                QMessageBox.information(self, "Unsupported", "File viewing not supported on this platform")
        except Exception as e:
            logger.error(f"Failed to open file in external viewer: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")
    
    def checkout_session(self, item):
        """Create symbolic links for session files in a Siril-friendly format"""
        try:
            # Get session information from the tree item
            session_date = item.text(2)
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
            
            # Check if lights are already calibrated
            lights_calibrated = all(lf.fitsFileCalibrated for lf in light_files)
            
            # Get calibration files and masters if this is a light session with uncalibrated frames
            dark_files = []
            bias_files = []
            flat_files = []
            master_files = []

            if object_name not in ['Bias', 'Dark', 'Flat']:
                if not lights_calibrated:
                    # Get linked calibration files for uncalibrated lights
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
                    
                    # Find matching master frames
                    from ..core.master_manager import get_master_manager
                    from ..models import Masters
                    
                    master_manager = get_master_manager()
                    session_data = {
                        'telescope': session.fitsSessionTelescope,
                        'instrument': session.fitsSessionImager,
                        'exposure_time': session.fitsSessionExposure,
                        'filter_name': session.fitsSessionFilter,
                        'binning_x': session.fitsSessionBinningX,
                        'binning_y': session.fitsSessionBinningY,
                        'ccd_temp': session.fitsSessionCCDTemp,
                        'gain': session.fitsSessionGain,
                        'offset': session.fitsSessionOffset
                    }
                    
                    master_bias = master_manager.find_matching_master(session_data, 'bias')
                    master_dark = master_manager.find_matching_master(session_data, 'dark')
                    master_flat = master_manager.find_matching_master(session_data, 'flat')
                    
                    if master_bias and os.path.exists(master_bias.master_path):
                        master_files.append(('bias', master_bias.master_path))
                        logger.info(f"Found matching bias master: {os.path.basename(master_bias.master_path)}")
                    
                    if master_dark and os.path.exists(master_dark.master_path):
                        master_files.append(('dark', master_dark.master_path))
                        logger.info(f"Found matching dark master: {os.path.basename(master_dark.master_path)}")
                    
                    if master_flat and os.path.exists(master_flat.master_path):
                        master_files.append(('flat', master_flat.master_path))
                        logger.info(f"Found matching flat master: {os.path.basename(master_flat.master_path)}")
                else:
                    logger.info(f"Light frames are already calibrated, skipping calibration files and masters")

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
            
            # Create lights directory
            os.makedirs(light_dir, exist_ok=True)
            
            # Create calibration and master directories only if lights are uncalibrated
            dark_dir = None
            flat_dir = None
            bias_dir = None
            masters_dir = None
            
            if not lights_calibrated and object_name not in ['Bias', 'Dark', 'Flat']:
                dark_dir = os.path.join(session_dir, "darks")
                flat_dir = os.path.join(session_dir, "flats")
                bias_dir = os.path.join(session_dir, "bias")
                masters_dir = os.path.join(session_dir, "masters")
                
                os.makedirs(dark_dir, exist_ok=True)
                os.makedirs(flat_dir, exist_ok=True)
                os.makedirs(bias_dir, exist_ok=True)
                os.makedirs(masters_dir, exist_ok=True)
                logger.info(f"Created session directory structure with calibration folders at {session_dir}")
            else:
                logger.info(f"Created session directory structure (lights only) at {session_dir}")  

            # Progress dialog
            progress = QProgressDialog("Creating symbolic links...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)

            # Create symbolic links for each file
            created_links = 0
            total_items = len(all_files) + len(master_files)
            current_item = 0
            
            for file in all_files:
                # Update progress
                progress.setValue(int(current_item * 100 / total_items) if total_items > 0 else 0)
                current_item += 1
                if progress.wasCanceled():
                    break
                    
                # Determine destination directory based on file type
                if "LIGHT" in file.fitsFileType.upper():
                    dest_folder = light_dir
                elif "DARK" in file.fitsFileType.upper():
                    dest_folder = dark_dir if dark_dir else None
                elif "FLAT" in file.fitsFileType.upper():
                    dest_folder = flat_dir if flat_dir else None
                elif "BIAS" in file.fitsFileType.upper():
                    dest_folder = bias_dir if bias_dir else None
                else:
                    logger.warning(f"Unknown file type for {file.fitsFileName}, skipping")
                    continue  # Skip unknown file types
                
                if dest_folder is None:
                    logger.debug(f"Skipping calibration file {file.fitsFileName} (lights already calibrated)")
                    continue
                    
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
                        # Windows - use mklink (note: argument order is reversed from os.symlink)
                        import subprocess
                        # mklink syntax: mklink Link Target
                        result = subprocess.run(f'mklink "{dest_path}" "{file.fitsFileName}"', 
                                              shell=True, capture_output=True, text=True)
                        if result.returncode != 0:
                            raise Exception(f"mklink failed: {result.stderr}")
                    else:
                        # Mac/Linux - use symbolic link
                        os.symlink(file.fitsFileName, dest_path)
                    created_links += 1
                    logger.info(f"Created link for {file.fitsFileName} -> {dest_path}")
                except Exception as e:
                    logger.error(f"Error creating link for {file.fitsFileName}: {e}")
            
            # Create links for master frames if lights are uncalibrated
            if masters_dir and master_files:
                for master_type, master_path in master_files:
                    progress.setValue(int(current_item * 100 / total_items) if total_items > 0 else 0)
                    current_item += 1
                    if progress.wasCanceled():
                        break
                    
                    filename = os.path.basename(master_path)
                    dest_path = os.path.join(masters_dir, filename)
                    
                    try:
                        if not os.path.exists(dest_path):
                            if sys.platform == "win32":
                                import subprocess
                                result = subprocess.run(f'mklink "{dest_path}" "{master_path}"', 
                                                      shell=True, capture_output=True, text=True)
                                if result.returncode != 0:
                                    raise Exception(f"mklink failed: {result.stderr}")
                            else:
                                os.symlink(master_path, dest_path)
                            created_links += 1
                            logger.info(f"Created link for {master_type} master: {filename}")
                    except Exception as e:
                        logger.error(f"Error creating link for master {master_path}: {e}")
            
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
            
            # Create main checkout directory with shared subdirectories
            checkout_dir = os.path.join(dest_dir, f"Sessions_Checkout_{dt.now().strftime('%Y%m%d_%H%M%S')}")
            light_dir = os.path.join(checkout_dir, "lights")
            dark_dir = os.path.join(checkout_dir, "darks")
            flat_dir = os.path.join(checkout_dir, "flats")
            bias_dir = os.path.join(checkout_dir, "bias")
            process_dir = os.path.join(checkout_dir, "process")
            
            # Create shared directories once
            os.makedirs(light_dir, exist_ok=True)
            os.makedirs(dark_dir, exist_ok=True)
            os.makedirs(flat_dir, exist_ok=True)
            os.makedirs(bias_dir, exist_ok=True)
            os.makedirs(process_dir, exist_ok=True)
            
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
                    # Get session ID from tree item
                    session_id = session_item.data(0, Qt.UserRole)
                    if not session_id:
                        logger.error(f"Session item has no session ID, skipping")
                        failed_sessions.append(f"Session item missing ID")
                        current_session += 1
                        continue
                    
                    # Get the session from database using unique session ID
                    session = FitsSessionModel.get_by_id(session_id)
                    
                    if not session:
                        failed_sessions.append(f"Session ID {session_id}: Not found in database")
                        current_session += 1
                        continue
                    
                    # Get display information
                    parent_item = session_item.parent()
                    object_name = parent_item.text(0) if parent_item else session.fitsSessionObjectName
                    session_date = session.fitsSessionDate
                    filter_name = session.fitsSessionFilter or "NoFilter"
                    
                    overall_progress.setLabelText(f"Processing {object_name} - {session_date} ({filter_name})...")
                    overall_progress.setValue(current_session)
                    
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
                                    # Windows - use mklink (note: argument order is reversed from os.symlink)
                                    import subprocess
                                    # mklink syntax: mklink Link Target
                                    result = subprocess.run(f'mklink "{dest_path}" "{file.fitsFileName}"', 
                                                          shell=True, capture_output=True, text=True)
                                    if result.returncode != 0:
                                        raise Exception(f"mklink failed: {result.stderr}")
                                else:
                                    os.symlink(file.fitsFileName, dest_path)
                                session_links += 1
                        except Exception as e:
                            logger.error(f"Error creating link for {file.fitsFileName}: {e}")
                    
                    successful_sessions += 1
                    logger.info(f"Successfully processed session {object_name} - {session_date} with {session_links} links")
                    
                except Exception as e:
                    error_msg = f"{object_name if 'object_name' in locals() else 'Unknown'} - {session_date if 'session_date' in locals() else 'Unknown'}: {str(e)}"
                    failed_sessions.append(error_msg)
                    logger.error(f"Error processing session: {error_msg}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                
                current_session += 1
                logger.info(f"Completed session {current_session} of {total_sessions}")
            
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

    def calibrate_session(self, item, *, confirm: bool = True, show_results: bool = True):
        """Calibrate light frames in a session using available master frames"""
        try:
            from astropy.io import fits
            import numpy as np
            from ..core.master_manager import get_master_manager
            from ..models import Masters
            from ..core.utils import normalize_file_path
            import uuid
            import hashlib
            
            # Get session ID from tree item
            session_id = item.data(0, Qt.UserRole)
            if not session_id:
                if show_results:
                    QMessageBox.warning(self, "Error", "Session ID not found")
                return {"error": "Session ID not found"}
            
            # Get the session from database
            session = FitsSessionModel.get_by_id(session_id)
            if not session:
                if show_results:
                    QMessageBox.warning(self, "Error", "Session not found in database")
                return {"error": "Session not found in database"}
            
            parent_item = item.parent()
            object_name = parent_item.text(0) if parent_item else session.fitsSessionObjectName
            session_date = session.fitsSessionDate
            
            logger.info(f"Starting calibration for session: {object_name} on {session_date}")
            
            # Check if this is a calibration session
            if object_name in ['Bias', 'Dark', 'Flat']:
                if show_results:
                    QMessageBox.information(
                        self,
                        "Not Applicable",
                        "Calibration is only applicable to light frame sessions.",
                    )
                return {"error": "Calibration not applicable to calibration sessions"}
            
            # Find matching master frames
            master_manager = get_master_manager()
            session_data = {
                'telescope': session.fitsSessionTelescope,
                'instrument': session.fitsSessionImager,
                'exposure_time': session.fitsSessionExposure,
                'filter_name': session.fitsSessionFilter,
                'binning_x': session.fitsSessionBinningX,
                'binning_y': session.fitsSessionBinningY,
                'ccd_temp': session.fitsSessionCCDTemp,
                'gain': session.fitsSessionGain,
                'offset': session.fitsSessionOffset
            }
            
            master_bias = master_manager.find_matching_master(session_data, 'bias')
            master_dark = master_manager.find_matching_master(session_data, 'dark')
            master_flat = master_manager.find_matching_master(session_data, 'flat')
            
            has_bias = master_bias is not None and os.path.exists(master_bias.master_path)
            has_dark = master_dark is not None and os.path.exists(master_dark.master_path)
            has_flat = master_flat is not None and os.path.exists(master_flat.master_path)
            
            if not (has_bias or has_dark or has_flat):
                details = (
                    f"No matching master frames found for this session.\n\n"
                    f"Telescope: {session.fitsSessionTelescope}\n"
                    f"Instrument: {session.fitsSessionImager}\n"
                    f"Filter: {session.fitsSessionFilter}\n"
                    f"Binning: {session.fitsSessionBinningX}x{session.fitsSessionBinningY}\n\n"
                    f"Please create master frames first using Auto-Calibration."
                )
                if show_results:
                    QMessageBox.warning(self, "No Master Frames", details)
                return {"error": "No matching master frames found", "details": details}
            
            # Show available masters
            available_masters = []
            if has_bias:
                available_masters.append(f"Bias: {os.path.basename(master_bias.master_path)}")
            if has_dark:
                available_masters.append(f"Dark: {os.path.basename(master_dark.master_path)}")
            if has_flat:
                available_masters.append(f"Flat: {os.path.basename(master_flat.master_path)}")
            
            if confirm:
                # Confirm calibration
                reply = QMessageBox.question(self, "Calibrate Session",
                    f"Calibrate light frames in session {object_name} ({session_date})?\n\n"
                    f"Available master frames:\n" + "\n".join(available_masters) + "\n\n"
                    f"Calibrated frames will be saved with 'cal_' prefix.\n"
                    f"Source uncalibrated frames will be soft-deleted.",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                
                if reply != QMessageBox.Yes:
                    return {"cancelled": True}
            
            # Get light frames from session
            light_files = list(FitsFileModel.select().where(
                (FitsFileModel.fitsFileSession == session.fitsSessionId) &
                (FitsFileModel.fitsFileSoftDelete == False) &
                (FitsFileModel.fitsFileType.in_(['LIGHT', 'LIGHT FRAME']))
            ))
            
            if not light_files:
                if show_results:
                    QMessageBox.information(self, "No Files", "No light frames found in this session.")
                return {"total": 0, "calibrated": 0, "skipped": 0, "errors": 0}
            
            # Progress dialog
            progress = QProgressDialog("Calibrating light frames...", "Cancel", 0, len(light_files), self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("Calibrating Session")
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()
            
            # Load master frames
            master_bias_data = None
            master_dark_data = None
            master_flat_data = None
            
            try:
                if has_bias:
                    progress.setLabelText("Loading bias master...")
                    QApplication.processEvents()
                    with fits.open(master_bias.master_path) as hdul:
                        master_bias_data = hdul[0].data.astype(np.float32)
                    logger.info(f"Loaded bias master: {os.path.basename(master_bias.master_path)}")
                
                if has_dark:
                    progress.setLabelText("Loading dark master...")
                    QApplication.processEvents()
                    with fits.open(master_dark.master_path) as hdul:
                        master_dark_data = hdul[0].data.astype(np.float32)
                    logger.info(f"Loaded dark master: {os.path.basename(master_dark.master_path)}")
                
                if has_flat:
                    progress.setLabelText("Loading flat master...")
                    QApplication.processEvents()
                    with fits.open(master_flat.master_path) as hdul:
                        master_flat_data = hdul[0].data.astype(np.float32)
                        flat_mean = np.mean(master_flat_data)
                        if flat_mean > 0:
                            master_flat_data = master_flat_data / flat_mean
                        else:
                            logger.warning("Flat frame has zero mean, skipping flat correction")
                            master_flat_data = None
                    if master_flat_data is not None:
                        logger.info(f"Loaded and normalized flat master: {os.path.basename(master_flat.master_path)}")
                
            except Exception as e:
                progress.close()
                if show_results:
                    QMessageBox.critical(self, "Error", f"Failed to load master frames: {str(e)}")
                logger.error(f"Error loading master frames: {e}")
                return {"error": f"Failed to load master frames: {str(e)}"}
            
            # Calibrate each light frame
            calibrated_count = 0
            skipped_count = 0
            error_count = 0
            
            for i, light_file in enumerate(light_files):
                if progress.wasCanceled():
                    break
                
                try:
                    progress.setLabelText(f"Calibrating {i+1}/{len(light_files)}: {os.path.basename(light_file.fitsFileName)}")
                    progress.setValue(i)
                    QApplication.processEvents()
                    
                    # Check if already calibrated
                    if light_file.fitsFileCalibrated:
                        logger.debug(f"File already calibrated, skipping: {os.path.basename(light_file.fitsFileName)}")
                        skipped_count += 1
                        continue
                    
                    if not os.path.exists(light_file.fitsFileName):
                        logger.warning(f"File not found: {light_file.fitsFileName}")
                        error_count += 1
                        continue
                    
                    # Load light frame
                    with fits.open(light_file.fitsFileName) as hdul:
                        light_data = hdul[0].data.astype(np.float32)
                        light_header = hdul[0].header.copy()
                    
                    # Apply calibration: (Light - Bias - Dark) / Flat
                    calibrated_data = light_data.copy()
                    
                    if master_bias_data is not None:
                        calibrated_data -= master_bias_data
                        light_header['HISTORY'] = f'Bias corrected using {os.path.basename(master_bias.master_path)}'
                    
                    if master_dark_data is not None:
                        calibrated_data -= master_dark_data
                        light_header['HISTORY'] = f'Dark corrected using {os.path.basename(master_dark.master_path)}'
                    
                    if master_flat_data is not None:
                        mask = master_flat_data > 0
                        calibrated_data[mask] /= master_flat_data[mask]
                        light_header['HISTORY'] = f'Flat corrected using {os.path.basename(master_flat.master_path)}'
                    
                    # Update header
                    light_header['CALIBRAT'] = True
                    # NOTE: this file imports `datetime` module at top-level; use `dt` alias for datetime.datetime
                    light_header['CALDATE'] = dt.now().isoformat()
                    light_header['HISTORY'] = 'Calibrated by AstroFiler'
                    
                    # Save calibrated frame in same directory with cal_ prefix
                    source_dir = os.path.dirname(light_file.fitsFileName)
                    base_filename = os.path.basename(light_file.fitsFileName)
                    calibrated_filename = f"cal_{base_filename}"
                    calibrated_path = os.path.join(source_dir, calibrated_filename)
                    
                    # Clip and convert
                    calibrated_data = np.clip(calibrated_data, 0, 65535).astype(np.uint16)
                    
                    hdu = fits.PrimaryHDU(data=calibrated_data, header=light_header)
                    hdu.writeto(calibrated_path, overwrite=True)

                    # Add calibrated file to DB so it shows up in the session
                    calibrated_hash = None
                    try:
                        with open(calibrated_path, 'rb') as f:
                            calibrated_hash = hashlib.md5(f.read()).hexdigest()
                    except Exception as e:
                        logger.warning(f"Failed to hash calibrated file {calibrated_path}: {e}")

                    FitsFileModel.create(
                        fitsFileId=str(uuid.uuid4()),
                        fitsFileName=normalize_file_path(calibrated_path),
                        fitsFileDate=light_file.fitsFileDate,
                        fitsFileCalibrated=1,
                        fitsFileType=light_file.fitsFileType,
                        fitsFileStacked=light_file.fitsFileStacked,
                        fitsFileObject=light_file.fitsFileObject,
                        fitsFileExpTime=light_file.fitsFileExpTime,
                        fitsFileXBinning=light_file.fitsFileXBinning,
                        fitsFileYBinning=light_file.fitsFileYBinning,
                        fitsFileCCDTemp=light_file.fitsFileCCDTemp,
                        fitsFileTelescop=light_file.fitsFileTelescop,
                        fitsFileInstrument=light_file.fitsFileInstrument,
                        fitsFileGain=light_file.fitsFileGain,
                        fitsFileOffset=light_file.fitsFileOffset,
                        fitsFileFilter=light_file.fitsFileFilter,
                        fitsFileHash=calibrated_hash,
                        fitsFileSession=light_file.fitsFileSession,
                        fitsFileCloudURL=None,
                        fitsFileSoftDelete=False,
                        fitsFileCalibrationDate=dt.now(),
                        fitsFileOriginalFile=normalize_file_path(light_file.fitsFileName),
                        fitsFileOriginalCloudURL=light_file.fitsFileCloudURL
                    )
                    
                    # Soft-delete the source record so the session shows calibrated outputs
                    light_file.fitsFileSoftDelete = True
                    light_file.save()
                    
                    calibrated_count += 1
                    logger.info(f"Calibrated: {calibrated_filename}")
                    
                except Exception as e:
                    logger.error(f"Error calibrating {light_file.fitsFileName}: {e}")
                    error_count += 1
            
            progress.setValue(len(light_files))
            progress.close()
            
            # Show results
            message = f"Calibration complete!\n\n"
            message += f"Processed: {len(light_files)} files\n"
            message += f"Calibrated: {calibrated_count}\n"
            message += f"Skipped: {skipped_count}\n"
            message += f"Errors: {error_count}\n\n"
            message += f"Calibrated frames saved with 'cal_' prefix.\n"
            message += f"Source frames marked as soft-deleted."
            
            if show_results:
                if calibrated_count > 0:
                    QMessageBox.information(self, "Calibration Complete", message)
                else:
                    QMessageBox.warning(self, "Calibration Complete", message)
            
            logger.info(f"Session calibration complete: {calibrated_count} calibrated, {skipped_count} skipped, {error_count} errors")

            # Refresh sessions tree so new calibrated records appear
            try:
                self.load_sessions_data()
            except Exception as e:
                logger.warning(f"Failed to refresh sessions view after calibration: {e}")

            return {
                "total": len(light_files),
                "calibrated": calibrated_count,
                "skipped": skipped_count,
                "errors": error_count,
            }
            
        except Exception as e:
            if show_results:
                QMessageBox.critical(self, "Error", f"Failed to calibrate session: {str(e)}")
            logger.error(f"Error in calibrate_session: {str(e)}")
            return {"error": str(e)}

        # === SESSION MANAGEMENT METHODS ===

    def sample_stack_session(self, item):
        """Create a quick stack of calibrated frames for review and open it in external viewer."""
        try:
            from ..core.master_manager import get_master_manager
            from ..core.utils import sanitize_filesystem_name

            session_id = item.data(0, Qt.UserRole)
            if not session_id:
                QMessageBox.warning(self, "Error", "Session ID not found")
                return

            session = FitsSessionModel.get_by_id(session_id)
            if not session:
                QMessageBox.warning(self, "Error", "Session not found in database")
                return

            parent_item = item.parent()
            object_name = parent_item.text(0) if parent_item else (session.fitsSessionObjectName or "Unknown")
            if object_name in ['Bias', 'Dark', 'Flat']:
                QMessageBox.information(self, "Not Applicable", "Stack is only available for light sessions.")
                return

            # Check if this is a precalibrated telescope/instrument (iTelescope or SeeStar)
            telescope = session.fitsSessionTelescope or ""
            instrument = session.fitsSessionImager or ""
            is_precalibrated_session = (
                ('itelescope' in telescope.lower()) or
                ('seestar' in instrument.lower())
            )

            if is_precalibrated_session:
                # Precalibrated sessions should skip calibration entirely and stack the light frames as-is.
                stack_candidates = list(FitsFileModel.select().where(
                    (FitsFileModel.fitsFileSession == session.fitsSessionId) &
                    (FitsFileModel.fitsFileSoftDelete == False) &
                    (FitsFileModel.fitsFileType.in_(['LIGHT', 'LIGHT FRAME']))
                ))
            else:
                # Find calibrated light frames in this session
                stack_candidates = list(FitsFileModel.select().where(
                    (FitsFileModel.fitsFileSession == session.fitsSessionId) &
                    (FitsFileModel.fitsFileSoftDelete == False) &
                    (FitsFileModel.fitsFileCalibrated == 1) &
                    (FitsFileModel.fitsFileType.in_(['LIGHT', 'LIGHT FRAME']))
                ))

                # If not calibrated, run calibration first (no confirmation popups)
                if not stack_candidates:
                    logger.info(f"No calibrated frames found for session {session.fitsSessionId}; running calibration")
                    cal_result = self.calibrate_session(item, confirm=False, show_results=False)
                    if isinstance(cal_result, dict) and cal_result.get("cancelled"):
                        return
                    if isinstance(cal_result, dict) and cal_result.get("error"):
                        details = cal_result.get("details")
                        msg = cal_result.get("error")
                        if details:
                            msg = f"{msg}\n\n{details}"
                        QMessageBox.warning(self, "Calibration Failed", f"Calibration failed:\n{msg}")
                        return

                    stack_candidates = list(FitsFileModel.select().where(
                        (FitsFileModel.fitsFileSession == session.fitsSessionId) &
                        (FitsFileModel.fitsFileSoftDelete == False) &
                        (FitsFileModel.fitsFileCalibrated == 1) &
                        (FitsFileModel.fitsFileType.in_(['LIGHT', 'LIGHT FRAME']))
                    ))

            if not stack_candidates:
                QMessageBox.information(self, "No Frames", "No light frames were found to stack.")
                return

            file_paths = [f.fitsFileName for f in stack_candidates if f.fitsFileName and os.path.exists(f.fitsFileName)]
            if len(file_paths) < 2:
                QMessageBox.information(self, "Not Enough Frames", "Need at least 2 frames to create a stack.")
                return

            # Output path next to the calibrated frames
            out_dir = os.path.dirname(file_paths[0])
            date_str = str(session.fitsSessionDate) if session.fitsSessionDate else "unknown_date"
            safe_object = sanitize_filesystem_name(object_name)
            output_path = os.path.join(out_dir, f"stack_{safe_object}_{date_str}.fits")

            # Progress dialog for stacking
            progress = QProgressDialog("Stacking calibrated frames...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("Stack")
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()

            def _progress_callback(current, total, message):
                # Map arbitrary current/total to 0-100
                if progress.wasCanceled():
                    raise RuntimeError("Stack cancelled by user")
                try:
                    pct = int((float(current) / float(total)) * 100) if total else 0
                except Exception:
                    pct = 0
                pct = max(0, min(100, pct))
                progress.setValue(pct)
                if message:
                    progress.setLabelText(str(message))
                QApplication.processEvents()

            # Use existing internal sigma-clipped stacker (same engine used for masters)
            master_manager = get_master_manager()
            ok = master_manager._create_master_sigma_clip(
                file_paths=file_paths,
                output_path=output_path,
                cal_type='light',
                progress_callback=_progress_callback,
                thumbnail_session_id=str(session.fitsSessionId),
            )

            progress.setValue(100)
            progress.close()

            if not ok or not os.path.exists(output_path):
                QMessageBox.warning(self, "Stack Failed", "Failed to create stack.")
                return

            logger.info(f"Stack created: {output_path}")
            self._open_path_in_external_viewer(output_path)
            self.load_sessions_data()

        except RuntimeError as e:
            # Cancellation
            logger.info(f"Stack cancelled: {e}")
        except Exception as e:
            logger.error(f"Error creating stack: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create stack:\n{str(e)}")

    def photometric_stack_session(self, item):
        """Create a photometry-safe stack of light frames and open it in the external viewer."""
        try:
            from astrofiler.core.master_manager import get_master_manager
            from astrofiler.core.utils import sanitize_filesystem_name
            from astrofiler.models import fitsSession as FitsSessionModel
            from astrofiler.models import fitsFile as FitsFileModel

            session_id = item.data(0, Qt.UserRole)
            if not session_id:
                QMessageBox.warning(self, "Error", "Session ID not found")
                return

            session = FitsSessionModel.get_by_id(session_id)
            if not session:
                QMessageBox.warning(self, "Error", "Session not found in database")
                return

            parent_item = item.parent()
            object_name = parent_item.text(0) if parent_item else (session.fitsSessionObjectName or "Unknown")
            if object_name in ['Bias', 'Dark', 'Flat']:
                QMessageBox.information(self, "Not Applicable", "Photometric stack is only available for light sessions.")
                return

            telescope = session.fitsSessionTelescope or ""
            instrument = session.fitsSessionImager or ""
            is_precalibrated_session = (
                ('itelescope' in telescope.lower()) or
                ('seestar' in instrument.lower())
            )

            if is_precalibrated_session:
                stack_candidates = list(FitsFileModel.select().where(
                    (FitsFileModel.fitsFileSession == session.fitsSessionId) &
                    (FitsFileModel.fitsFileSoftDelete == False) &
                    (FitsFileModel.fitsFileType.in_(['LIGHT', 'LIGHT FRAME']))
                ))
            else:
                stack_candidates = list(FitsFileModel.select().where(
                    (FitsFileModel.fitsFileSession == session.fitsSessionId) &
                    (FitsFileModel.fitsFileSoftDelete == False) &
                    (FitsFileModel.fitsFileCalibrated == 1) &
                    (FitsFileModel.fitsFileType.in_(['LIGHT', 'LIGHT FRAME']))
                ))

                if not stack_candidates:
                    logger.info(f"No calibrated frames found for session {session.fitsSessionId}; running calibration")
                    cal_result = self.calibrate_session(item, confirm=False, show_results=False)
                    if isinstance(cal_result, dict) and cal_result.get("cancelled"):
                        return
                    if isinstance(cal_result, dict) and cal_result.get("error"):
                        details = cal_result.get("details")
                        msg = cal_result.get("error")
                        if details:
                            msg = f"{msg}\n\n{details}"
                        QMessageBox.warning(self, "Calibration Failed", f"Calibration failed:\n{msg}")
                        return

                    stack_candidates = list(FitsFileModel.select().where(
                        (FitsFileModel.fitsFileSession == session.fitsSessionId) &
                        (FitsFileModel.fitsFileSoftDelete == False) &
                        (FitsFileModel.fitsFileCalibrated == 1) &
                        (FitsFileModel.fitsFileType.in_(['LIGHT', 'LIGHT FRAME']))
                    ))

            if not stack_candidates:
                QMessageBox.information(self, "No Frames", "No light frames were found to stack.")
                return

            file_paths = [f.fitsFileName for f in stack_candidates if f.fitsFileName and os.path.exists(f.fitsFileName)]
            if len(file_paths) < 2:
                QMessageBox.information(self, "Not Enough Frames", "Need at least 2 frames to create a stack.")
                return

            # Prefer best-HFR as reference if available
            best_ref_path = None
            best_hfr = None
            for f in stack_candidates:
                p = getattr(f, 'fitsFileName', None)
                if not p or not os.path.exists(p):
                    continue
                hfr = getattr(f, 'fitsFileAvgHFRArcsec', None)
                if hfr is None:
                    continue
                try:
                    hfr_val = float(hfr)
                except Exception:
                    continue
                if best_hfr is None or hfr_val < best_hfr:
                    best_hfr = hfr_val
                    best_ref_path = p

            out_dir = os.path.dirname(file_paths[0])
            date_str = str(session.fitsSessionDate) if session.fitsSessionDate else "unknown_date"
            safe_object = sanitize_filesystem_name(object_name)
            output_path = os.path.join(out_dir, f"photometric_stack_{safe_object}_{date_str}.fits")

            progress = QProgressDialog("Creating photometric stack...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("Stack (photometric)")
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()

            def _progress_callback(current, total, message):
                if progress.wasCanceled():
                    raise RuntimeError("Stack cancelled by user")
                try:
                    pct = int((float(current) / float(total)) * 100) if total else 0
                except Exception:
                    pct = 0
                pct = max(0, min(100, pct))
                progress.setValue(pct)
                if message:
                    progress.setLabelText(str(message))
                QApplication.processEvents()

            master_manager = get_master_manager()
            ok = master_manager._create_light_stack_photometric_mean(
                file_paths=file_paths,
                output_path=output_path,
                progress_callback=_progress_callback,
                reference_path=best_ref_path,
                thumbnail_session_id=str(session.fitsSessionId),
            )

            progress.setValue(100)
            progress.close()

            if not ok or not os.path.exists(output_path):
                QMessageBox.warning(self, "Stack Failed", "Failed to create photometric stack.")
                return

            logger.info(f"Photometric stack created: {output_path}")
            self._open_path_in_external_viewer(output_path)
            self.load_sessions_data()

        except RuntimeError as e:
            logger.info(f"Photometric stack cancelled: {e}")
        except Exception as e:
            logger.error(f"Error creating photometric stack: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create photometric stack:\n{str(e)}")

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
            session_date = session_item.text(2)
            
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

            # Precompute counts/master flags up-front to avoid N+1 queries
            from peewee import fn

            sessions = list(FitsSessionModel.select())

            # File counts per session (matches previous behavior: includes soft-deleted rows)
            self._session_file_counts = {
                row["sid"]: int(row["cnt"])
                for row in (
                    FitsFileModel
                    .select(
                        FitsFileModel.fitsFileSession.alias("sid"),
                        fn.COUNT(FitsFileModel.fitsFileId).alias("cnt"),
                    )
                    .where(FitsFileModel.fitsFileSession.is_null(False))
                    .group_by(FitsFileModel.fitsFileSession)
                    .dicts()
                )
                if row.get("sid")
            }

            # Which sessions have created masters
            self._master_source_session_ids = set(
                Masters
                .select(Masters.source_session_id)
                .where(
                    (Masters.soft_delete == False) &
                    (Masters.source_session_id.is_null(False))
                )
                .tuples()
            )
            # tuples() yields 1-tuples
            self._master_source_session_ids = {sid for (sid,) in self._master_source_session_ids if sid}
            
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
                    total_images += self._session_file_counts.get(session.fitsSessionId, 0)
                
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
                parent_item.setText(1, "")  # No thumbnail for parent
                parent_item.setText(2, "")  # No date for parent
                parent_item.setText(3, "")  # No telescope for parent
                parent_item.setText(4, "")  # No imager for parent
                parent_item.setText(5, "")  # No filter for parent
                parent_item.setText(6, str(total_images))  # Total images for this object
                
                # Show resource summary for parent
                if total_light_sessions > 0:
                    cal_percentage = (calibrated_sessions / total_light_sessions) * 100
                    cal_summary = f"{calibrated_sessions}/{total_light_sessions} ({cal_percentage:.0f}%)"
                    parent_item.setText(7, cal_summary)
                    parent_item.setToolTip(7, f"Resource Coverage: {calibrated_sessions} of {total_light_sessions} sessions have calibration resources")
                else:
                    parent_item.setText(7, "")
                
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
                    session_image_count = self._session_file_counts.get(session.fitsSessionId, 0)
                    
                    # Build enhanced resources status
                    calibration_info = self._build_resources_status(session)
                    
                    # Check if this session has created a master frame
                    has_master = session.fitsSessionId in self._master_source_session_ids
                    
                    child_item = QTreeWidgetItem()
                    # Show (master) for calibration sessions that have created masters
                    if has_master and session.fitsSessionObjectName in ['Bias', 'Dark', 'Flat']:
                        child_item.setText(0, "(master)")
                    else:
                        child_item.setText(0, "")  # Empty object name for child
                    child_item.setText(1, "")  # Thumbnail column
                    child_item.setText(2, str(session.fitsSessionDate) if session.fitsSessionDate else "Unknown Date")
                    child_item.setText(3, session.fitsSessionTelescope or "Unknown")
                    child_item.setText(4, session.fitsSessionImager or "Unknown")
                    child_item.setText(5, session.fitsSessionFilter or "Unknown")
                    child_item.setText(6, str(session_image_count))  # Image count for this session
                    
                    # Store session ID in the item for later retrieval
                    child_item.setData(0, Qt.UserRole, session.fitsSessionId)

                    # Attach thumbnail icon if it exists (light sessions only)
                    if session.fitsSessionObjectName not in ['Bias', 'Dark', 'Flat']:
                        thumb_path = self._get_thumbnail_path(str(session.fitsSessionId))
                        if thumb_path and os.path.exists(thumb_path):
                            pix = QPixmap(thumb_path)
                            if not pix.isNull():
                                pix = pix.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                child_item.setIcon(1, QIcon(pix))
                                child_item.setToolTip(1, f"Thumbnail: {thumb_path}")
                    
                    # Set resources status as simple text only
                    if calibration_info["text"]:
                        child_item.setText(7, calibration_info["text"])
                        child_item.setToolTip(7, calibration_info["tooltip"])
                    else:
                        child_item.setText(7, "")
                    
                    # Build quality metrics tooltip for all columns
                    quality_tooltip = self._build_quality_tooltip(session)
                    for col in range(8):  # Apply tooltip to all columns
                        if col == 7 and calibration_info["tooltip"]:
                            # Combine calibration tooltip with quality metrics
                            combined_tooltip = f"{calibration_info['tooltip']}\n\n{quality_tooltip}"
                            child_item.setToolTip(col, combined_tooltip)
                        else:
                            child_item.setToolTip(col, quality_tooltip)
                    
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

    def _get_thumbnail_path(self, session_id: str) -> str:
        """Return the expected thumbnail path for a session id."""
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            repo_path = config.get('DEFAULT', 'repo', fallback='')
        except Exception:
            repo_path = ''

        if not repo_path:
            return ''
        return os.path.join(repo_path, 'Thumbnails', f"{session_id}.png")
    
    def _build_quality_tooltip(self, session):
        """
        Build a tooltip string with quality metrics for a session.
        
        Args:
            session: fitsSession object
            
        Returns:
            str: Formatted tooltip with quality metrics
        """
        parts = []
        parts.append("=== Quality Metrics ===")
        
        if session.fitsSessionAvgFWHMArcsec is not None:
            parts.append(f"Average FWHM: {session.fitsSessionAvgFWHMArcsec:.2f} arcsec")
        else:
            parts.append("Average FWHM: N/A")
        
        if session.fitsSessionAvgEccentricity is not None:
            parts.append(f"Average Eccentricity: {session.fitsSessionAvgEccentricity:.3f}")
        else:
            parts.append("Average Eccentricity: N/A")
        
        if session.fitsSessionAvgHFRArcsec is not None:
            parts.append(f"Average HFR: {session.fitsSessionAvgHFRArcsec:.2f} arcsec")
        else:
            parts.append("Average HFR: N/A")
        
        if session.fitsSessionImageSNR is not None:
            parts.append(f"Average SNR: {session.fitsSessionImageSNR:.1f}")
        else:
            parts.append("Average SNR: N/A")
        
        if session.fitsSessionStarCount is not None:
            parts.append(f"Average Star Count: {session.fitsSessionStarCount}")
        else:
            parts.append("Average Star Count: N/A")
        
        if session.fitsSessionImageScale is not None:
            parts.append(f"Image Scale: {session.fitsSessionImageScale:.2f} arcsec/pixel")
        else:
            parts.append("Image Scale: N/A")
        
        return "\n".join(parts)

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
            dark_count = self._session_file_counts.get(session.fitsDarkSession)
            if dark_count is not None:
                status_parts.append(f"Dark: {dark_count}")
                tooltip_parts.append(f"✓ {dark_count} dark frames available")
            else:
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
            flat_count = self._session_file_counts.get(session.fitsFlatSession)
            if flat_count is not None:
                status_parts.append(f"Flat: {flat_count}")
                tooltip_parts.append(f"✓ {flat_count} flat frames available")
            else:
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
            bias_count = self._session_file_counts.get(session.fitsBiasSession)
            if bias_count is not None:
                status_parts.append(f"Bias: {bias_count}")
                tooltip_parts.append(f"✓ {bias_count} bias frames available")
            else:
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
        """Run the auto-calibration workflow with customizable operation selection"""
        try:
            from .auto_calibration_dialog import AutoCalibrationDialog
            from PySide6.QtWidgets import QDialog
            
            # Create and show the workflow selection dialog
            dialog = AutoCalibrationDialog(self)
            result = dialog.exec()
            
            # Refresh the sessions display if workflow completed
            if result == QDialog.Accepted:
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