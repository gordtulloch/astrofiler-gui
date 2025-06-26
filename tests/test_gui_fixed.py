"""
Tests for astrofiler_gui.py - GUI module
"""
import pytest
import sys
import os
from unittest.mock import patch, Mock, MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

# Ensure we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astrofiler_gui import (
    load_stylesheet, get_dark_stylesheet, get_light_stylesheet,
    detect_system_theme, ImagesTab, SequencesTab, ConfigTab, AboutTab, AstroFilerGUI
)


class TestStylesheetFunctions:
    """Test stylesheet loading functions."""
    
    @patch('builtins.open')
    def test_load_stylesheet_success(self, mock_open):
        """Test successful stylesheet loading."""
        mock_open.return_value.__enter__.return_value.read.return_value = "test css"
        
        result = load_stylesheet("test.css")
        
        assert result == "test css"
        mock_open.assert_called_once_with("test.css", 'r', encoding='utf-8')
    
    @patch('builtins.open', side_effect=FileNotFoundError())
    @patch('astrofiler_gui.logger')
    def test_load_stylesheet_file_not_found(self, mock_logger, mock_open):
        """Test stylesheet loading with file not found."""
        result = load_stylesheet("nonexistent.css")
        
        assert result == ""
        mock_logger.error.assert_called_once()
    
    @patch('builtins.open', side_effect=Exception("Test error"))
    @patch('astrofiler_gui.logger')
    def test_load_stylesheet_error(self, mock_logger, mock_open):
        """Test stylesheet loading with error."""
        result = load_stylesheet("error.css")

        assert result == ""
        mock_logger.error.assert_called_once()
    
    @patch('astrofiler_gui.load_stylesheet')
    def test_get_dark_stylesheet(self, mock_load):
        """Test getting dark stylesheet."""
        mock_load.return_value = "dark theme css"
        
        result = get_dark_stylesheet()
        
        assert result == "dark theme css"
        mock_load.assert_called_once_with("css/dark.css")
    
    @patch('astrofiler_gui.load_stylesheet')
    def test_get_light_stylesheet(self, mock_load):
        """Test getting light stylesheet."""
        mock_load.return_value = "light theme css"
        
        result = get_light_stylesheet()
        
        assert result == "light theme css"
        mock_load.assert_called_once_with("css/light.css")


class TestSystemThemeDetection:
    """Test system theme detection."""
    
    @patch('astrofiler_gui.os.name', 'nt')
    @patch('builtins.__import__')
    def test_detect_system_theme_windows_dark(self, mock_import):
        """Test Windows dark theme detection."""
        # Mock winreg module
        mock_winreg = Mock()
        mock_registry = Mock()
        mock_key = Mock()
        mock_winreg.ConnectRegistry.return_value = mock_registry
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = (0, None)  # Dark theme
        mock_winreg.HKEY_CURRENT_USER = -2147483647
        
        def import_side_effect(name, *args):
            if name == 'winreg':
                return mock_winreg
            return __import__(name, *args)
        
        mock_import.side_effect = import_side_effect
        
        result = detect_system_theme()
        
        assert result is True
    
    @patch('astrofiler_gui.os.name', 'nt')
    @patch('builtins.__import__')
    def test_detect_system_theme_windows_light(self, mock_import):
        """Test Windows light theme detection."""
        # Mock winreg module
        mock_winreg = Mock()
        mock_registry = Mock()
        mock_key = Mock()
        mock_winreg.ConnectRegistry.return_value = mock_registry
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = (1, None)  # Light theme
        mock_winreg.HKEY_CURRENT_USER = -2147483647
        
        def import_side_effect(name, *args):
            if name == 'winreg':
                return mock_winreg
            return __import__(name, *args)
        
        mock_import.side_effect = import_side_effect
        
        result = detect_system_theme()
        
        assert result is False
    
    @patch('astrofiler_gui.os.name', 'posix')
    def test_detect_system_theme_non_windows(self):
        """Test theme detection on non-Windows systems."""
        result = detect_system_theme()
        
        assert result is False  # Default to light theme
    
    @patch('astrofiler_gui.os.name', 'nt')
    @patch('builtins.__import__', side_effect=ImportError())
    def test_detect_system_theme_error(self, mock_import):
        """Test theme detection with error."""
        result = detect_system_theme()
        
        assert result is False  # Default on error


class TestImagesTab:
    """Test ImagesTab widget."""
    
    @pytest.fixture
    def images_tab(self, qapp):
        """Create an ImagesTab instance for testing."""
        with patch('astrofiler_gui.FitsFileModel'):
            tab = ImagesTab()
        return tab
    
    def test_images_tab_initialization(self, images_tab):
        """Test ImagesTab initialization."""
        assert images_tab.load_repo_button is not None
        assert images_tab.sync_repo_button is not None
        assert images_tab.clear_button is not None
        assert images_tab.file_tree is not None
    
    def test_images_tab_buttons_exist(self, images_tab):
        """Test that all expected buttons exist."""
        assert images_tab.load_repo_button.text() == "Load Repo"
        assert images_tab.sync_repo_button.text() == "Sync Repo"
        assert images_tab.clear_button.text() == "Clear Repo"
    
    def test_file_tree_headers(self, images_tab):
        """Test file tree headers."""
        expected_headers = ["Filename", "Object", "Type", "Filter", "Exptime", "Date", "Telescope", "Camera"]
        
        for i, header in enumerate(expected_headers):
            assert images_tab.file_tree.headerItem().text(i) == header
    
    @patch('astrofiler_gui.fitsProcessing')
    @patch('astrofiler_gui.QMessageBox')
    @patch('astrofiler_gui.QFileDialog')
    def test_load_repo_success(self, mock_dialog, mock_msgbox, mock_fits_processing, images_tab):
        """Test successful repo loading."""
        mock_dialog.getExistingDirectory.return_value = "/test/path"
        mock_processor = Mock()
        mock_fits_processing.return_value = mock_processor
        mock_processor.registerFitsImages.return_value = [1, 2, 3]
        
        with patch.object(images_tab, 'populate_file_tree'):
            images_tab.load_repo()
        
        mock_processor.registerFitsImages.assert_called_once_with(moveFiles=True)
        mock_msgbox.information.assert_called_once()
    
    @patch('astrofiler_gui.QFileDialog')
    def test_load_repo_error(self, mock_dialog, images_tab):
        """Test repo loading with no directory selected."""
        mock_dialog.getExistingDirectory.return_value = ""
        
        images_tab.load_repo()
        
        # Should return early without doing anything
        mock_dialog.getExistingDirectory.assert_called_once()
    
    @patch('astrofiler_gui.FitsFileModel')
    @patch('astrofiler_gui.QMessageBox')
    def test_clear_files(self, mock_msgbox, mock_model, images_tab):
        """Test clearing files."""
        images_tab.clear_files()
        
        mock_model.delete().execute.assert_called_once()
        mock_msgbox.information.assert_called_once()


class TestSequencesTab:
    """Test SequencesTab widget."""
    
    @pytest.fixture
    def sequences_tab(self, qapp):
        """Create a SequencesTab instance for testing."""
        with patch('astrofiler_gui.FitsSequenceModel'):
            tab = SequencesTab()
        return tab
    
    def test_sequences_tab_initialization(self, sequences_tab):
        """Test SequencesTab initialization."""
        assert sequences_tab.update_button is not None
        assert sequences_tab.sequences_tree is not None
    
    def test_update_button_text(self, sequences_tab):
        """Test update button text."""
        assert sequences_tab.update_button.text() == "Update"
    
    def test_sequences_tree_headers(self, sequences_tab):
        """Test sequences tree headers."""
        expected_headers = ["Sequence ID", "Object", "Type", "Filter", "Count", "Total Exp", "Date"]
        
        for i, header in enumerate(expected_headers):
            assert sequences_tab.sequences_tree.headerItem().text(i) == header
    
    @patch('astrofiler_gui.fitsProcessing')
    @patch('astrofiler_gui.QMessageBox')
    def test_update_sequences_success(self, mock_msgbox, mock_fits_processing, sequences_tab):
        """Test successful sequence update."""
        mock_processor = Mock()
        mock_fits_processing.return_value = mock_processor
        
        with patch.object(sequences_tab, 'load_sequences_data'):
            sequences_tab.update_sequences()
        
        mock_processor.createSequences.assert_called_once()
        mock_msgbox.information.assert_called_once()


class TestConfigTab:
    """Test ConfigTab widget."""
    
    @pytest.fixture
    def config_tab(self, qapp, mock_config_with_strings, mock_stylesheets):
        """Create a ConfigTab instance for testing."""
        with patch('builtins.open'), \
             patch('astrofiler_gui.configparser.ConfigParser', return_value=mock_config_with_strings), \
             patch('astrofiler_gui.detect_system_theme', return_value=False):
            tab = ConfigTab()
        return tab
    
    def test_config_tab_initialization(self, config_tab):
        """Test ConfigTab initialization."""
        assert config_tab.source_path is not None
        assert config_tab.repo_path is not None
        assert config_tab.theme is not None
        assert config_tab.save_button is not None
    
    def test_theme_options(self, config_tab):
        """Test theme combo box options."""
        theme_items = [config_tab.theme.itemText(i) for i in range(config_tab.theme.count())]
        expected_themes = ["Light", "Dark", "Auto"]
        
        assert theme_items == expected_themes
    
    @patch('builtins.open')
    @patch('astrofiler_gui.configparser.ConfigParser')
    @patch('astrofiler_gui.QMessageBox')
    def test_save_settings(self, mock_msgbox, mock_config_parser, mock_open, config_tab):
        """Test saving settings."""
        mock_config = Mock()
        mock_config_parser.return_value = mock_config
        
        config_tab.source_path.setText("/test/source")
        config_tab.repo_path.setText("/test/repo")
        
        config_tab.save_settings()
        
        mock_config.set.assert_called()
        mock_open.assert_called()
        mock_msgbox.information.assert_called_once()
    
    @patch('builtins.open')
    @patch('astrofiler_gui.configparser.ConfigParser')
    @patch('astrofiler_gui.QMessageBox')
    def test_reset_settings(self, mock_msgbox, mock_config_parser, mock_open, config_tab):
        """Test resetting settings."""
        mock_config = Mock()
        mock_config_parser.return_value = mock_config
        
        with patch.object(config_tab, 'load_settings'):
            config_tab.reset_settings()
        
        mock_msgbox.information.assert_called_once()


class TestAboutTab:
    """Test AboutTab widget."""
    
    @pytest.fixture
    def about_tab(self, qapp):
        """Create an AboutTab instance for testing."""
        tab = AboutTab()
        return tab
    
    def test_about_tab_initialization(self, about_tab):
        """Test AboutTab initialization."""
        assert about_tab.container is not None
        assert about_tab.background_label is not None
        assert about_tab.text_widget is not None
    
    def test_title_label_content(self, about_tab):
        """Test title label content."""
        title_text = about_tab.text_widget.toPlainText()
        assert "AstroFiler" in title_text


class TestAstroFilerGUI:
    """Test AstroFilerGUI main window."""
    
    @pytest.fixture
    def main_gui(self, qapp, mock_config_with_strings, mock_stylesheets, mock_database_setup):
        """Create an AstroFilerGUI instance for testing."""
        with patch('astrofiler_gui.FitsFileModel'), \
             patch('astrofiler_gui.FitsSequenceModel'), \
             patch('builtins.open'), \
             patch('astrofiler_gui.configparser.ConfigParser', return_value=mock_config_with_strings), \
             patch('astrofiler_gui.detect_system_theme', return_value=False), \
             patch('astrofiler_gui.setup_database'), \
             patch('astrofiler_gui.QApplication.instance', return_value=qapp):
            gui = AstroFilerGUI()
        return gui
    
    def test_main_gui_initialization(self, main_gui):
        """Test main GUI initialization."""
        assert main_gui.tab_widget is not None
        assert main_gui.images_tab is not None
        assert main_gui.sequences_tab is not None
        assert main_gui.views_tab is not None
        assert main_gui.config_tab is not None
        assert main_gui.about_tab is not None
    
    def test_tab_count(self, main_gui):
        """Test that all tabs are added."""
        assert main_gui.tab_widget.count() == 5
    
    def test_tab_titles(self, main_gui):
        """Test tab titles."""
        expected_titles = ["Images", "Sequences", "Views", "Config", "About"]
        
        for i, title in enumerate(expected_titles):
            assert main_gui.tab_widget.tabText(i) == title
    
    def test_window_title(self, main_gui):
        """Test window title."""
        assert "AstroFiler" in main_gui.windowTitle()
    
    def test_current_theme_default(self, main_gui):
        """Test default theme setting."""
        assert main_gui.current_theme == "Dark"
    
    def test_get_config_settings(self, main_gui):
        """Test getting configuration settings."""
        settings = main_gui.get_config_settings()
        
        assert 'source_path' in settings
        assert 'repo_path' in settings
        assert 'theme' in settings
        assert 'font_size' in settings
    
    def test_set_config_settings(self, main_gui):
        """Test setting configuration settings."""
        test_settings = {
            'source_path': '/test/source',
            'repo_path': '/test/repo',
            'theme': 'Light',
            'font_size': 12
        }
        
        main_gui.set_config_settings(test_settings)
        
        # Verify settings were applied
        assert main_gui.config_tab.source_path.text() == '/test/source'
        assert main_gui.config_tab.repo_path.text() == '/test/repo'
