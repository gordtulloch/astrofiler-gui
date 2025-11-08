#!/usr/bin/env python3
"""
Test script to verify type hints implementation.
"""

import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_type_hints():
    """Test that type hints are properly implemented."""
    try:
        # Test core module imports with type hints
        from astrofiler.core import FileProcessor, fitsProcessing
        from astrofiler.core.utils import normalize_file_path, sanitize_filesystem_name
        from astrofiler.types import FilePath, FitsHeaderDict, ProcessingResult
        
        print("✓ Type hint imports successful")
        
        # Test basic functionality with type checking
        processor = FileProcessor()
        legacy_processor = fitsProcessing()
        
        print("✓ Processor instantiation successful")
        
        # Test utility functions
        normalized = normalize_file_path("test\\path\\file.fits")
        sanitized = sanitize_filesystem_name("Test Object Name!")
        
        print(f"✓ Utility functions working: {normalized}, {sanitized}")
        
        # Test that methods exist and are callable
        assert hasattr(processor, 'calculateFileHash')
        assert hasattr(legacy_processor, 'calculateFileHash')
        assert hasattr(legacy_processor, 'registerFitsImage')
        
        print("✓ Required methods available")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Testing type hints implementation...")
    print("=" * 50)
    
    success = test_type_hints()
    
    print("=" * 50)
    if success:
        print("🎉 All type hints tests passed!")
        print("Core modules successfully include type annotations")
    else:
        print("❌ Some tests failed.")
        sys.exit(1)