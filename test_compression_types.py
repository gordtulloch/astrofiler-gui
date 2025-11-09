#!/usr/bin/env python3
"""
Test different FITS compression types
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

def test_compression_types():
    """Test different FITS compression algorithms"""
    
    fits_file = os.path.join(project_root, 'misc', 'example.fits')
    
    compression_types = ['RICE_1', 'GZIP_1', 'GZIP_2']
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for comp_type in compression_types:
            print(f"\nTesting {comp_type} compression:")
            output_file = os.path.join(temp_dir, f'compressed_{comp_type.lower()}.fits')
            
            try:
                # Load and compress
                with fits.open(fits_file) as hdul:
                    compressed_hdu = fits.CompImageHDU(
                        data=hdul[0].data,
                        header=hdul[0].header,
                        compression_type=comp_type
                    )
                    
                    new_hdul = fits.HDUList([fits.PrimaryHDU(header=hdul[0].header), compressed_hdu])
                    new_hdul.writeto(output_file, overwrite=True)
                
                original_size = os.path.getsize(fits_file)
                compressed_size = os.path.getsize(output_file)
                ratio = (1 - compressed_size / original_size) * 100
                
                print(f"  Compression ratio: {ratio:.1f}%")
                
                # Test verification
                with fits.open(fits_file) as orig_hdul:
                    with fits.open(output_file) as comp_hdul:
                        comp_data = comp_hdul[1].data  # CompImageHDU is at index 1
                        
                        # Check exact equality
                        if np.array_equal(orig_hdul[0].data, comp_data):
                            print(f"  ✓ Lossless: Data arrays are exactly equal")
                        else:
                            # Check approximate equality
                            if np.allclose(orig_hdul[0].data, comp_data, rtol=1e-6):
                                diff = np.abs(orig_hdul[0].data - comp_data)
                                max_diff = np.max(diff)
                                mean_diff = np.mean(diff)
                                print(f"  ~ Near-lossless: max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e}")
                            else:
                                print(f"  ✗ Lossy compression detected")
                        
                        print(f"  Original dtype: {orig_hdul[0].data.dtype}")
                        print(f"  Compressed dtype: {comp_data.dtype}")
                        
            except Exception as e:
                print(f"  ✗ Error: {e}")

if __name__ == "__main__":
    test_compression_types()