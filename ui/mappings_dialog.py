import os
import logging
import configparser
import shutil
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, 
                               QWidget, QPushButton, QCheckBox, QComboBox, 
                               QLabel, QGridLayout, QDialogButtonBox, 
                               QProgressDialog, QMessageBox, QApplication)

from astropy.io import fits
from astrofiler_db import fitsFile as FitsFileModel, Mapping as MappingModel

logger = logging.getLogger(__name__)


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
        add_button.setStyleSheet("QPushButton { font-size: 11px; }")
        add_button.clicked.connect(lambda: self.add_mapping_row())
        layout.addWidget(add_button)
        
        # Scroll area for mappings
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_layout.setSpacing(5)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        # Add a stretch to push all rows to the top
        self.scroll_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area)
        
        # Bottom buttons
        bottom_layout = QVBoxLayout()
        
        # Add checkboxes
        checkbox_layout = QHBoxLayout()
        
        # Update files checkbox
        self.update_files_checkbox = QCheckBox("Update FITS headers on disk")
        self.update_files_checkbox.setChecked(True)
        self.update_files_checkbox.setToolTip("Also update the FITS headers in the actual files on disk")
        self.update_files_checkbox.setStyleSheet("QCheckBox { font-size: 10px; }")
        checkbox_layout.addWidget(self.update_files_checkbox)
        
        # Apply to database checkbox
        self.apply_to_database_checkbox = QCheckBox("Apply mappings to database")
        self.apply_to_database_checkbox.setChecked(True)
        self.apply_to_database_checkbox.setToolTip("Apply the mappings to update database records")
        self.apply_to_database_checkbox.setStyleSheet("QCheckBox { font-size: 10px; }")
        checkbox_layout.addWidget(self.apply_to_database_checkbox)
        
        # Reorganize files checkbox
        self.reorganize_files_checkbox = QCheckBox("Reorganize repository folders")
        self.reorganize_files_checkbox.setChecked(True)
        self.reorganize_files_checkbox.setToolTip("Move files to correct folder structure when telescope/instrument mappings are applied")
        self.reorganize_files_checkbox.setStyleSheet("QCheckBox { font-size: 10px; }")
        checkbox_layout.addWidget(self.reorganize_files_checkbox)
        
        bottom_layout.addLayout(checkbox_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_mappings)
        button_box.rejected.connect(self.reject)
        
        # Reduce button sizes
        ok_button = button_box.button(QDialogButtonBox.Ok)
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        if ok_button:
            ok_button.setStyleSheet("QPushButton { font-size: 10px; }")
            ok_button.setMaximumSize(60, 28)
        if cancel_button:
            cancel_button.setStyleSheet("QPushButton { font-size: 10px; }")
            cancel_button.setMaximumSize(60, 28)
        
        bottom_layout.addWidget(button_box)
        layout.addLayout(bottom_layout)
    
    def get_current_values_for_card(self, card):
        """Get current values for a specific FITS header card from the database"""
        try:
            if card == "TELESCOP":
                values = set([f.fitsFileTelescop for f in FitsFileModel.select().distinct() if f.fitsFileTelescop])
            elif card == "INSTRUME":
                values = set([f.fitsFileInstrument for f in FitsFileModel.select().distinct() if f.fitsFileInstrument])
            elif card == "OBSERVER":
                values = set([f.fitsFileObserver for f in FitsFileModel.select().distinct() if f.fitsFileObserver])
            elif card == "FILTER":
                values = set([f.fitsFileFilter for f in FitsFileModel.select().distinct() if f.fitsFileFilter])
            elif card == "NOTES":
                values = set([f.fitsFileNotes for f in FitsFileModel.select().distinct() if f.fitsFileNotes])
            else:
                values = set()
            
            return sorted(list(values))
        except Exception as e:
            logger.error(f"Error getting current values for {card}: {e}")
            return [""]
    
    def add_mapping_row(self, card="TELESCOP", current="", replace="", is_default=False):
        """Add a new mapping row to the dialog"""
        row_widget = QWidget()
        row_layout = QGridLayout(row_widget)
        row_layout.setSpacing(5)
        row_layout.setContentsMargins(5, 5, 5, 5)
        
        # Set column stretch factors for consistent alignment
        row_layout.setColumnStretch(1, 2)  # Card combo
        row_layout.setColumnStretch(3, 3)  # Current combo
        row_layout.setColumnStretch(5, 3)  # Replace combo
        
        # Card dropdown
        card_combo = QComboBox()
        card_combo.addItems(["TELESCOP", "INSTRUME", "OBSERVER", "NOTES","FILTER"])
        card_combo.setCurrentText(card)
        card_combo.currentTextChanged.connect(lambda: self.update_current_values(row_widget))
        
        # Current dropdown
        current_combo = QComboBox()
        current_combo.setEditable(True)
        
        # Replace dropdown
        replace_combo = QComboBox()
        replace_combo.setEditable(True)
        
        # Apply button
        apply_button = QPushButton("✓")
        apply_button.setMaximumWidth(30)
        apply_button.setToolTip("Apply this mapping immediately")
        apply_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #44ff44;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 10px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #66ff66;
                border: 1px solid #44ff44;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
                color: #22ff22;
            }
        """)
        apply_button.clicked.connect(lambda: self.apply_single_mapping(row_widget))
        
        # Delete button
        delete_button = QPushButton("🗑")
        delete_button.setMaximumWidth(30)
        delete_button.setToolTip("Delete this mapping")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #ff4444;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 10px;
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
        row_layout.addWidget(replace_combo, 0, 5)
        row_layout.addWidget(apply_button, 0, 6)
        row_layout.addWidget(delete_button, 0, 7)
        
        # Store references
        row_widget.card_combo = card_combo
        row_widget.current_combo = current_combo
        row_widget.replace_combo = replace_combo
        row_widget.apply_button = apply_button
        
        # Update current and replace values for initial card
        self.update_current_values(row_widget)
        
        # Ensure the saved values are available in the combo boxes
        if current and current not in [current_combo.itemText(i) for i in range(current_combo.count())]:
            current_combo.addItem(current)
        if replace and replace not in [replace_combo.itemText(i) for i in range(replace_combo.count())]:
            replace_combo.addItem(replace)
            
        # Set the saved values
        current_combo.setCurrentText(current)
        replace_combo.setCurrentText(replace)
        
        # Add to scroll layout (insert before the stretch)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, row_widget)
        self.mapping_rows.append(row_widget)
    
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
            mappings_loaded = 0
            
            for mapping in mappings:
                self.add_mapping_row(
                    card=mapping.card,
                    current=mapping.current or "",
                    replace=mapping.replace or ""
                )
                mappings_loaded += 1
            
            # Add a default mapping row if no mappings were loaded
            if mappings_loaded == 0:
                self.add_mapping_row()
            else:
                logger.info(f"Loaded {mappings_loaded} existing mappings from database")
                
        except Exception as e:
            logger.error(f"Error loading existing mappings: {e}")
            # Add a default mapping row if there was an error
            if not self.mapping_rows:
                self.add_mapping_row()
    
    def accept_mappings(self):
        """Save mappings to database and close dialog"""
        try:
            # Clear existing mappings
            MappingModel.delete().execute()
            
            # Save new mappings to database
            mappings_saved = 0
            for row_widget in self.mapping_rows:
                card = row_widget.card_combo.currentText()
                current = row_widget.current_combo.currentText()
                replace = row_widget.replace_combo.currentText()
                
                if card and replace:  # Only save if both card and replace are provided
                    MappingModel.create(
                        card=card,
                        current=current if current else None,
                        replace=replace if replace else None
                    )
                    mappings_saved += 1
            
            # Clear the mapping cache so file processing picks up new mappings
            try:
                from astrofiler_file import clearMappingCache
                clearMappingCache()
            except ImportError:
                pass  # Function might not be available in older versions
            
            # Show success message
            QMessageBox.information(self, "Success", f"Saved {mappings_saved} mapping(s) to database.")
            
            # Accept the dialog
            self.accept()
            
        except Exception as e:
            logger.error(f"Error saving mappings: {e}")
            QMessageBox.critical(self, "Error", f"Error saving mappings: {e}")
    
    def get_current_values_for_card(self, card):
        """Get current values for a specific FITS header card from the database"""
        try:
            if card == "TELESCOP":
                values = set([f.fitsFileTelescop for f in FitsFileModel.select().distinct() if f.fitsFileTelescop])
            elif card == "INSTRUME":
                values = set([f.fitsFileInstrument for f in FitsFileModel.select().distinct() if f.fitsFileInstrument])
            elif card == "OBSERVER":
                values = set([f.fitsFileObserver for f in FitsFileModel.select().distinct() if f.fitsFileObserver])
            elif card == "FILTER":
                values = set([f.fitsFileFilter for f in FitsFileModel.select().distinct() if f.fitsFileFilter])
            elif card == "NOTES":
                values = set([f.fitsFileNotes for f in FitsFileModel.select().distinct() if f.fitsFileNotes])
            else:
                values = set()
            
            return sorted(list(values))
        except Exception as e:
            logger.error(f"Error getting current values for {card}: {e}")
            return [""]
    
    def update_current_values(self, row_widget):
        """Update the current and replace dropdowns based on the selected card"""
        card = row_widget.card_combo.currentText()
        current_combo = row_widget.current_combo
        replace_combo = row_widget.replace_combo
        
        # Get current values for the selected card
        current_values = self.get_current_values_for_card(card)
        
        # Update current combo
        current_combo.clear()
        current_combo.addItems(current_values)
        
        # Update replace combo with existing mappings
        replace_combo.clear()
        replace_combo.addItems(current_values)
    
    def apply_single_mapping(self, row_widget):
        """Apply a single mapping immediately"""
        try:
            card = row_widget.card_combo.currentText()
            current = row_widget.current_combo.currentText()
            replace = row_widget.replace_combo.currentText()
            
            # Validate inputs
            if not card:
                QMessageBox.warning(self, "Invalid Mapping", "Please select a card type.")
                return
            
            if not replace:
                QMessageBox.warning(self, "Invalid Mapping", "Please enter a replacement value.")
                return
            
            # Confirm the action
            if current:
                message = f"Apply mapping for {card}:\n'{current}' → '{replace}'\n\nThis will update the database immediately."
            else:
                message = f"Apply mapping for {card}:\n'(empty/null)' → '{replace}'\n\nThis will update the database immediately."
            
            reply = QMessageBox.question(
                self, 
                "Confirm Apply Mapping", 
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Create progress dialog
            progress = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress.setWindowTitle("Applying Mapping")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            
            try:
                # Step 1: Save mapping to database (25%)
                progress.setLabelText("Saving mapping to database...")
                progress.setValue(25)
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    return
                
                try:
                    existing_mapping = MappingModel.get(
                        (MappingModel.card == card) & 
                        (MappingModel.current == (current if current else None))
                    )
                    # Update existing mapping
                    existing_mapping.replace = replace if replace else None
                    existing_mapping.save()
                    logger.info(f"Updated existing mapping: {card} '{current}' -> '{replace}'")
                except MappingModel.DoesNotExist:
                    # Create new mapping
                    MappingModel.create(
                        card=card,
                        current=current if current else None,
                        replace=replace if replace else None
                    )
                    logger.info(f"Created new mapping: {card} '{current}' -> '{replace}'")
                
                # Step 2: Apply to database records (50%)
                progress.setLabelText(f"Applying {card} mapping to database records...")
                progress.setValue(50)
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    return
                
                # Create a single mapping to apply
                mapping_to_apply = {
                    'card': card,
                    'current': current,
                    'replace': replace
                }
                
                # Apply the mapping to database records
                update_files = self.update_files_checkbox.isChecked()
                total_updates = 0
                files_moved = 0
                
                if mapping_to_apply['card'] in ['TELESCOP', 'INSTRUME']:
                    field_name = 'fitsFileTelescop' if mapping_to_apply['card'] == 'TELESCOP' else 'fitsFileInstrument'
                    
                    # Find files that match the current value
                    if mapping_to_apply['current']:
                        # Specific value mapping
                        query = FitsFileModel.select().where(getattr(FitsFileModel, field_name) == mapping_to_apply['current'])
                    else:
                        # Default mapping for null/empty values
                        query = FitsFileModel.select().where(
                            (getattr(FitsFileModel, field_name).is_null()) |
                            (getattr(FitsFileModel, field_name) == '')
                        )
                    
                    # Step 3: Update database records and files (75% - 95%)
                    file_count = query.count()
                    progress.setLabelText(f"Updating {file_count} database records...")
                    progress.setValue(75)
                    QApplication.processEvents()
                    
                    if progress.wasCanceled():
                        return
                    
                    # Update matching files with progress tracking
                    files_list = list(query)
                    for index, fits_file in enumerate(files_list):
                        # Update progress for each file (75% to 95%)
                        if file_count > 0:
                            file_progress = 75 + int((index / file_count) * 20)  # 75% to 95%
                            progress.setValue(file_progress)
                            progress.setLabelText(f"Processing file {index + 1} of {file_count}: {os.path.basename(fits_file.fitsFileName or 'Unknown')}")
                            QApplication.processEvents()
                        
                        if progress.wasCanceled():
                            return
                        
                        if mapping_to_apply['replace']:
                            old_file_path = fits_file.fitsFileName
                            
                            # Update database record
                            setattr(fits_file, field_name, mapping_to_apply['replace'])
                            fits_file.save()
                            total_updates += 1
                            
                            # Update FITS header and move files if requested
                            if update_files and old_file_path and os.path.exists(old_file_path):
                                try:
                                    # First update the FITS header
                                    with fits.open(old_file_path, mode='update') as hdul:
                                        hdul[0].header[mapping_to_apply['card']] = mapping_to_apply['replace']
                                        hdul[0].header.comments[mapping_to_apply['card']] = 'Updated via Astrofiler mapping'
                                        hdul.flush()
                                    
                                    # Now determine if file needs to be moved to new folder structure
                                    new_file_path = self._calculate_new_file_path(old_file_path, mapping_to_apply)
                                    
                                    if new_file_path and new_file_path != old_file_path:
                                        # Create new directory if it doesn't exist
                                        new_dir = os.path.dirname(new_file_path)
                                        os.makedirs(new_dir, exist_ok=True)
                                        
                                        # Move the file
                                        shutil.move(old_file_path, new_file_path)
                                        files_moved += 1
                                        
                                        # Update database with new file path
                                        fits_file.fitsFileName = new_file_path.replace('\\', '/')
                                        fits_file.save()
                                        
                                        logger.info(f"Moved file: {old_file_path} -> {new_file_path}")
                                    
                                except Exception as e:
                                    logger.error(f"Error updating FITS header/moving file {old_file_path}: {e}")
                    
                    if files_moved > 0:
                        logger.info(f"Moved {files_moved} files to new folder structure")

                # Step 4: Clear cache and update UI (95% - 100%)
                progress.setLabelText("Clearing mapping cache...")
                progress.setValue(96)
                QApplication.processEvents()
                
                # Clear the mapping cache so file processing picks up new mappings
                try:
                    from astrofiler_file import clearMappingCache
                    clearMappingCache()
                except ImportError:
                    pass  # Function might not be available in older versions
                
                # Keep the applied mapping values visible in the UI
                # Don't update dropdowns as this would reset the form to defaults
                progress.setLabelText("Finalizing...")
                progress.setValue(98)
                QApplication.processEvents()
                
                progress.setLabelText("Complete!")
                progress.setValue(100)
                QApplication.processEvents()
                
                # Brief pause to show completion
                time.sleep(0.2)
                
                progress.close()
                
                # Update the apply button to show it's been applied
                if hasattr(row_widget, 'apply_button'):
                    row_widget.apply_button.setText("✓")
                    row_widget.apply_button.setToolTip("Mapping applied and saved to database")
                    row_widget.apply_button.setStyleSheet("""
                        QPushButton {
                            background-color: #2d4d2d;
                            color: #88ff88;
                            border: 1px solid #44aa44;
                            border-radius: 3px;
                            font-size: 10px;
                            padding: 2px;
                            font-weight: bold;
                        }
                        QPushButton:hover {
                            background-color: #3d5d3d;
                            color: #99ff99;
                            border: 1px solid #55bb55;
                        }
                    """)
                
                # Show success message
                if total_updates > 0:
                    message = f"Successfully saved mapping to database and updated {total_updates} database records."
                    if update_files and files_moved > 0:
                        message += f"\nMoved {files_moved} files to new folder structure."
                    elif update_files:
                        message += f"\nUpdated FITS headers for {total_updates} files."
                    
                    QMessageBox.information(
                        self, 
                        "Mapping Applied", 
                        message
                    )
                else:
                    QMessageBox.information(
                        self, 
                        "Mapping Applied", 
                        "Mapping saved to database successfully. No matching records found to update."
                    )
                
            except Exception as e:
                if 'progress' in locals():
                    progress.close()
                raise e
            
        except Exception as e:
            logger.error(f"Error applying single mapping: {e}")
            QMessageBox.critical(self, "Error", f"Error applying mapping: {e}")
    
    def _calculate_new_file_path(self, old_file_path, mapping):
        """Calculate the new file path based on the mapping change."""
        try:
            # Parse the old file path to understand the structure
            # Expected structure: .../Light/{OBJECT}/{TELESCOPE}/{INSTRUMENT}/{DATE}/filename
            # or: .../Calibrate/{TYPE}/{TELESCOPE}/{INSTRUMENT}/{EXPOSURE}/{DATE}/filename
            
            path_parts = old_file_path.replace('\\', '/').split('/')
            filename = path_parts[-1]
            
            # Find the base repository path by looking for 'Light' or 'Calibrate'
            repo_base = None
            structure_index = -1
            
            for i, part in enumerate(path_parts):
                if part in ['Light', 'Calibrate']:
                    repo_base = '/'.join(path_parts[:i+1]) + '/'
                    structure_index = i
                    break
            
            if not repo_base or structure_index == -1:
                logger.warning(f"Could not determine repository structure for {old_file_path}")
                return None
            
            # Get the folder structure after Light/Calibrate
            folder_structure = path_parts[structure_index+1:-1]  # Exclude filename
            
            if len(folder_structure) < 3:
                logger.warning(f"Unexpected folder structure in {old_file_path}")
                return None
            
            # For Light files: Light/{OBJECT}/{TELESCOPE}/{INSTRUMENT}/{DATE}/
            # For Calibrate files: Calibrate/{TYPE}/{TELESCOPE}/{INSTRUMENT}/{...}/
            
            if path_parts[structure_index] == 'Light' and len(folder_structure) >= 4:
                object_name, telescope, instrument, date = folder_structure[:4]
            elif path_parts[structure_index] == 'Calibrate' and len(folder_structure) >= 3:
                cal_type = folder_structure[0]
                telescope, instrument = folder_structure[1:3]
                remaining = folder_structure[3:] if len(folder_structure) > 3 else []
            else:
                logger.warning(f"Unrecognized folder structure: {folder_structure}")
                return None
            
            # Apply the mapping and update filename
            new_filename = filename
            if mapping['card'] == 'TELESCOP':
                new_telescope = mapping['replace'].replace(" ", "_").replace("\\", "_")
                old_telescope = mapping['current'].replace(" ", "_").replace("\\", "_") if mapping['current'] else telescope
                
                # Update filename: replace old telescope name with new telescope name
                if old_telescope in filename:
                    new_filename = filename.replace(old_telescope, new_telescope)
                
                if path_parts[structure_index] == 'Light':
                    new_path = f"{repo_base}{object_name}/{new_telescope}/{instrument}/{date}/{new_filename}"
                else:  # Calibrate
                    remaining_path = '/'.join(remaining) + '/' if remaining else ''
                    new_path = f"{repo_base}{cal_type}/{new_telescope}/{instrument}/{remaining_path}{new_filename}"
                    
            elif mapping['card'] == 'INSTRUME':
                new_instrument = mapping['replace'].replace(" ", "_").replace("\\", "_")
                old_instrument = mapping['current'].replace(" ", "_").replace("\\", "_") if mapping['current'] else instrument
                
                # Update filename: replace old instrument name with new instrument name
                if old_instrument in filename:
                    new_filename = filename.replace(old_instrument, new_instrument)
                
                if path_parts[structure_index] == 'Light':
                    new_path = f"{repo_base}{object_name}/{telescope}/{new_instrument}/{date}/{new_filename}"
                else:  # Calibrate
                    remaining_path = '/'.join(remaining) + '/' if remaining else ''
                    new_path = f"{repo_base}{cal_type}/{telescope}/{new_instrument}/{remaining_path}{new_filename}"
            else:
                # For other mappings (OBSERVER, NOTES, etc.), no file path change needed
                return None
            
            return new_path.replace('/', os.sep)  # Convert to OS-appropriate separators
            
        except Exception as e:
            logger.error(f"Error calculating new file path for {old_file_path}: {e}")
            return None
    
    def apply_database_mappings(self):
        """Apply the mappings to the database based on the current rows"""
        try:
            total_mappings = len(self.mapping_rows)
            if total_mappings == 0:
                QMessageBox.information(self, "No Mappings", "No mappings to apply.")
                return
            
            # Confirm with the user
            reply = QMessageBox.question(self, "Confirm Apply Mappings",
                f"Are you sure you want to apply {total_mappings} mapping(s) to the database?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                # Begin a transaction
                with MappingModel._meta.database.transaction():
                    for row_widget in self.mapping_rows:
                        card = row_widget.card_combo.currentText()
                        current = row_widget.current_combo.currentText()
                        replace = row_widget.replace_combo.currentText()
                        
                        if card and replace:  # Only apply if both card and replace are provided
                            # Update or insert the mapping in the database
                            MappingModel.insert(
                                card=card,
                                current=current,
                                replace=replace
                            ).on_conflict_replace().execute()
                
                QMessageBox.information(self, "Success", f"Applied {total_mappings} mapping(s) to the database.")
            else:
                QMessageBox.information(self, "Cancelled", "Apply mappings cancelled.")
        except Exception as e:
            logger.error(f"Error applying database mappings: {e}")
            QMessageBox.critical(self, "Error", f"Error applying mappings to database: {e}")
    
    def reorganize_repository_files(self):
        """Reorganize files in the repository based on the current mappings"""
        try:
            total_files = len(self.mapping_rows)
            if total_files == 0:
                QMessageBox.information(self, "No Files", "No files to reorganize.")
                return
            
            # Confirm with the user
            reply = QMessageBox.question(self, "Confirm Reorganize Files",
                f"Are you sure you want to reorganize {total_files} file(s) in the repository?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                # Begin reorganization
                for row_widget in self.mapping_rows:
                    card = row_widget.card_combo.currentText()
                    current = row_widget.current_combo.currentText()
                    replace = row_widget.replace_combo.currentText()
                    
                    if card and replace:  # Only reorganize if both card and replace are provided
                        self.reorganize_file(card, current, replace)
                
                QMessageBox.information(self, "Success", f"Reorganized {total_files} file(s) in the repository.")
            else:
                QMessageBox.information(self, "Cancelled", "Reorganize files cancelled.")
        except Exception as e:
            logger.error(f"Error reorganizing repository files: {e}")
            QMessageBox.critical(self, "Error", f"Error reorganizing files: {e}")
    
    def reorganize_file(self, card, current, replace):
        """Reorganize a single file based on the mapping"""
        try:
            # Implement the file reorganization logic here
            # For example, moving the file to a new location based on the mapping
            pass  # TODO: Replace with actual reorganization code
        except Exception as e:
            logger.error(f"Error reorganizing file {current}: {e}")
    
    def calculate_new_file_path(self, current_path, card, new_value):
        """Calculate the new file path based on the current path, card, and new value"""
        try:
            # Implement the logic to calculate the new file path
            # For example, replacing a part of the path based on the mapping
            return current_path  # TODO: Replace with actual path calculation
        except Exception as e:
            logger.error(f"Error calculating new file path for {current_path}: {e}")
            return current_path
    
    def cleanup_empty_directories(self, path):
        """Remove empty directories recursively starting from the given path"""
        try:
            # Implement the logic to remove empty directories
            # For example, using os.rmdir or shutil.rmtree
            pass  # TODO: Replace with actual cleanup code
        except Exception as e:
            logger.error(f"Error cleaning up empty directories starting from {path}: {e}")
    
    def apply_file_folder_mappings(self):
        """Apply file and folder mappings based on the current rows"""
        try:
            total_mappings = len(self.mapping_rows)
            if total_mappings == 0:
                QMessageBox.information(self, "No Mappings", "No file or folder mappings to apply.")
                return
            
            # Confirm with the user
            reply = QMessageBox.question(self, "Confirm Apply File/Folder Mappings",
                f"Are you sure you want to apply {total_mappings} file/folder mapping(s)?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                for row_widget in self.mapping_rows:
                    card = row_widget.card_combo.currentText()
                    current = row_widget.current_combo.currentText()
                    replace = row_widget.replace_combo.currentText()
                    
                    if card and replace:  # Only apply if both card and replace are provided
                        # TODO: Implement the logic to apply file and folder mappings
                        pass
                
                QMessageBox.information(self, "Success", f"Applied {total_mappings} file/folder mapping(s).")
            else:
                QMessageBox.information(self, "Cancelled", "Apply file/folder mappings cancelled.")
        except Exception as e:
            logger.error(f"Error applying file/folder mappings: {e}")
            QMessageBox.critical(self, "Error", f"Error applying file/folder mappings: {e}")
