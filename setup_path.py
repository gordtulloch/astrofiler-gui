"""
Automatic Python path setup for AstroFiler development.

Import this module at the top of any script to automatically add the src directory
to the Python path, enabling the new package structure.

Usage:
    import setup_path  # This automatically configures the path
    from astrofiler.core import fitsProcessing
"""
import sys
import os

# Get the project root directory (where this file is located)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')

# Add src to Python path if not already present
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# Set environment variable for other processes
os.environ['PYTHONPATH'] = SRC_PATH + os.pathsep + os.environ.get('PYTHONPATH', '')