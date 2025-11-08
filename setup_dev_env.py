#!/usr/bin/env python3
"""
Development environment setup for AstroFiler
Adds the src directory to Python path for local development
"""
import sys
import os

# Add the src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')

if src_path not in sys.path:
    sys.path.insert(0, src_path)
    print(f"Added {src_path} to Python path")

# Test imports
if __name__ == "__main__":
    try:
        print("Testing package imports...")
        
        # Test main package import
        import astrofiler
        print("✓ astrofiler package imported successfully")
        
        # Test core functionality
        from astrofiler.core import fitsProcessing
        print("✓ fitsProcessing imported successfully")
        
        # Test individual components
        from astrofiler.core import FileProcessor, CalibrationProcessor
        print("✓ Core components imported successfully")
        
        # Test types and exceptions
        from astrofiler.types import FitsHeaderDict, FilePath
        from astrofiler.exceptions import AstroFilerError
        print("✓ Types and exceptions imported successfully")
        
        print("\n🎉 All imports successful! Development environment ready.")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        sys.exit(1)