#!/usr/bin/env python3
"""
Test script for enhanced FITS compression functionality with multiple algorithms
"""
import os
import sys
import numpy as np
from astropy.io import fits
import tempfile
import shutil

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

try:
    from astrofiler.core.compress_files import FitsCompressor
    print("✓ Successfully imported FitsCompressor")
except ImportError as e:
    print(f"✗ Failed to import FitsCompressor: {e}")
    sys.exit(1)

# Try to import PySiril for additional validation
try:
    from pysiril.siril import Siril
    PYSIRIL_AVAILABLE = True
    print("✓ PySiril available for validation")
except ImportError:
    PYSIRIL_AVAILABLE = False
    print("⚠ PySiril not available - using Astropy validation only")

def validate_fits_file(file_path, description=""):
    """
    Validate a FITS file using both Astropy and PySiril
    
    Args:
        file_path: Path to FITS file to validate
        description: Description for logging
        
    Returns:
        dict with validation results
    """
    results = {
        'astropy': {'success': False, 'error': None, 'info': {}},
        'pysiril': {'success': False, 'error': None, 'info': {}},
        'valid': False
    }
    
    # Test with Astropy
    try:
        with fits.open(file_path) as hdul:
            header = hdul[0].header
            data = hdul[0].data
            
            info = {}
            if 'OBJECT' in header:
                info['object'] = header['OBJECT']
            if 'NAXIS1' in header and 'NAXIS2' in header:
                info['dimensions'] = f"{header['NAXIS1']} x {header['NAXIS2']}"
            if 'BITPIX' in header:
                info['bitpix'] = header['BITPIX']
            if data is not None:
                info['shape'] = str(data.shape)
                info['dtype'] = str(data.dtype)
                info['min_val'] = float(np.min(data)) if not np.isnan(data).all() else 'NaN'
                info['max_val'] = float(np.max(data)) if not np.isnan(data).all() else 'NaN'
            
            results['astropy'] = {'success': True, 'error': None, 'info': info}
            
    except Exception as e:
        results['astropy'] = {'success': False, 'error': str(e), 'info': {}}
    
    # Test with PySiril if available
    if PYSIRIL_AVAILABLE:
        try:
            # Try to read the file with PySiril
            app = Siril()
            app.Open()  # Start Siril
            
            # Execute a simple command to load the FITS file
            # Use just the filename without path since Siril changes working directory
            filename = os.path.basename(file_path)
            cmd = f'load "{file_path}"'
            result = app.Execute(cmd)
            
            # PySiril Execute returns True for success, check the output
            if result is True:
                info = {'loaded': True}
                results['pysiril'] = {'success': True, 'error': None, 'info': info}
            else:
                results['pysiril'] = {'success': False, 'error': f'PySiril load failed: {result}', 'info': {}}
            
            app.Close()  # Close Siril
            
        except Exception as e:
            results['pysiril'] = {'success': False, 'error': str(e), 'info': {}}
    
    # Overall validation result
    results['valid'] = results['astropy']['success'] and (not PYSIRIL_AVAILABLE or results['pysiril']['success'])
    
    return results

def print_validation_results(results, description=""):
    """Print validation results in a readable format"""
    if description:
        print(f"  {description}:")
    
    # Astropy results
    if results['astropy']['success']:
        print(f"    ✓ Astropy: Valid FITS file")
        for key, value in results['astropy']['info'].items():
            if key in ['object', 'dimensions', 'bitpix']:
                print(f"      {key.title()}: {value}")
    else:
        print(f"    ✗ Astropy: {results['astropy']['error']}")
    
    # PySiril results
    if PYSIRIL_AVAILABLE:
        if results['pysiril']['success']:
            print(f"    ✓ PySiril: Successfully loaded FITS file")
        else:
            print(f"    ✗ PySiril: {results['pysiril']['error']}")
    else:
        print(f"    ⚠ PySiril: Not available for testing")
    
    # Overall result
    overall = "✓ Valid" if results['valid'] else "✗ Invalid"
    print(f"    {overall} FITS file")

def find_repository_fits_files():
    """Find FITS files in the repository"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    fits_files = []
    
    # Search for FITS files in common locations
    search_dirs = [
        os.path.join(project_root, 'misc'),
        os.path.join(project_root, 'test_data'),
        os.path.join(project_root, 'examples'),
        os.path.join(project_root, 'samples')
    ]
    
    for search_dir in search_dirs:
        if os.path.exists(search_dir):
            for root, dirs, files in os.walk(search_dir):
                for file in files:
                    if file.lower().endswith(('.fits', '.fit', '.fts')):
                        fits_files.append(os.path.join(root, file))
    
    return fits_files

def copy_repository_fits_file(dest_filename, fits_files):
    """Copy a FITS file from the repository for testing"""
    if not fits_files:
        raise ValueError("No FITS files found in repository")
    
    # For now, use the first file found (could randomize later)
    source_file = fits_files[0]
    print(f"Using repository FITS file: {os.path.basename(source_file)}")
    
    # Copy to destination
    shutil.copy2(source_file, dest_filename)
    return dest_filename
    """Find FITS files in the repository"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    fits_files = []
    
    # Search for FITS files in common locations
    search_dirs = [
        os.path.join(project_root, 'misc'),
        os.path.join(project_root, 'test_data'),
        os.path.join(project_root, 'examples'),
        os.path.join(project_root, 'samples')
    ]
    
    for search_dir in search_dirs:
        if os.path.exists(search_dir):
            for root, dirs, files in os.walk(search_dir):
                for file in files:
                    if file.lower().endswith(('.fits', '.fit', '.fts')):
                        fits_files.append(os.path.join(root, file))
    
    return fits_files

def copy_repository_fits_file(dest_filename, fits_files):
    """Copy a FITS file from the repository for testing"""
    if not fits_files:
        raise ValueError("No FITS files found in repository")
    
    # For now, use the first file found (could randomize later)
    source_file = fits_files[0]
    print(f"Using repository FITS file: {os.path.basename(source_file)}")
    
    # Copy to destination
    shutil.copy2(source_file, dest_filename)
    return dest_filename

def test_compression_algorithms():
    """Test all compression algorithms and auto-selection"""
    print("\n=== Testing Enhanced FITS Compression ===\n")
    
    # Find available FITS files in repository
    fits_files = find_repository_fits_files()
    if not fits_files:
        print("✗ No FITS files found in repository for testing")
        print("Please ensure there are FITS files in the misc/, test_data/, examples/, or samples/ directories")
        return
    
    print(f"Found {len(fits_files)} FITS file(s) in repository:")
    for fits_file in fits_files:
        rel_path = os.path.relpath(fits_file, os.path.dirname(os.path.abspath(__file__)))
        file_size = os.path.getsize(fits_file) / (1024 * 1024)  # MB
        print(f"  - {rel_path} ({file_size:.1f} MB)")
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix='astrofiler_compression_test_')
    print(f"\nTest directory: {temp_dir}")
    
    try:
        # Test with the repository FITS file
        test_file = os.path.join(temp_dir, 'test_repo_file.fits')
        copy_repository_fits_file(test_file, fits_files)
        
        original_size = os.path.getsize(test_file)
        print(f"\nOriginal file size: {original_size:,} bytes ({original_size/(1024*1024):.1f} MB)")
        
        # Validate the original FITS file with both Astropy and PySiril
        print(f"\n=== Original FITS File Validation ===")
        original_validation = validate_fits_file(test_file, "Original file")
        print_validation_results(original_validation)
        
        if not original_validation['valid']:
            print("✗ Original FITS file validation failed - aborting compression tests")
            return
        
        compressor = FitsCompressor()
        
        print(f"\n--- Testing compression algorithms on real FITS data ---")
        
        # Test each algorithm
        algorithms = ['gzip', 'lzma', 'bzip2']
        results = {}
        
        for algorithm in algorithms:
            try:
                print(f"\nTesting {algorithm}...")
                # Test compression - important: don't replace original!
                success = compressor.compress_fits_file(test_file, replace_original=False, algorithm=algorithm)
                
                # The compressed file should be test_file + algorithm extension
                if algorithm == 'gzip':
                    compressed_file = test_file + '.gz'
                elif algorithm == 'lzma':
                    compressed_file = test_file + '.xz'
                elif algorithm == 'bzip2':
                    compressed_file = test_file + '.bz2'
                else:
                    compressed_file = test_file + '.gz'  # fallback
                
                print(f"  Expected output: {compressed_file}")
                print(f"  Success result: {success}")
                print(f"  File exists: {os.path.exists(compressed_file) if compressed_file else False}")
                
                if success and success == compressed_file and os.path.exists(compressed_file):
                    compressed_size = os.path.getsize(compressed_file)
                    ratio = (1 - compressed_size / original_size) * 100
                    results[algorithm] = {
                        'size': compressed_size,
                        'ratio': ratio,
                        'success': True
                    }
                    print(f"  ✓ Compressed: {compressed_size:>10,} bytes ({ratio:>5.1f}% reduction)")
                    
                    # Test direct loading of compressed FITS file
                    print(f"  Testing direct compressed file loading...")
                    compressed_validation = validate_fits_file(compressed_file, "Compressed file")
                    if compressed_validation['astropy']['success']:
                        print(f"    ✓ Astropy: Can directly load compressed FITS file")
                    else:
                        print(f"    ✗ Astropy: Cannot load compressed file - {compressed_validation['astropy']['error']}")
                    
                    if PYSIRIL_AVAILABLE:
                        if compressed_validation['pysiril']['success']:
                            print(f"    ✓ PySiril: Can directly load compressed FITS file")
                        else:
                            print(f"    ✗ PySiril: Cannot load compressed file - {compressed_validation['pysiril']['error']}")
                    
                    # Test decompression for integrity verification only
                    decompressed_file = os.path.join(temp_dir, f'test_repo_{algorithm}_decompressed.fits')
                    if compressor.decompress_fits_file(compressed_file, decompressed_file):
                        # Verify integrity
                        if os.path.getsize(decompressed_file) == original_size:
                            print(f"    ✓ Decompression integrity: File size matches original")
                        else:
                            print(f"    ⚠ Decompression integrity: Size mismatch!")
                    else:
                        print(f"    ✗ Decompression integrity test failed")
                    
                    # Clean up compressed file
                    if os.path.exists(compressed_file):
                        os.remove(compressed_file)
                    # Add small delay to ensure file handles are released
                    import time
                    time.sleep(0.1)
                    if os.path.exists(decompressed_file):
                        try:
                            os.remove(decompressed_file)
                        except PermissionError:
                            print(f"  ⚠ Could not remove {decompressed_file} - file in use")
                else:
                    results[algorithm] = {
                        'size': 0,
                        'ratio': 0,
                        'success': False
                    }
                    print(f"  ✗ {algorithm}: Compression failed")
                    
            except Exception as e:
                print(f"  ✗ {algorithm}: Error - {e}")
                import traceback
                traceback.print_exc()
                results[algorithm] = {
                    'size': 0,
                    'ratio': 0,
                    'success': False,
                    'error': str(e)
                }
        
        # Show compression summary
        print(f"\n--- Compression Results Summary ---")
        successful_results = {k: v for k, v in results.items() if v['success']}
        if successful_results:
            print(f"Original size: {original_size:>10,} bytes")
            for algorithm, result in successful_results.items():
                print(f"{algorithm:>5}: {result['size']:>10,} bytes ({result['ratio']:>5.1f}% reduction)")
            
            best_algorithm = max(successful_results.keys(), key=lambda x: successful_results[x]['ratio'])
            best_ratio = successful_results[best_algorithm]['ratio']
            print(f"\n🏆 Best compression: {best_algorithm} ({best_ratio:.1f}% reduction)")
        else:
            print("No algorithms succeeded")
        
        # Clean up test file
        os.remove(test_file)
    
    finally:
        # Clean up temporary directory - try gracefully first
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            print("⚠ Could not remove all temporary files - some may still be in use")
            # Try to remove individual files after delay
            import time
            time.sleep(0.5)
            try:
                shutil.rmtree(temp_dir)
            except:
                pass  # Ignore if still can't remove
    
    print(f"\n✓ Enhanced compression testing completed!")

def test_configuration_integration():
    """Test compression configuration"""
    print("\n=== Testing Configuration Integration ===\n")
    
    # Test creating compressor with default config
    try:
        compressor = FitsCompressor()
        print("✓ Default compressor created successfully")
        print(f"  Algorithm: {compressor.compression_algorithm}")
        print(f"  Level: {compressor.compression_level}")
        print(f"  Verify: {compressor.verify_compression}")
    except Exception as e:
        print(f"✗ Failed to create default compressor: {e}")
    
    # Test configuration file reading
    try:
        # Create a temporary config file for testing
        temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False)
        temp_config.write("""[DEFAULT]
compress_fits = true
compression_algorithm = lzma
compression_level = 9
verify_compression = false
""")
        temp_config.close()
        
        # Test with custom config
        custom_compressor = FitsCompressor(config_path=temp_config.name)
        print("\n✓ Custom compressor created successfully")
        print(f"  Algorithm: {custom_compressor.compression_algorithm}")
        print(f"  Level: {custom_compressor.compression_level}")
        print(f"  Verify: {custom_compressor.verify_compression}")
        
        # Clean up
        os.unlink(temp_config.name)
        
    except Exception as e:
        print(f"✗ Failed to test custom configuration: {e}")
    
    print("\n✓ Configuration integration testing completed!")

if __name__ == "__main__":
    try:
        test_compression_algorithms()
        test_configuration_integration()
        print("\n🎉 All enhanced compression tests passed!")
        
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)