# Configure Python path for new package structure - must be before any astrofiler imports
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')

# Ensure src path is first in path to avoid conflicts with root astrofiler.py
if src_path in sys.path:
    sys.path.remove(src_path)
sys.path.insert(0, src_path)

from datetime import datetime
from PySide6.QtWidgets import QApplication
from astrofiler.ui.main_window import AstroFilerGUI
from astrofiler.database import setup_database
import logging

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

if __name__ == "__main__":
    if (setup_database() == True):  # Initialize the database and table
        app = QApplication(sys.argv)
        
        # Create and show main widget
        widget = AstroFilerGUI()
        
        # Show main window
        widget.show()
        widget.center_on_screen()  # Ensure the main window is centered
        
        sys.exit(app.exec())
        return_code = 0
    else:   
        logger.error("Failed to set up the database. Exiting application.")
        return_code = 1
    logger.info("AstroFiler application exited with return code: %d", return_code)
    sys.exit(return_code)
