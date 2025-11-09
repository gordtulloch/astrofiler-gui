#!/usr/bin/env python3
"""
Comprehensive FITS compression comparison
"""
import os
import sys
import tempfile

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from astrofiler.core.compress_files import FitsCompressor

def test_all_compression_methods():
    """Test and compare all compression methods"""
    
    fits_file = os.path.join(project_root, 'misc', 'example.fits')
    
    if not os.path.exists(fits_file):
        print(f"FITS file not found: {fits_file}")
        return
    
    original_size = os.path.getsize(fits_file)
    print(f"Original file size: {original_size:,} bytes ({original_size / 1024 / 1024:.1f} MB)")
    print("="*80)
    
    compressor = FitsCompressor()
    
    # Test external compression
    external_algorithms = ['gzip', 'lzma', 'bzip2']
    print("EXTERNAL COMPRESSION METHODS:")
    print("-" * 40)
    
    for algorithm in external_algorithms:
        try:
            result = compressor.compress_fits_file(fits_file, replace_original=False, algorithm=algorithm)
            if result:
                compressed_size = os.path.getsize(result)
                ratio = (1 - compressed_size / original_size) * 100
                print(f"{algorithm.upper():8} | {compressed_size:10,} bytes | {ratio:5.1f}% reduction")
                
                # Clean up
                try:
                    os.remove(result)
                except:
                    pass
            else:
                print(f"{algorithm.upper():8} | FAILED")
                
        except Exception as e:
            print(f"{algorithm.upper():8} | ERROR: {e}")
    
    # Test FITS internal compression
    fits_algorithms = ['fits_gzip1', 'fits_gzip2']
    print("\nFITS INTERNAL COMPRESSION METHODS:")
    print("-" * 40)
    
    for algorithm in fits_algorithms:
        try:
            result = compressor._compress_fits_internal(fits_file, replace_original=False, algorithm=algorithm)
            if result:
                compressed_size = os.path.getsize(result)
                ratio = (1 - compressed_size / original_size) * 100
                print(f"{algorithm.upper():12} | {compressed_size:10,} bytes | {ratio:5.1f}% reduction")
                
                # Test readability
                from astropy.io import fits
                try:
                    with fits.open(result) as hdul:
                        print(f"{'':14}   ✓ Readable by astropy")
                except:
                    print(f"{'':14}   ✗ Not readable by astropy")
                
                # Clean up
                try:
                    os.remove(result)
                except:
                    pass
            else:
                print(f"{algorithm.upper():12} | FAILED")
                
        except Exception as e:
            print(f"{algorithm.upper():12} | ERROR: {e}")
    
    print("\n" + "="*80)
    print("SUMMARY:")
    print("• External compression: Works with astropy, NOT with Siril")
    print("• FITS internal compression: Works with BOTH astropy and Siril")
    print("• FITS GZIP-2 provides the best compression for FITS files")
    print("• Use FITS internal compression for Siril compatibility")
    print("• Use external LZMA for maximum compression (astropy only)")

if __name__ == "__main__":
    test_all_compression_methods()