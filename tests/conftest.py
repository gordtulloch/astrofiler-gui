"""
Pytest configuration and shared fixtures for AstroFiler tests.
"""
import pytest
import tempfile
import shutil
import os
import sys
from unittest.mock import Mock, patch, MagicMock
import configparser
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Add the parent directory to sys.path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import application modules at module level for proper mocking
from astrofiler_db import setup_database, fitsFile as FitsFileModel, fitsSequence as FitsSequenceModel, db
from astrofiler_file import fitsProcessing

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)

@pytest.fixture
def mock_config_file(temp_dir):
    """Create a mock configuration file for testing."""
    config_path = os.path.join(temp_dir, 'astrofiler.ini')
    config = configparser.ConfigParser()
    config['DEFAULT'] = {
        'source': os.path.join(temp_dir, 'source'),
        'repo': os.path.join(temp_dir, 'repo'),
        'refresh_on_startup': 'True',
        'theme': 'Dark',
        'font_size': '10',
        'grid_size': '64'
    }
    
    with open(config_path, 'w') as f:
        config.write(f)
    
    return config_path

@pytest.fixture
def mock_fits_header():
    """Create a mock FITS header for testing."""
    return {
        'DATE-OBS': '2023-01-01T20:00:00.000',
        'IMAGETYP': 'Light',
        'OBJECT': 'M31',
        'EXPTIME': 300,
        'XBINNING': 1,
        'YBINNING': 1,
        'CCD-TEMP': -10.0,
        'TELESCOP': 'Test Telescope',
        'INSTRUME': 'Test Camera',
        'FILTER': 'Luminance'
    }

@pytest.fixture
def mock_database():
    """Create a mock database for testing."""
    with patch('astrofiler_db.db') as mock_db:
        mock_db.connect.return_value = None
        mock_db.create_tables.return_value = None
        mock_db.close.return_value = None
        yield mock_db

@pytest.fixture
def sample_fits_files(temp_dir):
    """Create sample FITS file structure for testing."""
    source_dir = os.path.join(temp_dir, 'source')
    repo_dir = os.path.join(temp_dir, 'repo')
    
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(repo_dir, exist_ok=True)
    
    # Create some dummy FITS files
    fits_files = [
        'M31_Light_001.fits',
        'M31_Light_002.fits',
        'Bias_001.fits',
        'Dark_001.fits',
        'Flat_001.fits'
    ]
    
    for fits_file in fits_files:
        file_path = os.path.join(source_dir, fits_file)
        with open(file_path, 'wb') as f:
            f.write(b'SIMPLE  =                    T / file does conform to FITS standard')
    
    return {
        'source_dir': source_dir,
        'repo_dir': repo_dir,
        'fits_files': fits_files
    }

@pytest.fixture
def qapp():
    """Create QApplication for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture
def mock_fits_hdul():
    """Create a mock FITS HDUList using MagicMock for __getitem__ support."""
    mock_hdul = MagicMock()
    mock_hdu = MagicMock()
    mock_hdu.header = {
        'DATE-OBS': '2023-01-01T20:00:00.000',
        'IMAGETYP': 'Light',
        'OBJECT': 'M31',
        'EXPTIME': 300,
        'XBINNING': 1,
        'YBINNING': 1,
        'CCD-TEMP': -10.0,
        'TELESCOP': 'Test Telescope',
        'INSTRUME': 'Test Camera',
        'FILTER': 'Luminance'
    }
    mock_hdu.data = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]  # Dummy image data
    mock_hdul.__getitem__.return_value = mock_hdu
    mock_hdul.__len__.return_value = 1
    mock_hdul.close = Mock()
    return mock_hdul

@pytest.fixture
def mock_config_with_strings():
    """Create a mock config that returns strings instead of MagicMocks."""
    mock_config = MagicMock()
    mock_config.get.side_effect = lambda section, key, fallback=None: {
        ('DEFAULT', 'source'): 'C:\\test\\source',
        ('DEFAULT', 'repo'): 'C:\\test\\repo',
        ('DEFAULT', 'refresh_on_startup'): 'True',
        ('DEFAULT', 'theme'): 'Dark',
        ('DEFAULT', 'font_size'): '10',
        ('DEFAULT', 'grid_size'): '64'
    }.get((section, key), fallback or 'default_value')
    return mock_config

@pytest.fixture
def mock_stylesheets():
    """Mock stylesheet functions to return actual CSS strings."""
    dark_css = "QMainWindow { background-color: #2b2b2b; color: white; }"
    light_css = "QMainWindow { background-color: white; color: black; }"
    
    with patch('astrofiler_gui.get_dark_stylesheet', return_value=dark_css), \
         patch('astrofiler_gui.get_light_stylesheet', return_value=light_css):
        yield

@pytest.fixture
def mock_database_setup():
    """Mock database setup to avoid actual database operations."""
    with patch('astrofiler_db.db') as mock_db:
        # Mock database connection
        mock_db.connect.return_value = None
        mock_db.create_tables.return_value = None
        mock_db.close.return_value = None
        mock_db.is_closed.return_value = False
        
        # Setup in-memory database for testing
        mock_db.database = ':memory:'
        
        # Mock the actual database setup
        with patch('astrofiler_db.setup_database') as mock_setup:
            mock_setup.return_value = None
            yield mock_db
