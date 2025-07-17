#!/usr/bin/env python3
"""
Tests for the GUI components.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication

# Add the parent directory to the path to import the application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Create a QApplication instance for GUI tests
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()

class TestGUIComponents:
    """Test the GUI components of the application."""
    
    @pytest.mark.skip(reason="This test requires a GUI environment")
    def test_session_tab_creation(self, qapp):
        """Test creating the Sessions tab."""
        from astrofiler_gui import SessionsTab
        
        # Create a sessions tab
        with patch('astrofiler_gui.FitsSessionModel.select') as mock_select:
            # Mock the select method to return an empty list
            mock_select.return_value = []
            
            # Create the tab
            tab = SessionsTab()
            
            # Check if the tab was created
            assert tab is not None
            
            # Check if the tree widget was created
            assert hasattr(tab, 'sessions_tree')
    
    @pytest.mark.skip(reason="This test requires a GUI environment")
    def test_images_tab_creation(self, qapp):
        """Test creating the Images tab."""
        from astrofiler_gui import ImagesTab
        
        # Create an images tab
        with patch('astrofiler_gui.FitsFileModel.select') as mock_select:
            # Mock the select method to return an empty list
            mock_select.return_value = []
            
            # Create the tab
            tab = ImagesTab()
            
            # Check if the tab was created
            assert tab is not None
            
            # Check if the tree widget was created
            assert hasattr(tab, 'file_tree')
    
    @pytest.mark.skip(reason="This test requires a GUI environment")
    def test_context_menu_creation(self, qapp):
        """Test creating a context menu."""
        from astrofiler_gui import SessionsTab
        from PySide6.QtCore import Qt, QPoint
        
        # Create a sessions tab
        with patch('astrofiler_gui.FitsSessionModel.select') as mock_select:
            # Mock the select method to return an empty list
            mock_select.return_value = []
            
            # Create the tab
            tab = SessionsTab()
            
            # Check if the context menu policy is set
            assert tab.sessions_tree.contextMenuPolicy() == Qt.CustomContextMenu
            
            # Check if the context menu signal is connected
            assert hasattr(tab, 'show_context_menu')
    
    @pytest.mark.skip(reason="This test requires a GUI environment")
    def test_checkout_session(self, qapp):
        """Test checking out a session."""
        from astrofiler_gui import SessionsTab
        from PySide6.QtWidgets import QTreeWidgetItem
        
        # Create a sessions tab
        with patch('astrofiler_gui.FitsSessionModel.select') as mock_select:
            # Mock the select method to return an empty list for initialization
            mock_select.return_value = []
            
            # Create the tab
            tab = SessionsTab()
            
            # Create a mock session item
            parent_item = QTreeWidgetItem()
            parent_item.setText(0, "TestObject")
            
            child_item = QTreeWidgetItem(parent_item)
            child_item.setText(0, "TestObject")
            child_item.setText(1, "2025-07-17")
            
            # Mock the database queries for checkout
            with patch('astrofiler_gui.FitsSessionModel.select') as mock_session_select, \
                 patch('astrofiler_gui.FitsFileModel.select') as mock_file_select, \
                 patch('astrofiler_gui.QFileDialog.getExistingDirectory') as mock_dialog, \
                 patch('os.makedirs') as mock_makedirs, \
                 patch('os.path.exists') as mock_exists, \
                 patch('os.symlink') as mock_symlink, \
                 patch('astrofiler_gui.QMessageBox.information') as mock_info:
                
                # Mock the session select to return a mock session
                mock_session = MagicMock()
                mock_session.fitsSessionId = 1
                mock_session.fitsSessionObjectName = "TestObject"
                mock_session.fitsSessionDate = "2025-07-17"
                mock_session.fitsBiasSession = 2
                mock_session.fitsDarkSession = 3
                mock_session.fitsFlatSession = 4
                mock_session_select.return_value.where.return_value.first.return_value = mock_session
                
                # Mock the file select to return a list of mock files
                mock_light_file = MagicMock()
                mock_light_file.fitsFileName = "/path/to/light.fits"
                mock_light_file.fitsFileType = "LIGHT"
                
                mock_dark_file = MagicMock()
                mock_dark_file.fitsFileName = "/path/to/dark.fits"
                mock_dark_file.fitsFileType = "DARK"
                
                mock_bias_file = MagicMock()
                mock_bias_file.fitsFileName = "/path/to/bias.fits"
                mock_bias_file.fitsFileType = "BIAS"
                
                mock_flat_file = MagicMock()
                mock_flat_file.fitsFileName = "/path/to/flat.fits"
                mock_flat_file.fitsFileType = "FLAT"
                
                # Set up return values for each where clause
                mock_file_select.return_value.where.side_effect = [
                    [mock_light_file],  # Light files
                    [mock_bias_file],   # Bias files
                    [mock_dark_file],   # Dark files
                    [mock_flat_file]    # Flat files
                ]
                
                # Mock the file dialog to return a test directory
                mock_dialog.return_value = "/test/output"
                
                # Mock exists to always return False (files don't exist yet)
                mock_exists.return_value = False
                
                # Call the checkout method
                tab.checkout_session(child_item)
                
                # Check if directories were created
                mock_makedirs.assert_called()
                
                # Check if symlinks were created
                mock_symlink.assert_called()
                
                # Check if success message was shown
                mock_info.assert_called()
