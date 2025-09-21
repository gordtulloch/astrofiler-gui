import os
import logging
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTreeWidget, QTreeWidgetItem,
                               QProgressDialog, QApplication, QMessageBox)
from PySide6.QtGui import QFont

from astrofiler_db import fitsFile as FitsFileModel

logger = logging.getLogger(__name__)

class DuplicatesWidget(QWidget):
    """Widget for managing duplicate FITS files"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        # Do not run duplicate detection on startup - user can manually refresh
    
    def init_ui(self):
        """Initialize the duplicates widget UI"""
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
        refresh_button.setStyleSheet("QPushButton { font-size: 11px; }")
        refresh_button.clicked.connect(self.refresh_duplicates)
        layout.addWidget(refresh_button)
        
        # Duplicates tree widget
        self.duplicates_tree = QTreeWidget()
        self.duplicates_tree.setHeaderLabels(["File", "Object", "Date", "Filter", "Exposure", "Type", "Full Path"])
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
        self.duplicates_tree.clear()
        duplicate_groups = []
        progress_dialog = None
        was_cancelled = False
        
        try:
            # Query for files with duplicate hashes
            query = """
            SELECT fitsFileHash, COUNT(*) as count
            FROM fitsfile 
            WHERE fitsFileHash IS NOT NULL 
            GROUP BY fitsFileHash 
            HAVING COUNT(*) > 1
            """
            conn = sqlite3.connect('astrofiler.db')
            cursor = conn.cursor()
            cursor.execute(query)
            duplicate_hashes = cursor.fetchall()
            conn.close()
            
            # Only show progress dialog if we have duplicates to process
            if duplicate_hashes:
                progress_dialog = QProgressDialog("Scanning for duplicate files...", "Cancel", 0, len(duplicate_hashes), self)
                progress_dialog.setWindowTitle("Finding Duplicates")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.show()
            
            total_duplicates = 0
            
            for i, (hash_value, count) in enumerate(duplicate_hashes):
                if progress_dialog and progress_dialog.wasCanceled():
                    was_cancelled = True
                    break
                
                if progress_dialog:
                    progress_dialog.setValue(i)
                    progress_dialog.setLabelText(f"Processing duplicate group {i+1} of {len(duplicate_hashes)}")
                    QApplication.processEvents()
                
                # Get all files with this hash
                duplicate_files = FitsFileModel.select().where(FitsFileModel.fitsFileHash == hash_value)
                
                # Create parent item for this duplicate group
                parent_item = QTreeWidgetItem()
                parent_item.setText(0, f"Duplicate Group - {count} files")
                parent_item.setText(1, "")
                parent_item.setText(2, "")
                parent_item.setText(3, "")
                parent_item.setText(4, "")
                parent_item.setText(5, "")
                parent_item.setText(6, f"Hash: {hash_value}")
                
                # Make parent item bold
                font = parent_item.font(0)
                font.setBold(True)
                for col in range(7):
                    parent_item.setFont(col, font)
                
                # Add child items for each duplicate file
                for fits_file in duplicate_files:
                    child_item = QTreeWidgetItem()
                    child_item.setText(0, os.path.basename(fits_file.fitsFileName) if fits_file.fitsFileName else "Unknown")
                    child_item.setText(1, fits_file.fitsFileObject or "")
                    child_item.setText(2, str(fits_file.fitsFileDate)[:10] if fits_file.fitsFileDate else "")
                    child_item.setText(3, fits_file.fitsFileFilter or "")
                    child_item.setText(4, str(fits_file.fitsFileExpTime) if fits_file.fitsFileExpTime else "")
                    child_item.setText(5, fits_file.fitsFileType or "")
                    child_item.setText(6, fits_file.fitsFileName or "")
                    parent_item.addChild(child_item)
                
                self.duplicates_tree.addTopLevelItem(parent_item)
                parent_item.setExpanded(True)
                total_duplicates += count
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Update info label and button state
            if was_cancelled:
                self.info_label.setText("Duplicate scan cancelled.")
                self.delete_button.setEnabled(False)
            elif duplicate_groups or duplicate_hashes:
                self.info_label.setText(f"Found {len(duplicate_hashes)} duplicate groups with {total_duplicates} total files.")
                self.delete_button.setEnabled(True)
            else:
                self.info_label.setText("No duplicates found.")
                self.delete_button.setEnabled(False)
                
        except Exception as e:
            logging.error(f"Error refreshing duplicates: {str(e)}")
            if progress_dialog:
                progress_dialog.close()
            self.info_label.setText(f"Error loading duplicates: {str(e)}")
            self.delete_button.setEnabled(False)
    
    def delete_duplicates(self):
        """Delete duplicate files, keeping only one copy of each"""
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
        progress_dialog = None
        was_cancelled = False
        
        try:
            # Get all duplicate groups
            query = """
            SELECT fitsFileHash
            FROM fitsfile 
            WHERE fitsFileHash IS NOT NULL 
            GROUP BY fitsFileHash 
            HAVING COUNT(*) > 1
            """
            conn = sqlite3.connect('astrofiler.db')
            cursor = conn.cursor()
            cursor.execute(query)
            duplicate_hashes = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            # Only show progress dialog if we have duplicates to delete
            if duplicate_hashes:
                progress_dialog = QProgressDialog("Deleting duplicate files...", "Cancel", 0, len(duplicate_hashes), self)
                progress_dialog.setWindowTitle("Deleting Duplicates")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.show()
            
            for i, hash_value in enumerate(duplicate_hashes):
                if progress_dialog and progress_dialog.wasCanceled():
                    was_cancelled = True
                    break
                
                if progress_dialog:
                    progress_dialog.setValue(i)
                    progress_dialog.setLabelText(f"Processing duplicate group {i+1} of {len(duplicate_hashes)}")
                    QApplication.processEvents()
                
                # Get all files with this hash, ordered by ID (keep the first one)
                duplicate_files = list(FitsFileModel.select().where(FitsFileModel.fitsFileHash == hash_value).order_by(FitsFileModel.fitsFileId))
                
                # Skip the first file (keep it), delete the rest
                for fits_file in duplicate_files[1:]:
                    try:
                        # Delete physical file if it exists
                        if fits_file.fitsFileName and os.path.exists(fits_file.fitsFileName):
                            os.remove(fits_file.fitsFileName)
                        
                        # Delete from database
                        fits_file.delete_instance()
                        deleted_count += 1
                        
                    except Exception as e:
                        logging.error(f"Error deleting duplicate file {fits_file.fitsFileName}: {str(e)}")
                        error_count += 1
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close()
            
            # Show results
            if was_cancelled:
                QMessageBox.information(self, "Cancelled", f"Deletion cancelled. {deleted_count} files were deleted before cancellation.")
            elif error_count == 0:
                QMessageBox.information(self, "Success", f"Successfully deleted {deleted_count} duplicate files.")
            else:
                QMessageBox.warning(self, "Completed with Errors", f"Deleted {deleted_count} files with {error_count} errors. Check log for details.")
            
            # Refresh the display
            self.refresh_duplicates()
            
        except Exception as e:
            logging.error(f"Error during duplicate deletion: {str(e)}")
            if progress_dialog:
                progress_dialog.close()
            QMessageBox.critical(
                self, 
                "Deletion Error", 
                f"An error occurred during deletion: {str(e)}"
            )
