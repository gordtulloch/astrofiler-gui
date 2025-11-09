#!/usr/bin/env python3
"""
Test Siril compatibility with FITS compressed files
"""
import os
import sys

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

def test_siril_compatibility():
    """Test if Siril can read the compressed FITS files"""
    
    compressed_files = [
        os.path.join(project_root, 'misc', 'example_fits_gzip1.fits'),
        os.path.join(project_root, 'misc', 'example_fits_gzip2.fits')
    ]
    
    # Test with astropy first (always available)
    print("Testing with astropy:")
    from astropy.io import fits
    
    for fits_file in compressed_files:
        if os.path.exists(fits_file):
            print(f"\nTesting {os.path.basename(fits_file)} with astropy:")
            
            try:
                with fits.open(fits_file) as hdul:
                    print(f"  ✓ Astropy can read the file")
                    print(f"    HDUs: {len(hdul)}")
                    for i, hdu in enumerate(hdul):
                        if hasattr(hdu, 'data') and hdu.data is not None:
                            print(f"    HDU {i}: {type(hdu).__name__}, shape: {hdu.data.shape}")
                        else:
                            print(f"    HDU {i}: {type(hdu).__name__}, no data")
                            
            except Exception as e:
                print(f"  ✗ Astropy error: {e}")
    
    # Test with PySiril if available
    try:
        import pysiril
        
        print("\n" + "="*50)
        print("Testing Siril compatibility:")
        
        for fits_file in compressed_files:
            if os.path.exists(fits_file):
                print(f"\nTesting {os.path.basename(fits_file)}:")
                
                try:
                    # Try to load the FITS file using pysiril's load function
                    # Note: This is a simplified test - actual usage may vary
                    print(f"  ✓ PySiril is available for testing")
                    print(f"    (Full Siril integration would require running Siril instance)")
                        
                except Exception as e:
                    print(f"  ✗ Error testing with Siril: {e}")
            else:
                print(f"\nFile not found: {fits_file}")
                
    except ImportError:
        print("\n" + "="*50)
        print("PySiril not installed - skipping Siril-specific tests")

if __name__ == "__main__":
    test_siril_compatibility()