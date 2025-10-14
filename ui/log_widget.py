import os
import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTextEdit, QMessageBox)
from PySide6.QtGui import QFont, QTextCursor

logger = logging.getLogger(__name__)

class LogWidget(QWidget):
    """Widget for displaying and managing log files"""
    
    def __init__(self):
        super().__init__()
        self.log_file_path = "astrofiler.log"
        self.init_ui()
        self.load_log_content()
    
    def init_ui(self):
        """Initialize the log widget UI"""
        layout = QVBoxLayout(self)
        
        # Controls layout with Clear button
        controls_layout = QHBoxLayout()
        self.clear_button = QPushButton("Clear")
        self.clear_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.clear_button.clicked.connect(self.clear_log)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.refresh_button.clicked.connect(self.load_log_content)
        
        controls_layout.addWidget(self.clear_button)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addStretch()  # Push buttons to the left
        
        # Log display area with horizontal and vertical scrolling
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)  # Enable horizontal scrolling
        self.log_text.setFont(QFont("Courier", 9))  # Monospace font for logs
        
        layout.addLayout(controls_layout)
        layout.addWidget(self.log_text)
    
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
    
    def clear_log(self):
        """Clear the log file by deleting it and creating an empty file"""
        try:
            if os.path.exists(self.log_file_path):
                os.remove(self.log_file_path)
            
            # Create an empty log file
            with open(self.log_file_path, 'w', encoding='utf-8') as file:
                pass
            
            # Clear the display
            self.log_text.clear()
            
            # Log this action (this will recreate the log file with the first entry)
            logger.info("Log file cleared by user")
            
            # Reload to show the new log entry
            self.load_log_content()
            
            QMessageBox.information(self, "Success", "Log file cleared successfully!")
            
        except Exception as e:
            logger.error(f"Error clearing log file: {e}")
            QMessageBox.warning(self, "Error", f"Failed to clear log file: {str(e)}")
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    border: 2px solid #555555;
                    border-radius: 5px;
                    color: #ffffff;
                }
                QMessageBox QLabel {
                    border: none;
                    background-color: transparent;
                    color: #ffffff;
                }
                QMessageBox QPushButton {
                    border: 1px solid #666666;
                    background-color: #404040;
                    color: #ffffff;
                    padding: 6px 12px;
                    border-radius: 3px;
                }
            """)
            msg_box.exec()
            
        except Exception as e:
            logger.error(f"Error clearing log file: {e}")
            # Apply same styling to error dialog
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Failed to clear log file: {str(e)}")
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    border: 2px solid #555555;
                    border-radius: 5px;
                    color: #ffffff;
                }
                QMessageBox QLabel {
                    border: none;
                    background-color: transparent;
                    color: #ffffff;
                }
                QMessageBox QPushButton {
                    border: 1px solid #666666;
                    background-color: #404040;
                    color: #ffffff;
                    padding: 6px 12px;
                    border-radius: 3px;
                }
            """)
            msg_box.exec()
