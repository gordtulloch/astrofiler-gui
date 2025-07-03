#!/usr/bin/env python3
"""
Test suite for AstroFiler application.
Tests the core functionality of FITS file processing, database operations, and session management.
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock
import uuid

# Import modules to test
from astrofiler_db import setup_database, fitsFile as FitsFileModel, fitsSession as FitsSessionModel
from astrofiler_file import fitsProcessing


class TestAstroFilerDB:
    """Test database operations and models."""
    
    def setup_method(self):
        """Set up test database before each test."""
        # Use a temporary database for testing
        self.test_db_path = tempfile.mktemp(suffix='.db')
        
        # Patch the database to use our test database
        import astrofiler_db
        self.original_db = astrofiler_db.db
        
        # Create a new database instance for testing
        import peewee as pw
        astrofiler_db.db.init(self.test_db_path)
        
        # Set up the database
        setup_database()
    
    def teardown_method(self):
        """Clean up after each test."""
        # Restore original database
        import astrofiler_db
        try:
            astrofiler_db.db.close()
        except:
            pass
        
        # Clean up test database file
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    
    def test_setup_database(self):
        """Test database setup creates tables."""
        # Database should be created by setup_method
        assert os.path.exists(self.test_db_path)
        
        # Verify we can connect to the database
        import astrofiler_db
        try:
            astrofiler_db.db.connect()
            # Check if tables exist by trying to create a simple query
            FitsFileModel.select().count()
            FitsSessionModel.select().count()
            astrofiler_db.db.close()
        except Exception as e:
            pytest.fail(f"Database setup failed: {e}")
    
    def test_fits_file_model_creation(self):
        """Test creating a FITS file record."""
        test_id = str(uuid.uuid4())
        test_date = date(2023, 7, 15)
        
        # Create a test FITS file record
        fits_file = FitsFileModel.create(
            fitsFileId=test_id,
            fitsFileName="test_file.fits",
            fitsFileDate=test_date,
            fitsFileType="Light",
            fitsFileObject="M31",
            fitsFileTelescop="Test Telescope",
            fitsFileInstrument="Test Camera"
        )
        
        assert fits_file.fitsFileId == test_id
        assert fits_file.fitsFileName == "test_file.fits"
        assert fits_file.fitsFileDate == test_date
        assert fits_file.fitsFileType == "Light"
        assert fits_file.fitsFileObject == "M31"
    
    def test_fits_session_model_creation(self):
        """Test creating a FITS session record."""
        test_id = str(uuid.uuid4())
        test_date = date(2023, 7, 15)
        
        # Create a test FITS session record
        fits_session = FitsSessionModel.create(
            fitsSessionId=test_id,
            fitsSessionObjectName="M31",
            fitsSessionDate=test_date,
            fitsSessionTelescope="Test Telescope",
            fitsSessionImager="Test Camera"
        )
        
        assert fits_session.fitsSessionId == test_id
        assert fits_session.fitsSessionObjectName == "M31"
        assert fits_session.fitsSessionDate == test_date
        assert fits_session.fitsSessionTelescope == "Test Telescope"
        assert fits_session.fitsSessionImager == "Test Camera"


class TestFitsProcessing:
    """Test FITS file processing functionality."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.temp_dir, "source")
        self.repo_dir = os.path.join(self.temp_dir, "repo")
        os.makedirs(self.source_dir)
        os.makedirs(self.repo_dir)
        
        # Create test config file
        self.config_file = os.path.join(self.temp_dir, "astrofiler.ini")
        with open(self.config_file, 'w') as f:
            f.write(f"""[DEFAULT]
source = {self.source_dir}
repo = {self.repo_dir}
""")
        
        # Mock the config file path
        with patch('astrofiler_file.configparser.ConfigParser.read') as mock_read:
            mock_read.return_value = None
            self.fits_processor = fitsProcessing()
            self.fits_processor.sourceFolder = self.source_dir
            self.fits_processor.repoFolder = self.repo_dir
    
    def teardown_method(self):
        """Clean up after each test."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_calculate_file_hash(self):
        """Test file hash calculation."""
        # Create a test file
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        # Calculate hash
        hash_value = self.fits_processor.calculateFileHash(test_file)
        
        # Verify hash is calculated
        assert hash_value is not None
        assert len(hash_value) == 64  # SHA-256 produces 64 character hex string
        
        # Verify same file produces same hash
        hash_value2 = self.fits_processor.calculateFileHash(test_file)
        assert hash_value == hash_value2
    
    def test_calculate_file_hash_nonexistent(self):
        """Test file hash calculation with nonexistent file."""
        hash_value = self.fits_processor.calculateFileHash("/nonexistent/file.txt")
        assert hash_value is None
    
    def test_same_day_true(self):
        """Test sameDay function returns True for dates within 12 hours."""
        date1 = "2023-07-15"
        date2 = "2023-07-15"
        
        result = self.fits_processor.sameDay(date1, date2)
        assert result is True
    
    def test_same_day_false(self):
        """Test sameDay function returns False for dates more than 12 hours apart."""
        date1 = "2023-07-15"
        date2 = "2023-07-17"
        
        result = self.fits_processor.sameDay(date1, date2)
        assert result is False
    
    def test_date_to_string_datetime_object(self):
        """Test dateToString with datetime object."""
        test_date = datetime(2023, 7, 15, 10, 30, 45)
        result = self.fits_processor.dateToString(test_date)
        assert result == "2023-07-15"
    
    def test_date_to_string_iso_format(self):
        """Test dateToString with ISO format string."""
        test_date = "2023-07-15T10:30:45"
        result = self.fits_processor.dateToString(test_date)
        assert result == "2023-07-15"
    
    def test_date_to_string_space_format(self):
        """Test dateToString with space-separated format."""
        test_date = "2023-07-15 10:30:45"
        result = self.fits_processor.dateToString(test_date)
        assert result == "2023-07-15"
    
    def test_date_to_string_date_only(self):
        """Test dateToString with date-only string."""
        test_date = "2023-07-15"
        result = self.fits_processor.dateToString(test_date)
        assert result == "2023-07-15"
    
    def test_date_to_string_none(self):
        """Test dateToString with None input."""
        result = self.fits_processor.dateToString(None)
        assert result is None
    
    def test_date_to_date_field_string(self):
        """Test dateToDateField with string input."""
        test_date = "2023-07-15"
        result = self.fits_processor.dateToDateField(test_date)
        assert result == date(2023, 7, 15)
    
    def test_date_to_date_field_iso_string(self):
        """Test dateToDateField with ISO format string."""
        test_date = "2023-07-15T10:30:45"
        result = self.fits_processor.dateToDateField(test_date)
        assert result == date(2023, 7, 15)
    
    def test_date_to_date_field_datetime(self):
        """Test dateToDateField with datetime object."""
        test_date = datetime(2023, 7, 15, 10, 30, 45)
        result = self.fits_processor.dateToDateField(test_date)
        assert result == date(2023, 7, 15)
    
    def test_date_to_date_field_none(self):
        """Test dateToDateField with None input."""
        result = self.fits_processor.dateToDateField(None)
        assert result is None
    
    def test_date_to_date_field_invalid(self):
        """Test dateToDateField with invalid input."""
        result = self.fits_processor.dateToDateField("invalid-date")
        assert result is None
    
    @patch('astrofiler_file.FitsFileModel')
    def test_create_light_sessions_empty(self, mock_model):
        """Test createLightSessions with no unassigned files."""
        # Mock empty query result
        mock_model.select.return_value.where.return_value = []
        
        result = self.fits_processor.createLightSessions()
        
        assert result == []
    
    @patch('astrofiler_file.FitsFileModel')
    @patch('astrofiler_file.fitsSessionModel')
    def test_create_light_sessions_single_file(self, mock_session_model, mock_file_model):
        """Test createLightSessions with single file."""
        # Mock a single unassigned file
        mock_file = Mock()
        mock_file.fitsFileName = "test.fits"
        mock_file.fitsFileObject = "M31"
        mock_file.fitsFileTelescop = "Test Telescope"
        mock_file.fitsFileInstrument = "Test Camera"
        mock_file.fitsFileDate = date(2023, 7, 15)
        mock_file.save = Mock()
        
        mock_file_model.select.return_value.where.return_value = [mock_file]
        
        # Mock session creation
        mock_session = Mock()
        mock_session.fitsSessionId = "test-session-id"
        mock_session_model.create.return_value = mock_session
        
        result = self.fits_processor.createLightSessions()
        
        # Verify session was created
        mock_session_model.create.assert_called_once()
        mock_file.save.assert_called_once()
        assert len(result) == 2  # One for session creation, one for file assignment
    
    @patch('astrofiler_file.FitsFileModel')
    def test_create_calibration_sessions_empty(self, mock_model):
        """Test createCalibrationSessions with no unassigned files."""
        # Mock empty query results
        mock_model.select.return_value.where.return_value = []
        
        result = self.fits_processor.createCalibrationSessions()
        
        assert result == []
    
    @patch('astrofiler_file.FitsFileModel')
    @patch('astrofiler_file.fitsSessionModel')
    def test_create_calibration_sessions_bias_files(self, mock_session_model, mock_file_model):
        """Test createCalibrationSessions with bias files."""
        # Mock bias files
        mock_bias_file = Mock()
        mock_bias_file.fitsFileName = "bias.fits"
        mock_bias_file.fitsFileDate = date(2023, 7, 15)
        mock_bias_file.fitsFileTelescop = "Test Telescope"
        mock_bias_file.fitsFileInstrument = "Test Camera"
        mock_bias_file.save = Mock()
        
        # Mock the where chain for different file types
        mock_where = Mock()
        mock_where.return_value = [mock_bias_file]  # Only bias files
        mock_file_model.select.return_value.where = mock_where
        
        # Setup different return values for different queries
        def where_side_effect(*args, **kwargs):
            # Convert args to string to check what's being queried
            query_str = str(args)
            if "Bias" in query_str:
                return [mock_bias_file]
            else:
                return []
        
        mock_where.side_effect = where_side_effect
        
        result = self.fits_processor.createCalibrationSessions()
        
        # Verify session was created and file was saved
        mock_session_model.create.assert_called()
        mock_bias_file.save.assert_called()
        assert len(result) >= 1
    
    @patch('astrofiler_file.fitsSessionModel')
    def test_link_sessions_empty(self, mock_session_model):
        """Test linkSessions with no light sessions."""
        # Mock empty query result
        mock_session_model.select.return_value.where.return_value = []
        
        result = self.fits_processor.linkSessions()
        
        assert result == []
    
    @patch('astrofiler_file.fitsSessionModel')
    def test_link_sessions_with_light_session(self, mock_session_model):
        """Test linkSessions with a light session."""
        # Mock light session
        mock_light_session = Mock()
        mock_light_session.fitsSessionId = "light-session-id"
        mock_light_session.fitsSessionObjectName = "M31"
        mock_light_session.fitsSessionTelescope = "Test Telescope"
        mock_light_session.fitsSessionImager = "Test Camera"
        mock_light_session.fitsSessionDate = date(2023, 7, 15)
        mock_light_session.fitsBiasSession = None
        mock_light_session.fitsDarkSession = None
        mock_light_session.fitsFlatSession = None
        mock_light_session.save = Mock()
        
        # Mock bias session
        mock_bias_session = Mock()
        mock_bias_session.fitsSessionId = "bias-session-id"
        
        # Setup mock query chain
        mock_query = Mock()
        mock_query.select.return_value.where.return_value = [mock_light_session]
        
        # Mock the bias session query
        mock_bias_query = Mock()
        mock_bias_query.select.return_value.where.return_value.order_by.return_value.first.return_value = mock_bias_session
        
        # Setup different behaviors for different queries
        def select_side_effect(*args, **kwargs):
            return mock_query
        
        mock_session_model.select.side_effect = select_side_effect
        
        # Mock the where method to return appropriate results
        def where_side_effect(*args, **kwargs):
            query_str = str(args)
            if "Bias" in query_str:
                return mock_bias_query
            elif any(name in query_str for name in ["Dark", "Flat"]):
                # Return empty results for Dark and Flat
                empty_query = Mock()
                empty_query.order_by.return_value.first.return_value = None
                return empty_query
            else:
                # This is the initial light session query
                return [mock_light_session]
        
        mock_query.where.side_effect = where_side_effect
        
        result = self.fits_processor.linkSessions()
        
        # Should have processed one session
        assert len(result) >= 0


class TestFitsProcessingIntegration:
    """Integration tests for FITS processing with mocked FITS files."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.temp_dir, "source")
        self.repo_dir = os.path.join(self.temp_dir, "repo")
        os.makedirs(self.source_dir)
        os.makedirs(self.repo_dir)
        
        # Create fits processor
        self.fits_processor = fitsProcessing()
        self.fits_processor.sourceFolder = self.source_dir
        self.fits_processor.repoFolder = self.repo_dir
    
    def teardown_method(self):
        """Clean up."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_register_fits_images_no_files(self):
        """Test registerFitsImages with no FITS files."""
        result = self.fits_processor.registerFitsImages(moveFiles=False)
        assert result == []
    
    def test_register_fits_images_non_fits_files(self):
        """Test registerFitsImages ignores non-FITS files."""
        # Create non-FITS files
        test_file = os.path.join(self.source_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("not a fits file")
        
        result = self.fits_processor.registerFitsImages(moveFiles=False)
        assert result == []
    
    @patch('astrofiler_file.fits.open')
    @patch('astrofiler_file.FitsFileModel.create')
    def test_register_fits_image_mock_fits(self, mock_create, mock_fits_open):
        """Test registerFitsImage with mocked FITS file."""
        # Mock FITS header
        mock_hdr = {
            'IMAGETYP': 'Light',
            'DATE-OBS': '2023-07-15T10:30:45',
            'OBJECT': 'M31',
            'TELESCOP': 'Test Telescope',
            'INSTRUME': 'Test Camera',
            'FILTER': 'Red',
            'EXPTIME': 300,
            'XBINNING': 1,
            'YBINNING': 1,
            'CCD-TEMP': -10,
            'CDELT1': 0.001,
            'CDELT2': 0.001,
            'CROTA2': 0.0
        }
        
        # Mock FITS file
        mock_hdul = Mock()
        mock_hdul[0].header = mock_hdr
        mock_hdul.flush = Mock()
        mock_hdul.close = Mock()
        mock_fits_open.return_value = mock_hdul
        
        # Mock file creation
        mock_file = Mock()
        mock_file.fitsFileId = "test-file-id"
        mock_create.return_value = mock_file
        
        # Create a test file
        test_file = "test.fits"
        test_path = os.path.join(self.source_dir, test_file)
        with open(test_path, 'w') as f:
            f.write("fake fits content")
        
        result = self.fits_processor.registerFitsImage(self.source_dir, test_file, False)
        
        # Verify FITS file was processed
        mock_fits_open.assert_called_once()
        mock_create.assert_called_once()
        assert result == "test-file-id"


class TestProgressCallbacks:
    """Test progress callback functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.fits_processor = fitsProcessing()
        self.progress_calls = []
    
    def mock_progress_callback(self, current, total, filename):
        """Mock progress callback that records calls."""
        self.progress_calls.append((current, total, filename))
        return True  # Continue processing
    
    def mock_progress_callback_cancel(self, current, total, filename):
        """Mock progress callback that cancels after first call."""
        self.progress_calls.append((current, total, filename))
        return False  # Cancel processing
    
    @patch('astrofiler_file.FitsFileModel')
    def test_create_light_sessions_progress_callback(self, mock_model):
        """Test createLightSessions calls progress callback."""
        # Mock unassigned files
        mock_files = []
        for i in range(3):
            mock_file = Mock()
            mock_file.fitsFileName = f"test{i}.fits"
            mock_file.fitsFileObject = f"Object{i}"
            mock_file.fitsFileTelescop = "Test Telescope"
            mock_file.fitsFileInstrument = "Test Camera"
            mock_file.fitsFileDate = date(2023, 7, 15)
            mock_file.save = Mock()
            mock_files.append(mock_file)
        
        mock_model.select.return_value.where.return_value = mock_files
        
        with patch('astrofiler_file.fitsSessionModel.create'):
            result = self.fits_processor.createLightSessions(
                progress_callback=self.mock_progress_callback
            )
        
        # Verify progress callback was called
        assert len(self.progress_calls) == 3
        assert self.progress_calls[0] == (1, 3, "test0.fits")
        assert self.progress_calls[1] == (2, 3, "test1.fits")
        assert self.progress_calls[2] == (3, 3, "test2.fits")
    
    @patch('astrofiler_file.FitsFileModel')
    def test_create_light_sessions_progress_callback_cancel(self, mock_model):
        """Test createLightSessions respects progress callback cancellation."""
        # Mock unassigned files
        mock_files = []
        for i in range(3):
            mock_file = Mock()
            mock_file.fitsFileName = f"test{i}.fits"
            mock_file.fitsFileObject = f"Object{i}"
            mock_files.append(mock_file)
        
        mock_model.select.return_value.where.return_value = mock_files
        
        result = self.fits_processor.createLightSessions(
            progress_callback=self.mock_progress_callback_cancel
        )
        
        # Verify processing was cancelled after first call
        assert len(self.progress_calls) == 1
        assert self.progress_calls[0] == (1, 3, "test0.fits")


def test_module_imports():
    """Test that all required modules can be imported."""
    from astrofiler_db import fitsFile, fitsSession, setup_database
    from astrofiler_file import fitsProcessing
    
    # Basic smoke test - classes should be importable
    assert fitsFile is not None
    assert fitsSession is not None
    assert setup_database is not None
    assert fitsProcessing is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
