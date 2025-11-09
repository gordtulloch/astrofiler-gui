#!/usr/bin/env python3
"""
Test updated FITS compression without RICE
"""
import os
import sys
import tempfile

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from astrofiler.core.compress_files import FitsCompressor

def test_fits_gzip_compression():
    """Test FITS GZIP compression methods"""
    
    fits_file = os.path.join(project_root, 'misc', 'example.fits')
    
    if not os.path.exists(fits_file):
        print(f"FITS file not found: {fits_file}")
        return
    
    compression_manager = FitsCompressor()
    
    algorithms = ['fits_gzip1', 'fits_gzip2']
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for algorithm in algorithms:
            print(f"\nTesting {algorithm}:")
            
            try:
                # Test compression
                result = compression_manager._compress_fits_internal(
                    input_path=fits_file,
                    replace_original=False,
                    algorithm=algorithm
                )
                
                if result:
                    original_size = os.path.getsize(fits_file)
                    compressed_size = os.path.getsize(result)
                    ratio = (1 - compressed_size / original_size) * 100
                    
                    print(f"  ✓ Compression successful: {ratio:.1f}% size reduction")
                    print(f"    Original: {original_size:,} bytes")
                    print(f"    Compressed: {compressed_size:,} bytes")
                    print(f"    Output: {result}")
                else:
                    print(f"  ✗ Compression failed")
                    
            except Exception as e:
                print(f"  ✗ Error: {e}")

if __name__ == "__main__":
    test_fits_gzip_compression()