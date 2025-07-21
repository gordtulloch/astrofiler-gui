#!/usr/bin/env python3
"""
Basic tests for the AstroFiler application.
"""
import os
import sys
import pytest
import uuid
from unittest.mock import patch, MagicMock
import peewee as pw

# Add the parent directory to the path to import the application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from astrofiler_db import setup_database, fitsSession, fitsFile

class TestBasicFunctionality:
    """Test basic functionality of the AstroFiler application."""
    
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Set up a temporary database for testing."""
        # Create a temporary database file
        db_path = str(tmp_path / "test.db")
        
        # Import the database modules to patch them
        import astrofiler_db
        
        # Create a new database instance for testing
        test_db = pw.SqliteDatabase(db_path)
        
        # Patch the global database instance
        original_db = astrofiler_db.db
        astrofiler_db.db = test_db
        astrofiler_db.fitsFile._meta.database = test_db
        astrofiler_db.fitsSession._meta.database = test_db
        
        # Setup the database tables
        test_db.connect()
        test_db.create_tables([astrofiler_db.fitsFile, astrofiler_db.fitsSession])
        
        yield
        
        # Clean up after the test
        test_db.close()
        astrofiler_db.db = original_db
        astrofiler_db.fitsFile._meta.database = original_db
        astrofiler_db.fitsSession._meta.database = original_db
        
        if os.path.exists(db_path):
            os.remove(db_path)
    
    def test_database_creation(self, tmp_path):
        """Test database initialization."""
        # Create a temporary database file
        db_path = str(tmp_path / "test_creation.db")
        
        # Mock the database setup to use the temporary file
        with patch('astrofiler_db.db', pw.SqliteDatabase(db_path)):
            setup_database()
            
            # Check if the database file was created
            assert os.path.exists(db_path)
    
    def test_session_creation(self):
        """Test creating a session."""
        # Create a new session
        session_id = str(uuid.uuid4())
        session = fitsSession.create(
            fitsSessionId=session_id,
            fitsSessionObjectName="TestObject",
            fitsSessionDate="2025-07-17",
            fitsSessionImager="TestImager",
            fitsSessionTelescope="TestTelescope"
        )
        
        # Check if the session was created
        assert session.fitsSessionObjectName == "TestObject"
        assert session.fitsSessionDate == "2025-07-17"
        assert session.fitsSessionImager == "TestImager"
        assert session.fitsSessionTelescope == "TestTelescope"
        
        # Check if the session can be retrieved from the database
        retrieved_session = fitsSession.get(fitsSession.fitsSessionId == session.fitsSessionId)
        assert retrieved_session.fitsSessionObjectName == "TestObject"
    
    def test_file_creation_and_linking(self):
        """Test creating a file and linking it to a session."""
        # Create a new session
        session_id = str(uuid.uuid4())
        session = fitsSession.create(
            fitsSessionId=session_id,
            fitsSessionObjectName="TestObject",
            fitsSessionDate="2025-07-17"
        )
        
        # Create a new file with required fitsFileId
        file_id = str(uuid.uuid4())
        fits_file = fitsFile.create(
            fitsFileId=file_id,
            fitsFileName="/path/to/test_file.fits",
            fitsFileObject="TestObject",
            fitsFileDate="2025-07-17",
            fitsFileType="LIGHT",
            fitsFileSession=session.fitsSessionId
        )
        
        # Check if the file was created
        assert fits_file.fitsFileName == "/path/to/test_file.fits"
        assert fits_file.fitsFileObject == "TestObject"
        assert fits_file.fitsFileDate == "2025-07-17"
        assert fits_file.fitsFileType == "LIGHT"
        
        # Check if the file is linked to the session
        assert fits_file.fitsFileSession == session.fitsSessionId
        
        # Check if the file can be retrieved from the database
        retrieved_file = fitsFile.get(fitsFile.fitsFileId == fits_file.fitsFileId)
        assert retrieved_file.fitsFileName == "/path/to/test_file.fits"
        
        # Get files for the session
        session_files = list(fitsFile.select().where(
            fitsFile.fitsFileSession == session.fitsSessionId
        ))
        assert len(session_files) == 1
        assert session_files[0].fitsFileId == fits_file.fitsFileId
