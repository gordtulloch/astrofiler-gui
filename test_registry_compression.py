#!/usr/bin/env python3
"""
Test if file registry functions can handle compressed FITS files
"""
import os
import sys
import tempfile
from astropy.io import fits
import numpy as np

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

def test_file_registry_compression_support():
    """Test if the file registry can handle compressed FITS files"""
    
    from astrofiler.core import fitsProcessing
    from astrofiler.core.compress_files import FitsCompressor
    
    print("Testing File Registry Support for Compressed FITS Files")
    print("=" * 60)
    
    # Create a test FITS file
    with tempfile.TemporaryDirectory() as temp_dir:
        test_fits = os.path.join(temp_dir, 'test.fits')
        
        # Create simple FITS file with required headers
        data = np.random.randint(0, 65535, size=(100, 100), dtype=np.uint16)
        hdu = fits.PrimaryHDU(data)
        hdu.header['IMAGETYP'] = 'LIGHT'
        hdu.header['OBJECT'] = 'M42'
        hdu.header['EXPTIME'] = 60.0
        hdu.header['DATE-OBS'] = '2024-01-01T00:00:00'
        hdu.header['TELESCOP'] = 'Test'
        hdu.header['INSTRUME'] = 'TestCam'
        hdu.header['FILTER'] = 'L'
        hdu.header['XBINNING'] = 1
        hdu.header['YBINNING'] = 1
        hdu.header['CCD-TEMP'] = -10.0
        hdu.writeto(test_fits, overwrite=True)
        
        # Create compressed versions
        compressor = FitsCompressor()
        
        # Test FITS internal compression
        compressed_fits = compressor._compress_fits_internal(
            input_path=test_fits,
            replace_original=False, 
            algorithm='fits_gzip2'
        )
        
        print(f"Original FITS: {test_fits}")
        print(f"Compressed FITS: {compressed_fits}")
        
        # Test file registry on both files
        processor = fitsProcessing()
        
        print(f"\nTesting file registry...")
        
        # Test original file
        print(f"1. Testing original FITS file:")
        try:
            result1 = processor.registerFitsImage(
                root=os.path.dirname(test_fits),
                file=os.path.basename(test_fits),
                moveFiles=False
            )
            if result1:
                print(f"   ✓ Original FITS file registered successfully")
            else:
                print(f"   ✗ Original FITS file registration failed")
        except Exception as e:
            print(f"   ✗ Original FITS file registration error: {e}")
        
        # Test compressed file  
        print(f"2. Testing compressed FITS file:")
        try:
            result2 = processor.registerFitsImage(
                root=os.path.dirname(compressed_fits),
                file=os.path.basename(compressed_fits),
                moveFiles=False
            )
            if result2:
                print(f"   ✓ Compressed FITS file registered successfully")
            else:
                print(f"   ✗ Compressed FITS file registration failed")
        except Exception as e:
            print(f"   ✗ Compressed FITS file registration error: {e}")
        
        # Test if compressed files are detected by scanning
        print(f"\n3. Testing directory scanning:")
        try:
            # Use the wrapper function that scans directories
            results = processor.registerFitsImages(
                moveFiles=False,
                source_folder=temp_dir
            )
            
            print(f"   Results type: {type(results)}")
            print(f"   Results value: {results}")
            
            if isinstance(results, tuple) and len(results) == 2:
                registered_files, duplicate_count = results
                print(f"   Directory scan found {len(registered_files)} files")
                print(f"   Duplicates: {duplicate_count}")
                
                if len(registered_files) >= 1:  # Should find at least the compressed file
                    print(f"   ✓ Directory scanning working")
                else:
                    print(f"   ✗ Directory scanning missed compressed files")
            elif isinstance(results, list):
                print(f"   Directory scan found {len(results)} files (legacy format)")
                if len(results) >= 1:
                    print(f"   ✓ Directory scanning working")
                else:
                    print(f"   ✗ Directory scanning missed compressed files")
            else:
                print(f"   ✗ Unexpected return format from registerFitsImages")
                
        except Exception as e:
            print(f"   ✗ Directory scanning error: {e}")

if __name__ == "__main__":
    test_file_registry_compression_support()