import os
import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QMainWindow, 
                               QStackedWidget, QStatusBar, QMessageBox)
from PySide6.QtGui import QAction

from .images_widget import ImagesWidget
from .sessions_widget import SessionsWidget
from .merge_widget import MergeWidget
from .stats_widget import StatsWidget
from .config_widget import ConfigWidget
from .duplicates_widget import DuplicatesWidget
from .log_widget import LogWidget
from .about_widget import AboutWidget
from .download_dialog import SmartTelescopeDownloadDialog

logger = logging.getLogger(__name__)

# Global version variable
VERSION = "1.1.2"

def load_stylesheet(filename):
    """Load stylesheet from a file"""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            logger.debug(f"Successfully loaded stylesheet: {filename}")
            return file.read()
    except FileNotFoundError:
        logger.warning(f"Stylesheet file '{filename}' not found. Using fallback styles.")
        return ""
    except Exception as e:
        logger.error(f"Error loading stylesheet '{filename}': {e}")
        return ""

def get_dark_stylesheet():
    """Return a dark theme stylesheet for the application"""
    return load_stylesheet("css/dark.css")

def get_light_stylesheet():
    """Return a light theme stylesheet for the application"""
    return load_stylesheet("css/light.css")

def detect_system_theme():
    """Detect if the system is using dark theme"""
    try:
        if os.name == 'nt':  # Windows
            import winreg  # Import only when on Windows
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0  # 0 means dark theme, 1 means light theme
        else:
            # For other systems, default to light theme
            return False
    except:
        return False

class AstroFilerGUI(QMainWindow):
    """Main GUI class that encapsulates the entire AstroFiler application interface"""
    
    def __init__(self):
        super().__init__()
        self.current_theme = "Dark"
        self.init_ui()
        self.apply_initial_theme()
    
    def init_ui(self):
        """Initialize the user interface"""
        # Set window properties
        self.setWindowTitle("AstroFiler - Astronomy File Management Tool")
        self.resize(1200, 800)
        
        # Center the window on the screen
        self.center_on_screen()
        
        # Create central widget with stacked layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create stacked widget to hold the different views
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # Create the different view widgets
        self.images_widget = ImagesWidget()
        self.sessions_widget = SessionsWidget()
        self.merge_widget = MergeWidget()
        self.stats_widget = StatsWidget()
        self.config_widget = ConfigWidget()
        self.duplicates_widget = DuplicatesWidget()
        self.log_widget = LogWidget()
        self.about_widget = AboutWidget()
        
        # Add views to stacked widget
        self.stacked_widget.addWidget(self.images_widget)      # Index 0 - Default view
        self.stacked_widget.addWidget(self.sessions_widget)    # Index 1
        self.stacked_widget.addWidget(self.merge_widget)       # Index 2
        self.stacked_widget.addWidget(self.stats_widget)       # Index 3
        self.stacked_widget.addWidget(self.duplicates_widget)  # Index 4
        self.stacked_widget.addWidget(self.log_widget)         # Index 5
        self.stacked_widget.addWidget(self.config_widget)      # Index 6
        self.stacked_widget.addWidget(self.about_widget)       # Index 7
        
        # Set default view to Images
        self.stacked_widget.setCurrentIndex(0)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Images View")

    def create_menu_bar(self):
        """Create the menu bar with pulldown menus"""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu('&File')
        file_menu.addAction('E&xit', self.close, 'Ctrl+Q')
        
        # View Menu (main navigation)
        view_menu = menubar.addMenu('&View')
        
        # Images view (default)
        images_action = view_menu.addAction('&Images')
        images_action.setShortcut('Ctrl+1')
        images_action.triggered.connect(lambda: self.switch_view(0))
        
        # Sessions view
        sessions_action = view_menu.addAction('&Sessions')
        sessions_action.setShortcut('Ctrl+2')
        sessions_action.triggered.connect(lambda: self.switch_view(1))
        
        # Statistics view
        stats_action = view_menu.addAction('&Statistics')
        stats_action.setShortcut('Ctrl+4')
        stats_action.triggered.connect(lambda: self.switch_view(3))
        
        # Log view
        log_action = view_menu.addAction('&Log')
        log_action.setShortcut('Ctrl+6')
        log_action.triggered.connect(lambda: self.switch_view(5))
        
        view_menu.addSeparator()
        
        # Refresh action
        refresh_action = view_menu.addAction('&Refresh Current View')
        refresh_action.setShortcut('F5')
        refresh_action.triggered.connect(self.refresh_current_view)
        
        # Tools Menu
        tools_menu = menubar.addMenu('&Tools')
        
        # Field Mappings
        mappings_action = tools_menu.addAction('Field &Mappings...')
        mappings_action.setShortcut('Ctrl+M')
        mappings_action.triggered.connect(self.open_mappings_dialog)
        
        tools_menu.addSeparator()
        
        # Merge view
        merge_action = tools_menu.addAction('&Merge Objects...')
        merge_action.setShortcut('Ctrl+3')
        merge_action.triggered.connect(lambda: self.switch_view(2))
        
        # Duplicates view
        duplicates_action = tools_menu.addAction('&Duplicates...')
        duplicates_action.setShortcut('Ctrl+5')
        duplicates_action.triggered.connect(lambda: self.switch_view(4))
        
        tools_menu.addSeparator()
        
        # Configuration
        config_action = tools_menu.addAction('&Configuration...')
        config_action.setShortcut('Ctrl+,')
        config_action.triggered.connect(lambda: self.switch_view(6))
        
        # Help Menu
        help_menu = menubar.addMenu('&Help')
        
        about_action = help_menu.addAction('&About AstroFiler')
        about_action.triggered.connect(lambda: self.switch_view(7))

    def switch_view(self, index):
        """Switch to the specified view"""
        self.stacked_widget.setCurrentIndex(index)
        
        # Update status bar to show current view
        view_names = ['Images', 'Sessions', 'Merge', 'Statistics', 'Duplicates', 'Log', 'Configuration', 'About']
        self.status_bar.showMessage(f"Current View: {view_names[index]}")
        
        # Update window title to include current view
        self.setWindowTitle(f"AstroFiler - {view_names[index]}")

    def refresh_current_view(self):
        """Refresh the currently active view"""
        current_index = self.stacked_widget.currentIndex()
        current_widget = self.stacked_widget.currentWidget()
        
        # Call refresh method based on current view
        if current_index == 0:  # Images
            if hasattr(current_widget, 'load_fits_data'):
                current_widget.load_fits_data()
        elif current_index == 1:  # Sessions
            if hasattr(current_widget, 'load_sessions_data'):
                current_widget.load_sessions_data()
        elif current_index == 3:  # Stats
            if hasattr(current_widget, 'load_stats_data'):
                current_widget.load_stats_data()
        elif current_index == 4:  # Duplicates
            if hasattr(current_widget, 'refresh_duplicates'):
                current_widget.refresh_duplicates()
        elif current_index == 5:  # Log
            if hasattr(current_widget, 'load_log_content'):
                current_widget.load_log_content()

    def refresh_stats(self):
        """Refresh statistics by forcing a cache refresh"""
        if hasattr(self.stats_widget, 'force_refresh_stats'):
            self.stats_widget.force_refresh_stats()

    def open_download_dialog(self):
        """Open the telescope download dialog"""
        try:
            dialog = SmartTelescopeDownloadDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open download dialog: {e}")

    def open_mappings_dialog(self):
        """Open the field mappings dialog"""
        try:
            if hasattr(self.images_widget, 'open_mappings_dialog'):
                self.images_widget.open_mappings_dialog()
            else:
                QMessageBox.information(self, "Info", "Mappings dialog will be implemented in the images widget.")
        except Exception as e:
            logger.error(f"Error in open_mappings_dialog: {e}")
            QMessageBox.warning(self, "Error", f"Could not open mappings dialog: {e}")

    def load_repo(self):
        """Load repository via Images widget"""
        try:
            if hasattr(self.images_widget, 'load_repo'):
                self.images_widget.load_repo()
            else:
                QMessageBox.information(self, "Info", "Load repository function will be implemented in the images widget.")
        except Exception as e:
            logger.error(f"Error in load_repo: {e}")
            QMessageBox.warning(self, "Error", f"Could not load repository: {e}")

    def sync_repo(self):
        """Sync repository via Images widget"""
        try:
            if hasattr(self.images_widget, 'sync_repo'):
                self.images_widget.sync_repo()
            else:
                QMessageBox.information(self, "Info", "Sync repository function will be implemented in the images widget.")
        except Exception as e:
            logger.error(f"Error in sync_repo: {e}")
            QMessageBox.warning(self, "Error", f"Could not sync repository: {e}")

    def download_repo(self):
        """Download repository via Images widget - REMOVED"""
        pass  # Method kept for compatibility but functionality removed

    def clear_repo(self):
        """Clear repository via Images widget"""
        try:
            if hasattr(self.images_widget, 'clear_files'):
                self.images_widget.clear_files()
            else:
                QMessageBox.information(self, "Info", "Clear repository function will be implemented in the images widget.")
        except Exception as e:
            logger.error(f"Error in clear_repo: {e}")
            QMessageBox.warning(self, "Error", f"Could not clear repository: {e}")

    def invalidate_stats_cache(self):
        """Helper method to invalidate stats cache from any widget"""
        if hasattr(self, 'stats_widget'):
            self.stats_widget.invalidate_stats_cache()
    
    def center_on_screen(self):
        """Center the main window on the screen"""
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        center_point = screen.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())
    
    def apply_initial_theme(self):
        """Apply dark theme as default"""
        app = QApplication.instance()
        app.setStyleSheet(get_dark_stylesheet())
        self.current_theme = "Dark"
        if hasattr(self, 'config_widget'):
            self.config_widget.theme.setCurrentText("Dark")

    def showEvent(self, event):
        """Handle show events to reload data when window regains focus"""
        super().showEvent(event)
        # Load images data by default since that's the default view
        if hasattr(self.images_widget, 'load_fits_data'):
            self.images_widget.load_fits_data()
        super().showEvent(event)
        # Load images data by default since that's the default view
        if hasattr(self.images_widget, 'load_fits_data'):
            self.images_widget.load_fits_data()
            self.images_widget.load_fits_data()
        app = QApplication.instance()
        app.setStyleSheet(get_dark_stylesheet())
        self.current_theme = "Dark"
        if hasattr(self, 'config_widget'):
            self.config_widget.theme.setCurrentText("Dark")
            self.images_widget.load_fits_data()
        app = QApplication.instance()
        app.setStyleSheet(get_dark_stylesheet())
        self.current_theme = "Dark"
        if hasattr(self, 'config_widget'):
            self.config_widget.theme.setCurrentText("Dark")
        if hasattr(self.images_widget, 'load_fits_data'):
            self.images_widget.load_fits_data()
        app = QApplication.instance()
        app.setStyleSheet(get_dark_stylesheet())
        self.current_theme = "Dark"
        if hasattr(self, 'config_widget'):
            self.config_widget.theme.setCurrentText("Dark")
            self.images_widget.load_fits_data()
        app = QApplication.instance()
        app.setStyleSheet(get_dark_stylesheet())
        self.current_theme = "Dark"
        if hasattr(self, 'config_widget'):
            self.config_widget.theme.setCurrentText("Dark")
        app = QApplication.instance()
        app.setStyleSheet(get_dark_stylesheet())
        self.current_theme = "Dark"
        if hasattr(self, 'config_widget'):
            self.config_widget.theme.setCurrentText("Dark")
        if hasattr(self, 'config_widget'):
            self.config_widget.theme.setCurrentText("Dark")
        app = QApplication.instance()
        app.setStyleSheet(get_dark_stylesheet())
        self.current_theme = "Dark"
        if hasattr(self, 'config_widget'):
            self.config_widget.theme.setCurrentText("Dark")
