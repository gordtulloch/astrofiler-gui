"""
UI package for AstroFiler application.

This package contains all user interface components organized as separate modules
for better maintainability and modularity.
"""

# Import main GUI class for easy access
from .main_window import AstroFilerGUI

# Import dialog classes that might be used by other modules
from .download_dialog import SmartTelescopeDownloadDialog
from .mappings_dialog import MappingsDialog

__all__ = [
    'AstroFilerGUI',
    'SmartTelescopeDownloadDialog',
    'MappingsDialog'
]
