import os
import logging
import configparser
import setup_path  # Configure Python path for new package structure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLabel, QPushButton, QLineEdit, QCheckBox, 
                               QTextEdit, QGroupBox, QMessageBox, QProgressDialog, QApplication)
from PySide6.QtGui import QFont
from astropy.io import fits

from astrofiler.models import fitsFile as FitsFileModel, fitsSession as FitsSessionModel

logger = logging.getLogger(__name__)

class MergeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.images_widget = None  # Reference to images widget for refreshing
        self.init_ui()
    
    def set_images_widget(self, images_widget):
        """Set reference to images widget for refreshing after merge operations"""
        self.images_widget = images_widget
    
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

            # Create progress dialog
            total_files = len(files_to_merge)
            progress_dialog = QProgressDialog(f"Initializing merge operation...", "Cancel", 0, total_files + 2, self)
            progress_dialog.setWindowTitle("Merging Objects")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()

            merged_count = 0
            renamed_count = 0
            moved_count = 0
            directories_renamed = 0
            header_updated_count = 0
            errors = []

            result_text = f"MERGE EXECUTION RESULTS:\n\n"
            result_text += f"From: '{from_object}' → To: '{to_object}'\n"
            result_text += f"Change filenames: {'Yes' if change_files else 'No'}\n"
            result_text += f"Total files to process: {total_files}\n\n"
            
            # Update progress
            progress_dialog.setLabelText(f"Processing {total_files} files...")
            progress_dialog.setValue(1)
            QApplication.processEvents()
            
            if progress_dialog.wasCanceled():
                return
            
            # Simple directory handling: Look for $REPO/Light/<OBJECT> pattern
            if change_files:
                progress_dialog.setLabelText("Checking directory structure...")
                QApplication.processEvents()
                
                old_object_dir = os.path.join(repo_folder, 'Light', from_object)
                new_object_dir = os.path.join(repo_folder, 'Light', to_object)
                
                if os.path.exists(old_object_dir):
                    try:
                        if not os.path.exists(new_object_dir):
                            # Simple case: rename directory
                            logger.info(f"Renaming directory: {old_object_dir} -> {new_object_dir}")
                            os.rename(old_object_dir, new_object_dir)
                            directories_renamed += 1
                            logger.info(f"Successfully renamed directory to: {new_object_dir}")
                        else:
                            # Target exists: move all files from old to new directory
                            logger.info(f"Moving files from {old_object_dir} to existing {new_object_dir}")
                            progress_dialog.setLabelText(f"Moving files to existing directory...")
                            QApplication.processEvents()
                            
                            for filename in os.listdir(old_object_dir):
                                old_file = os.path.join(old_object_dir, filename)
                                new_file = os.path.join(new_object_dir, filename)
                                if os.path.isfile(old_file) and not os.path.exists(new_file):
                                    os.rename(old_file, new_file)
                                    logger.info(f"Moved file: {old_file} -> {new_file}")
                            
                            # Remove old directory if empty
                            try:
                                if not os.listdir(old_object_dir):
                                    os.rmdir(old_object_dir)
                                    logger.info(f"Removed empty directory: {old_object_dir}")
                            except OSError:
                                pass  # Directory not empty, leave it
                                
                    except Exception as dir_error:
                        error_msg = f"Error handling directory {old_object_dir}: {str(dir_error)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
            
            for file_index, fits_file in enumerate(files_to_merge):
                # Update progress
                progress_dialog.setLabelText(f"Processing file {file_index + 1} of {total_files}: {os.path.basename(fits_file.fitsFileName or 'Unknown')}")
                progress_dialog.setValue(file_index + 2)  # +2 because we started at 1
                QApplication.processEvents()
                
                if progress_dialog.wasCanceled():
                    QMessageBox.information(self, "Cancelled", "Merge operation was cancelled by user.")
                    return
                
                try:
                    # Update database record
                    fits_file.fitsFileObject = to_object
                    fits_file.save()
                    merged_count += 1
                    
                    # Handle file operations if requested
                    if change_files and fits_file.fitsFileName:
                        old_file_path = fits_file.fitsFileName
                        
                        # Simple path handling - files should now be in the new directory structure
                        original_file_path = fits_file.fitsFileName
                        current_file_path = original_file_path
                        
                        # If the file was in the old object directory, update path to new directory
                        if f"/Light/{from_object}/" in original_file_path.replace('\\', '/'):
                            current_file_path = original_file_path.replace(f"/Light/{from_object}/", f"/Light/{to_object}/").replace(f"\\Light\\{from_object}\\", f"\\Light\\{to_object}\\")
                            logger.debug(f"Updated file path: {original_file_path} -> {current_file_path}")
                        
                        if os.path.exists(current_file_path):
                            try:
                                # Update the FITS header first
                                logger.info(f"Updating FITS header for: {current_file_path}")
                                with fits.open(current_file_path, mode='update') as hdul:
                                    hdul[0].header['OBJECT'] = to_object
                                    hdul[0].header.comments['OBJECT'] = 'Updated via Astrofiler merge'
                                    hdul.flush()
                                header_updated_count += 1
                                logger.info(f"Successfully updated FITS header: OBJECT = '{to_object}'")
                                
                                # Handle filename renaming
                                old_filename = os.path.basename(current_file_path)
                                new_filename = old_filename
                                current_directory = os.path.dirname(current_file_path)
                                
                                # Replace object name in filename
                                if from_object in old_filename:
                                    new_filename = old_filename.replace(from_object, to_object)
                                    logger.info(f"Renaming file: {old_filename} -> {new_filename}")
                                
                                # Try sanitized versions too
                                if new_filename == old_filename:
                                    from_sanitized = from_object.replace(' ', '_').replace('-', '_')
                                    to_sanitized = to_object.replace(' ', '_').replace('-', '_')
                                    if from_sanitized in old_filename:
                                        new_filename = old_filename.replace(from_sanitized, to_sanitized)
                                        logger.info(f"Renaming file (sanitized): {old_filename} -> {new_filename}")
                                
                                # Rename file if needed
                                new_file_path = os.path.join(current_directory, new_filename)
                                if new_file_path != current_file_path:
                                    if not os.path.exists(new_file_path):
                                        logger.info(f"Renaming file: {current_file_path} -> {new_file_path}")
                                        os.rename(current_file_path, new_file_path)
                                        renamed_count += 1
                                        current_file_path = new_file_path
                                        logger.info(f"Successfully renamed file to: {new_file_path}")
                                    else:
                                        logger.warning(f"Cannot rename file, target exists: {new_file_path}")
                                
                                # Update database with final file path
                                if current_file_path != original_file_path:
                                    fits_file.fitsFileName = current_file_path.replace('\\', '/')
                                    fits_file.save()
                                    moved_count += 1
                                    
                            except Exception as file_error:
                                error_msg = f"Error processing file {current_file_path}: {str(file_error)}"
                                errors.append(error_msg)
                                logger.error(error_msg)
                        else:
                            logger.warning(f"File not found: {current_file_path} (original: {original_file_path})")
                    
                    
                except Exception as e:
                    error_msg = f"Error processing {fits_file.fitsFileName}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # Update Sessions that reference the old object name
            progress_dialog.setLabelText("Updating sessions...")
            progress_dialog.setValue(total_files + 2)
            QApplication.processEvents()
            
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
            
            # Clean up empty directories if files were moved
            if change_files and (moved_count > 0 or directories_renamed > 0):
                progress_dialog.setLabelText("Cleaning up empty directories...")
                QApplication.processEvents()
                try:
                    # Look for and remove empty directories that may have been left behind
                    empty_dirs_removed = self.cleanup_empty_directories(repo_folder)
                    if empty_dirs_removed > 0:
                        result_text += f"Empty directories cleaned up: {empty_dirs_removed}\n"
                        logger.info(f"Cleaned up {empty_dirs_removed} empty directories")
                except Exception as cleanup_error:
                    logger.warning(f"Error during directory cleanup: {cleanup_error}")

            # Close progress dialog
            progress_dialog.close()
            
            result_text += f"Database records updated: {merged_count}\n"
            if change_files:
                result_text += f"Files renamed on disk: {renamed_count}\n"
                result_text += f"Files moved to new directory structure: {moved_count}\n"
                result_text += f"Directories renamed: {directories_renamed}\n"
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
            
            # Refresh the Images view to reflect the merge changes
            if self.images_widget and hasattr(self.images_widget, 'load_fits_data'):
                logger.debug("Refreshing Images view after merge operation")
                self.images_widget.load_fits_data()
            
        except Exception as e:
            # Close progress dialog on error
            if 'progress_dialog' in locals():
                progress_dialog.close()
            error_msg = f"Critical error during merge execution: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Merge Error", f"A critical error occurred during merge: {str(e)}")
            self.results_text.setPlainText(f"CRITICAL ERROR: {error_msg}")

    def cleanup_empty_directories(self, repo_folder):
        """Remove empty directories recursively, starting from the deepest level"""
        empty_dirs_removed = 0
        try:
            # Walk through all directories in the repository
            for root, dirs, files in os.walk(repo_folder, topdown=False):
                for directory in dirs:
                    dir_path = os.path.join(root, directory)
                    try:
                        # Try to remove the directory if it's empty
                        if os.path.exists(dir_path) and not os.listdir(dir_path):
                            os.rmdir(dir_path)
                            empty_dirs_removed += 1
                            logger.debug(f"Removed empty directory: {dir_path}")
                    except OSError:
                        # Directory not empty or other error, skip it
                        pass
        except Exception as e:
            logger.error(f"Error during directory cleanup: {e}")
        
        return empty_dirs_removed
