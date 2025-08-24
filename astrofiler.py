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

# Reduce verbosity of some logging
#logging.getLogger('SMB').setLevel(logging.WARNING)
#logging.getLogger('SMB.SMBConnection').setLevel(logging.WARNING)
#logging.getLogger('SMB.SMBProtocol').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting AstroFiler application")
    if (setup_database() == True):  # Initialize the database and table
        app = QApplication(sys.argv)
        
        # Create and show main widget
        logger.info("Creating main widget")
        widget = AstroFilerGUI()
        logger.info("Main widget created")
        
        # Show main window
        logger.info("Showing main window")
        widget.show()
        widget.center_on_screen()  # Ensure the main window is centered
        
        sys.exit(app.exec())
        return_code = 0
    else:   
        logger.error("Failed to set up the database. Exiting application.")
        return_code = 1
    logger.info("AstroFiler application exited with return code: %d", return_code)
    sys.exit(return_code)
