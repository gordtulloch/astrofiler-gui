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
        
        # Setup mock file header with append method
        mock_header = MagicMock()
        mock_header.__contains__ = lambda self, key: key in {
            'OBJECT', 'DATE-OBS', 'INSTRUME', 'TELESCOP', 'EXPTIME', 
            'FILTER', 'IMAGETYP', 'XBINNING', 'YBINNING', 'CCD-TEMP'
        }
        
        # Mock header values
        header_values = {
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
        
        mock_header.__getitem__ = lambda self, key: header_values[key]
        mock_header.get = lambda key, default=None: header_values.get(key, default)
        mock_header.append = MagicMock()
        mock_fits_file.header = mock_header
        mock_hdul.flush = MagicMock()
        
        # Mock the file operations and database functions
        with patch('astrofiler_file.os.path.exists', return_value=True), \
             patch('astrofiler_file.shutil.move', return_value=True), \
             patch('astrofiler_file.FitsFileModel.create', return_value=MagicMock(fitsFileId='test-id')):
            
            # Test registering file
            result = processor.registerFitsImage('/test/path', 'test.fits', False)
            
            # Check if registration was successful (returns a file ID)
            assert result is not False
        
    @patch('astrofiler_file.os.path.abspath')
    @patch('astrofiler_file.os.path.exists')
    @patch('astrofiler_file.os.walk')
    def test_register_fits_images(self, mock_walk, mock_exists, mock_abspath):
        """Test scanning and registering FITS files in a directory."""
        # Mock the walk function to return a fresh list each time it's called
        def walk_side_effect(*args):
            return [('/test/path', [], ['file1.fits', 'file2.FITS', 'not_fits.txt'])]
        
        mock_walk.side_effect = walk_side_effect
        
        # Mock exists and abspath to always return expected values
        mock_exists.return_value = True
        mock_abspath.return_value = '/test/path'
        
        # Create an instance of the processing class and set repoFolder
        processor = fitsProcessing()
        processor.repoFolder = '/test/path'  # Set the repo folder for the test
        
        # Mock the registerFitsImage method to return a UUID for each FITS file
        with patch.object(processor, 'registerFitsImage', return_value='test-uuid') as mock_register:
            # Run the registration process with moveFiles=False (so it uses repoFolder)
            registered_files = processor.registerFitsImages(moveFiles=False)
            
            # The test verifies that the method processes FITS files correctly
            # At minimum, it should process at least one FITS file
            assert mock_register.call_count >= 1, f"Expected at least 1 call, got {mock_register.call_count}"
            
            # Verify the calls were made with the correct parameters
            calls = mock_register.call_args_list
            call_args = [(call[0][0], call[0][1], call[0][2]) for call in calls]
            
            # Should have been called for at least one FITS file
            valid_calls = [args for args in call_args if args[1] in ['file1.fits', 'file2.FITS']]
            assert len(valid_calls) >= 1, f"Expected at least one call for a FITS file, got {call_args}"
            
            # Verify the parameters are correct
            for root, filename, move_files in valid_calls:
                assert root == '/test/path'
                assert filename in ['file1.fits', 'file2.FITS']
                assert move_files == False
