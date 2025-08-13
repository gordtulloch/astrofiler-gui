#!/usr/bin/env python3
"""
Tests for the Mapping functionality in AstroFiler application.
"""
import os
import sys
import pytest
import uuid
from unittest.mock import patch, MagicMock
import peewee as pw

# Add the parent directory to the path to import the application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from astrofiler_db import setup_database, fitsSession, fitsFile, Mapping

class TestMappingFunctionality:
    """Test the Mapping functionality of the AstroFiler application."""
    
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Set up a temporary database for testing."""
        # Create a temporary database file
        db_path = str(tmp_path / "test_mapping.db")
        
        # Import the database modules to patch them
        import astrofiler_db
        
        # Create a new database instance for testing
        test_db = pw.SqliteDatabase(db_path)
        
        # Patch the global database instance
        original_db = astrofiler_db.db
        astrofiler_db.db = test_db
        astrofiler_db.fitsFile._meta.database = test_db
        astrofiler_db.fitsSession._meta.database = test_db
        astrofiler_db.Mapping._meta.database = test_db
        
        # Setup the database tables
        test_db.connect()
        test_db.create_tables([astrofiler_db.fitsFile, astrofiler_db.fitsSession, astrofiler_db.Mapping])
        
        yield
        
        # Clean up after the test
        test_db.close()
        astrofiler_db.db = original_db
        astrofiler_db.fitsFile._meta.database = original_db
        astrofiler_db.fitsSession._meta.database = original_db
        astrofiler_db.Mapping._meta.database = original_db
        
        if os.path.exists(db_path):
            os.remove(db_path)
    
    def test_mapping_model_creation(self):
        """Test creating a Mapping model instance."""
        # Create a test mapping
        mapping = Mapping.create(
            card='TELESCOP',
            current='Old Telescope',
            replace='New Telescope',
            is_default=False
        )
        
        # Verify the mapping was created
        assert mapping.id is not None
        assert mapping.card == 'TELESCOP'
        assert mapping.current == 'Old Telescope'
        assert mapping.replace == 'New Telescope'
        assert mapping.is_default is False
    
    def test_mapping_model_retrieval(self):
        """Test retrieving a Mapping model instance."""
        # Create a test mapping
        original_mapping = Mapping.create(
            card='INSTRUME',
            current='Old Camera',
            replace='New Camera',
            is_default=True
        )
        
        # Retrieve the mapping
        retrieved_mapping = Mapping.get_by_id(original_mapping.id)
        
        # Verify the retrieved mapping matches
        assert retrieved_mapping.card == 'INSTRUME'
        assert retrieved_mapping.current == 'Old Camera'
        assert retrieved_mapping.replace == 'New Camera'
        assert retrieved_mapping.is_default is True
    
    def test_mapping_model_update(self):
        """Test updating a Mapping model instance."""
        # Create a test mapping
        mapping = Mapping.create(
            card='OBSERVER',
            current='John Doe',
            replace='Jane Smith',
            is_default=False
        )
        
        # Update the mapping
        mapping.replace = 'Updated Observer'
        mapping.is_default = True
        mapping.save()
        
        # Retrieve and verify the update
        updated_mapping = Mapping.get_by_id(mapping.id)
        assert updated_mapping.replace == 'Updated Observer'
        assert updated_mapping.is_default is True
    
    def test_mapping_model_deletion(self):
        """Test deleting a Mapping model instance."""
        # Create a test mapping
        mapping = Mapping.create(
            card='NOTES',
            current='Old Note',
            replace='New Note',
            is_default=False
        )
        mapping_id = mapping.id
        
        # Delete the mapping
        mapping.delete_instance()
        
        # Verify the mapping was deleted
        with pytest.raises(Mapping.DoesNotExist):
            Mapping.get_by_id(mapping_id)
    
    def test_mapping_null_values(self):
        """Test mapping with null/empty values."""
        # Create mapping with null current value (for default mappings)
        mapping = Mapping.create(
            card='TELESCOP',
            current=None,
            replace='Default Telescope',
            is_default=True
        )
        
        # Verify null values are handled correctly
        assert mapping.current is None
        assert mapping.replace == 'Default Telescope'
        assert mapping.is_default is True
        
        # Create mapping with empty replace value
        mapping2 = Mapping.create(
            card='INSTRUME',
            current='Remove This',
            replace=None,
            is_default=False
        )
        
        assert mapping2.current == 'Remove This'
        assert mapping2.replace is None
    
    def test_mapping_query_by_card(self):
        """Test querying mappings by card type."""
        # Create multiple mappings
        Mapping.create(card='TELESCOP', current='Tel1', replace='Telescope 1', is_default=False)
        Mapping.create(card='TELESCOP', current='Tel2', replace='Telescope 2', is_default=False)
        Mapping.create(card='INSTRUME', current='Cam1', replace='Camera 1', is_default=False)
        
        # Query by card type
        telescope_mappings = Mapping.select().where(Mapping.card == 'TELESCOP')
        instrument_mappings = Mapping.select().where(Mapping.card == 'INSTRUME')
        
        # Verify results
        assert len(telescope_mappings) == 2
        assert len(instrument_mappings) == 1
        
        # Verify content
        tel_values = [m.current for m in telescope_mappings]
        assert 'Tel1' in tel_values
        assert 'Tel2' in tel_values
    
    def test_mapping_bulk_operations(self):
        """Test bulk operations on mappings."""
        # Create multiple mappings
        mappings_data = [
            {'card': 'TELESCOP', 'current': 'T1', 'replace': 'Telescope 1', 'is_default': False},
            {'card': 'TELESCOP', 'current': 'T2', 'replace': 'Telescope 2', 'is_default': False},
            {'card': 'INSTRUME', 'current': 'C1', 'replace': 'Camera 1', 'is_default': False},
        ]
        
        for data in mappings_data:
            Mapping.create(**data)
        
        # Verify all were created
        all_mappings = Mapping.select()
        assert len(all_mappings) == 3
        
        # Bulk delete by card type
        deleted_count = Mapping.delete().where(Mapping.card == 'TELESCOP').execute()
        assert deleted_count == 2
        
        # Verify only instrument mapping remains
        remaining_mappings = Mapping.select()
        assert len(remaining_mappings) == 1
        assert remaining_mappings[0].card == 'INSTRUME'
    
    def test_mapping_with_fits_files(self):
        """Test mapping functionality with actual FITS file records."""
        # Create test FITS file records
        fits_file1 = fitsFile.create(
            fitsFileId='test-file-1',
            fitsFileName='/path/to/file1.fits',
            fitsFileTelescop='Old Telescope',
            fitsFileInstrument='Old Camera'
        )
        
        fits_file2 = fitsFile.create(
            fitsFileId='test-file-2',
            fitsFileName='/path/to/file2.fits',
            fitsFileTelescop='Old Telescope',
            fitsFileInstrument='Different Camera'
        )
        
        # Create mapping
        mapping = Mapping.create(
            card='TELESCOP',
            current='Old Telescope',
            replace='New Telescope',
            is_default=False
        )
        
        # Simulate applying the mapping
        files_to_update = fitsFile.select().where(fitsFile.fitsFileTelescop == mapping.current)
        update_count = 0
        
        for fits_file in files_to_update:
            fits_file.fitsFileTelescop = mapping.replace
            fits_file.save()
            update_count += 1
        
        # Verify updates
        assert update_count == 2
        
        # Verify all files now have the new telescope name
        updated_files = fitsFile.select().where(fitsFile.fitsFileTelescop == 'New Telescope')
        assert len(updated_files) == 2


class TestMappingDialogImports:
    """Test that the MappingsDialog can be imported and initialized."""
    
    def test_mappings_dialog_import(self):
        """Test that MappingsDialog can be imported."""
        try:
            from astrofiler_gui import MappingsDialog
            assert MappingsDialog is not None
        except ImportError as e:
            pytest.fail(f"Failed to import MappingsDialog: {e}")
    
    def test_qt_dependencies_available(self):
        """Test that required Qt dependencies are available."""
        try:
            from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QGridLayout
            from PySide6.QtCore import Qt
            assert QApplication is not None
            assert QDialog is not None
            assert QDialogButtonBox is not None
            assert QGridLayout is not None
            assert Qt is not None
        except ImportError as e:
            pytest.fail(f"Failed to import required Qt components: {e}")
    
    @pytest.mark.skipif(
        os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true',
        reason="Skip GUI tests in CI environment"
    )
    def test_mappings_dialog_creation(self):
        """Test that MappingsDialog can be created (skip in CI)."""
        try:
            from PySide6.QtWidgets import QApplication
            from astrofiler_gui import MappingsDialog
            
            # Create QApplication if it doesn't exist
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            # Create dialog instance
            dialog = MappingsDialog()
            assert dialog is not None
            assert dialog.windowTitle() == "Mappings"
            
            # Clean up
            dialog.close()
            
        except ImportError as e:
            pytest.skip(f"GUI dependencies not available: {e}")
        except Exception as e:
            pytest.fail(f"Failed to create MappingsDialog: {e}")
    
    @pytest.mark.skipif(
        os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true',
        reason="Skip GUI tests in CI environment"
    )
    def test_add_mapping_row_no_args(self):
        """Test that add_mapping_row works when called without arguments (like from button click)."""
        try:
            from PySide6.QtWidgets import QApplication
            from astrofiler_gui import MappingsDialog
            
            # Create QApplication if it doesn't exist
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            # Create dialog instance
            dialog = MappingsDialog()
            
            # Record the initial number of rows (may have existing mappings from database)
            initial_rows = len(dialog.mapping_rows)
            
            # This should not raise a TypeError
            dialog.add_mapping_row()
            
            # Verify a row was added
            assert len(dialog.mapping_rows) == initial_rows + 1
            
            # Verify the new row has the default card type
            new_row = dialog.mapping_rows[-1]  # Get the last (newest) row
            assert new_row.card_combo.currentText() == "TELESCOP"
            
            # Clean up
            dialog.close()
            
        except ImportError as e:
            pytest.skip(f"GUI dependencies not available: {e}")
        except Exception as e:
            pytest.fail(f"Failed to add mapping row without arguments: {e}")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
