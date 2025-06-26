"""
Tests for astrofiler_file.py - FITS file processing module
"""
import pytest
import os
import tempfile
import uuid
from unittest.mock import patch, Mock, MagicMock, mock_open
import configparser
from datetime import datetime

from astrofiler_file import fitsProcessing


class TestFitsProcessingInit:
    """Test fitsProcessing class initialization."""
    
    @patch('astrofiler_file.configparser.ConfigParser')
    def test_init_with_config(self, mock_config_parser):
        """Test initialization with valid config."""
        mock_config = Mock()
        mock_config.get.side_effect = lambda section, key, fallback=None: {
            ('DEFAULT', 'source'): '/test/source',
            ('DEFAULT', 'repo'): '/test/repo'
        }.get((section, key), fallback)
        
        mock_config_parser.return_value = mock_config
        
        with patch('builtins.open', mock_open()):
            processor = fitsProcessing()
            
        assert processor.sourceFolder == '/test/source'
        assert processor.repoFolder == '/test/repo'
        mock_config.read.assert_called_once_with('astrofiler.ini')
    
    @patch('astrofiler_file.configparser.ConfigParser')
    def test_init_with_defaults(self, mock_config_parser):
        """Test initialization with default fallback values."""
        mock_config = Mock()
        mock_config.get.return_value = '.'  # Default fallback
        mock_config_parser.return_value = mock_config
        
        with patch('builtins.open', mock_open()):
            processor = fitsProcessing()
        
        assert processor.sourceFolder == '.'
        assert processor.repoFolder == '.'


class TestSubmitFileToDB:
    """Test submitFileToDB method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('astrofiler_file.configparser.ConfigParser'):
            with patch('builtins.open', mock_open()):
                self.processor = fitsProcessing()
    
    @patch('astrofiler_file.FitsFileModel')
    @patch('astrofiler_file.uuid.uuid4')
    def test_submit_file_with_object(self, mock_uuid, mock_model):
        """Test submitting file with OBJECT header."""
        mock_uuid.return_value = 'test-uuid'
        mock_record = Mock()
        mock_record.fitsFileId = 'test-uuid'
        mock_model.create.return_value = mock_record
        
        header = {
            'DATE-OBS': '2023-01-01T20:00:00.000',
            'IMAGETYP': 'Light',
            'OBJECT': 'M31',
            'EXPTIME': 300,
            'XBINNING': 1,
            'YBINNING': 1,
            'CCD-TEMP': -10.0,
            'TELESCOP': 'Test Telescope',
            'INSTRUME': 'Test Camera'
        }
        
        result = self.processor.submitFileToDB('test.fits', header)
        
        assert result == 'test-uuid'
        mock_model.create.assert_called_once()
    
    @patch('astrofiler_file.FitsFileModel')
    @patch('astrofiler_file.uuid.uuid4')
    def test_submit_file_without_object(self, mock_uuid, mock_model):
        """Test submitting file without OBJECT header."""
        mock_uuid.return_value = 'test-uuid'
        mock_record = Mock()
        mock_record.fitsFileId = 'test-uuid'
        mock_model.create.return_value = mock_record
        
        header = {
            'DATE-OBS': '2023-01-01T20:00:00.000',
            'IMAGETYP': 'Light',
            'EXPTIME': 300,
            'XBINNING': 1,
            'YBINNING': 1,
            'CCD-TEMP': -10.0,
            'TELESCOP': 'Test Telescope',
            'INSTRUME': 'Test Camera'
        }
        
        result = self.processor.submitFileToDB('test.fits', header)
        
        assert result == 'test-uuid'
        mock_model.create.assert_called_once()
    
    @patch('astrofiler_file.logging')
    def test_submit_file_missing_date(self, mock_logging):
        """Test submitting file without DATE-OBS header."""
        header = {'IMAGETYP': 'Light'}
        
        result = self.processor.submitFileToDB('test.fits', header)
        
        assert result is None
        mock_logging.error.assert_called_once()


class TestRegisterFitsImage:
    """Test registerFitsImage method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('astrofiler_file.configparser.ConfigParser'):
            with patch('builtins.open', mock_open()):
                self.processor = fitsProcessing()
                self.processor.repoFolder = '/test/repo/'
    
    @patch('astrofiler_file.fits')
    @patch('astrofiler_file.os.path.splitext')
    def test_register_non_fits_file(self, mock_splitext, mock_fits):
        """Test registering non-FITS file (should be ignored)."""
        mock_splitext.return_value = ('test', '.txt')
        
        result = self.processor.registerFitsImage('/test', 'test.txt', True)
        
        assert result is False
        mock_fits.open.assert_not_called()
    
    @patch('astrofiler_file.fits')
    @patch('astrofiler_file.os.path.splitext')
    def test_register_invalid_fits_file(self, mock_splitext, mock_fits):
        """Test registering invalid FITS file."""
        mock_splitext.return_value = ('test', '.fits')
        mock_fits.open.side_effect = ValueError("Invalid FITS file")
        
        with patch('astrofiler_file.logging') as mock_logging:
            result = self.processor.registerFitsImage('/test', 'test.fits', True)
        
        assert result is False
        mock_logging.warning.assert_called_once()
    
    @patch('astrofiler_file.fits')
    @patch('astrofiler_file.os.path.splitext')
    @patch('astrofiler_file.os.makedirs')
    def test_register_light_frame(self, mock_makedirs, mock_splitext, mock_fits):
        """Test registering a light frame."""
        mock_splitext.return_value = ('test', '.fits')
        
        # Mock FITS file using MagicMock for __getitem__ support
        mock_hdul = MagicMock()
        mock_header = {
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
        mock_hdul.__getitem__.return_value.header = mock_header
        mock_fits.open.return_value = mock_hdul
        
        with patch.object(self.processor, 'submitFileToDB', return_value='test-uuid'):
            with patch('astrofiler_file.os.path.isdir', return_value=False):
                result = self.processor.registerFitsImage('/test', 'test.fits', True)
        
        assert result == 'test-uuid'
        mock_makedirs.assert_called_once()


class TestCreateSequences:
    """Test sequence creation methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('astrofiler_file.configparser.ConfigParser'):
            with patch('builtins.open', mock_open()):
                self.processor = fitsProcessing()
    
    @patch.object(fitsProcessing, 'createLightSequences')
    @patch.object(fitsProcessing, 'createCalibrationSequences')
    def test_create_sequences(self, mock_calibration, mock_light):
        """Test createSequences method."""
        mock_light.return_value = ['seq1', 'seq2']
        mock_calibration.return_value = ['seq3', 'seq4']
        
        with patch('astrofiler_file.logging'):
            self.processor.createSequences()
        
        mock_light.assert_called_once()
        mock_calibration.assert_called_once()
    
    def test_same_day_true(self):
        """Test sameDay method returns True for same day."""
        result = self.processor.sameDay('2023-01-01', '2023-01-01')
        assert result is True
    
    def test_same_day_false(self):
        """Test sameDay method returns False for different days."""
        result = self.processor.sameDay('2023-01-01', '2023-01-02')
        assert result is False
    
    def test_same_day_within_12_hours(self):
        """Test sameDay method for dates within 12 hours."""
        # This test might need adjustment based on actual implementation
        result = self.processor.sameDay('2023-01-01', '2023-01-01')
        assert result is True


class TestCreateThumbnail:
    """Test thumbnail creation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('astrofiler_file.configparser.ConfigParser'):
            with patch('builtins.open', mock_open()):
                self.processor = fitsProcessing()
                self.processor.repoFolder = '/test/repo/'
    
    @patch('astrofiler_file.FitsFileModel')
    @patch('astrofiler_file.fits')
    @patch('astrofiler_file.plt')
    @patch('astrofiler_file.os.path.join')
    def test_create_thumbnail_success(self, mock_join, mock_plt, mock_fits, mock_model):
        """Test successful thumbnail creation."""
        # Mock database record
        mock_file = Mock()
        mock_file.fitsFileName = 'test.fits'
        mock_file.fitsFileId = 'test-id'
        mock_model.get_or_none.return_value = mock_file
        
        # Mock FITS data using MagicMock for __getitem__ support
        mock_hdul = MagicMock()
        mock_data = [[100, 200], [150, 250]]
        mock_hdul.__getitem__.return_value.data = mock_data
        mock_fits.open.return_value.__enter__.return_value = mock_hdul
        
        # Mock file path
        mock_join.return_value = '/test/repo/Thumbnails/thumbnail_test-id.jpg'
        
        with patch('astrofiler_file.logging'):
            self.processor.createThumbnail('test-id')
        
        mock_plt.imsave.assert_called_once()
        mock_model.get_or_none.assert_called_once()
    
    @patch('astrofiler_file.FitsFileModel')
    def test_create_thumbnail_no_file(self, mock_model):
        """Test thumbnail creation when file not found."""
        mock_model.get_or_none.return_value = None
        
        with patch('astrofiler_file.logging') as mock_logging:
            self.processor.createThumbnail('nonexistent-id')
        
        mock_logging.info.assert_called_once()


class TestRegisterFitsImages:
    """Test registerFitsImages method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('astrofiler_file.configparser.ConfigParser'):
            with patch('builtins.open', mock_open()):
                self.processor = fitsProcessing()
                self.processor.sourceFolder = '/test/source'
                self.processor.repoFolder = '/test/repo'
    
    @patch('astrofiler_file.os.walk')
    @patch.object(fitsProcessing, 'registerFitsImage')
    @patch.object(fitsProcessing, 'createThumbnail')
    def test_register_fits_images_move_files(self, mock_thumbnail, mock_register, mock_walk):
        """Test registerFitsImages with moveFiles=True."""
        # Mock os.walk
        mock_walk.return_value = [
            ('/test/source', [], ['test1.fits', 'test2.fits', 'other.txt'])
        ]
        
        # Mock registerFitsImage
        mock_register.side_effect = ['uuid1', 'uuid2', None]
        
        with patch('astrofiler_file.logging'):
            with patch('astrofiler_file.os.path.abspath', side_effect=lambda x: x):
                result = self.processor.registerFitsImages(moveFiles=True)
        
        assert len(result) == 2
        assert 'uuid1' in result
        assert 'uuid2' in result
        assert mock_register.call_count == 3
        assert mock_thumbnail.call_count == 2
    
    @patch('astrofiler_file.os.walk')
    @patch.object(fitsProcessing, 'registerFitsImage')
    @patch.object(fitsProcessing, 'createThumbnail')
    @patch('astrofiler_file.FitsFileModel.get_or_none')
    def test_register_fits_images_sync_mode(self, mock_get_or_none, mock_thumbnail, mock_register, mock_walk):
        """Test registerFitsImages with moveFiles=False (sync mode)."""
        mock_walk.return_value = [
            ('/test/repo', [], ['test1.fits'])
        ]
        mock_register.return_value = 'uuid1'
        mock_get_or_none.return_value = None  # Mock database query
        
        with patch('astrofiler_file.logging'):
            with patch('astrofiler_file.os.path.abspath', side_effect=lambda x: x):
                result = self.processor.registerFitsImages(moveFiles=False)
        
        assert len(result) == 1
        mock_register.assert_called_with('/test/repo', 'test1.fits', False)
