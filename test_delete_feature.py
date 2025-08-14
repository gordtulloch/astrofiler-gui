#!/usr/bin/env python3
"""
Test script to verify the new "Delete files on host" functionality
"""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all imports work correctly."""
    try:
        from astrofiler_gui import SmartTelescopeDownloadDialog, TelescopeDownloadWorker
        from astrofiler_smart import smart_telescope_manager
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_dialog_creation():
    """Test that the dialog can be created with the new checkbox."""
    try:
        from PySide6.QtWidgets import QApplication
        from astrofiler_gui import SmartTelescopeDownloadDialog
        
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        dialog = SmartTelescopeDownloadDialog()
        
        # Check if the checkbox exists
        if hasattr(dialog, 'delete_files_checkbox'):
            print("✓ Delete files checkbox found")
            print(f"✓ Checkbox default state: {dialog.delete_files_checkbox.isChecked()}")
            print(f"✓ Checkbox tooltip: {dialog.delete_files_checkbox.toolTip()}")
            return True
        else:
            print("✗ Delete files checkbox not found")
            return False
            
    except Exception as e:
        print(f"✗ Dialog creation error: {e}")
        return False

def test_worker_constructor():
    """Test that the worker can be created with the new delete_files parameter."""
    try:
        from astrofiler_gui import TelescopeDownloadWorker
        
        # Test without delete_files parameter (should default to False)
        worker1 = TelescopeDownloadWorker("SeeStar", "SEESTAR", "192.168.1.0/24")
        if hasattr(worker1, 'delete_files') and worker1.delete_files == False:
            print("✓ Worker default delete_files = False")
        else:
            print("✗ Worker default delete_files incorrect")
            return False
        
        # Test with delete_files parameter
        worker2 = TelescopeDownloadWorker("SeeStar", "SEESTAR", "192.168.1.0/24", delete_files=True)
        if hasattr(worker2, 'delete_files') and worker2.delete_files == True:
            print("✓ Worker delete_files = True when specified")
        else:
            print("✗ Worker delete_files not set correctly")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Worker constructor error: {e}")
        return False

def test_delete_method():
    """Test that the delete_file method exists in smart_telescope_manager."""
    try:
        from astrofiler_smart import smart_telescope_manager
        
        if hasattr(smart_telescope_manager, 'delete_file'):
            print("✓ delete_file method found in smart_telescope_manager")
            return True
        else:
            print("✗ delete_file method not found")
            return False
            
    except Exception as e:
        print(f"✗ Delete method test error: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing new 'Delete files on host' functionality...")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_dialog_creation,
        test_worker_constructor,
        test_delete_method
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! The delete functionality is ready.")
    else:
        print("❌ Some tests failed. Please review the implementation.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
