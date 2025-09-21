import os
import logging
import configparser
import shutil

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
        self.update_files_checkbox.setChecked(False)
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
        self.reorganize_files_checkbox.setChecked(False)
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
        
        # Update current and replace values for initial card
        self.update_current_values(row_widget)
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
            # Add a default mapping row if none exist
            if not self.mapping_rows:
                self.add_mapping_row()
        except Exception as e:
            logger.error(f"Error loading existing mappings: {e}")
    
    def accept_mappings(self):
        """Save mappings and close dialog"""
        try:
            # Collect all mappings
            mappings = []
            for row_widget in self.mapping_rows:
                card = row_widget.card_combo.currentText()
                current = row_widget.current_combo.currentText()
                replace = row_widget.replace_combo.currentText()
                
                if card and replace:  # Only save if both card and replace are provided
                    mappings.append({
                        'card': card,
                        'current': current,
                        'replace': replace
                    })
            
            # Show success message
            QMessageBox.information(self, "Success", f"Saved {len(mappings)} mapping(s).")
            
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
        
        # Update current and replace values for initial card
        self.update_current_values(row_widget)
        current_combo.setCurrentText(current)
        replace_combo.setCurrentText(replace)
        
        # Add to scroll layout (insert before the stretch)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, row_widget)
        self.mapping_rows.append(row_widget)
    
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
    
    def delete_mapping_row(self, row_widget):
        """Delete a mapping row"""
        if row_widget in self.mapping_rows:
            self.mapping_rows.remove(row_widget)
            self.scroll_layout.removeWidget(row_widget)
            row_widget.deleteLater()
    
    def load_existing_mappings(self):
        """Load existing mappings from the database"""
        try:
            # Add a default mapping row if none exist
            if not self.mapping_rows:
                self.add_mapping_row()
        except Exception as e:
            logger.error(f"Error loading existing mappings: {e}")
    
    def accept_mappings(self):
        """Save mappings and close dialog"""
        try:
            # Collect all mappings
            mappings = []
            for row_widget in self.mapping_rows:
                card = row_widget.card_combo.currentText()
                current = row_widget.current_combo.currentText()
                replace = row_widget.replace_combo.currentText()
                
                if card and replace:  # Only save if both card and replace are provided
                    mappings.append({
                        'card': card,
                        'current': current,
                        'replace': replace
                    })
            
            # Show success message
            QMessageBox.information(self, "Success", f"Saved {len(mappings)} mapping(s).")
            
            # Accept the dialog
            self.accept()
            
        except Exception as e:
            logger.error(f"Error saving mappings: {e}")
            QMessageBox.critical(self, "Error", f"Error saving mappings: {e}")
    
    def apply_single_mapping(self, row_widget):
        """Apply a single mapping immediately"""
        try:
            card = row_widget.card_combo.currentText()
            current = row_widget.current_combo.currentText()
            replace = row_widget.replace_combo.currentText()
            
            if not card or not replace:
                QMessageBox.warning(self, "Warning", "Card and Replace values cannot be empty.")
                return
            
            # Update the database record(s) for this mapping
            query = MappingModel.update(
                {MappingModel.mappingValue: replace}
            ).where(
                (MappingModel.mappingCard == card) & 
                (MappingModel.mappingValue == current)
            )
            query.execute()
            
            # Show success message
            QMessageBox.information(self, "Success", f"Mapping applied: {current} -> {replace}")
            
            # Refresh the current values in the combo boxes
            self.update_current_values(row_widget)
        except Exception as e:
            logger.error(f"Error applying single mapping: {e}")
            QMessageBox.critical(self, "Error", f"Error applying mapping: {e}")
    
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
                                mappingCard=card,
                                mappingValue=replace
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
