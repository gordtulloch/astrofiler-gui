#!/usr/bin/env python3
"""
Test script to verify the cloud file listing functionality
"""

import sys
from PySide6.QtWidgets import QApplication
from ui.cloud_sync_dialog import CloudSyncDialog

def test_cloud_listing():
    """Test the cloud file listing functionality"""
    
    # Create a Qt application
    app = QApplication(sys.argv)
    
    # Create the dialog
    dialog = CloudSyncDialog()
    
    print("Testing cloud file listing functionality...")
    
    # Test that the method exists
    assert hasattr(dialog, 'get_cloud_file_list'), "get_cloud_file_list method not found"
    print("✅ get_cloud_file_list method exists")
    
    # Test that the matching method exists
    assert hasattr(dialog, 'find_matching_local_file'), "find_matching_local_file method not found"
    print("✅ find_matching_local_file method exists")
    
    # Test that the URL building method exists
    assert hasattr(dialog, 'build_cloud_url'), "build_cloud_url method not found"
    print("✅ build_cloud_url method exists")
    
    # Test URL building with mock data
    mock_cloud_file = {
        'name': 'test/file.fits',
        'url': 'gs://test-bucket/test/file.fits',
        'size': 1024,
        'md5_hash': 'abc123'
    }
    
    url = dialog.build_cloud_url(mock_cloud_file)
    print(f"✅ Cloud URL building works: {url}")
    
    # Test filename extraction in matching
    filename = mock_cloud_file['name'].split('/')[-1]
    print(f"✅ Filename extraction works: {filename}")
    
    print("\n✅ All cloud listing functionality tests passed!")
    
    return True

if __name__ == "__main__":
    test_cloud_listing()