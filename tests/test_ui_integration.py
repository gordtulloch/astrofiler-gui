#!/usr/bin/env python3
"""
Test script to verify UI package integration.
"""

import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_ui_imports():
    """Test that UI modules can be imported correctly."""
    try:
        # Test basic package import
        import astrofiler.ui
        print("✓ Basic UI package import successful")
        
        # Test specific module import
        from astrofiler.ui.main_window import AstroFilerGUI
        print("✓ Main window import successful")
        
        # Test UI package exports
        if hasattr(astrofiler.ui, 'AstroFilerGUI'):
            print("✓ Main GUI class available through package")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Testing UI package integration...")
    print("=" * 50)
    
    success = test_ui_imports()
    
    print("=" * 50)
    if success:
        print("🎉 All UI import tests passed!")
    else:
        print("❌ Some tests failed.")
        sys.exit(1)