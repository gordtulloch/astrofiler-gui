#!/usr/bin/env python3
"""
Test script to verify the refactored modules work correctly.

This script tests the basic functionality of the new modular structure
to ensure backwards compatibility is maintained.
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for setup_path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setup_path  # Configure Python path for new package structure

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all imports work correctly."""
    logger.info("Testing imports...")
    
    try:
        # Test core module imports
        from astrofiler.core import fitsProcessing
        from astrofiler.core import FileProcessor, CalibrationProcessor, QualityAnalyzer, RepositoryManager
        from astrofiler.core import normalize_file_path, sanitize_filesystem_name, dwarfFixHeader
        logger.info("✓ Core module imports successful")
        
        # Test individual module imports
        from astrofiler.core.utils import normalize_file_path, sanitize_filesystem_name
        from astrofiler.core.file_processing import FileProcessor
        from astrofiler.core.calibration import CalibrationProcessor
        from astrofiler.core.quality_analysis import QualityAnalyzer
        from astrofiler.core.repository import RepositoryManager
        logger.info("✓ Individual module imports successful")
        
        return True
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error during import: {e}")
        return False

def test_utility_functions():
    """Test utility functions work correctly."""
    logger.info("Testing utility functions...")
    
    try:
        from astrofiler.core import normalize_file_path, sanitize_filesystem_name
        
        # Test normalize_file_path
        test_path = "C:\\Users\\Test\\Image.fits"
        normalized = normalize_file_path(test_path)
        assert isinstance(normalized, str), "normalize_file_path should return string"
        logger.info("✓ normalize_file_path working")
        
        # Test sanitize_filesystem_name
        test_name = "M31 Andromeda/Galaxy*Test?"
        sanitized = sanitize_filesystem_name(test_name)
        assert isinstance(sanitized, str), "sanitize_filesystem_name should return string"
        assert "/" not in sanitized, "Sanitized name should not contain slashes"
        assert "*" not in sanitized, "Sanitized name should not contain asterisks"
        logger.info("✓ sanitize_filesystem_name working")
        
        return True
    except Exception as e:
        logger.error(f"✗ Utility function test failed: {e}")
        return False

def test_processor_classes():
    """Test that processor classes can be instantiated."""
    logger.info("Testing processor classes...")
    
    try:
        from astrofiler.core import fitsProcessing
        from astrofiler.core import FileProcessor, CalibrationProcessor, QualityAnalyzer, RepositoryManager
        
        # Test main fitsProcessing class
        processor = fitsProcessing()
        assert processor is not None, "fitsProcessing should instantiate"
        assert hasattr(processor, 'calculateFileHash'), "Should have calculateFileHash method"
        assert hasattr(processor, 'registerFitsImage'), "Should have registerFitsImage method"
        logger.info("✓ fitsProcessing class working")
        
        # Test individual classes
        file_proc = FileProcessor()
        assert file_proc is not None, "FileProcessor should instantiate"
        logger.info("✓ FileProcessor class working")
        
        calib_proc = CalibrationProcessor()
        assert calib_proc is not None, "CalibrationProcessor should instantiate"
        logger.info("✓ CalibrationProcessor class working")
        
        quality_analyzer = QualityAnalyzer()
        assert quality_analyzer is not None, "QualityAnalyzer should instantiate"
        logger.info("✓ QualityAnalyzer class working")
        
        repo_manager = RepositoryManager()
        assert repo_manager is not None, "RepositoryManager should instantiate"
        logger.info("✓ RepositoryManager class working")
        
        return True
    except Exception as e:
        logger.error(f"✗ Processor class test failed: {e}")
        return False

def test_backwards_compatibility():
    """Test backwards compatibility with original API."""
    logger.info("Testing backwards compatibility...")
    
    try:
        from astrofiler.core import fitsProcessing
        
        processor = fitsProcessing()
        
        # Test that original method signatures work
        assert hasattr(processor, 'calculateFileHash'), "Should have calculateFileHash"
        assert hasattr(processor, 'registerFitsImage'), "Should have registerFitsImage"
        assert hasattr(processor, 'submitFileToDB'), "Should have submitFileToDB"
        assert hasattr(processor, 'extractZipFile'), "Should have extractZipFile"
        assert hasattr(processor, 'convertXisfToFits'), "Should have convertXisfToFits"
        assert hasattr(processor, 'createMasterCalibrationFrames'), "Should have createMasterCalibrationFrames"
        assert hasattr(processor, 'checkCalibrationSessionsForMasters'), "Should have checkCalibrationSessionsForMasters"
        
        # Test that configuration attributes exist
        assert hasattr(processor, 'sourceFolder'), "Should have sourceFolder attribute"
        assert hasattr(processor, 'repoFolder'), "Should have repoFolder attribute"
        
        logger.info("✓ Backwards compatibility maintained")
        return True
    except Exception as e:
        logger.error(f"✗ Backwards compatibility test failed: {e}")
        return False

def test_file_operations():
    """Test basic file operations that don't require actual files."""
    logger.info("Testing file operations...")
    
    try:
        from astrofiler.core import fitsProcessing
        
        processor = fitsProcessing()
        
        # Test calculateFileHash with a known file (this script itself)
        current_file = __file__
        if os.path.exists(current_file):
            hash_result = processor.calculateFileHash(current_file)
            assert isinstance(hash_result, str), "Hash should be a string"
            assert len(hash_result) == 64, "SHA-256 hash should be 64 characters"
            logger.info("✓ File hash calculation working")
        else:
            logger.warning("Skipping hash test - current file not found")
        
        return True
    except Exception as e:
        logger.error(f"✗ File operations test failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("Starting refactored modules test suite...")
    logger.info("=" * 50)
    
    tests = [
        test_imports,
        test_utility_functions,
        test_processor_classes,
        test_backwards_compatibility,
        test_file_operations
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Test {test.__name__} crashed: {e}")
            failed += 1
        
        logger.info("-" * 30)
    
    logger.info("=" * 50)
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        logger.info("🎉 All tests passed! Refactoring appears successful.")
        return True
    else:
        logger.error("❌ Some tests failed. Check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)