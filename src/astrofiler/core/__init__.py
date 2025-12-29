"""
Core modules for AstroFiler application.

This package contains modular components extracted from the original monolithic 
astrofiler_file.py for better maintainability and organization:

- utils: Common utility functions
- file_processing: FITS file handling and database operations  
- calibration: Master frame creation and calibration processing
- enhanced_quality: Advanced image quality assessment with SEP star detection
- repository: File organization and repository management
"""

import os
import sys
from typing import Optional, Union, Any

from ..types import FilePath

__version__ = "1.2.0"

# Import key classes and functions for convenient access
from .file_processing import FileProcessor
from .calibration import CalibrationProcessor
from .enhanced_quality import EnhancedQualityAnalyzer
from .repository import RepositoryManager
from .master_manager import MasterFrameManager, get_master_manager
from .compress_files import get_fits_compressor, compress_fits_file, is_compression_enabled
from .session_processing import SessionProcessor
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
        self.quality_analyzer = EnhancedQualityAnalyzer()
        self.repository_manager = RepositoryManager()
        self.master_manager = get_master_manager()  # Advanced master frame management
        self.session_processor = SessionProcessor()  # Session creation and linking
        
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
        return self.file_processor.registerFitsImage(root, file, moveFiles)

    def registerMasters(
        self,
        progress_callback=None,
        source_folder: Optional[str] = None,
        moveFiles: bool = False,
        destination_folder: Optional[str] = None,
        precount: bool = False,
    ):
        """Scan for existing master FITS files and register them in the Masters table."""
        return self.file_processor.registerMasters(
            progress_callback=progress_callback,
            source_folder=source_folder,
            moveFiles=moveFiles,
            destination_folder=destination_folder,
            precount=precount,
        )
    
    def registerFitsImages(self, moveFiles=True, progress_callback=None, source_folder=None):
        """Register multiple FITS images from source folder."""
        import os
        processed_files = []
        
        # Use specified folder or default to sourceFolder
        scan_folder = source_folder if source_folder else self.sourceFolder
        
        # First, count total files to process
        total_files = 0
        from .compress_files import get_fits_compressor
        compressor = get_fits_compressor()

        def _is_master_fits_by_imagetyp(file_path: str) -> bool:
            """Return True if FITS header IMAGETYP indicates a master calibration frame."""
            try:
                from astropy.io import fits
                hdr = fits.getheader(file_path, 0)
                imagetyp = str(hdr.get('IMAGETYP', '')).upper()
                if 'MASTER' not in imagetyp:
                    return False
                return any(token in imagetyp for token in ('DARK', 'FLAT', 'BIAS'))
            except Exception:
                return False
        
        for root, dirs, files in os.walk(scan_folder):
            for file in files:
                # Use the comprehensive FITS file detection that includes compressed files
                file_path = os.path.join(root, file)
                if compressor.is_fits_file(file_path):
                    if _is_master_fits_by_imagetyp(file_path):
                        continue
                    total_files += 1
        
        current_file = 0
        for root, dirs, files in os.walk(scan_folder):
            for file in files:
                # Use the comprehensive FITS file detection that includes compressed files
                file_path = os.path.join(root, file)
                if compressor.is_fits_file(file_path) or file.lower().endswith('.xisf'):
                    if compressor.is_fits_file(file_path) and _is_master_fits_by_imagetyp(file_path):
                        continue
                    current_file += 1
                    try:
                        result = self.registerFitsImage(root, file, moveFiles)
                        if result:  # If registration was successful
                            processed_files.append(file_path)
                        if progress_callback:
                            # Call with expected signature: current, total, filename
                            if not progress_callback(current_file, total_files, file_path):
                                break  # Stop if callback returns False (user cancelled)
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
    
    def runAutoCalibrationWorkflow(self, progress_callback=None, operations=None):
        """
        Run the auto-calibration workflow with optional operation selection.
        
        Args:
            progress_callback: Callback function for progress updates (percentage, message)
            operations: List of operations to run ['analyze', 'masters', 'calibrate', 'quality']
                       If None, runs all operations
        
        Returns:
            dict: Results with keys: status, sessions_analyzed, masters_created,
                  calibration_opportunities, light_frames_calibrated, errors
        """
        import logging
        from .auto_calibration import (
            load_config, validate_database_access,
            analyze_calibration_opportunities, create_master_frames,
            calibrate_light_frames, perform_quality_assessment
        )
        
        logger = logging.getLogger(__name__)
        
        # Default operations if none specified
        if operations is None:
            operations = ['analyze', 'masters', 'calibrate', 'quality']
        
        results = {
            'status': 'success',
            'sessions_analyzed': 0,
            'masters_created': 0,
            'calibration_opportunities': 0,
            'light_frames_calibrated': 0,
            'errors': []
        }
        
        try:
            # Load configuration
            config = load_config('astrofiler.ini')
            
            # Validate database access
            if not validate_database_access():
                raise Exception("Database validation failed")
            
            # Progress tracking
            total_operations = len(operations)
            completed_operations = 0
            
            for operation in operations:
                if progress_callback:
                    progress = int((completed_operations / total_operations) * 100)
                    progress_callback(progress, f"Running {operation} operation...")
                
                logger.info(f"Running auto-calibration operation: {operation}")
                
                try:
                    # Define progress callback for this operation
                    def operation_progress(percentage, message):
                        if progress_callback:
                            # Map operation progress to overall progress
                            base_progress = int((completed_operations / total_operations) * 100)
                            operation_progress_range = int(100 / total_operations)
                            overall_progress = base_progress + int((percentage * operation_progress_range) / 100)
                            progress_callback(overall_progress, message)
                    
                    if operation == 'analyze':
                        analysis_result = analyze_calibration_opportunities(config, progress_callback=operation_progress)
                        if analysis_result:
                            results['calibration_opportunities'] = analysis_result.get('total_opportunities', 0)
                        else:
                            raise Exception("Analysis failed")
                    
                    elif operation == 'masters':
                        success = create_master_frames(config, progress_callback=operation_progress)
                        if success:
                            # Count created masters (rough estimate based on opportunities)
                            results['masters_created'] = results.get('calibration_opportunities', 1)
                        else:
                            raise Exception("Master creation failed")
                    
                    elif operation == 'calibrate':
                        success = calibrate_light_frames(config, progress_callback=operation_progress)
                        if success:
                            # Rough estimate of calibrated sessions
                            results['light_frames_calibrated'] = 10  # Placeholder
                        else:
                            raise Exception("Light frame calibration failed")
                    
                    elif operation == 'quality':
                        success = perform_quality_assessment(config, progress_callback=operation_progress)
                        if not success:
                            raise Exception("Quality assessment failed")
                
                except Exception as e:
                    error_msg = f"{operation} operation failed: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
                    
                    # Critical operations cause complete failure
                    if operation in ['analyze', 'masters']:
                        results['status'] = 'error'
                        results['message'] = error_msg
                        return results
                
                completed_operations += 1
                
                if progress_callback:
                    progress = int((completed_operations / total_operations) * 100)
                    progress_callback(progress, f"Completed {operation} operation")
            
            # Final progress update
            if progress_callback:
                progress_callback(100, "Auto-calibration workflow completed")
            
            # Set sessions analyzed (rough estimate)
            results['sessions_analyzed'] = results.get('calibration_opportunities', 0) + results.get('light_frames_calibrated', 0)
            
            logger.info(f"Auto-calibration workflow completed: {results}")
            
        except Exception as e:
            error_msg = f"Auto-calibration workflow failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['status'] = 'error'
            results['message'] = error_msg
            results['errors'].append(error_msg)
        
        return results
    
    def validateMasters(self, progress_callback=None):
        """Validate all master frames in the database and filesystem."""
        return self.master_manager.validate_masters(progress_callback)
    
    def cleanupMasters(self, retention_days=None, progress_callback=None):
        """Clean up old and unused master frames."""
        return self.master_manager.cleanup_masters(retention_days, progress_callback)
    
    def getMasterStatistics(self):
        """Get comprehensive statistics about master frames."""
        return self.master_manager.get_master_statistics()
    
    # Session processing methods - delegate to SessionProcessor
    def createLightSessions(self, progress_callback=None):
        """Create sessions for all Light files not currently assigned to one."""
        return self.session_processor.createLightSessions(progress_callback)
    
    def createCalibrationSessions(self, progress_callback=None):
        """Create sessions for all calibration files not currently assigned to one."""
        return self.session_processor.createCalibrationSessions(progress_callback)

    def linkSessions(self, progress_callback=None):
        """Link calibration sessions to light sessions based on matching criteria."""
        return self.session_processor.linkSessions(progress_callback)

# Export the main class for backwards compatibility
__all__ = [
    'fitsProcessing',
    'FileProcessor', 
    'CalibrationProcessor',
    'EnhancedQualityAnalyzer',
    'RepositoryManager',
    'MasterFrameManager',
    'SessionProcessor',
    'get_master_manager',
    'get_fits_compressor',
    'compress_fits_file',
    'is_compression_enabled',
    'normalize_file_path',
    'sanitize_filesystem_name',
    'dwarfFixHeader',
    'mapFitsHeader',
    'clearMappingCache',
    'get_master_calibration_path'
]