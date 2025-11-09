#!/usr/bin/env python3
"""
Debug script for compression algorithm issues
"""
import os
import sys

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from astrofiler.core.compress_files import FitsCompressor

def test_algorithm_support():
    """Test individual algorithm support"""
    compressor = FitsCompressor()
    
    print("Testing compression algorithm support:")
    print(f"Available algorithms: {list(compressor.algorithms.keys())}")
    
    # Test each algorithm info
    for algo in ['gzip', 'lzma', 'bzip2', 'auto']:
        try:
            info = compressor.get_algorithm_info(algo)
            print(f"  {algo}: {info}")
        except Exception as e:
            print(f"  {algo}: ERROR - {e}")
    
    # Test path generation
    test_file = "test.fits"
    for algo in ['gzip', 'lzma', 'bzip2']:
        try:
            path = compressor.get_compressed_path(test_file, algo)
            print(f"  {algo} path: {path}")
        except Exception as e:
            print(f"  {algo} path: ERROR - {e}")

if __name__ == "__main__":
    test_algorithm_support()