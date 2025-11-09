#!/usr/bin/env python3
"""
Debug FITS internal compression
"""
import os
import sys
from astropy.io import fits
import tempfile

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

def test_astropy_fits_compression():
    """Test astropy FITS compression directly"""
    
    fits_file = os.path.join(project_root, 'misc', 'example.fits')
    
    print("Testing astropy FITS compression directly...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test Rice compression
        output_file = os.path.join(temp_dir, 'compressed_rice.fits')
        
        try:
            # Load original FITS file
            with fits.open(fits_file) as hdul:
                print(f"Original file structure:")
                print(f"  Number of HDUs: {len(hdul)}")
                for i, hdu in enumerate(hdul):
                    print(f"  HDU {i}: {type(hdu).__name__}")
                    if hasattr(hdu, 'data') and hdu.data is not None:
                        print(f"    Data shape: {hdu.data.shape}, dtype: {hdu.data.dtype}")
                    if hasattr(hdu, 'header'):
                        print(f"    Header keys: {len(hdu.header)}")
                
                # Create compressed HDU
                if hdul[0].data is not None:
                    print(f"\nCreating Rice compressed HDU...")
                    compressed_hdu = fits.CompImageHDU(
                        data=hdul[0].data,
                        header=hdul[0].header,
                        compression_type='RICE_1'
                    )
                    
                    # Create new HDU list
                    new_hdul = fits.HDUList([fits.PrimaryHDU(header=hdul[0].header), compressed_hdu])
                    
                    print(f"Writing compressed file...")
                    new_hdul.writeto(output_file, overwrite=True)
                    
                    original_size = os.path.getsize(fits_file)
                    compressed_size = os.path.getsize(output_file)
                    ratio = (1 - compressed_size / original_size) * 100
                    
                    print(f"✓ Compression successful!")
                    print(f"  Original size: {original_size:,} bytes")
                    print(f"  Compressed size: {compressed_size:,} bytes")
                    print(f"  Compression ratio: {ratio:.1f}%")
                    
                    # Test reading the compressed file
                    print(f"\nTesting compressed file reading...")
                    with fits.open(output_file) as comp_hdul:
                        print(f"Compressed file structure:")
                        print(f"  Number of HDUs: {len(comp_hdul)}")
                        for i, hdu in enumerate(comp_hdul):
                            print(f"  HDU {i}: {type(hdu).__name__}")
                            if hasattr(hdu, 'data') and hdu.data is not None:
                                print(f"    Data shape: {hdu.data.shape}, dtype: {hdu.data.dtype}")
                        
                        print(f"✓ Successfully read compressed FITS file!")
                else:
                    print("✗ No data in original FITS file")
                    
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_astropy_fits_compression()