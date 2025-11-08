"""
Test utilities for AstroFiler application.

Provides common fixtures and utilities for testing.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Dict, Any
from datetime import datetime
import pytest
from unittest.mock import Mock, patch

# Add parent directory to sys.path for setup_path import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import setup_path
except ImportError:
    pass  # setup_path may not be needed in all test environments

from astrofiler.models import BaseModel, db
from astrofiler.config import AstroFilerConfig, DatabaseConfig, RepositoryConfig


@pytest.fixture(scope="session")
def test_config() -> AstroFilerConfig:
    """Provide test configuration."""
    config = AstroFilerConfig()
    
    # Use in-memory SQLite for testing
    config.database = DatabaseConfig(
        database=":memory:",
        type="sqlite"
    )
    
    # Use temporary directory for repository
    temp_dir = tempfile.mkdtemp()
    config.repository = RepositoryConfig(
        repository_path=temp_dir,
        incoming_path=os.path.join(temp_dir, "incoming")
    )
    
    return config


@pytest.fixture
def temp_repository() -> Generator[str, None, None]:
    """Provide temporary repository directory."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


@pytest.fixture
def sample_fits_header() -> Dict[str, Any]:
    """Provide sample FITS header data."""
    return {
        'SIMPLE': True,
        'BITPIX': -32,
        'NAXIS': 2,
        'NAXIS1': 4096,
        'NAXIS2': 4096,
        'EXTEND': True,
        'TELESCOP': 'Test Telescope',
        'INSTRUME': 'Test Camera',
        'OBJECT': 'M31',
        'IMAGETYP': 'LIGHT',
        'EXPTIME': 300.0,
        'DATE-OBS': '2025-11-07T12:00:00.000',
        'CCD-TEMP': -20.0,
        'XBINNING': 1,
        'YBINNING': 1,
        'FILTER': 'Luminance',
    }


@pytest.fixture
def sample_fits_file(temp_repository, sample_fits_header) -> Generator[str, None, None]:
    """Create sample FITS file for testing."""
    from astropy.io import fits
    import numpy as np
    
    # Create sample image data
    data = np.random.randint(0, 65535, (100, 100), dtype=np.uint16)
    
    # Create FITS file
    hdu = fits.PrimaryHDU(data, header=fits.Header(sample_fits_header))
    hdul = fits.HDUList([hdu])
    
    fits_path = os.path.join(temp_repository, "test_image.fits")
    hdul.writeto(fits_path, overwrite=True)
    hdul.close()
    
    yield fits_path
    
    # Cleanup
    if os.path.exists(fits_path):
        os.remove(fits_path)


@pytest.fixture
def mock_database():
    """Provide mock database for testing."""
    with patch('astrofiler.database.connection.db') as mock_db:
        mock_db.is_connection_usable.return_value = True
        mock_db.connect.return_value = True
        mock_db.close.return_value = None
        yield mock_db


@pytest.fixture
def mock_fits_processing():
    """Provide mock FITS processing for testing."""
    with patch('astrofiler.core.file_processing.fitsProcessing') as mock_proc:
        mock_instance = Mock()
        mock_proc.return_value = mock_instance
        
        # Setup common return values
        mock_instance.calculateFileHash.return_value = "test_hash_123"
        mock_instance.analyzeQuality.return_value = {
            'overall_score': 85.0,
            'metrics': {'snr': 10.5, 'fwhm': 2.1},
            'recommendations': []
        }
        
        yield mock_instance


class TestDatabase:
    """Test database context manager."""
    
    def __init__(self, config: AstroFilerConfig):
        self.config = config
        self.models = []
    
    def __enter__(self):
        """Setup test database."""
        # Import all models
        from astrofiler.models import fitsFile, fitsSession, Mapping, Masters
        self.models = [fitsFile, fitsSession, Mapping, Masters]
        
        # Connect to test database
        db.init(self.config.database.database)
        db.connect()
        
        # Create tables
        db.create_tables(self.models, safe=True)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup test database."""
        # Drop tables
        db.drop_tables(self.models, safe=True)
        
        # Close connection
        db.close()


def create_test_session():
    """Create a test session in the database."""
    from astrofiler.models import fitsSession
    
    session_data = {
        'fitsSessionId': 'test_session_123',
        'fitsSessionObjectName': 'M31',
        'fitsSessionDate': datetime.now().date(),
        'fitsSessionTelescope': 'Test Telescope',
        'fitsSessionImager': 'Test Camera',
        'fitsSessionExposure': '300',
        'fitsSessionBinningX': '1',
        'fitsSessionBinningY': '1',
        'fitsSessionFilter': 'Luminance',
    }
    
    return fitsSession.create(**session_data)


def create_test_file():
    """Create a test file in the database."""
    from astrofiler.models import fitsFile
    import uuid
    
    file_data = {
        'fitsFileId': str(uuid.uuid4()),
        'fitsFileName': '/test/path/test_image.fits',
        'fitsFileDate': '2025-11-07T12:00:00.000',
        'fitsFileType': 'LIGHT',
        'fitsFileObject': 'M31',
        'fitsFileExpTime': 300.0,
        'fitsFileXBinning': 1,
        'fitsFileYBinning': 1,
        'fitsFileCCDTemp': -20.0,
        'fitsFileTelescop': 'Test Telescope',
        'fitsFileInstrument': 'Test Camera',
        'fitsFileFilter': 'Luminance',
        'fitsFileHash': 'test_hash_123',
        'fitsFileSession': None,
        'fitsFileCalibrated': 0,
    }
    
    return fitsFile.create(**file_data)


# Pytest marks for categorizing tests
pytestmark = pytest.mark.asyncio

# Custom assertion helpers
def assert_file_exists(file_path: str):
    """Assert that a file exists."""
    assert os.path.exists(file_path), f"File does not exist: {file_path}"


def assert_valid_fits_file(file_path: str):
    """Assert that a file is a valid FITS file."""
    from astropy.io import fits
    
    assert_file_exists(file_path)
    
    try:
        with fits.open(file_path) as hdul:
            assert len(hdul) > 0, "FITS file has no HDUs"
            assert hdul[0].header is not None, "Primary HDU has no header"
    except Exception as e:
        pytest.fail(f"Invalid FITS file {file_path}: {e}")


def assert_database_record_exists(model_class, **kwargs):
    """Assert that a database record exists."""
    try:
        record = model_class.get(**kwargs)
        assert record is not None, f"No {model_class.__name__} record found with {kwargs}"
    except model_class.DoesNotExist:
        pytest.fail(f"No {model_class.__name__} record found with {kwargs}")


# Performance testing utilities
class PerformanceTimer:
    """Context manager for measuring execution time."""
    
    def __init__(self, max_time: float = None):
        self.max_time = max_time
        self.elapsed_time = 0.0
    
    def __enter__(self):
        import time
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        self.elapsed_time = time.perf_counter() - self.start_time
        
        if self.max_time and self.elapsed_time > self.max_time:
            pytest.fail(f"Operation took too long: {self.elapsed_time:.2f}s > {self.max_time:.2f}s")