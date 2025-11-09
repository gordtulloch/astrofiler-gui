#!/usr/bin/env python3
"""
Test script for FITS internal compression compatibility with Siril
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
from astropy.io import fits

# Try to import PySiril for Siril compatibility testing
try:
    from pysiril.siril import Siril
    PYSIRIL_AVAILABLE = True
    print("✓ PySiril available for Siril compatibility testing")
except ImportError:
    PYSIRIL_AVAILABLE = False
    print("⚠ PySiril not available - cannot test Siril compatibility")

def test_fits_internal_compression():
    """Test FITS internal compression methods supported by Siril"""
    
    # Find repository FITS file
    fits_file = os.path.join(project_root, 'misc', 'example.fits')
    if not os.path.exists(fits_file):
        print(f"✗ FITS file not found: {fits_file}")
        return
    
    print(f"Testing FITS internal compression with: {os.path.basename(fits_file)}")
    original_size = os.path.getsize(fits_file)
    print(f"Original file size: {original_size:,} bytes ({original_size/(1024*1024):.1f} MB)")
    
    # Test Siril-supported FITS compression methods (excluding RICE - for integer data only)
    algorithms = ['fits_gzip1', 'fits_gzip2']
    
    with tempfile.TemporaryDirectory(prefix='fits_compression_test_') as temp_dir:
        compressor = FitsCompressor()
        
        for algorithm in algorithms:
            print(f"\n=== Testing {algorithm} ===")
            
            # Copy original file to temp directory
            test_file = os.path.join(temp_dir, 'test.fits')
            shutil.copy2(fits_file, test_file)
            
            try:
                # Test FITS internal compression
                compressed_file = compressor.compress_fits_file(
                    test_file, replace_original=False, algorithm=algorithm
                )
                
                if compressed_file and os.path.exists(compressed_file):
                    compressed_size = os.path.getsize(compressed_file)
                    ratio = (1 - compressed_size / original_size) * 100
                    print(f"✓ Compression successful: {compressed_size:,} bytes ({ratio:.1f}% reduction)")
                    
                    # Test if Astropy can read the compressed file
                    try:
                        with fits.open(compressed_file) as hdul:
                            data = None
                            for hdu in hdul:
                                if hasattr(hdu, 'data') and hdu.data is not None:
                                    data = hdu.data
                                    break
                            
                            if data is not None:
                                print(f"✓ Astropy can read compressed FITS file")
                                print(f"  Data shape: {data.shape}, dtype: {data.dtype}")
                            else:
                                print(f"⚠ Astropy: No image data found in compressed file")
                                
                    except Exception as e:
                        print(f"✗ Astropy cannot read compressed file: {e}")
                    
                    # Test if Siril can read the compressed file
                    if PYSIRIL_AVAILABLE:
                        try:
                            app = Siril()
                            app.Open()
                            
                            cmd = f'load "{compressed_file}"'
                            result = app.Execute(cmd)
                            
                            if result is True:
                                print(f"✓ Siril can read FITS internal compressed file")
                            else:
                                print(f"✗ Siril cannot read compressed file")
                            
                            app.Close()
                            
                        except Exception as e:
                            print(f"✗ Siril test failed: {e}")
                    else:
                        print(f"⚠ Siril compatibility test skipped (PySiril not available)")
                    
                    # Clean up
                    os.remove(compressed_file)
                    
                else:
                    print(f"✗ Compression failed for {algorithm}")
                    
            except Exception as e:
                print(f"✗ Error testing {algorithm}: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    test_fits_internal_compression()