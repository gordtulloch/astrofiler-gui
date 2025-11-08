import os
import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QFont, QPixmap

logger = logging.getLogger(__name__)

# Version should be imported from main_window or defined here
VERSION = "1.1.2"

class AboutWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a container widget that will hold both background and text
        self.container = QWidget()
        self.container.setMinimumSize(800, 600)
        
        # Create background label
        self.background_label = QLabel(self.container)
        self.background_label.setAlignment(Qt.AlignCenter)
        self.background_label.setGeometry(0, 0, 800, 600)
        
        # Create text overlay widget with transparent background
        self.text_widget = QWidget(self.container)
        self.text_widget.setStyleSheet("background-color: transparent;")
        text_layout = QVBoxLayout(self.text_widget)
        text_layout.setAlignment(Qt.AlignCenter)
        
        # Main title
        self.title_label = QLabel(f"AstroFiler Version {VERSION}")
        title_font = QFont()
        title_font.setPointSize(32)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 120);
                padding: 20px;
                border-radius: 10px;
                margin: 10px;
            }
        """)
        
        # Subtitle
        self.subtitle_label = QLabel("By Gord Tulloch\nJuly 2025\n\nQuestions to:\nEmail: gord.tulloch@gmail.com\nGithub: https://github.com/gordtulloch/astrofiler-gui\n\nContributions gratefully accepted via\nPaypal to the above email address.")
        subtitle_font = QFont()
        subtitle_font.setPointSize(16)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 120);
                padding: 15px;
                border-radius: 10px;
                margin: 10px;
            }
        """)
        
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)
        
        layout.addWidget(self.container)
        
        # Set default background first
        self.set_default_background()
        
        # Then try to load the actual background image
        self.load_background_image()
    
    def load_background_image(self):
        """Load the background image from local images/background.jpg file"""
        try:
            # Try to load the image from the images directory
            pixmap = QPixmap("images/background.jpg")
            
            if not pixmap.isNull():
                # Get the size of the container
                container_size = self.container.size()
                if container_size.width() <= 0:
                    container_size = self.container.sizeHint()
                
                # Scale the image to fit the container while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    container_size, 
                    Qt.KeepAspectRatioByExpanding, 
                    Qt.SmoothTransformation
                )
                
                self.background_label.setPixmap(scaled_pixmap)
                self.background_label.setScaledContents(True)
                logger.debug("Successfully loaded images/background.jpg as background")
            else:
                # If image loading fails, use the default background
                logger.warning("Failed to load images/background.jpg, using default background")
                self.set_default_background()
        except Exception as e:
            logger.error(f"Error loading background image: {e}")
            self.set_default_background()
    
    def set_default_background(self):
        """Set a default starry background if image download fails"""
        self.background_label.setStyleSheet("""
            QLabel {
                background: qradialgradient(cx:0.5, cy:0.5, radius:1.0,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1.0 #0f0f23);
            }
        """)
    
    def resizeEvent(self, event):
        """Handle resize events to reposition text overlay and reload background"""
        super().resizeEvent(event)
        if hasattr(self, 'container') and hasattr(self, 'background_label') and hasattr(self, 'text_widget'):
            # Resize container and its children
            container_size = self.container.size()
            self.background_label.resize(container_size)
            self.text_widget.resize(container_size)
            # Reload the background image with new size
            self.load_background_image()
    
    def showEvent(self, event):
        """Handle show events to ensure background loads when widget is visible"""
        super().showEvent(event)
        # Load background when widget becomes visible and ensure text positioning
        if hasattr(self, 'container') and hasattr(self, 'background_label') and hasattr(self, 'text_widget'):
            container_size = self.container.size()
            self.background_label.resize(container_size)
            self.text_widget.resize(container_size)
        self.load_background_image()
