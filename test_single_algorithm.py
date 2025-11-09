#!/usr/bin/env python3
"""
Simple LZMA compression test
"""
import os
import sys
import tempfile
import shutil

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from astrofiler.core.compress_files import FitsCompressor

def test_single_algorithm():
    """Test a single compression algorithm with detailed error reporting"""
    
    # Find the repository FITS file
    fits_file = os.path.join(project_root, 'misc', 'example.fits')
    if not os.path.exists(fits_file):
        print(f"FITS file not found: {fits_file}")
        return
    
    print(f"Testing with file: {fits_file}")
    print(f"File size: {os.path.getsize(fits_file):,} bytes")
    
    compressor = FitsCompressor()
    
    # Test LZMA specifically
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy file to temp directory
        test_file = os.path.join(temp_dir, 'test.fits')
        shutil.copy2(fits_file, test_file)
        
        print("\nTesting LZMA compression...")
        try:
            result = compressor.compress_fits_file(test_file, replace_original=False, algorithm='lzma')
            print(f"LZMA Result: {result}")
            
            if result and os.path.exists(result):
                compressed_size = os.path.getsize(result)
                original_size = os.path.getsize(test_file)
                ratio = (1 - compressed_size / original_size) * 100
                print(f"✓ LZMA Success: {original_size:,} -> {compressed_size:,} bytes ({ratio:.1f}% reduction)")
            else:
                print("✗ LZMA failed - no output file created")
                
        except Exception as e:
            print(f"✗ LZMA failed with exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_single_algorithm()