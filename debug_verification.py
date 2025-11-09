#!/usr/bin/env python3
"""
Debug FITS verification process
"""
import os
import sys
from astropy.io import fits
import numpy as np
import tempfile

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

def debug_verification():
    """Debug the verification process"""
    
    fits_file = os.path.join(project_root, 'misc', 'example.fits')
    
    print("Testing verification process...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test Rice compression
        output_file = os.path.join(temp_dir, 'compressed_rice.fits')
        
        try:
            # Load and compress
            with fits.open(fits_file) as hdul:
                print(f"Original data: shape={hdul[0].data.shape}, dtype={hdul[0].data.dtype}")
                print(f"Original data sample: {hdul[0].data[0, 0:5]}")
                
                compressed_hdu = fits.CompImageHDU(
                    data=hdul[0].data,
                    header=hdul[0].header,
                    compression_type='RICE_1'
                )
                
                new_hdul = fits.HDUList([fits.PrimaryHDU(header=hdul[0].header), compressed_hdu])
                new_hdul.writeto(output_file, overwrite=True)
            
            # Now test verification
            print("\nVerification process:")
            
            with fits.open(fits_file) as orig_hdul:
                print(f"Original file: {len(orig_hdul)} HDUs")
                print(f"  HDU 0: {type(orig_hdul[0]).__name__}, data shape: {orig_hdul[0].data.shape if orig_hdul[0].data is not None else 'None'}")
                
                with fits.open(output_file) as comp_hdul:
                    print(f"Compressed file: {len(comp_hdul)} HDUs")
                    for i, hdu in enumerate(comp_hdul):
                        print(f"  HDU {i}: {type(hdu).__name__}, data shape: {hdu.data.shape if hdu.data is not None else 'None'}")
                    
                    # Find compressed data
                    comp_data = None
                    for hdu in comp_hdul:
                        if hasattr(hdu, 'data') and hdu.data is not None:
                            comp_data = hdu.data
                            print(f"Found data in {type(hdu).__name__}: shape={comp_data.shape}, dtype={comp_data.dtype}")
                            print(f"Compressed data sample: {comp_data[0, 0:5]}")
                            break
                    
                    if comp_data is None:
                        print("✗ No data found in compressed file")
                        return
                    
                    # Check shape
                    if orig_hdul[0].data.shape != comp_data.shape:
                        print(f"✗ Shape mismatch: {orig_hdul[0].data.shape} vs {comp_data.shape}")
                        return
                    
                    print(f"✓ Shapes match: {orig_hdul[0].data.shape}")
                    
                    # Check data equality
                    if np.allclose(orig_hdul[0].data, comp_data, rtol=1e-6):
                        print("✓ Data arrays are approximately equal")
                        print("✓ Verification PASSED")
                    else:
                        print("✗ Data arrays are not equal")
                        
                        # Check exact equality
                        if np.array_equal(orig_hdul[0].data, comp_data):
                            print("✓ Data arrays are exactly equal")
                        else:
                            diff = np.abs(orig_hdul[0].data - comp_data)
                            max_diff = np.max(diff)
                            print(f"Max difference: {max_diff}")
                            print(f"Mean difference: {np.mean(diff)}")
                            
                            # Check for type differences
                            print(f"Original dtype: {orig_hdul[0].data.dtype}")
                            print(f"Compressed dtype: {comp_data.dtype}")
                            
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_verification()