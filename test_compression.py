#!/usr/bin/env python3
"""
Test FITS Compression Functionality

Simple test script to verify that FITS file compression is working correctly.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add the src directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

def test_compression():
    """Test FITS compression functionality."""
    try:
        # Import directly without going through the full package
        import sys
        import os
        import tempfile
        import shutil
        import gzip
        import hashlib
        import configparser
        from pathlib import Path
        
        # Add src to path for direct import
        project_root = os.path.dirname(os.path.abspath(__file__))
        src_path = os.path.join(project_root, 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        
        # Import just the compressor class directly
        sys.path.append(os.path.join(src_path, 'astrofiler', 'core'))
        from compress_files import FitsCompressor
        
        import numpy as np
        from astropy.io import fits
        
        print("Testing FITS compression functionality...")
        
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test FITS file
            test_fits_path = os.path.join(temp_dir, "test_image.fits")
            
            # Create test data
            data = np.random.randint(0, 65535, size=(512, 512), dtype=np.uint16)
            
            # Create FITS file with header
            hdu = fits.PrimaryHDU(data)
            hdu.header['IMAGETYP'] = 'LIGHT'
            hdu.header['OBJECT'] = 'Test Object'
            hdu.header['EXPTIME'] = 30.0
            hdu.header['DATE-OBS'] = '2024-11-09T20:30:00'
            hdu.header['TELESCOP'] = 'Test Telescope'
            hdu.header['INSTRUME'] = 'Test Camera'
            
            hdul = fits.HDUList([hdu])
            hdul.writeto(test_fits_path)
            hdul.close()
            
            original_size = os.path.getsize(test_fits_path)
            print(f"Created test FITS file: {test_fits_path}")
            print(f"Original size: {original_size:,} bytes")
            
            # Test compression with enabled configuration
            # Create a temporary config file for testing
            test_config_path = os.path.join(temp_dir, "test_astrofiler.ini")
            with open(test_config_path, 'w') as f:
                f.write("""[DEFAULT]
compress_fits = True
compression_level = 6
verify_compression = True
min_compression_size = 1024
""")
            
            # Initialize compressor with test config
            compressor = FitsCompressor(test_config_path)
            print(f"Compression enabled: {compressor.compression_enabled}")
            
            # Test compression
            compressed_path = compressor.compress_fits_file(test_fits_path, replace_original=False)
            
            if compressed_path:
                compressed_size = os.path.getsize(compressed_path)
                compression_ratio = (1 - compressed_size / original_size) * 100
                
                print(f"Compressed file: {compressed_path}")
                print(f"Compressed size: {compressed_size:,} bytes")
                print(f"Compression ratio: {compression_ratio:.1f}%")
                
                # Test decompression
                decompressed_path = compressor.decompress_fits_file(compressed_path, replace_compressed=False)
                
                if decompressed_path:
                    decompressed_size = os.path.getsize(decompressed_path)
                    print(f"Decompressed file: {decompressed_path}")
                    print(f"Decompressed size: {decompressed_size:,} bytes")
                    
                    # Verify files match
                    original_hash = compressor.calculate_file_hash(test_fits_path)
                    decompressed_hash = compressor.calculate_file_hash(decompressed_path)
                    
                    if original_hash == decompressed_hash:
                        print("✓ Compression/decompression test PASSED - Files match perfectly!")
                        return True
                    else:
                        print("✗ Compression/decompression test FAILED - File hashes don't match")
                        return False
                else:
                    print("✗ Decompression failed")
                    return False
            else:
                print("✗ Compression failed")
                return False
                
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Make sure required packages are installed: astropy, numpy")
        return False
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        return False

def test_configuration_integration():
    """Test that compression integrates with the configuration system."""
    try:
        # Import directly without going through the full package
        import sys
        import os
        
        # Add src to path for direct import
        project_root = os.path.dirname(os.path.abspath(__file__))
        src_path = os.path.join(project_root, 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        
        # Import just the compressor functions directly
        sys.path.append(os.path.join(src_path, 'astrofiler', 'core'))
        from compress_files import get_fits_compressor, is_compression_enabled
        
        print("\nTesting configuration integration...")
        
        # Test with default config (should be disabled)
        compressor = get_fits_compressor()
        enabled = is_compression_enabled()
        
        print(f"Default compression enabled: {enabled}")
        print(f"Compression level: {compressor.compression_level}")
        print(f"Verify compression: {compressor.verify_compression}")
        
        print("✓ Configuration integration test PASSED")
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("FITS Compression Test Suite")
    print("=" * 60)
    
    # Run tests
    test1_result = test_compression()
    test2_result = test_configuration_integration()
    
    print("\n" + "=" * 60)
    if test1_result and test2_result:
        print("All tests PASSED! 🎉")
        print("\nTo enable compression in AstroFiler:")
        print("1. Edit astrofiler.ini")
        print("2. Set 'compress_fits = True'")
        print("3. Restart AstroFiler")
        print("4. New files will be automatically compressed during import")
        sys.exit(0)
    else:
        print("Some tests FAILED! ❌")
        sys.exit(1)