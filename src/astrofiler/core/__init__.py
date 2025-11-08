"""
Core modules for AstroFiler application.

This package contains modular components extracted from the original monolithic 
astrofiler_file.py for better maintainability and organization:

- utils: Common utility functions
- file_processing: FITS file handling and database operations  
- calibration: Master frame creation and calibration processing
- quality_analysis: Image quality assessment and metrics
- repository: File organization and repository management
"""

import os
from typing import Optional, Union, Any

from ..types import FilePath

__version__ = "1.2.0"

# Import key classes and functions for convenient access
from .file_processing import FileProcessor
from .calibration import CalibrationProcessor
from .quality_analysis import QualityAnalyzer
from .repository import RepositoryManager
from .master_manager import MasterFrameManager, get_master_manager
from .utils import (
    normalize_file_path,
    sanitize_filesystem_name,
    dwarfFixHeader,
    mapFitsHeader,
    clearMappingCache,
    get_master_calibration_path
)

# Create a unified processing class that combines all functionality
class fitsProcessing:
    """
    Unified FITS processing class that combines all core functionality.
    
    This class provides backwards compatibility with the original fitsProcessing
    class while using the new modular architecture internally.
    """
    
    def __init__(self) -> None:
        """Initialize all processor components."""
        self.file_processor = FileProcessor()
        self.calibration_processor = CalibrationProcessor()
        self.quality_analyzer = QualityAnalyzer()
        self.repository_manager = RepositoryManager()
        self.master_manager = get_master_manager()  # Advanced master frame management
        
        # Load configuration for backwards compatibility
        import configparser
        self.config = configparser.ConfigParser()
        self.config.read('astrofiler.ini')
        self.sourceFolder: str = self.config.get('DEFAULT', 'source', fallback='.')
        self.repoFolder: str = self.config.get('DEFAULT', 'repo', fallback='.')
    
    # Delegate methods to appropriate processors with original signatures
    def calculateFileHash(self, filePath: FilePath) -> Optional[str]:
        """Calculate hash for file - delegates to FileProcessor."""
        return self.file_processor.calculateFileHash(filePath)
    
    def registerFitsImage(self, root: str, file: str, moveFiles: bool) -> Union[str, bool]:
        """Register FITS image - original signature from astrofiler_file."""
        # Combine root and file to get full path
        fileName = os.path.join(root, file)
        return self.file_processor.registerFitsImage(fileName, file=file, verbose=True, 
                                                   initalProcess=True, progressbar=None)
    
    def registerFitsImages(self, moveFiles=True, progress_callback=None):
        """Register multiple FITS images from source folder."""
        import os
        processed_files = 0
        
        for root, dirs, files in os.walk(self.sourceFolder):
            for file in files:
                if file.lower().endswith(('.fits', '.fit', '.fts')):
                    try:
                        self.registerFitsImage(root, file, moveFiles)
                        processed_files += 1
                        if progress_callback:
                            progress_callback(processed_files)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error processing {file}: {e}")
        
        return processed_files
    
    def submitFileToDB(self, fileName, hdr, fileHash=None):
        """Submit file to database - original signature."""
        # Extract required parameters from header
        newName = os.path.basename(fileName)
        newPath = os.path.dirname(fileName)
        exptime = hdr.get('EXPTIME', 0)
        source = 'astrofiler'
        
        # Get HDU data - for backwards compatibility, set to None if not available
        hduData = None
        
        return self.file_processor.submitFileToDB(fileName, hdr, hduData, 
                                                newName, newPath, exptime, source)
    
    def extractZipFile(self, zip_path):
        """Extract ZIP file - original signature."""
        return self.file_processor.extractZipFile(zip_path, progressbar=None)
    
    def convertXisfToFits(self, xisf_file_path):
        """Convert XISF to FITS - original signature."""
        return self.file_processor.convertXisfToFits(xisf_file_path, outputFile=None)
    
    def createMasterCalibrationFrames(self, progress_callback=None):
        """Create master calibration frames - original signature."""
        return self.calibration_processor.createMasterCalibrationFrames(
            sessionList=None, imageType=None, progressbar=progress_callback)
    
    def createMasterCalibrationFramesForSessions(self, session_list, progress_callback=None):
        """Create master calibration frames for specific sessions."""
        return self.calibration_processor.createMasterCalibrationFrames(
            sessionList=session_list, imageType=None, progressbar=progress_callback)
    
    def checkCalibrationSessionsForMasters(self, min_files=2, progress_callback=None):
        """Check calibration sessions for masters - original signature."""
        return self.calibration_processor.checkCalibrationSessionsForMasters(
            progressbar=progress_callback)
    
    # Advanced master management methods
    def createAdvancedMaster(self, session_id, cal_type, min_files=2, progress_callback=None):
        """Create master frame using advanced Siril integration."""
        return self.master_manager.create_master_from_session(
            session_id, cal_type, min_files, progress_callback)
    
    def findMatchingMaster(self, session_data, cal_type):
        """Find a matching master frame for the given session."""
        return self.master_manager.find_matching_master(session_data, cal_type)
    
    def validateMasters(self, progress_callback=None):
        """Validate all master frames in the database and filesystem."""
        return self.master_manager.validate_masters(progress_callback)
    
    def cleanupMasters(self, retention_days=None, progress_callback=None):
        """Clean up old and unused master frames."""
        return self.master_manager.cleanup_masters(retention_days, progress_callback)
    
    def getMasterStatistics(self):
        """Get comprehensive statistics about master frames."""
        return self.master_manager.get_master_statistics()

# Export the main class for backwards compatibility
__all__ = [
    'fitsProcessing',
    'FileProcessor', 
    'CalibrationProcessor',
    'QualityAnalyzer',
    'RepositoryManager',
    'MasterFrameManager',
    'get_master_manager',
    'normalize_file_path',
    'sanitize_filesystem_name',
    'dwarfFixHeader',
    'mapFitsHeader',
    'clearMappingCache',
    'get_master_calibration_path'
]