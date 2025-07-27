import sys
from PySide6.QtWidgets import QApplication
from astrofiler_gui import AstroFilerGUI
from astrofiler_db import setup_database
import logging


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='astrofiler.log',
    filemode='a'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting AstroFiler application")
    if (setup_database()):  # Initialize the database and table
        app = QApplication(sys.argv)
        widget = AstroFilerGUI()
        widget.show()
        sys.exit(app.exec())
    logger.info("AstroFiler application closed")