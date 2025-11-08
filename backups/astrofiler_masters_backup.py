"""
Master Calibration Frame Management Module

This module handles all operations related to master calibration frames,
including creation, validation, storage, and matching to sessions.
"""

import os
import logging
import hashlib
import datetime
import shutil
import configparser
from pathlib import Path

from astrofiler_db import Masters, fitsSession, fitsFile, db

logger = logging.getLogger(__name__)


def _get_config():
    """Get configuration from astrofiler.ini file."""
    config = configparser.ConfigParser()
    config.read('astrofiler.ini')
    return config


class MasterFrameManager:
    """Manager class for master calibration frame operations."""
    
    def __init__(self):
        """Initialize the master frame manager."""
        self.config = _get_config()
        self.masters_dir = self._get_master_calibration_path()
    
    def _get_master_calibration_path(self):
        """
        Get the path to the master calibration frames directory.
        
        Returns:
            str: Path to the Masters directory within the repository folder
        """
        try:
            config = _get_config()
            repo_folder = config.get('DEFAULT', 'repository_folder')
        except Exception as e:
            logger.warning(f"Could not get repository folder from config: {e}")
            repo_folder = os.getcwd()
        
        masters_dir = os.path.join(repo_folder, 'Masters')
        os.makedirs(masters_dir, exist_ok=True)
        
        return masters_dir
    
    def find_matching_master(self, session_data, cal_type):
        """
        Find a matching master frame for the given session and calibration type.
        
        Args:
            session_data (dict): Session data with equipment and settings
            cal_type (str): Type of calibration ('bias', 'dark', 'flat')
            
        Returns:
            Masters: Matching master frame or None
        """
        try:
            criteria = {
                'exposure_time': session_data.get('exposure_time') if cal_type == 'dark' else None,
                'filter_name': session_data.get('filter_name') if cal_type == 'flat' else None,
                'binning_x': session_data.get('binning_x'),
                'binning_y': session_data.get('binning_y'),
                'ccd_temp': session_data.get('ccd_temp'),
                'gain': session_data.get('gain'),
                'offset': session_data.get('offset')
            }
            
            # Remove None values
            criteria = {k: v for k, v in criteria.items() if v is not None}
            
            return Masters.find_matching_master(
                telescope=session_data.get('telescope'),
                instrument=session_data.get('instrument'),
                master_type=cal_type,
                **criteria
            )
            
        except Exception as e:
            logger.error(f"Error finding matching master: {e}")
            return None
    
    def create_master_from_session(self, session_id, cal_type, min_files=2, progress_callback=None):
        """
        Create a master calibration frame from a session's files.
        
        Args:
            session_id (str): Session ID to create master from
            cal_type (str): Type of calibration ('bias', 'dark', 'flat')
            min_files (int): Minimum number of files required
            progress_callback (callable): Progress reporting function
            
        Returns:
            Masters: Created master record or None if failed
        """
        try:
            # Get session
            session = fitsSession.get_or_none(fitsSession.fitsSessionId == session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return None
            
            # Get files for this session and type
            files = list(fitsFile.select().where(
                fitsFile.fitsFileSession == session_id,
                fitsFile.fitsFileType.in_([cal_type, cal_type.upper()]),
                fitsFile.fitsFileSoftDelete == False
            ))
            
            if len(files) < min_files:
                logger.warning(f"Not enough {cal_type} files in session {session_id}: {len(files)} < {min_files}")
                return None
            
            if progress_callback:
                progress_callback(0, 100, f"Creating {cal_type} master from {len(files)} files...")
            
            # Generate master file path
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{cal_type}_master_{session.fitsSessionTelescope}_{timestamp}.fits"
            master_path = os.path.join(self.masters_dir, filename)
            
            # Create master using Siril
            file_paths = [file.fitsFileId for file in files]
            success = self._create_master_with_siril(file_paths, master_path, cal_type, progress_callback)
            
            if not success:
                logger.error(f"Failed to create master {cal_type} frame")
                return None
            
            # Create session data for master record
            session_data = {
                'telescope': session.fitsSessionTelescope,
                'instrument': session.fitsSessionImager,
                'exposure_time': session.fitsSessionExposure if cal_type == 'dark' else None,
                'binning_x': session.fitsSessionBinningX,
                'binning_y': session.fitsSessionBinningY,
                'ccd_temp': session.fitsSessionCCDTemp,
                'gain': session.fitsSessionGain,
                'offset': session.fitsSessionOffset,
                'filter_name': session.fitsSessionFilter if cal_type == 'flat' else None,
                'session_id': session_id
            }
            
            # Create master record
            master = Masters.create_master_record(
                master_path=master_path,
                session_data=session_data,
                cal_type=cal_type,
                file_count=len(files)
            )
            
            # Update master file header
            self._update_master_header(master_path, session, files, cal_type)
            
            if progress_callback:
                progress_callback(100, 100, f"Master {cal_type} frame created successfully")
            
            logger.info(f"Created master {cal_type} frame: {master.master_id}")
            return master
            
        except Exception as e:
            logger.error(f"Error creating master {cal_type} frame: {e}")
            return None
    
    def _create_master_with_siril(self, file_paths, output_path, cal_type, progress_callback=None):
        """
        Create a master calibration frame using Siril CLI.
        
        Args:
            file_paths (list): List of file paths to stack
            output_path (str): Output path for master frame
            cal_type (str): Type of calibration
            progress_callback (callable): Progress reporting function
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import subprocess
            import tempfile
            
            # Get Siril CLI path from config
            siril_cli_path = self.config.get('DEFAULT', 'siril_cli_path', fallback='siril-cli')
            
            # Create temporary directory for Siril work
            with tempfile.TemporaryDirectory() as temp_dir:
                script_path = os.path.join(temp_dir, f"stack_{cal_type}.ssf")
                
                # Create Siril script
                script_content = self._generate_siril_script(file_paths, output_path, cal_type)
                
                with open(script_path, 'w') as f:
                    f.write(script_content)
                
                if progress_callback:
                    progress_callback(25, 100, f"Running Siril to create {cal_type} master...")
                
                # Run Siril
                cmd = [siril_cli_path, '-s', script_path]
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_dir)
                
                if result.returncode != 0:
                    logger.error(f"Siril failed: {result.stderr}")
                    return False
                
                if progress_callback:
                    progress_callback(90, 100, f"Master {cal_type} frame processing complete")
                
                return os.path.exists(output_path)
                
        except Exception as e:
            logger.error(f"Error creating master with Siril: {e}")
            return False
    
    def _generate_siril_script(self, file_paths, output_path, cal_type):
        """
        Generate Siril script for stacking calibration frames.
        
        Args:
            file_paths (list): List of input file paths
            output_path (str): Output file path
            cal_type (str): Calibration type
            
        Returns:
            str: Siril script content
        """
        # Convert files to sequence
        file_list = '\n'.join([f'load {path}' for path in file_paths])
        
        if cal_type.lower() == 'bias':
            method = 'stack median'
        elif cal_type.lower() == 'dark':
            method = 'stack median'
        elif cal_type.lower() == 'flat':
            method = 'stack median -norm=mul'
        else:
            method = 'stack median'
        
        script = f"""
# Auto-generated Siril script for {cal_type} master creation
{file_list}
{method}
save {output_path}
"""
        return script
    
    def _update_master_header(self, master_path, session, files, cal_type):
        """
        Update the master frame FITS header with metadata.
        
        Args:
            master_path (str): Path to master file
            session: Session object
            files (list): List of source files
            cal_type (str): Calibration type
        """
        try:
            from astropy.io import fits
            
            with fits.open(master_path, mode='update') as hdul:
                header = hdul[0].header
                
                # Add master frame metadata
                header['IMAGETYP'] = f'{cal_type.upper()}MASTER'
                header['OBJECT'] = f'{cal_type.upper()}MASTER'
                header['TELESCOP'] = session.fitsSessionTelescope or 'Unknown'
                header['INSTRUME'] = session.fitsSessionImager or 'Unknown'
                header['NFILES'] = len(files)
                header['CREATED'] = datetime.datetime.now().isoformat()
                header['SESSION'] = session.fitsSessionId
                
                # Add calibration-specific headers
                if cal_type.lower() == 'dark':
                    header['EXPTIME'] = float(session.fitsSessionExposure or 0)
                elif cal_type.lower() == 'flat':
                    header['FILTER'] = session.fitsSessionFilter or 'Unknown'
                
                # Add equipment settings
                if session.fitsSessionBinningX:
                    header['XBINNING'] = int(session.fitsSessionBinningX)
                if session.fitsSessionBinningY:
                    header['YBINNING'] = int(session.fitsSessionBinningY)
                if session.fitsSessionCCDTemp:
                    header['CCD-TEMP'] = float(session.fitsSessionCCDTemp)
                if session.fitsSessionGain:
                    header['GAIN'] = float(session.fitsSessionGain)
                if session.fitsSessionOffset:
                    header['OFFSET'] = float(session.fitsSessionOffset)
                
                hdul.flush()
                
        except Exception as e:
            logger.error(f"Error updating master header: {e}")
    
    def validate_masters(self, progress_callback=None):
        """
        Validate all master frames in the database.
        
        Args:
            progress_callback (callable): Progress reporting function
            
        Returns:
            dict: Validation results
        """
        results = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'missing': 0,
            'errors': []
        }
        
        try:
            masters = list(Masters.select().where(Masters.soft_delete == False))
            results['total'] = len(masters)
            
            for i, master in enumerate(masters):
                if progress_callback:
                    progress_callback(i, len(masters), f"Validating {master.master_id}...")
                
                try:
                    if not os.path.exists(master.master_path):
                        results['missing'] += 1
                        results['errors'].append(f"Missing file: {master.master_path}")
                        continue
                    
                    if master.validate_file_integrity():
                        results['valid'] += 1
                        # Update validation status
                        master.is_validated = True
                        master.validation_date = datetime.datetime.now()
                        master.save()
                    else:
                        results['invalid'] += 1
                        results['errors'].append(f"Invalid file: {master.master_path}")
                        
                except Exception as e:
                    results['errors'].append(f"Error validating {master.master_id}: {e}")
            
            if progress_callback:
                progress_callback(len(masters), len(masters), "Validation complete")
                
        except Exception as e:
            logger.error(f"Error during master validation: {e}")
            results['errors'].append(f"Validation error: {e}")
        
        return results
    
    def cleanup_masters(self, retention_days=None, progress_callback=None):
        """
        Clean up old or orphaned master frames.
        
        Args:
            retention_days (int): Days to retain masters (None = keep all)
            progress_callback (callable): Progress reporting function
            
        Returns:
            dict: Cleanup results
        """
        results = {
            'total': 0,
            'removed': 0,
            'errors': []
        }
        
        try:
            query = Masters.select().where(Masters.soft_delete == False)
            
            if retention_days:
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
                query = query.where(Masters.creation_date < cutoff_date)
            
            masters = list(query)
            results['total'] = len(masters)
            
            for i, master in enumerate(masters):
                if progress_callback:
                    progress_callback(i, len(masters), f"Processing {master.master_id}...")
                
                try:
                    # Soft delete the master record
                    master.soft_delete = True
                    master.save()
                    
                    # Optionally remove the physical file
                    if os.path.exists(master.master_path):
                        os.remove(master.master_path)
                    
                    results['removed'] += 1
                    
                except Exception as e:
                    results['errors'].append(f"Error removing {master.master_id}: {e}")
            
            if progress_callback:
                progress_callback(len(masters), len(masters), "Cleanup complete")
                
        except Exception as e:
            logger.error(f"Error during master cleanup: {e}")
            results['errors'].append(f"Cleanup error: {e}")
        
        return results
    
    def update_session_with_master(self, session_id, master_id, cal_type):
        """
        Update a session to reference a master calibration frame.
        
        Args:
            session_id (str): Session ID to update
            master_id (str): Master frame ID
            cal_type (str): Calibration type
            
        Returns:
            bool: True if successful
        """
        try:
            session = fitsSession.get_or_none(fitsSession.fitsSessionId == session_id)
            if not session:
                return False
            
            # Update the appropriate session field
            if cal_type.lower() == 'bias':
                session.fitsBiasSession = master_id
            elif cal_type.lower() == 'dark':
                session.fitsDarkSession = master_id
            elif cal_type.lower() == 'flat':
                session.fitsFlatSession = master_id
            
            session.save()
            return True
            
        except Exception as e:
            logger.error(f"Error updating session with master: {e}")
            return False
    
    def get_master_statistics(self):
        """
        Get statistics about master calibration frames.
        
        Returns:
            dict: Statistics summary
        """
        try:
            stats = {
                'total_masters': 0,
                'by_type': {},
                'by_telescope': {},
                'total_size': 0,
                'avg_quality': 0,
                'validation_status': {}
            }
            
            masters = list(Masters.select().where(Masters.soft_delete == False))
            stats['total_masters'] = len(masters)
            
            total_quality = 0
            quality_count = 0
            
            for master in masters:
                # Count by type
                master_type = master.master_type
                stats['by_type'][master_type] = stats['by_type'].get(master_type, 0) + 1
                
                # Count by telescope
                telescope = master.telescope or 'Unknown'
                stats['by_telescope'][telescope] = stats['by_telescope'].get(telescope, 0) + 1
                
                # Sum file sizes
                if master.file_size:
                    stats['total_size'] += master.file_size
                
                # Average quality
                if master.quality_score:
                    total_quality += master.quality_score
                    quality_count += 1
                
                # Validation status
                validated = 'validated' if master.is_validated else 'not_validated'
                stats['validation_status'][validated] = stats['validation_status'].get(validated, 0) + 1
            
            if quality_count > 0:
                stats['avg_quality'] = total_quality / quality_count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting master statistics: {e}")
            return {}


def get_master_manager():
    """Get a singleton instance of the master frame manager."""
    if not hasattr(get_master_manager, '_instance'):
        get_master_manager._instance = MasterFrameManager()
    return get_master_manager._instance