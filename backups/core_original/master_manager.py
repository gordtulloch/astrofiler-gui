"""
Advanced Master Calibration Frame Management Module

This module provides advanced master calibration frame operations including:
- Siril integration for high-quality master frame creation
- Intelligent matching of master frames to sessions
- Validation and quality assessment of master frames
- Cleanup and maintenance operations
- Statistics and analytics for master frame management
"""

import os
import logging
import hashlib
import datetime
import shutil
import configparser
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

from astrofiler_db import Masters, fitsSession, fitsFile, db

logger = logging.getLogger(__name__)


def _get_config():
    """Get configuration from astrofiler.ini file."""
    config = configparser.ConfigParser()
    config.read('astrofiler.ini')
    return config


class MasterFrameManager:
    """Advanced manager class for master calibration frame operations."""
    
    def __init__(self):
        """Initialize the master frame manager."""
        self.config = _get_config()
        self.masters_dir = self._get_master_calibration_path()
    
    def _get_master_calibration_path(self) -> str:
        """
        Get the path to the master calibration frames directory.
        
        Returns:
            str: Path to the Masters directory within the repository folder
        """
        try:
            config = _get_config()
            repo_folder = config.get('DEFAULT', 'repository_folder', fallback='.')
        except Exception as e:
            logger.warning(f"Could not get repository folder from config: {e}")
            repo_folder = os.getcwd()
        
        masters_dir = os.path.join(repo_folder, 'Masters')
        os.makedirs(masters_dir, exist_ok=True)
        
        return masters_dir
    
    def find_matching_master(self, session_data: Dict[str, Any], cal_type: str) -> Optional[Masters]:
        """
        Find a matching master frame for the given session and calibration type.
        
        Args:
            session_data: Session data with equipment and settings
            cal_type: Type of calibration ('bias', 'dark', 'flat')
            
        Returns:
            Matching master frame or None
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
    
    def create_master_from_session(self, session_id: str, cal_type: str, 
                                 min_files: int = 2, 
                                 progress_callback: Optional[Callable] = None) -> Optional[Masters]:
        """
        Create a master calibration frame from a session's files using advanced Siril integration.
        
        Args:
            session_id: Session ID to create master from
            cal_type: Type of calibration ('bias', 'dark', 'flat')
            min_files: Minimum number of files required
            progress_callback: Progress reporting function
            
        Returns:
            Created master frame record or None if creation failed
        """
        try:
            if progress_callback:
                progress_callback(0, 100, f"Starting {cal_type} master creation...")
            
            # Get session and files
            session = fitsSession.get_by_id(session_id)
            files = list(fitsFile.select().where(
                fitsFile.session == session,
                fitsFile.imageType.contains(cal_type.upper())
            ))
            
            if len(files) < min_files:
                logger.warning(f"Not enough files for {cal_type} master: {len(files)} < {min_files}")
                return None
            
            if progress_callback:
                progress_callback(10, 100, f"Found {len(files)} {cal_type} frames...")
            
            # Generate output filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"master_{cal_type}_{session.telescope}_{session.instrument}_{timestamp}.fits"
            output_path = os.path.join(self.masters_dir, output_filename)
            
            # Extract file paths
            file_paths = [f.fitsFileName for f in files]
            
            if progress_callback:
                progress_callback(20, 100, "Creating master frame with Siril...")
            
            # Create master frame using Siril
            success = self._create_master_with_siril(file_paths, output_path, cal_type, progress_callback)
            
            if not success or not os.path.exists(output_path):
                logger.error(f"Failed to create master {cal_type} frame")
                return None
            
            if progress_callback:
                progress_callback(80, 100, "Updating FITS header...")
            
            # Update FITS header with metadata
            self._update_master_header(output_path, session, files, cal_type)
            
            if progress_callback:
                progress_callback(90, 100, "Saving master frame record...")
            
            # Create database record
            file_hash = self._calculate_file_hash(output_path)
            file_size = os.path.getsize(output_path)
            
            master_record = Masters.create(
                telescope=session.telescope,
                instrument=session.instrument,
                master_type=cal_type,
                file_path=output_path,
                file_hash=file_hash,
                file_size=file_size,
                exposure_time=getattr(session, 'exposure', None) if cal_type == 'dark' else None,
                filter_name=getattr(session, 'filter', None) if cal_type == 'flat' else None,
                binning_x=getattr(session, 'binning_x', None),
                binning_y=getattr(session, 'binning_y', None),
                ccd_temp=getattr(session, 'ccd_temp', None),
                gain=getattr(session, 'gain', None),
                offset=getattr(session, 'offset', None),
                frame_count=len(files),
                creation_date=datetime.datetime.now(),
                source_session_id=session_id,
                is_validated=False
            )
            
            if progress_callback:
                progress_callback(100, 100, f"Master {cal_type} frame created successfully")
            
            logger.info(f"Created master {cal_type} frame: {output_filename}")
            return master_record
            
        except Exception as e:
            logger.error(f"Error creating master {cal_type} frame: {e}")
            if progress_callback:
                progress_callback(100, 100, f"Error creating master {cal_type} frame")
            return None
    
    def _create_master_with_siril(self, file_paths: List[str], output_path: str, 
                                cal_type: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        Create master frame using Siril command-line interface.
        
        Args:
            file_paths: List of input FITS file paths
            output_path: Output path for master frame
            cal_type: Type of calibration
            progress_callback: Progress reporting function
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if Siril is available
            siril_cmd = self.config.get('processing', 'siril_command', fallback='siril-cli')
            
            # Create temporary script directory
            temp_dir = os.path.join(os.path.dirname(output_path), 'temp_siril')
            os.makedirs(temp_dir, exist_ok=True)
            
            script_path = os.path.join(temp_dir, f'create_master_{cal_type}.ssf')
            
            # Generate Siril script
            script_content = self._generate_siril_script(file_paths, output_path, cal_type)
            
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            if progress_callback:
                progress_callback(30, 100, "Executing Siril script...")
            
            # Execute Siril script
            result = subprocess.run(
                [siril_cmd, '-s', script_path],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if progress_callback:
                progress_callback(70, 100, "Siril processing completed")
            
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            if result.returncode == 0:
                logger.info(f"Siril master {cal_type} creation successful")
                return True
            else:
                logger.error(f"Siril error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Siril processing timed out for {cal_type} master")
            return False
        except FileNotFoundError:
            logger.warning(f"Siril not found, falling back to simple averaging for {cal_type}")
            return self._create_master_simple_average(file_paths, output_path)
        except Exception as e:
            logger.error(f"Error in Siril master creation: {e}")
            return False
    
    def _generate_siril_script(self, file_paths: List[str], output_path: str, cal_type: str) -> str:
        """
        Generate Siril script for master frame creation.
        
        Args:
            file_paths: List of input FITS files
            output_path: Output path for master frame
            cal_type: Type of calibration
            
        Returns:
            Siril script content
        """
        script_lines = [
            "# Siril script for master frame creation",
            f"# Master {cal_type} creation",
            "",
            "# Set working directory",
            f"cd {os.path.dirname(output_path)}",
            "",
            "# Convert and register files",
            "convert light -out=../converted/",
            "",
            "# Load sequence",
            "load ../converted/light_",
            ""
        ]
        
        if cal_type == 'bias':
            script_lines.extend([
                "# Stack bias frames",
                "stack r_pp_light average -nonorm",
                f"save {os.path.basename(output_path)}"
            ])
        elif cal_type == 'dark':
            script_lines.extend([
                "# Stack dark frames",
                "stack r_pp_light average -nonorm",
                f"save {os.path.basename(output_path)}"
            ])
        elif cal_type == 'flat':
            script_lines.extend([
                "# Stack flat frames with normalization",
                "stack r_pp_light average -norm=mul",
                f"save {os.path.basename(output_path)}"
            ])
        
        return "\n".join(script_lines)
    
    def _create_master_simple_average(self, file_paths: List[str], output_path: str) -> bool:
        """
        Fallback method to create master frame using simple averaging.
        
        Args:
            file_paths: List of input FITS files
            output_path: Output path for master frame
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from astropy.io import fits
            import numpy as np
            
            if not file_paths:
                return False
            
            # Read first file to get dimensions and header
            with fits.open(file_paths[0]) as hdul:
                header = hdul[0].header.copy()
                data_shape = hdul[0].data.shape
                data_stack = np.zeros((len(file_paths), *data_shape), dtype=np.float32)
                data_stack[0] = hdul[0].data.astype(np.float32)
            
            # Read remaining files
            for i, file_path in enumerate(file_paths[1:], 1):
                try:
                    with fits.open(file_path) as hdul:
                        data_stack[i] = hdul[0].data.astype(np.float32)
                except Exception as e:
                    logger.warning(f"Skipping corrupted file {file_path}: {e}")
                    continue
            
            # Calculate average
            master_data = np.mean(data_stack, axis=0)
            
            # Update header
            header['HISTORY'] = f'Created master frame from {len(file_paths)} files'
            header['NFILES'] = len(file_paths)
            header['CREATOR'] = 'AstroFiler Master Frame Manager'
            header['DATE'] = datetime.datetime.now().isoformat()
            
            # Save master frame
            hdu = fits.PrimaryHDU(data=master_data.astype(np.uint16), header=header)
            hdu.writeto(output_path, overwrite=True)
            
            logger.info(f"Created simple average master frame: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error in simple average master creation: {e}")
            return False
    
    def _update_master_header(self, master_path: str, session: fitsSession, 
                            files: List[fitsFile], cal_type: str):
        """
        Update master frame FITS header with comprehensive metadata.
        
        Args:
            master_path: Path to master frame file
            session: Source session
            files: List of input files
            cal_type: Type of calibration
        """
        try:
            from astropy.io import fits
            
            with fits.open(master_path, mode='update') as hdul:
                header = hdul[0].header
                
                # Basic master frame info
                header['IMAGETYP'] = f'Master {cal_type.title()}'
                header['MSTTYPE'] = cal_type.upper()
                header['NFILES'] = len(files)
                header['CREATOR'] = 'AstroFiler Advanced Master Manager'
                header['VERSION'] = '2.0.0'
                header['DATE'] = datetime.datetime.now().isoformat()
                
                # Session information
                header['TELESCOP'] = session.telescope
                header['INSTRUME'] = session.instrument
                header['SESSID'] = str(session.id)
                
                # Equipment settings
                if hasattr(session, 'exposure') and session.exposure:
                    header['EXPTIME'] = session.exposure
                if hasattr(session, 'filter') and session.filter:
                    header['FILTER'] = session.filter
                if hasattr(session, 'binning_x') and session.binning_x:
                    header['XBINNING'] = session.binning_x
                if hasattr(session, 'binning_y') and session.binning_y:
                    header['YBINNING'] = session.binning_y
                if hasattr(session, 'ccd_temp') and session.ccd_temp:
                    header['CCD-TEMP'] = session.ccd_temp
                if hasattr(session, 'gain') and session.gain:
                    header['GAIN'] = session.gain
                if hasattr(session, 'offset') and session.offset:
                    header['OFFSET'] = session.offset
                
                # File statistics
                total_size = sum(os.path.getsize(f.fitsFileName) for f in files if os.path.exists(f.fitsFileName))
                header['TOTSIZE'] = total_size
                
                # Add history
                header['HISTORY'] = f'Master {cal_type} created from {len(files)} frames'
                header['HISTORY'] = f'Source session: {session.id}'
                header['HISTORY'] = f'Processing date: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                
                # Add comment
                header['COMMENT'] = f'Created by AstroFiler Master Frame Manager v2.0'
                
        except Exception as e:
            logger.error(f"Error updating master frame header: {e}")
    
    def validate_masters(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Validate all master frames in the database and filesystem.
        
        Args:
            progress_callback: Progress reporting function
            
        Returns:
            Dictionary with validation results
        """
        try:
            results = {
                'total_masters': 0,
                'valid_masters': 0,
                'invalid_masters': 0,
                'missing_files': 0,
                'corrupted_files': 0,
                'validated_masters': []
            }
            
            masters = list(Masters.select())
            results['total_masters'] = len(masters)
            
            if progress_callback:
                progress_callback(0, len(masters), "Starting master validation...")
            
            for i, master in enumerate(masters):
                try:
                    # Check file existence
                    if not os.path.exists(master.file_path):
                        results['missing_files'] += 1
                        results['invalid_masters'] += 1
                        logger.warning(f"Master file not found: {master.file_path}")
                        continue
                    
                    # Verify file hash
                    current_hash = self._calculate_file_hash(master.file_path)
                    if master.file_hash and current_hash != master.file_hash:
                        results['corrupted_files'] += 1
                        results['invalid_masters'] += 1
                        logger.warning(f"Master file hash mismatch: {master.file_path}")
                        continue
                    
                    # Try to open FITS file
                    try:
                        from astropy.io import fits
                        with fits.open(master.file_path) as hdul:
                            # Basic validation - check if we can read the data
                            _ = hdul[0].data.shape
                    except Exception as e:
                        results['corrupted_files'] += 1
                        results['invalid_masters'] += 1
                        logger.warning(f"Cannot read master FITS file {master.file_path}: {e}")
                        continue
                    
                    # Mark as validated
                    master.is_validated = True
                    master.validation_date = datetime.datetime.now()
                    master.save()
                    
                    results['valid_masters'] += 1
                    results['validated_masters'].append(master.id)
                    
                    if progress_callback:
                        progress_callback(i + 1, len(masters), f"Validated: {os.path.basename(master.file_path)}")
                    
                except Exception as e:
                    logger.error(f"Error validating master {master.id}: {e}")
                    results['invalid_masters'] += 1
            
            if progress_callback:
                progress_callback(len(masters), len(masters), "Validation completed")
            
            logger.info(f"Master validation completed: {results['valid_masters']}/{results['total_masters']} valid")
            return results
            
        except Exception as e:
            logger.error(f"Error during master validation: {e}")
            return {'error': str(e)}
    
    def cleanup_masters(self, retention_days: Optional[int] = None, 
                       progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Clean up old and unused master frames.
        
        Args:
            retention_days: Number of days to retain masters (None = keep all)
            progress_callback: Progress reporting function
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            results = {
                'total_masters': 0,
                'deleted_masters': 0,
                'space_freed': 0,
                'errors': []
            }
            
            # Get retention period from config if not specified
            if retention_days is None:
                retention_days = self.config.getint('maintenance', 'master_retention_days', fallback=365)
            
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
            
            # Find masters older than retention period
            old_masters = list(Masters.select().where(
                Masters.creation_date < cutoff_date,
                Masters.is_validated == True  # Only delete validated masters
            ))
            
            results['total_masters'] = len(old_masters)
            
            if progress_callback:
                progress_callback(0, len(old_masters), f"Starting cleanup of {len(old_masters)} old masters...")
            
            for i, master in enumerate(old_masters):
                try:
                    # Check if master is still in use by any sessions
                    sessions_using = fitsSession.select().where(
                        (fitsSession.master_bias == master.id) |
                        (fitsSession.master_dark == master.id) |
                        (fitsSession.master_flat == master.id)
                    ).count()
                    
                    if sessions_using > 0:
                        logger.info(f"Keeping master {master.id} - still in use by {sessions_using} sessions")
                        continue
                    
                    # Get file size before deletion
                    file_size = 0
                    if os.path.exists(master.file_path):
                        file_size = os.path.getsize(master.file_path)
                        os.remove(master.file_path)
                        results['space_freed'] += file_size
                    
                    # Delete database record
                    master.delete_instance()
                    results['deleted_masters'] += 1
                    
                    if progress_callback:
                        progress_callback(i + 1, len(old_masters), 
                                        f"Deleted: {os.path.basename(master.file_path)}")
                    
                except Exception as e:
                    error_msg = f"Error deleting master {master.id}: {e}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            if progress_callback:
                progress_callback(len(old_masters), len(old_masters), "Cleanup completed")
            
            logger.info(f"Master cleanup completed: {results['deleted_masters']} deleted, "
                       f"{results['space_freed'] / (1024*1024):.2f} MB freed")
            return results
            
        except Exception as e:
            logger.error(f"Error during master cleanup: {e}")
            return {'error': str(e)}
    
    def update_session_with_master(self, session_id: str, master_id: int, cal_type: str) -> bool:
        """
        Update a session to use a specific master frame.
        
        Args:
            session_id: Session ID to update
            master_id: Master frame ID
            cal_type: Type of calibration ('bias', 'dark', 'flat')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session = fitsSession.get_by_id(session_id)
            master = Masters.get_by_id(master_id)
            
            # Update appropriate field based on calibration type
            if cal_type == 'bias':
                session.master_bias = master.id
            elif cal_type == 'dark':
                session.master_dark = master.id
            elif cal_type == 'flat':
                session.master_flat = master.id
            else:
                logger.error(f"Invalid calibration type: {cal_type}")
                return False
            
            session.save()
            logger.info(f"Updated session {session_id} with master {cal_type} {master_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating session with master: {e}")
            return False
    
    def get_master_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about master frames.
        
        Returns:
            Dictionary with master frame statistics
        """
        try:
            stats = {
                'total_masters': 0,
                'by_type': {},
                'by_telescope': {},
                'by_instrument': {},
                'total_size': 0,
                'avg_file_size': 0,
                'avg_frame_count': 0,
                'validation_status': {},
                'creation_dates': [],
                'avg_quality': 0
            }
            
            masters = list(Masters.select())
            stats['total_masters'] = len(masters)
            
            if len(masters) == 0:
                return stats
            
            total_size = 0
            total_frame_count = 0
            total_quality = 0
            quality_count = 0
            
            for master in masters:
                # By type
                master_type = master.master_type or 'unknown'
                stats['by_type'][master_type] = stats['by_type'].get(master_type, 0) + 1
                
                # By telescope
                telescope = master.telescope or 'unknown'
                stats['by_telescope'][telescope] = stats['by_telescope'].get(telescope, 0) + 1
                
                # By instrument
                instrument = master.instrument or 'unknown'
                stats['by_instrument'][instrument] = stats['by_instrument'].get(instrument, 0) + 1
                
                # File size
                if master.file_size:
                    total_size += master.file_size
                
                # Frame count
                if master.frame_count:
                    total_frame_count += master.frame_count
                
                # Creation dates
                if master.creation_date:
                    stats['creation_dates'].append(master.creation_date.isoformat())
                
                # Quality scores
                if hasattr(master, 'quality_score') and master.quality_score:
                    total_quality += master.quality_score
                    quality_count += 1
                
                # Validation status
                validated = 'validated' if master.is_validated else 'not_validated'
                stats['validation_status'][validated] = stats['validation_status'].get(validated, 0) + 1
            
            # Calculate averages
            stats['total_size'] = total_size
            if len(masters) > 0:
                stats['avg_file_size'] = total_size / len(masters)
                stats['avg_frame_count'] = total_frame_count / len(masters)
            
            if quality_count > 0:
                stats['avg_quality'] = total_quality / quality_count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting master statistics: {e}")
            return {}
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of a file."""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""


# Singleton instance
_master_manager_instance = None

def get_master_manager() -> MasterFrameManager:
    """Get a singleton instance of the master frame manager."""
    global _master_manager_instance
    if _master_manager_instance is None:
        _master_manager_instance = MasterFrameManager()
    return _master_manager_instance