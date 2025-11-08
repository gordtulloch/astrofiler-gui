"""
Calibration module for AstroFiler.

This module handles basic calibration operations and delegates advanced 
master frame management to the specialized MasterFrameManager.
"""

import os
import logging
import configparser
from astropy.io import fits

logger = logging.getLogger(__name__)


class CalibrationProcessor:
    """
    Handles basic calibration operations and coordinates with advanced master frame manager.
    """
    
    def __init__(self):
        """Initialize CalibrationProcessor with configuration."""
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        self.repoFolder = config.get('DEFAULT', 'repo', fallback='.')

    def createMasterCalibrationFrames(self, sessionList=None, imageType=None, progressbar=None):
        """
        Create master calibration frames using the advanced master manager.
        
        Args:
            sessionList: Optional list of session IDs to process
            imageType: Optional specific image type ('bias', 'dark', 'flat')
            progressbar: Optional progress callback
            
        Returns:
            dict: Results with counts of created masters
        """
        try:
            # Delegate to advanced master manager
            from .master_manager import get_master_manager
            master_manager = get_master_manager()
            
            from ..models import fitsSession as FitsSessionModel
            
            results = {'bias_masters': 0, 'dark_masters': 0, 'flat_masters': 0}
            
            # Get sessions to process
            if sessionList:
                sessions = [FitsSessionModel.get_by_id(sid) for sid in sessionList]
            else:
                # Find calibration sessions without masters
                calibration_sessions = []
                
                if not imageType or imageType == 'bias':
                    bias_sessions = FitsSessionModel.select().where(
                        (FitsSessionModel.fitsSessionObjectName.in_(['bias', 'Bias', 'BIAS'])) &
                        ((FitsSessionModel.fitsBiasMaster.is_null()) | (FitsSessionModel.fitsBiasMaster == ''))
                    )
                    calibration_sessions.extend(bias_sessions)
                
                if not imageType or imageType == 'dark':
                    dark_sessions = FitsSessionModel.select().where(
                        (FitsSessionModel.fitsSessionObjectName.in_(['dark', 'Dark', 'DARK'])) &
                        ((FitsSessionModel.fitsDarkMaster.is_null()) | (FitsSessionModel.fitsDarkMaster == ''))
                    )
                    calibration_sessions.extend(dark_sessions)
                
                if not imageType or imageType == 'flat':
                    flat_sessions = FitsSessionModel.select().where(
                        (FitsSessionModel.fitsSessionObjectName.in_(['flat', 'Flat', 'FLAT'])) &
                        ((FitsSessionModel.fitsFlatMaster.is_null()) | (FitsSessionModel.fitsFlatMaster == ''))
                    )
                    calibration_sessions.extend(flat_sessions)
                
                sessions = calibration_sessions
            
            total_sessions = len(sessions)
            if progressbar:
                progressbar(0, total_sessions, "Starting master frame creation...")
            
            for i, session in enumerate(sessions):
                try:
                    # Determine calibration type from session
                    obj_name = session.fitsSessionObjectName.lower()
                    cal_type = None
                    
                    if 'bias' in obj_name:
                        cal_type = 'bias'
                    elif 'dark' in obj_name:
                        cal_type = 'dark'
                    elif 'flat' in obj_name:
                        cal_type = 'flat'
                    
                    if not cal_type:
                        continue
                    
                    if progressbar:
                        progressbar(i + 1, total_sessions, f"Creating {cal_type} master for session {session.id}")
                    
                    # Use advanced master manager to create master
                    master = master_manager.create_master_from_session(
                        session_id=str(session.id),
                        cal_type=cal_type,
                        min_files=2,
                        progress_callback=progressbar
                    )
                    
                    if master:
                        # Update session with master reference
                        master_manager.update_session_with_master(
                            str(session.id), 
                            master.id, 
                            cal_type
                        )
                        results[f'{cal_type}_masters'] += 1
                        logger.info(f"Created {cal_type} master for session {session.id}")
                    
                except Exception as e:
                    logger.error(f"Error creating master for session {session.id}: {e}")
                    continue
            
            if progressbar:
                progressbar(total_sessions, total_sessions, "Master frame creation completed")
            
            logger.info(f"Master frame creation completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error in master frame creation: {e}")
            return {'error': str(e)}

    def checkCalibrationSessionsForMasters(self, progressbar=None):
        """
        Check calibration sessions and create masters where needed.
        
        Args:
            progressbar: Optional progress callback
            
        Returns:
            dict: Results of master creation check
        """
        try:
            # Delegate to advanced master manager for analysis
            from .master_manager import get_master_manager
            master_manager = get_master_manager()
            
            # First, validate existing masters
            if progressbar:
                progressbar(0, 100, "Validating existing masters...")
            
            validation_results = master_manager.validate_masters(progressbar)
            
            if progressbar:
                progressbar(50, 100, "Creating missing masters...")
            
            # Then create missing masters
            creation_results = self.createMasterCalibrationFrames(progressbar=progressbar)
            
            if progressbar:
                progressbar(100, 100, "Analysis completed")
            
            # Combine results
            results = {
                'validation': validation_results,
                'creation': creation_results,
                'summary': {
                    'validated_masters': validation_results.get('valid_masters', 0),
                    'created_masters': sum(creation_results.values()) if isinstance(creation_results, dict) else 0
                }
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Error in checkCalibrationSessionsForMasters: {e}")
            return {'error': str(e)}

    def findMatchingMaster(self, session_data, cal_type):
        """
        Find a matching master frame for the given session and calibration type.
        
        Args:
            session_data: Session data dictionary
            cal_type: Type of calibration ('bias', 'dark', 'flat')
            
        Returns:
            Master frame record or None
        """
        try:
            from .master_manager import get_master_manager
            master_manager = get_master_manager()
            
            return master_manager.find_matching_master(session_data, cal_type)
            
        except Exception as e:
            logger.error(f"Error finding matching master: {e}")
            return None

    def getMasterStatistics(self):
        """
        Get comprehensive statistics about master frames.
        
        Returns:
            Dictionary with master frame statistics
        """
        try:
            from .master_manager import get_master_manager
            master_manager = get_master_manager()
            
            return master_manager.get_master_statistics()
            
        except Exception as e:
            logger.error(f"Error getting master statistics: {e}")
            return {}

    def cleanupMasters(self, retention_days=None, progress_callback=None):
        """
        Clean up old and unused master frames.
        
        Args:
            retention_days: Number of days to retain masters
            progress_callback: Progress reporting function
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            from .master_manager import get_master_manager
            master_manager = get_master_manager()
            
            return master_manager.cleanup_masters(retention_days, progress_callback)
            
        except Exception as e:
            logger.error(f"Error cleaning up masters: {e}")
            return {'error': str(e)}