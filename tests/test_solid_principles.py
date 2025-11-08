#!/usr/bin/env python3
"""
Test suite for SOLID principles refactoring in AstroFiler.

Tests the new file format processor, hash calculator service, and other
refactored components that follow SOLID principles.
"""

import sys
import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add the project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.astrofiler.core.file_formats import (
    FileFormatProcessor, get_file_format_processor, reset_file_format_processor
)
from src.astrofiler.core.file_formats.handlers.fits_handler import FitsFileHandler
from src.astrofiler.core.file_formats.handlers.zip_handler import ZipFileHandler
from src.astrofiler.core.file_formats.handlers.xisf_handler import XisfFileHandler
from src.astrofiler.core.services.file_hash_calculator import (
    FileHashCalculator, get_file_hash_calculator, reset_file_hash_calculator
)
from src.astrofiler.exceptions import FileProcessingError
import logging

# Set up logging for tests
logging.basicConfig(level=logging.WARNING)  # Reduce noise in tests


class TestFileFormatProcessor(unittest.TestCase):
    """Test the FileFormatProcessor following Open/Closed Principle."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_file_format_processor()
        self.processor = FileFormatProcessor()
    
    def tearDown(self):
        """Clean up test fixtures."""
        reset_file_format_processor()
    
    def test_processor_initialization(self):
        """Test that processor initializes with default handlers."""
        handlers = self.processor.list_handlers()
        expected_handlers = ['FITS', 'ZIP Archive', 'XISF']
        
        self.assertEqual(len(handlers), 3)
        for expected in expected_handlers:
            self.assertIn(expected, handlers)
    
    def test_open_closed_principle_handler_registration(self):
        """Test that new handlers can be added without modifying existing code."""
        # Create a mock handler
        class MockTiffHandler:
            def can_handle(self, file_path):
                return file_path.lower().endswith('.tiff')
            
            def get_supported_extensions(self):
                return ['.tiff', '.tif']
            
            def process_file(self, file_path):
                return file_path + '.converted'
            
            def get_format_name(self):
                return "TIFF"
        
        # Register the new handler
        mock_handler = MockTiffHandler()
        initial_count = self.processor.get_handler_count()
        self.processor.register_handler(mock_handler)
        
        # Verify handler was added
        self.assertEqual(self.processor.get_handler_count(), initial_count + 1)
        self.assertIn("TIFF", self.processor.list_handlers())
        self.assertTrue(self.processor.can_process("/test/file.tiff"))
    
    def test_supported_formats_listing(self):
        """Test getting supported formats and extensions."""
        formats = self.processor.get_supported_formats()
        
        self.assertIn('FITS', formats)
        self.assertIn('ZIP Archive', formats)
        self.assertIn('XISF', formats)
        
        # Check FITS extensions
        fits_extensions = formats['FITS']
        expected_fits = ['.fits', '.fit', '.fts']
        for ext in expected_fits:
            self.assertIn(ext, fits_extensions)
    
    def test_handler_finding(self):
        """Test finding appropriate handler for files."""
        # Test FITS file
        fits_handler = self.processor.find_handler("/test/file.fits")
        self.assertIsNotNone(fits_handler)
        self.assertEqual(fits_handler.get_format_name(), "FITS")
        
        # Test ZIP file (FITS ZIP)
        zip_handler = self.processor.find_handler("/test/file.fit.zip")
        self.assertIsNotNone(zip_handler)
        self.assertEqual(zip_handler.get_format_name(), "ZIP Archive")
        
        # Test unsupported file
        unsupported_handler = self.processor.find_handler("/test/file.txt")
        self.assertIsNone(unsupported_handler)
    
    def test_unsupported_format_error(self):
        """Test error handling for unsupported formats."""
        with self.assertRaises(FileProcessingError) as context:
            self.processor.process_file("/test/file.unsupported")
        
        self.assertIn("UNSUPPORTED_FORMAT", str(context.exception))
    
    def test_handler_unregistration(self):
        """Test removing handlers by name."""
        initial_count = self.processor.get_handler_count()
        
        # Remove XISF handler
        result = self.processor.unregister_handler("XISF")
        self.assertTrue(result)
        self.assertEqual(self.processor.get_handler_count(), initial_count - 1)
        self.assertNotIn("XISF", self.processor.list_handlers())
        
        # Try to remove non-existent handler
        result = self.processor.unregister_handler("NonExistent")
        self.assertFalse(result)
    
    def test_singleton_global_processor(self):
        """Test global processor singleton pattern."""
        processor1 = get_file_format_processor()
        processor2 = get_file_format_processor()
        
        # Should be same instance
        self.assertIs(processor1, processor2)
        
        # Reset and get new instance
        reset_file_format_processor()
        processor3 = get_file_format_processor()
        self.assertIsNot(processor1, processor3)


class TestFitsFileHandler(unittest.TestCase):
    """Test FITS file handler implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.handler = FitsFileHandler()
    
    def test_supported_extensions(self):
        """Test FITS file extension support."""
        extensions = self.handler.get_supported_extensions()
        expected = ['.fits', '.fit', '.fts']
        
        self.assertEqual(set(extensions), set(expected))
    
    def test_can_handle_fits_files(self):
        """Test FITS file detection."""
        test_files = [
            "/test/image.fits",
            "/test/image.fit", 
            "/test/image.FTS",
            "/test/IMAGE.FITS"
        ]
        
        for file_path in test_files:
            with self.subTest(file_path=file_path):
                self.assertTrue(self.handler.can_handle(file_path))
    
    def test_cannot_handle_non_fits(self):
        """Test rejection of non-FITS files."""
        test_files = [
            "/test/image.jpg",
            "/test/image.tiff",
            "/test/data.txt"
        ]
        
        for file_path in test_files:
            with self.subTest(file_path=file_path):
                self.assertFalse(self.handler.can_handle(file_path))
    
    def test_format_name(self):
        """Test format name reporting."""
        self.assertEqual(self.handler.get_format_name(), "FITS")


class TestZipFileHandler(unittest.TestCase):
    """Test ZIP file handler implementation."""
    
    def setUp(self):
        """Set up test fixtures.""" 
        self.handler = ZipFileHandler()
    
    def test_supported_extensions(self):
        """Test ZIP file extension support."""
        extensions = self.handler.get_supported_extensions()
        self.assertIn('.zip', extensions)
    
    def test_can_handle_fits_zip_files(self):
        """Test FITS ZIP file detection."""
        test_files = [
            "/test/image.fit.zip",
            "/test/image.fits.zip",
            "/test/IMAGE.FIT.ZIP"
        ]
        
        for file_path in test_files:
            with self.subTest(file_path=file_path):
                self.assertTrue(self.handler.can_handle(file_path))
    
    def test_cannot_handle_regular_zip(self):
        """Test rejection of regular ZIP files."""
        test_files = [
            "/test/data.zip",
            "/test/archive.ZIP", 
            "/test/documents.zip"
        ]
        
        for file_path in test_files:
            with self.subTest(file_path=file_path):
                self.assertFalse(self.handler.can_handle(file_path))
    
    def test_format_name(self):
        """Test format name reporting."""
        self.assertEqual(self.handler.get_format_name(), "ZIP Archive")


class TestXisfFileHandler(unittest.TestCase):
    """Test XISF file handler implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.handler = XisfFileHandler()
    
    def test_supported_extensions(self):
        """Test XISF file extension support."""
        extensions = self.handler.get_supported_extensions()
        self.assertIn('.xisf', extensions)
    
    def test_can_handle_xisf_files(self):
        """Test XISF file detection."""
        test_files = [
            "/test/image.xisf",
            "/test/IMAGE.XISF"
        ]
        
        for file_path in test_files:
            with self.subTest(file_path=file_path):
                self.assertTrue(self.handler.can_handle(file_path))
    
    def test_format_name(self):
        """Test format name reporting."""
        self.assertEqual(self.handler.get_format_name(), "XISF")


class TestFileHashCalculator(unittest.TestCase):
    """Test file hash calculator service following Single Responsibility Principle."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_file_hash_calculator()
        self.calculator = FileHashCalculator()
    
    def tearDown(self):
        """Clean up test fixtures."""
        reset_file_hash_calculator()
    
    def test_sha256_calculation(self):
        """Test SHA-256 hash calculation."""
        # Create temporary file with known content
        test_content = b"Hello, AstroFiler!"
        expected_hash = "c2c8b4d6f9b4b8c7a1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_file_path = tmp_file.name
        
        try:
            # Calculate known SHA-256 for test content
            import hashlib
            expected = hashlib.sha256(test_content).hexdigest()
            
            result = self.calculator.calculate_sha256(tmp_file_path)
            self.assertEqual(result, expected)
        finally:
            os.unlink(tmp_file_path)
    
    def test_md5_calculation(self):
        """Test MD5 hash calculation."""
        test_content = b"Test MD5 content"
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_file_path = tmp_file.name
        
        try:
            import hashlib
            expected = hashlib.md5(test_content).hexdigest()
            
            result = self.calculator.calculate_md5(tmp_file_path)
            self.assertEqual(result, expected)
        finally:
            os.unlink(tmp_file_path)
    
    def test_multiple_hash_calculation(self):
        """Test calculating multiple hashes in single pass."""
        test_content = b"Multi-hash test content"
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_file_path = tmp_file.name
        
        try:
            result = self.calculator.calculate_multiple_hashes(
                tmp_file_path, ['sha256', 'md5', 'sha1']
            )
            
            # Verify all hashes present
            self.assertIn('sha256', result)
            self.assertIn('md5', result)
            self.assertIn('sha1', result)
            
            # Verify hash values are correct
            import hashlib
            self.assertEqual(result['sha256'], hashlib.sha256(test_content).hexdigest())
            self.assertEqual(result['md5'], hashlib.md5(test_content).hexdigest())
            self.assertEqual(result['sha1'], hashlib.sha1(test_content).hexdigest())
        finally:
            os.unlink(tmp_file_path)
    
    def test_nonexistent_file_error(self):
        """Test error handling for non-existent files."""
        with self.assertRaises(FileProcessingError) as context:
            self.calculator.calculate_sha256("/nonexistent/file.fits")
        
        self.assertIn("FILE_READ_ERROR", str(context.exception))
    
    def test_invalid_algorithm_error(self):
        """Test error handling for invalid algorithms."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            with self.assertRaises(FileProcessingError) as context:
                self.calculator.calculate_multiple_hashes(
                    tmp_file.name, ['invalid_algorithm']
                )
            
            self.assertIn("INVALID_HASH_ALGORITHM", str(context.exception))
    
    def test_singleton_global_calculator(self):
        """Test global calculator singleton pattern."""
        calc1 = get_file_hash_calculator()
        calc2 = get_file_hash_calculator()
        
        # Should be same instance
        self.assertIs(calc1, calc2)
        
        # Reset and get new instance
        reset_file_hash_calculator()
        calc3 = get_file_hash_calculator()
        self.assertIsNot(calc1, calc3)
    
    def test_custom_buffer_size(self):
        """Test hash calculator with custom buffer size."""
        custom_calculator = FileHashCalculator(buffer_size=1024)
        self.assertEqual(custom_calculator.buffer_size, 1024)
        
        # Test it still works with custom buffer
        test_content = b"Custom buffer test"
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_file_path = tmp_file.name
        
        try:
            result = custom_calculator.calculate_sha256(tmp_file_path)
            
            import hashlib
            expected = hashlib.sha256(test_content).hexdigest()
            self.assertEqual(result, expected)
        finally:
            os.unlink(tmp_file_path)


class TestSOLIDPrinciplesIntegration(unittest.TestCase):
    """Integration tests for SOLID principles refactoring."""
    
    def test_single_responsibility_separation(self):
        """Test that responsibilities are properly separated."""
        # File format processing
        processor = get_file_format_processor()
        self.assertTrue(hasattr(processor, 'process_file'))
        self.assertTrue(hasattr(processor, 'register_handler'))
        
        # Hash calculation
        calculator = get_file_hash_calculator()
        self.assertTrue(hasattr(calculator, 'calculate_sha256'))
        self.assertTrue(hasattr(calculator, 'calculate_md5'))
        
        # Ensure they are different objects with different responsibilities
        self.assertIsNot(processor, calculator)
        self.assertNotEqual(type(processor), type(calculator))
    
    def test_open_closed_principle_extensibility(self):
        """Test that system can be extended without modification."""
        processor = get_file_format_processor()
        
        # Create custom handler
        class CustomHandler:
            def can_handle(self, file_path):
                return file_path.endswith('.custom')
            
            def get_supported_extensions(self):
                return ['.custom']
            
            def process_file(self, file_path):
                return file_path
            
            def get_format_name(self):
                return "Custom Format"
        
        # Add without modifying existing code
        initial_count = processor.get_handler_count()
        processor.register_handler(CustomHandler())
        
        self.assertEqual(processor.get_handler_count(), initial_count + 1)
        self.assertTrue(processor.can_process("/test/file.custom"))
    
    def test_interface_segregation_principle(self):
        """Test that interfaces are focused and segregated."""
        # Each handler only implements what it needs
        fits_handler = FitsFileHandler()
        zip_handler = ZipFileHandler()
        
        # All handlers implement the same interface
        for handler in [fits_handler, zip_handler]:
            self.assertTrue(hasattr(handler, 'can_handle'))
            self.assertTrue(hasattr(handler, 'get_supported_extensions'))
            self.assertTrue(hasattr(handler, 'process_file'))
            self.assertTrue(hasattr(handler, 'get_format_name'))
        
        # But they have different behaviors
        self.assertNotEqual(fits_handler.get_format_name(), zip_handler.get_format_name())


def run_solid_principles_tests():
    """Run all SOLID principles tests."""
    print("🧪 Testing SOLID Principles Refactoring")
    print("=" * 50)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_cases = [
        TestFileFormatProcessor,
        TestFitsFileHandler,
        TestZipFileHandler,
        TestXisfFileHandler,
        TestFileHashCalculator,
        TestSOLIDPrinciplesIntegration
    ]
    
    for test_case in test_cases:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_case)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("🎉 All SOLID principles tests passed!")
        print("✅ Refactoring successfully follows SOLID principles")
    else:
        print(f"❌ {len(result.failures)} test failures")
        print(f"❌ {len(result.errors)} test errors")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(run_solid_principles_tests())