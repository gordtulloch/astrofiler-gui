#!/usr/bin/env python3
"""
Test script to verify the enhanced Cloud Sync dialog
"""

import sys
from PySide6.QtWidgets import QApplication
from ui.cloud_sync_dialog import CloudSyncDialog

def test_enhanced_cloud_sync_dialog():
    """Test the enhanced Cloud Sync dialog with configuration display"""
    
    # Create a Qt application
    app = QApplication(sys.argv)
    
    # Create the dialog
    dialog = CloudSyncDialog()
    
    print("Testing enhanced Cloud Sync dialog...")
    print(f"Dialog title: {dialog.windowTitle()}")
    print(f"Dialog size: {dialog.size().width()}x{dialog.size().height()}")
    
    # Test configuration loading
    config = dialog.cloud_config
    print(f"\nLoaded configuration:")
    print(f"  Vendor: {config['vendor']}")
    print(f"  Bucket: {config['bucket_url']}")
    print(f"  Auth file: {'Configured' if config['auth_file_path'] and config['auth_file_path'] != 'Not configured' else 'Not configured'}")
    print(f"  Sync profile: {config['sync_profile']}")
    
    print("\n✅ Enhanced Cloud Sync dialog created and configured successfully!")
    
    return True

if __name__ == "__main__":
    test_enhanced_cloud_sync_dialog()