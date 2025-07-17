#!/usr/bin/env python3
"""
Tests for the file processing module.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path to import the application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from astrofiler_file import fitsProcessing

class TestFitsProcessing:
    """Test the FITS file processing functionality."""
    
    @pytest.fixture
    def mock_fits_file(self):
        """Create a mock FITS file for testing."""
        # Create a mock fits_file with necessary attributes
        mock_file = MagicMock()
        mock_file.header = {
            'OBJECT': 'TestObject',
            'DATE-OBS': '2025-07-17T12:00:00',
            'INSTRUME': 'TestCamera',
            'TELESCOP': 'TestTelescope',
            'EXPTIME': 10.0,
            'FILTER': 'TestFilter',
            'IMAGETYP': 'Light Frame'
        }
        return mock_file
    
    @patch('astrofiler_file.fits.open')
    def test_register_fits_image(self, mock_fits_open, mock_fits_file):
        """Test registering a FITS file."""
        # Set up the mock to return our mock FITS file
        mock_hdul = MagicMock()
        mock_hdul.__getitem__.return_value = mock_fits_file
        mock_fits_open.return_value = mock_hdul
        
        # Create an instance of the processing class
        processor = fitsProcessing()
        
        # Setup mock file header
        mock_fits_file.header = {
            'OBJECT': 'TestObject',
            'DATE-OBS': '2025-07-17T12:00:00',
            'INSTRUME': 'TestCamera',
            'TELESCOP': 'TestTelescope',
            'EXPTIME': 10.0,
            'FILTER': 'TestFilter',
            'IMAGETYP': 'Light Frame',
            'XBINNING': 1,
            'YBINNING': 1,
            'CCD-TEMP': -20
        }
        
        # Mock the file operations and database functions
        with patch('astrofiler_file.os.path.exists', return_value=True), \
             patch('astrofiler_file.shutil.move', return_value=True), \
             patch('astrofiler_file.FitsFileModel.create', return_value=MagicMock(fitsFileId='test-id')):
            
            # Test registering file
            result = processor.registerFitsImage('/test/path', 'test.fits', False)
            
            # Check if registration was successful (returns a file ID)
            assert result is not False
        
    @patch('astrofiler_file.os.path.exists')
    @patch('astrofiler_file.os.walk')
    def test_register_fits_images(self, mock_walk, mock_exists):
        """Test scanning and registering FITS files in a directory."""
        # Mock the walk function to return a list of files
        mock_walk.return_value = [
            ('/test/path', [], ['file1.fits', 'file2.FITS', 'not_fits.txt'])
        ]
        
        # Mock exists to always return True
        mock_exists.return_value = True
        
        # Create an instance of the processing class
        processor = fitsProcessing()
        
        # Mock the registerFitsImage method to return a UUID for each FITS file
        with patch.object(processor, 'registerFitsImage', return_value='test-uuid') as mock_register:
            # Run the registration process
            registered_files = processor.registerFitsImages(moveFiles=False)
            
            # The implementation might scan all folders first, then process the files
            # So we'll just check that it was called at least once with the right parameters
            mock_register.assert_called_with('/test/path', 'file2.FITS', False)
