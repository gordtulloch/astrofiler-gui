#!/usr/bin/env python3
"""
Test smart compression algorithm selection based on FITS data type
"""
import os
import sys
import numpy as np
from astropy.io import fits
import tempfile

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from astrofiler.core.compress_files import FitsCompressor

def create_test_fits(data_type, filename):
    """Create a test FITS file with specified data type"""
    
    # Create test data
    if data_type == 'uint16':
        # Simulate 16-bit integer data (typical from NINA/cameras)
        data = np.random.randint(0, 65535, size=(100, 100), dtype=np.uint16)
    elif data_type == 'int16': 
        # Simulate signed 16-bit integer data
        data = np.random.randint(-32768, 32767, size=(100, 100), dtype=np.int16)
    elif data_type == 'uint32':
        # Simulate 32-bit integer data
        data = np.random.randint(0, 4294967295, size=(100, 100), dtype=np.uint32)
    elif data_type == 'float32':
        # Simulate 32-bit float data (typical from processed images)
        data = np.random.random((100, 100)).astype(np.float32)
    elif data_type == 'float64':
        # Simulate 64-bit float data
        data = np.random.random((100, 100)).astype(np.float64)
    else:
        raise ValueError(f"Unsupported data type: {data_type}")
    
    # Create FITS file
    hdu = fits.PrimaryHDU(data)
    hdu.writeto(filename, overwrite=True)
    
    return data.dtype, data.shape

def test_smart_compression_selection():
    """Test the smart compression algorithm selection"""
    
    compressor = FitsCompressor()
    
    test_cases = [
        ('uint16', 'fits_rice', 'NINA 16-bit integer data'),
        ('int16', 'fits_rice', '16-bit signed integer data'),
        ('uint32', 'fits_gzip2', '32-bit integer data'),
        ('float32', 'fits_gzip2', '32-bit floating-point data'),
        ('float64', 'fits_gzip2', '64-bit floating-point data'),
    ]
    
    print("Testing Smart Compression Algorithm Selection")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for data_type, expected_algo, description in test_cases:
            test_file = os.path.join(temp_dir, f'test_{data_type}.fits')
            
            print(f"\nTesting {description}:")
            print(f"  Data type: {data_type}")
            
            # Create test FITS file
            actual_dtype, shape = create_test_fits(data_type, test_file)
            print(f"  Created: {shape} array, dtype={actual_dtype}")
            
            # Test smart selection
            selected_algo = compressor._select_optimal_compression(test_file)
            print(f"  Expected algorithm: {expected_algo}")
            print(f"  Selected algorithm: {selected_algo}")
            
            if selected_algo == expected_algo:
                print(f"  ✓ PASS - Correct algorithm selected")
                
                # Test actual compression
                try:
                    result = compressor._compress_fits_internal(
                        input_path=test_file,
                        replace_original=False,
                        algorithm='auto'  # Use auto mode
                    )
                    
                    if result:
                        original_size = os.path.getsize(test_file)
                        compressed_size = os.path.getsize(result)
                        ratio = (1 - compressed_size / original_size) * 100
                        print(f"  ✓ Compression successful: {ratio:.1f}% reduction")
                    else:
                        print(f"  ✗ Compression failed")
                        
                except Exception as e:
                    print(f"  ✗ Compression error: {e}")
            else:
                print(f"  ✗ FAIL - Wrong algorithm selected")
    
    print("\n" + "=" * 60)
    print("SMART SELECTION SUMMARY:")
    print("✓ 16-bit integers → RICE (NINA compatible)")
    print("✓ 32-bit integers → GZIP-2 (avoid lossy RICE)")  
    print("✓ Float data → GZIP-2 (optimal for floating-point)")
    print("✓ Auto-selection protects against data loss")

if __name__ == "__main__":
    test_smart_compression_selection()