#!/usr/bin/env python3
"""
Quick test to see if Astropy can open compressed FITS files directly
"""
import os
import sys
from astropy.io import fits
import gzip
import tempfile
import shutil

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from astrofiler.core.compress_files import FitsCompressor

def test_astropy_compressed_support():
    """Test if Astropy can open compressed FITS files directly"""
    
    # Use the repository FITS file
    fits_file = os.path.join(project_root, 'misc', 'example.fits')
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create compressed version
        test_file = os.path.join(temp_dir, 'test.fits')
        shutil.copy2(fits_file, test_file)
        
        compressor = FitsCompressor()
        compressed_file = compressor.compress_fits_file(test_file, replace_original=False, algorithm='gzip')
        
        print(f"Original file: {test_file}")
        print(f"Compressed file: {compressed_file}")
        
        # Test Astropy's ability to read compressed files
        print("\n=== Testing Astropy compressed file support ===")
        
        try:
            with fits.open(compressed_file) as hdul:
                print("✓ Astropy can directly open .gz compressed FITS files!")
                header = hdul[0].header
                data = hdul[0].data
                print(f"  Object: {header.get('OBJECT', 'Unknown')}")
                print(f"  Dimensions: {header.get('NAXIS1', '?')} x {header.get('NAXIS2', '?')}")
                print(f"  Data shape: {data.shape if data is not None else 'No data'}")
        except Exception as e:
            print(f"✗ Astropy cannot read compressed file: {e}")

if __name__ == "__main__":
    test_astropy_compressed_support()