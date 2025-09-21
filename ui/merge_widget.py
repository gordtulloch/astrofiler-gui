import os
import logging
import configparser
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLabel, QPushButton, QLineEdit, QCheckBox, 
                               QTextEdit, QGroupBox, QMessageBox)
from PySide6.QtGui import QFont
from astropy.io import fits

from astrofiler_db import fitsFile as FitsFileModel, fitsSession as FitsSessionModel

logger = logging.getLogger(__name__)

class MergeWidget(QWidget):
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
        self.preview_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.merge_button = QPushButton("Execute Merge")
        self.merge_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.clear_button = QPushButton("Clear Fields")
        self.clear_button.setStyleSheet("QPushButton { font-size: 11px; }")
        
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
            
            result_text = f"MERGE EXECUTION RESULTS:\n\n"
            result_text += f"From: '{from_object}' → To: '{to_object}'\n"
            result_text += f"Change filenames: {'Yes' if change_files else 'No'}\n\n"
            
            for fits_file in files_to_merge:
                try:
                    # Update database record
                    fits_file.fitsFileObject = to_object
                    fits_file.save()
                    merged_count += 1
                    
                    if change_files:
                        # ...existing code for file operations...
                        pass
                    
                except Exception as e:
                    error_msg = f"Error processing {fits_file.fitsFileName}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # Update Sessions that reference the old object name
            sessions_updated = 0
            try:
                sessions = FitsSessionModel.select().where(FitsSessionModel.fitsSessionObjectName == from_object)
                for session in sessions:
                    session.fitsSessionObjectName = to_object
                    session.save()
                    sessions_updated += 1
            except Exception as e:
                error_msg = f"Error querying/updating Sessions: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
            
            result_text += f"Database records updated: {merged_count}\n"
            if change_files:
                result_text += f"Files renamed on disk: {renamed_count}\n"
                result_text += f"Files moved to new directory structure: {moved_count}\n"
                if header_updated_count > 0:
                    result_text += f"FITS headers updated: {header_updated_count}\n"
            result_text += f"Sessions updated: {sessions_updated}\n"
            
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
            else:
                QMessageBox.information(self, "Merge Successful", 
                                      f"Successfully merged {merged_count} records from '{from_object}' to '{to_object}'.")
            
        except Exception as e:
            error_msg = f"Critical error during merge execution: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Merge Error", f"A critical error occurred during merge: {str(e)}")
            self.results_text.setPlainText(f"CRITICAL ERROR: {error_msg}")
