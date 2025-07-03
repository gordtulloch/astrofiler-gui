#!/usr/bin/env python3
"""
Quick validation script to test core AstroFiler functionality.
This script performs basic validation of the most important functions.
"""

import sys
import os
import tempfile
import shutil
from datetime import datetime, date

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def validate_imports():
    """Validate that core modules can be imported."""
    try:
        from astrofiler_file import fitsProcessing
        from astrofiler_db import fitsFile, fitsSession, setup_database
        print("✓ All core modules imported successfully")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def validate_date_functions():
    """Validate date helper functions."""
    try:
        from astrofiler_file import fitsProcessing
        processor = fitsProcessing()
        
        # Test dateToString
        test_datetime = datetime(2023, 7, 15, 10, 30, 45)
        result = processor.dateToString(test_datetime)
        assert result == "2023-07-15", f"Expected '2023-07-15', got '{result}'"
        
        # Test dateToDateField
        result = processor.dateToDateField("2023-07-15T10:30:45")
        assert result == date(2023, 7, 15), f"Expected date(2023, 7, 15), got {result}"
        
        # Test sameDay
        assert processor.sameDay("2023-07-15", "2023-07-15") == True
        assert processor.sameDay("2023-07-15", "2023-07-17") == False
        
        print("✓ Date helper functions working correctly")
        return True
    except Exception as e:
        print(f"✗ Date function error: {e}")
        return False

def validate_file_hash():
    """Validate file hash calculation."""
    try:
        from astrofiler_file import fitsProcessing
        processor = fitsProcessing()
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name
        
        try:
            # Calculate hash
            hash_value = processor.calculateFileHash(tmp_path)
            assert hash_value is not None, "Hash should not be None"
            assert len(hash_value) == 64, f"Hash should be 64 characters, got {len(hash_value)}"
            
            # Test consistency
            hash_value2 = processor.calculateFileHash(tmp_path)
            assert hash_value == hash_value2, "Hash should be consistent"
            
            print("✓ File hash calculation working correctly")
            return True
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        print(f"✗ File hash error: {e}")
        return False

def validate_configuration():
    """Validate configuration handling."""
    try:
        from astrofiler_file import fitsProcessing
        processor = fitsProcessing()
        
        # Check that processor has required attributes
        assert hasattr(processor, 'sourceFolder'), "Missing sourceFolder attribute"
        assert hasattr(processor, 'repoFolder'), "Missing repoFolder attribute"
        
        print("✓ Configuration handling working correctly")
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def main():
    """Run all validation tests."""
    print("AstroFiler Quick Validation")
    print("=" * 40)
    
    tests = [
        ("Core Module Imports", validate_imports),
        ("Date Helper Functions", validate_date_functions),
        ("File Hash Calculation", validate_file_hash),
        ("Configuration Handling", validate_configuration),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\nTesting {test_name}...")
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
    
    print(f"\n" + "=" * 40)
    print(f"Validation Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All validation tests passed! AstroFiler core functionality is working correctly.")
        return 0
    else:
        print("⚠️  Some validation tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
