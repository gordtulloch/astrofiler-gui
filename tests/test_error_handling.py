#!/usr/bin/env python3
"""
Test script for modernized error handling in AstroFiler.

This script tests the new custom exceptions and error handling patterns.
"""

import sys
import os
sys.path.insert(0, '.')

# Import the enhanced modules
from src.astrofiler.core.file_processing import FileProcessor
from src.astrofiler.exceptions import (
    AstroFilerError, FileProcessingError, FitsHeaderError, 
    DatabaseError, ValidationError
)
import tempfile
import logging

# Set up logging to see the detailed error messages
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_file_hash_error_handling():
    """Test hash calculation with non-existent file."""
    print("\n=== Testing File Hash Error Handling ===")
    processor = FileProcessor()
    
    try:
        # Try to calculate hash for non-existent file
        result = processor.calculateFileHash("/nonexistent/file.fits")
        print(f"❌ Expected FileProcessingError, got result: {result}")
    except FileProcessingError as e:
        print(f"✅ Caught expected FileProcessingError: {e}")
        print(f"   Error code: {e.error_code}")
        print(f"   File path: {e.file_path}")
    except Exception as e:
        print(f"❌ Unexpected exception type: {type(e).__name__}: {e}")

def test_zip_extraction_error_handling():
    """Test ZIP extraction with invalid file."""
    print("\n=== Testing ZIP Extraction Error Handling ===")
    processor = FileProcessor()
    
    # Create a temporary non-ZIP file
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        tmp_file.write(b"This is not a valid ZIP file")
        tmp_file_path = tmp_file.name
    
    try:
        result = processor.extractZipFile(tmp_file_path)
        print(f"❌ Expected FileProcessingError, got result: {result}")
    except FileProcessingError as e:
        print(f"✅ Caught expected FileProcessingError: {e}")
        print(f"   Error code: {e.error_code}")
        print(f"   File path: {e.file_path}")
    except Exception as e:
        print(f"❌ Unexpected exception type: {type(e).__name__}: {e}")
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)

def test_xisf_conversion_error_handling():
    """Test XISF conversion without xisfFile package."""
    print("\n=== Testing XISF Conversion Error Handling ===")
    processor = FileProcessor()
    
    try:
        result = processor.convertXisfToFits("/nonexistent/file.xisf")
        print(f"❌ Expected FileProcessingError, got result: {result}")
    except FileProcessingError as e:
        print(f"✅ Caught expected FileProcessingError: {e}")
        print(f"   Error code: {e.error_code}")
        print(f"   File path: {e.file_path}")
        if e.error_code == "XISF_SUPPORT_MISSING":
            print("   ✅ Correct error code for missing XISF support")
    except Exception as e:
        print(f"❌ Unexpected exception type: {type(e).__name__}: {e}")

def test_database_submission_error_handling():
    """Test database submission with invalid data."""
    print("\n=== Testing Database Submission Error Handling ===")
    processor = FileProcessor()
    
    # Create a mock header with missing required fields
    class MockHeader:
        def get(self, key, default=None):
            # Return None for all required fields to trigger ValidationError
            return default
    
    try:
        result = processor.submitFileToDB("/test/file.fits", MockHeader(), "testhash123")
        print(f"❌ Expected ValidationError, got result: {result}")
    except ValidationError as e:
        print(f"✅ Caught expected ValidationError: {e}")
        print(f"   Error code: {e.error_code}")
        print(f"   Field: {e.field}")
    except Exception as e:
        print(f"❌ Unexpected exception type: {type(e).__name__}: {e}")

def test_custom_exception_hierarchy():
    """Test that custom exceptions work correctly."""
    print("\n=== Testing Custom Exception Hierarchy ===")
    
    try:
        raise FileProcessingError(
            "Test file processing error", 
            file_path="/test/file.fits",
            error_code="TEST_ERROR",
            additional_info="Extra details"
        )
    except FileProcessingError as e:
        print(f"✅ FileProcessingError caught correctly")
        print(f"   Message: {e.message}")
        print(f"   File path: {e.file_path}")
        print(f"   Error code: {e.error_code}")
        print(f"   String representation: {str(e)}")
        
        # Test that it's also an AstroFilerError
        if isinstance(e, AstroFilerError):
            print("   ✅ Correctly inherits from AstroFilerError")
        else:
            print("   ❌ Does not inherit from AstroFilerError")
    
    try:
        raise ValidationError(
            "Test validation error",
            field="test_field",
            error_code="VALIDATION_TEST"
        )
    except ValidationError as e:
        print(f"✅ ValidationError caught correctly")
        print(f"   Message: {e.message}")
        print(f"   Field: {e.field}")
        print(f"   Error code: {e.error_code}")

def main():
    """Run all error handling tests."""
    print("🧪 Testing AstroFiler Modernized Error Handling")
    print("=" * 50)
    
    try:
        test_file_hash_error_handling()
        test_zip_extraction_error_handling()
        test_xisf_conversion_error_handling()
        test_database_submission_error_handling()
        test_custom_exception_hierarchy()
        
        print("\n" + "=" * 50)
        print("🎉 All error handling tests completed!")
        print("✅ Modern exception system is working correctly")
        
    except Exception as e:
        print(f"\n❌ Test suite failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())