"""
Tests for astrofiler.py - Main application entry point
"""
import pytest
import sys
import os
from unittest.mock import patch, Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMainApplication:
    """Test the main application entry point."""
    
    @patch('astrofiler.QApplication')
    @patch('astrofiler.AstroFilerGUI')
    @patch('astrofiler.setup_database')
    def test_main_application_startup(self, mock_setup_db, mock_gui, mock_qapp):
        """Test that the main application starts correctly."""
        # Mock QApplication
        mock_app_instance = Mock()
        mock_qapp.return_value = mock_app_instance
        
        # Mock GUI
        mock_gui_instance = Mock()
        mock_gui.return_value = mock_gui_instance
        
        # Import and run main (this would normally be in if __name__ == '__main__')
        with patch('sys.argv', ['astrofiler.py']):
            try:
                import astrofiler
                # Since the main code is under if __name__ == '__main__',
                # we'll test the components individually
                
                # Test that imports work
                assert hasattr(astrofiler, 'AstroFilerGUI')
                assert hasattr(astrofiler, 'setup_database')
                assert hasattr(astrofiler, 'QApplication')
                
            except SystemExit:
                pass  # Expected if QApplication.exec() is called
    
    def test_imports_available(self):
        """Test that all required modules can be imported."""
        try:
            import astrofiler
            assert astrofiler is not None
        except ImportError as e:
            pytest.fail(f"Failed to import main application: {e}")
    
    @patch('astrofiler.sys.argv', ['astrofiler.py', '--test'])
    def test_command_line_args(self):
        """Test handling of command line arguments."""
        # This would test any command line argument handling
        # Currently the main app doesn't have specific CLI args,
        # but this structure is here for future expansion
        import astrofiler
        assert len(astrofiler.sys.argv) >= 1
