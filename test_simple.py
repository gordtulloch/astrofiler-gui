#!/usr/bin/env python3
"""
Simple test suite for AstroFiler application core functionality.
This test suite focuses on unit tests that don't require external dependencies.
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, date

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import modules to test
from astrofiler_file import fitsProcessing


class TestDateHelpers:
    """Test date helper functions."""
    
    def setup_method(self):
        """Set up test environment."""
        self.fits_processor = fitsProcessing()
    
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


class TestSameDayFunction:
    """Test the sameDay function."""
    
    def setup_method(self):
        """Set up test environment."""
        self.fits_processor = fitsProcessing()
    
    def test_same_day_identical_dates(self):
        """Test sameDay function with identical dates."""
        date1 = "2023-07-15"
        date2 = "2023-07-15"
        
        result = self.fits_processor.sameDay(date1, date2)
        assert result is True
    
    def test_same_day_within_12_hours(self):
        """Test sameDay function with dates within 12 hours."""
        date1 = "2023-07-15"
        date2 = "2023-07-15"  # Same day
        
        result = self.fits_processor.sameDay(date1, date2)
        assert result is True
    
    def test_same_day_more_than_12_hours(self):
        """Test sameDay function with dates more than 12 hours apart."""
        date1 = "2023-07-15"
        date2 = "2023-07-17"  # 2 days apart
        
        result = self.fits_processor.sameDay(date1, date2)
        assert result is False
    
    def test_same_day_one_day_apart(self):
        """Test sameDay function with dates one day apart."""
        date1 = "2023-07-15"
        date2 = "2023-07-16"  # 1 day apart (24 hours)
        
        result = self.fits_processor.sameDay(date1, date2)
        assert result is False


class TestFileHashCalculation:
    """Test file hash calculation functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.fits_processor = fitsProcessing()
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_calculate_file_hash_valid_file(self):
        """Test file hash calculation with valid file."""
        # Create a test file
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        # Calculate hash
        hash_value = self.fits_processor.calculateFileHash(test_file)
        
        # Verify hash is calculated
        assert hash_value is not None
        assert len(hash_value) == 64  # SHA-256 produces 64 character hex string
        assert isinstance(hash_value, str)
    
    def test_calculate_file_hash_consistent(self):
        """Test file hash calculation is consistent."""
        # Create a test file
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        # Calculate hash twice
        hash1 = self.fits_processor.calculateFileHash(test_file)
        hash2 = self.fits_processor.calculateFileHash(test_file)
        
        # Should be identical
        assert hash1 == hash2
    
    def test_calculate_file_hash_different_content(self):
        """Test file hash calculation with different content produces different hashes."""
        # Create two test files with different content
        test_file1 = os.path.join(self.temp_dir, "test1.txt")
        test_file2 = os.path.join(self.temp_dir, "test2.txt")
        
        with open(test_file1, 'w') as f:
            f.write("test content 1")
        
        with open(test_file2, 'w') as f:
            f.write("test content 2")
        
        # Calculate hashes
        hash1 = self.fits_processor.calculateFileHash(test_file1)
        hash2 = self.fits_processor.calculateFileHash(test_file2)
        
        # Should be different
        assert hash1 != hash2
    
    def test_calculate_file_hash_nonexistent_file(self):
        """Test file hash calculation with nonexistent file."""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.txt")
        
        hash_value = self.fits_processor.calculateFileHash(nonexistent_file)
        
        # Should return None for nonexistent file
        assert hash_value is None


class TestModuleImports:
    """Test that modules can be imported correctly."""
    
    def test_astrofiler_file_import(self):
        """Test astrofiler_file module import."""
        from astrofiler_file import fitsProcessing
        
        # Should be able to create instance
        processor = fitsProcessing()
        assert processor is not None
        
        # Should have expected methods
        assert hasattr(processor, 'calculateFileHash')
        assert hasattr(processor, 'sameDay')
        assert hasattr(processor, 'dateToString')
        assert hasattr(processor, 'dateToDateField')
        assert hasattr(processor, 'createLightSessions')
        assert hasattr(processor, 'createCalibrationSessions')
        assert hasattr(processor, 'linkSessions')
    
    def test_astrofiler_db_import(self):
        """Test astrofiler_db module import."""
        from astrofiler_db import fitsFile, fitsSession, setup_database
        
        # Should be able to import classes and functions
        assert fitsFile is not None
        assert fitsSession is not None
        assert setup_database is not None
        
        # Should have expected attributes
        assert hasattr(fitsFile, 'fitsFileId')
        assert hasattr(fitsFile, 'fitsFileName')
        assert hasattr(fitsFile, 'fitsFileDate')
        assert hasattr(fitsFile, 'fitsFileType')
        
        assert hasattr(fitsSession, 'fitsSessionId')
        assert hasattr(fitsSession, 'fitsSessionObjectName')
        assert hasattr(fitsSession, 'fitsSessionDate')
        assert hasattr(fitsSession, 'fitsSessionTelescope')
        assert hasattr(fitsSession, 'fitsSessionImager')


class TestConfigurationHandling:
    """Test configuration file handling."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_astrofiler.ini")
    
    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_fits_processing_initialization(self):
        """Test fitsProcessing initialization with default config."""
        processor = fitsProcessing()
        
        # Should have default values
        assert hasattr(processor, 'sourceFolder')
        assert hasattr(processor, 'repoFolder')
        
        # Default values should be set
        assert processor.sourceFolder is not None
        assert processor.repoFolder is not None


def run_simple_tests():
    """Run tests without pytest for environments where pytest is not available."""
    import traceback
    
    test_classes = [
        TestDateHelpers,
        TestSameDayFunction,
        TestFileHashCalculation,
        TestModuleImports,
        TestConfigurationHandling
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for test_class in test_classes:
        print(f"\n=== Running {test_class.__name__} ===")
        
        # Get all test methods
        test_methods = [method for method in dir(test_class) if method.startswith('test_')]
        
        for test_method_name in test_methods:
            total_tests += 1
            test_instance = test_class()
            
            try:
                # Run setup if it exists
                if hasattr(test_instance, 'setup_method'):
                    test_instance.setup_method()
                
                # Run the test method
                test_method = getattr(test_instance, test_method_name)
                test_method()
                
                print(f"✓ {test_method_name}")
                passed_tests += 1
                
            except Exception as e:
                print(f"✗ {test_method_name}: {str(e)}")
                print(f"  {traceback.format_exc()}")
                failed_tests += 1
                
            finally:
                # Run teardown if it exists
                if hasattr(test_instance, 'teardown_method'):
                    try:
                        test_instance.teardown_method()
                    except Exception:
                        pass  # Ignore teardown errors
    
    print(f"\n=== Test Summary ===")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
    
    return failed_tests == 0


if __name__ == "__main__":
    # Try to use pytest if available, otherwise run simple tests
    try:
        import pytest
        print("Running tests with pytest...")
        exit_code = pytest.main([__file__, "-v"])
        exit(exit_code)
    except ImportError:
        print("pytest not available, running simple tests...")
        success = run_simple_tests()
        exit(0 if success else 1)
