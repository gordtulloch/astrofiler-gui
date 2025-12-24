"""AstroFiler GUI launcher.

This entrypoint is kept intentionally lightweight so we can show a splash screen
quickly while heavier modules import and initialization proceeds.
"""

# Configure Python path for new package structure - must be before any astrofiler imports
import sys
import os
import re
import logging
from datetime import datetime

project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')

# Ensure src path is first in path to avoid conflicts with root astrofiler.py
if src_path in sys.path:
    sys.path.remove(src_path)
sys.path.insert(0, src_path)

def rotate_log_file():
    """Rotate log file if it's larger than 5MB"""
    log_file = 'astrofiler.log'
    max_size = 5 * 1024 * 1024  # 5 MB in bytes
    
    try:
        if os.path.exists(log_file):
            file_size = os.path.getsize(log_file)
            if file_size > max_size:
                # Create backup filename with current date
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = f'astrofiler_{timestamp}.log'
                
                # Rename current log to backup
                os.rename(log_file, backup_file)
                print(f"Log file rotated: {log_file} -> {backup_file} (size: {file_size:,} bytes)")
                
    except Exception as e:
        print(f"Error rotating log file: {e}")

# Rotate log file if needed before setting up logging
rotate_log_file()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='astrofiler.log',
    filemode='a'
)

# Reduce verbosity of some logging
logging.getLogger('SMB').setLevel(logging.WARNING)
logging.getLogger('SMB.SMBConnection').setLevel(logging.WARNING)
logging.getLogger('SMB.SMBProtocol').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _read_version() -> str:
    """Read AstroFiler version without importing the full package."""
    init_path = os.path.join(project_root, 'src', 'astrofiler', '__init__.py')
    try:
        with open(init_path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "(unknown)"


def _create_splash_pixmap(logo_path: str, version: str):
    """Create a pixmap with logo + static splash text baked in."""
    from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
    from PySide6.QtCore import Qt, QRect, QRectF

    logo = QPixmap(logo_path) if os.path.exists(logo_path) else QPixmap()

    # Sensible fallback size if logo missing
    if logo.isNull():
        width, height = 520, 280
    else:
        # Add extra vertical space for the static text area
        width = max(logo.width(), 520)
        height = max(logo.height(), 220) + 90

    canvas = QPixmap(width, height)
    # Use transparent background so rounded corners are actually visible.
    canvas.fill(Qt.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing, True)

    # Rounded container + border
    radius = 18.0
    border_color = QColor(170, 170, 170)
    fill_color = QColor(255, 255, 255)
    border_pen = QPen(border_color)
    border_pen.setWidth(2)

    # Inset so the border doesn't get clipped
    container = QRectF(1.0, 1.0, float(width) - 2.0, float(height) - 2.0)
    painter.setPen(border_pen)
    painter.setBrush(fill_color)
    painter.drawRoundedRect(container, radius, radius)

    # Draw logo centered
    if not logo.isNull():
        target_w = min(logo.width(), width)
        # Keep aspect ratio and avoid making it huge
        scaled = logo.scaled(target_w, height - 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (width - scaled.width()) // 2
        painter.drawPixmap(x, 10, scaled)

    # Static text
    text = (
        f"Astrofiler {version}\n"
        "Free Open Source Software\n"
        "Copyright (C) 2025 by Gord Tulloch\n"
        "ALL RIGHTS RESERVED"
    )
    text_rect = QRect(10, height - 95, width - 20, 85)
    painter.setPen(QColor(0, 0, 0))
    painter.drawText(text_rect, Qt.AlignCenter, text)
    painter.end()

    return canvas


def _show_splash(app):
    """Show splash screen early and return (splash, update_fn)."""
    from PySide6.QtWidgets import QSplashScreen
    from PySide6.QtGui import QColor
    from PySide6.QtCore import Qt

    version = _read_version()
    logo_path = os.path.join(project_root, 'astrofiler.png')
    pixmap = _create_splash_pixmap(logo_path, version)
    splash = QSplashScreen(pixmap)

    # Frameless + translucent so rounded corners/border render cleanly.
    splash.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    splash.setAttribute(Qt.WA_TranslucentBackground, True)

    splash.show()
    app.processEvents()

    def update(message: str):
        # Status line (kept separate from the static text baked into the pixmap)
        splash.showMessage(
            message,
            Qt.AlignBottom | Qt.AlignHCenter,
            QColor(0, 0, 0)
        )
        app.processEvents()

    update("Starting...")
    return splash, update

if __name__ == "__main__":
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from astrofiler.exceptions import DatabaseError

        app = QApplication(sys.argv)
        splash, splash_update = _show_splash(app)

        splash_update("Importing database layer...")
        from astrofiler.database import setup_database

        splash_update("Running database migrations...")
        setup_database()  # Initialize the database and tables

        splash_update("Importing UI shell...")
        from astrofiler.ui.main_window import AstroFilerGUI

        splash_update("Constructing main window...")
        widget = AstroFilerGUI(status_callback=splash_update)

        splash_update("Showing main window...")
        widget.show()
        widget.center_on_screen()
        splash.finish(widget)

        sys.exit(app.exec())
        
    except DatabaseError as e:
        # Handle database errors gracefully without traceback
        logger.error(f"Database error: {e}")
        print(f"\n{'='*70}")
        print("DATABASE ERROR")
        print(f"{'='*70}")
        print(f"\n{e}\n")
        print(f"{'='*70}\n")
        
        # Try to show GUI error dialog if possible
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(None, "Database Error", str(e))
        except:
            pass  # GUI might not be available
        
        sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        print("\nApplication interrupted by user")
        sys.exit(0)
        
    except Exception as e:
        # Unexpected errors - show traceback for debugging
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
