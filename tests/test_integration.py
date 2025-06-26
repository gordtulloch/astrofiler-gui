"""
Integration tests for AstroFiler application
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, Mock, MagicMock
import configparser

from astrofiler_file import fitsProcessing
from astrofiler_db import setup_database, fitsFile, fitsSequence


class TestIntegrationFitsProcessingDatabase:
    """Integration tests between FITS processing and database."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for integration testing."""
        base_temp = tempfile.mkdtemp()
        
        workspace = {
            'base': base_temp,
            'source': os.path.join(base_temp, 'source'),
            'repo': os.path.join(base_temp, 'repo'),
            'config': os.path.join(base_temp, 'astrofiler.ini')
        }
        
        # Create directories
        os.makedirs(workspace['source'])
        os.makedirs(workspace['repo'])
        
        # Create config file
        config = configparser.ConfigParser()
        config['DEFAULT'] = {
            'source': workspace['source'],
            'repo': workspace['repo']
        }
        
        with open(workspace['config'], 'w') as f:
            config.write(f)
        
        yield workspace
        
        # Cleanup
        shutil.rmtree(base_temp, ignore_errors=True)
    
    @patch('astrofiler_file.configparser.ConfigParser.read')
    def test_fits_processing_config_integration(self, mock_read, temp_workspace):
        """Test that fitsProcessing correctly reads configuration."""
        # Mock config reading to use our temp config
        def mock_read_func(filename):
            if filename == 'astrofiler.ini':
                config = configparser.ConfigParser()
                config.read(temp_workspace['config'])
                return config
        
        with patch('builtins.open'):
            with patch('astrofiler_file.configparser.ConfigParser') as mock_config_class:
                mock_config = Mock()
                mock_config.get.side_effect = lambda section, key, fallback=None: {
                    ('DEFAULT', 'source'): temp_workspace['source'],
                    ('DEFAULT', 'repo'): temp_workspace['repo']
                }.get((section, key), fallback)
                mock_config_class.return_value = mock_config
                
                processor = fitsProcessing()
        
        assert processor.sourceFolder == temp_workspace['source']
        assert processor.repoFolder == temp_workspace['repo']
    
    @patch('astrofiler_db.db')
    def test_database_setup_integration(self, mock_db):
        """Test database setup process."""
        mock_db.connect.return_value = None
        mock_db.create_tables.return_value = None
        mock_db.close.return_value = None
        
        setup_database()
        
        # Verify the correct sequence of calls
        mock_db.connect.assert_called_once()
        mock_db.create_tables.assert_called_once_with([fitsFile, fitsSequence])
        mock_db.close.assert_called_once()


class TestIntegrationEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.fixture
    def complete_test_environment(self):
        """Set up a complete test environment."""
        base_temp = tempfile.mkdtemp()
        
        env = {
            'base': base_temp,
            'source': os.path.join(base_temp, 'source'),
            'repo': os.path.join(base_temp, 'repo'),
            'config': os.path.join(base_temp, 'astrofiler.ini'),
            'db': os.path.join(base_temp, 'test.db')
        }
        
        # Create directory structure
        os.makedirs(env['source'])
        os.makedirs(env['repo'])
        os.makedirs(os.path.join(env['repo'], 'Thumbnails'))
        
        # Create config file
        config = configparser.ConfigParser()
        config['DEFAULT'] = {
            'source': env['source'],
            'repo': env['repo']
        }
        
        with open(env['config'], 'w') as f:
            config.write(f)
        
        # Create sample FITS files (mock)
        sample_files = [
            'M31_Light_001.fits',
            'M31_Light_002.fits',
            'Bias_001.fits',
            'Dark_300s_001.fits',
            'Flat_L_001.fits'
        ]
        
        for filename in sample_files:
            filepath = os.path.join(env['source'], filename)
            with open(filepath, 'wb') as f:
                # Write minimal FITS header
                f.write(b'SIMPLE  =                    T / file does conform to FITS standard             ')
                f.write(b'BITPIX  =                  -32 / number of bits per data pixel                  ')
                f.write(b'NAXIS   =                    2 / number of data axes                            ')
                f.write(b'NAXIS1  =                 1024 / length of data axis 1                         ')
                f.write(b'NAXIS2  =                 1024 / length of data axis 2                         ')
                f.write(b'END' + b' ' * 77)  # END keyword padded to 80 chars
        
        yield env
        
        # Cleanup
        shutil.rmtree(base_temp, ignore_errors=True)
    
    @patch('astrofiler_file.fits')
    @patch('astrofiler_file.FitsFileModel')
    def test_complete_workflow_simulation(self, mock_model, mock_fits, complete_test_environment):
        """Test a complete workflow simulation."""
        env = complete_test_environment
        
        # Mock FITS file opening
        def create_mock_fits_file(image_type, obj_name=None):
            mock_hdul = MagicMock()  # Changed to MagicMock for __getitem__ support
            mock_header = {
                'DATE-OBS': '2023-01-01T20:00:00.000',
                'IMAGETYP': image_type,
                'EXPTIME': 300,
                'XBINNING': 1,
                'YBINNING': 1,
                'CCD-TEMP': -10.0,
                'TELESCOP': 'Test Telescope',
                'INSTRUME': 'Test Camera'
            }
            
            if obj_name:
                mock_header['OBJECT'] = obj_name
            if image_type == 'Light':
                mock_header['FILTER'] = 'Luminance'
                
            mock_hdul.__getitem__.return_value.header = mock_header
            return mock_hdul
        
        # Configure mock to return different headers based on filename
        def mock_fits_open(filename, mode='readonly'):
            if 'M31_Light' in filename:
                return create_mock_fits_file('Light', 'M31')
            elif 'Bias' in filename:
                return create_mock_fits_file('Bias')
            elif 'Dark' in filename:
                return create_mock_fits_file('Dark')
            elif 'Flat' in filename:
                return create_mock_fits_file('Flat')
            else:
                return create_mock_fits_file('Light', 'Unknown')
        
        mock_fits.open.side_effect = mock_fits_open
        
        # Mock database operations
        mock_record = Mock()
        mock_record.fitsFileId = 'test-uuid'
        mock_model.create.return_value = mock_record
        
        # Initialize processor with test environment
        with patch('astrofiler_file.configparser.ConfigParser') as mock_config_class:
            mock_config = Mock()
            mock_config.get.side_effect = lambda section, key, fallback=None: {
                ('DEFAULT', 'source'): env['source'],
                ('DEFAULT', 'repo'): env['repo']
            }.get((section, key), fallback)
            mock_config_class.return_value = mock_config
            
            with patch('builtins.open'):
                processor = fitsProcessing()
        
        # Mock additional dependencies
        with patch('astrofiler_file.os.makedirs'):
            with patch('astrofiler_file.os.path.isdir', return_value=False):
                with patch('astrofiler_file.os.path.exists', return_value=False):
                    with patch('astrofiler_file.uuid.uuid4', return_value='test-uuid'):
                        with patch('astrofiler_file.logging'):
                            # Run the registration process
                            registered_files = processor.registerFitsImages(moveFiles=True)
        
        # Verify that files were processed
        assert len(registered_files) > 0
        
        # Verify that database create was called for each processed file
        assert mock_model.create.call_count > 0


class TestIntegrationErrorHandling:
    """Integration tests for error handling across modules."""
    
    def test_database_connection_error_handling(self):
        """Test error handling when database connection fails."""
        with patch('astrofiler_db.db.connect', side_effect=Exception("Connection failed")):
            with patch('astrofiler_db.logger') as mock_logger:
                with pytest.raises(Exception):
                    setup_database()
                # The error should have been logged
                mock_logger.error.assert_called()
    
    @patch('astrofiler_file.fits.open', side_effect=ValueError("Invalid FITS"))
    def test_fits_processing_error_handling(self, mock_fits_open):
        """Test error handling in FITS processing."""
        with patch('astrofiler_file.configparser.ConfigParser'):
            with patch('builtins.open'):
                processor = fitsProcessing()
        
        with patch('astrofiler_file.logging') as mock_logging:
            result = processor.registerFitsImage('/test', 'invalid.fits', True)
        
        assert result is False
        mock_logging.warning.assert_called_once()
    
    def test_config_file_missing_handling(self):
        """Test handling of missing configuration file."""
        with patch('astrofiler_file.configparser.ConfigParser') as mock_config_class:
            mock_config = Mock()
            mock_config.get.return_value = '.'  # Fallback values
            mock_config_class.return_value = mock_config
            
            with patch('builtins.open', side_effect=FileNotFoundError()):
                processor = fitsProcessing()
        
        # Should use fallback values
        assert processor.sourceFolder == '.'
        assert processor.repoFolder == '.'


class TestPerformanceIntegration:
    """Integration tests for performance considerations."""
    
    @patch('astrofiler_file.fits')
    @patch('astrofiler_file.FitsFileModel')
    def test_large_file_batch_processing(self, mock_model, mock_fits):
        """Test processing a large batch of files."""
        # Mock many files
        file_count = 100
        
        # Mock FITS opening
        mock_hdul = MagicMock()  # Changed to MagicMock for __getitem__ support
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
        
        # Mock database
        mock_record = Mock()
        mock_record.fitsFileId = 'test-uuid'
        mock_model.create.return_value = mock_record
        
        # Create processor
        with patch('astrofiler_file.configparser.ConfigParser'):
            with patch('builtins.open'):
                processor = fitsProcessing()
        
        # Mock file system
        mock_files = [f'test_{i:03d}.fits' for i in range(file_count)]
        
        with patch('astrofiler_file.os.walk') as mock_walk:
            mock_walk.return_value = [('/test/source', [], mock_files)]
            
            with patch('astrofiler_file.os.makedirs'):
                with patch('astrofiler_file.os.path.isdir', return_value=False):
                    with patch('astrofiler_file.os.path.exists', return_value=False):
                        with patch('astrofiler_file.uuid.uuid4', return_value='test-uuid'):
                            with patch('astrofiler_file.logging'):
                                with patch('astrofiler_file.os.path.abspath', side_effect=lambda x: x):
                                    registered_files = processor.registerFitsImages(moveFiles=True)
        
        # Should process all files
        assert len(registered_files) == file_count
        assert mock_model.create.call_count == file_count
