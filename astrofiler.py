import sys
from PySide6.QtWidgets import QApplication
from astrofiler_gui import AstroFilerGUI
from astrofiler_db import setup_database

if __name__ == "__main__":
    setup_database()  # Initialize the database and table
    app = QApplication(sys.argv)
    widget = AstroFilerGUI()
    widget.show()
    sys.exit(app.exec())