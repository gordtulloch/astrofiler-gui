"""
Tests for astrofiler_db.py - Database module
"""
import pytest
import os
import tempfile
from unittest.mock import patch, Mock
import peewee as pw

from astrofiler_db import fitsFile, fitsSequence, setup_database, db


class TestDatabaseModels:
    """Test the database model definitions."""
    
    def test_fits_file_model_fields(self):
        """Test that fitsFile model has all required fields."""
        expected_fields = [
            'fitsFileId', 'fitsFileName', 'fitsFileDate', 'fitsFileCalibrated',
            'fitsFileType', 'fitsFileStacked', 'fitsFileObject', 'fitsFileExpTime',
            'fitsFileXBinning', 'fitsFileYBinning', 'fitsFileCCDTemp',
            'fitsFileTelescop', 'fitsFileInstrument', 'fitsFileGain',
            'fitsFileOffset', 'fitsFileSequence'
        ]
        
        model_fields = list(fitsFile._meta.fields.keys())
        
        for field in expected_fields:
            assert field in model_fields, f"Field {field} not found in fitsFile model"
    
    def test_fits_sequence_model_fields(self):
        """Test that fitsSequence model has all required fields."""
        expected_fields = [
            'fitsSequenceId', 'fitsSequenceObjectName', 'fitsSequenceDate',
            'fitsSequenceTelescope', 'fitsSequenceImager', 'fitsMasterBias',
            'fitsMasterDark', 'fitsMasterFlat'
        ]
        
        model_fields = list(fitsSequence._meta.fields.keys())
        
        for field in expected_fields:
            assert field in model_fields, f"Field {field} not found in fitsSequence model"
    
    def test_fits_file_primary_key(self):
        """Test that fitsFile has correct primary key."""
        assert fitsFile._meta.primary_key.name == 'fitsFileId'
    
    def test_fits_sequence_primary_key(self):
        """Test that fitsSequence has correct primary key."""
        assert fitsSequence._meta.primary_key.name == 'fitsSequenceId'


class TestDatabaseSetup:
    """Test database setup functionality."""
    
    @patch('astrofiler_db.db')
    def test_setup_database_success(self, mock_db):
        """Test successful database setup."""
        mock_db.connect.return_value = None
        mock_db.create_tables.return_value = None
        mock_db.close.return_value = None
        
        setup_database()
        
        mock_db.connect.assert_called_once()
        mock_db.create_tables.assert_called_once_with([fitsFile, fitsSequence])
        mock_db.close.assert_called_once()
    
    @patch('astrofiler_db.db')
    @patch('astrofiler_db.logger')
    def test_setup_database_error(self, mock_logger, mock_db):
        """Test database setup error handling."""
        mock_db.connect.side_effect = pw.OperationalError("Test error")
        
        setup_database()
        
        mock_logger.error.assert_called_once()
    
    def test_database_file_path(self):
        """Test that database points to correct file."""
        assert db.database == 'astrofiler.db'


class TestDatabaseOperations:
    """Test database CRUD operations."""
    
    @pytest.fixture
    def in_memory_db(self):
        """Create an in-memory database for testing."""
        test_db = pw.SqliteDatabase(':memory:')
        
        # Bind models to test database
        fitsFile._meta.database = test_db
        fitsSequence._meta.database = test_db
        
        # Create tables
        test_db.create_tables([fitsFile, fitsSequence])
        
        yield test_db
        
        # Cleanup
        test_db.close()
    
    def test_create_fits_file(self, in_memory_db):
        """Test creating a FITS file record."""
        fits_record = fitsFile.create(
            fitsFileId='test-id-123',
            fitsFileName='test.fits',
            fitsFileDate='2023-01-01T20:00:00',
            fitsFileType='Light',
            fitsFileObject='M31'
        )
        
        assert fits_record.fitsFileId == 'test-id-123'
        assert fits_record.fitsFileName == 'test.fits'
        assert fits_record.fitsFileObject == 'M31'
    
    def test_create_fits_sequence(self, in_memory_db):
        """Test creating a FITS sequence record."""
        sequence_record = fitsSequence.create(
            fitsSequenceId='seq-123',
            fitsSequenceObjectName='M31',
            fitsSequenceDate='2023-01-01T20:00:00',
            fitsSequenceTelescope='Test Telescope',
            fitsSequenceImager='Test Camera'
        )
        
        assert sequence_record.fitsSequenceId == 'seq-123'
        assert sequence_record.fitsSequenceObjectName == 'M31'
        assert sequence_record.fitsSequenceTelescope == 'Test Telescope'
    
    def test_query_fits_files(self, in_memory_db):
        """Test querying FITS file records."""
        # Create test records
        fitsFile.create(
            fitsFileId='test-1',
            fitsFileName='test1.fits',
            fitsFileObject='M31'
        )
        fitsFile.create(
            fitsFileId='test-2',
            fitsFileName='test2.fits',
            fitsFileObject='M42'
        )
        
        # Query all records
        all_files = list(fitsFile.select())
        assert len(all_files) == 2
        
        # Query specific record
        m31_files = list(fitsFile.select().where(fitsFile.fitsFileObject == 'M31'))
        assert len(m31_files) == 1
        assert m31_files[0].fitsFileId == 'test-1'
