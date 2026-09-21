"""AstroFiler GUI entry point.

Kept intentionally lightweight so we can show a splash screen quickly while
heavier modules import and initialization proceeds.

Used by the ``astrofiler`` / ``astrofiler-gui`` console scripts and by the
root ``astrofiler.py`` launcher.
"""

import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from astrofiler.paths import get_log_path, resource_path

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent


def rotate_log_file() -> None:
    """Rotate log file if it's larger than 5MB"""
    log_file = str(get_log_path())
    max_size = 5 * 1024 * 1024  # 5 MB in bytes

    try:
        if os.path.exists(log_file):
            file_size = os.path.getsize(log_file)
            if file_size > max_size:
                # Create backup filename with current date
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = str(get_log_path().with_name(f'astrofiler_{timestamp}.log'))

                # Rename current log to backup
                os.rename(log_file, backup_file)
                print(f"Log file rotated: {log_file} -> {backup_file} (size: {file_size:,} bytes)")

    except Exception as e:
        print(f"Error rotating log file: {e}")


def _configure_logging() -> None:
    # Rotate log file if needed before setting up logging
    rotate_log_file()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=str(get_log_path()),
        filemode='a'
    )

    # Reduce verbosity of some logging
    logging.getLogger('SMB').setLevel(logging.WARNING)
    logging.getLogger('SMB.SMBConnection').setLevel(logging.WARNING)
    logging.getLogger('SMB.SMBProtocol').setLevel(logging.WARNING)


def _read_version() -> str:
    """Read AstroFiler version without importing the full package."""
    init_path = _PACKAGE_DIR / '__init__.py'
    try:
        content = init_path.read_text(encoding='utf-8')
        match = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "(unknown)"


def _find_logo() -> str:
    """Path to the splash logo bundled with the package."""
    return str(resource_path('astrofiler.png'))


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

    pixmap = _create_splash_pixmap(_find_logo(), _read_version())
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


def main() -> int:
    """Launch the AstroFiler GUI. Returns the process exit code."""
    _configure_logging()

    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QCoreApplication
        from astrofiler.exceptions import DatabaseError

        app = QApplication(sys.argv)
        QCoreApplication.setOrganizationName("AstroFiler")
        QCoreApplication.setApplicationName("AstroFiler")
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

        return app.exec()

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
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "Database Error", str(e))
        except Exception:
            pass  # GUI might not be available

        return 1

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        print("\nApplication interrupted by user")
        return 0

    except Exception as e:
        # Unexpected errors - show traceback for debugging
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
