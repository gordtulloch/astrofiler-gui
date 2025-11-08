"""
Advanced Master Calibration Frame Management Module

This module provides advanced master calibration frame operations including:
- PySiril integration for high-quality master frame creation
- Intelligent matching of master frames to sessions
- Validation and quality assessment of master frames
- Cleanup and maintenance operations
- Statistics and analytics for master frame management

Note: PySiril requires manual installation from https://gitlab.com/free-astro/pysiril/-/releases
If PySiril is not available, falls back to astropy-based simple averaging.
"""

import os
import logging
import hashlib
import datetime
import shutil
import configparser
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

from ..models import Masters, fitsSession, fitsFile, db

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
            repo_folder = config.get('DEFAULT', 'repo', fallback='.')
        except Exception as e:
            logger.warning(f"Could not get repository folder from config: {e}")
            repo_folder = os.getcwd()
        
        masters_dir = os.path.join(repo_folder, 'Masters')
        # Don't create the directory here - let it be created when actually needed
        return masters_dir
    
    def _ensure_masters_directory_exists(self) -> str:
        """
        Ensure the Masters directory exists and return its path.
        
        Returns:
            str: Path to the Masters directory
        """
        masters_dir = self.masters_dir
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
                fitsFile.fitsFileSession == session.fitsSessionId,
                fitsFile.fitsFileObject.contains(cal_type.upper())
            ))
            
            if len(files) < min_files:
                logger.warning(f"Not enough files for {cal_type} master: {len(files)} < {min_files}")
                return None
            
            if progress_callback:
                progress_callback(10, 100, f"Found {len(files)} {cal_type} frames...")
            
            # Generate output filename with Master prefix following fitsFile naming convention
            timestamp = datetime.datetime.now().strftime("%Y%m%d")
            
            # Clean telescope and imager names for filename compatibility  
            telescope_clean = session.fitsSessionTelescope.replace(" ", "_").replace("\\", "_").replace("@", "_").replace("/", "_")
            imager_clean = session.fitsSessionImager.replace(" ", "_").replace("\\", "_").replace("@", "_").replace("/", "_")
            
            # Build filename following the same pattern as calibration frames in fitsFile registration
            if cal_type.lower() == 'flat':
                # For flats: Master-Flat-[Telescope]-[Instrument]-[Filter]-[Date]-[Exposure]s-[XBinning]x[YBinning]-t[CCDTemp].fits
                filter_name = session.fitsSessionFilter or "OSC"
                output_filename = f"Master-Flat-{telescope_clean}-{imager_clean}-{filter_name}-{timestamp}-{session.fitsSessionExposure}s-{session.fitsSessionBinningX}x{session.fitsSessionBinningY}-t{session.fitsSessionCCDTemp}.fits"
            else:
                # For bias/dark: Master-[Type]-[Telescope]-[Instrument]-[Date]-[Exposure]s-[XBinning]x[YBinning]-t[CCDTemp].fits
                output_filename = f"Master-{cal_type.title()}-{telescope_clean}-{imager_clean}-{timestamp}-{session.fitsSessionExposure}s-{session.fitsSessionBinningX}x{session.fitsSessionBinningY}-t{session.fitsSessionCCDTemp}.fits"
            
            # Ensure Masters directory exists before creating the file
            masters_dir = self._ensure_masters_directory_exists()
            output_path = os.path.join(masters_dir, output_filename)
            
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
            session_data = {
                'session_id': str(session.fitsSessionId),
                'telescope': session.fitsSessionTelescope,
                'instrument': session.fitsSessionImager,
                'exposure_time': session.fitsSessionExposure,
                'filter_name': session.fitsSessionFilter,
                'binning_x': session.fitsSessionBinningX,
                'binning_y': session.fitsSessionBinningY,
                'ccd_temp': session.fitsSessionCCDTemp,
                'gain': session.fitsSessionGain,
                'offset': session.fitsSessionOffset
            }
            
            master_record = Masters.create_master_record(
                master_path=output_path,
                session_data=session_data,
                cal_type=cal_type,
                file_count=len(files)
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
        Create master frame using PySiril Python interface.
        
        Args:
            file_paths: List of input FITS file paths
            output_path: Output path for master frame
            cal_type: Type of calibration
            progress_callback: Progress reporting function
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to import PySiril
            try:
                from pysiril.siril import Siril
                from pysiril.wrapper import Wrapper
            except ImportError:
                logger.warning("PySiril not available, falling back to simple averaging")
                return self._create_master_simple_average(file_paths, output_path)
            
            if progress_callback:
                progress_callback(20, 100, "Initializing PySiril...")
            
            # Get Siril CLI path from config
            siril_path = self.config.get('DEFAULT', 'siril_cli_path', fallback='siril-cli')
            
            # Initialize PySiril with custom Siril path
            app = Siril(siril_path)
            
            if progress_callback:
                progress_callback(30, 100, "Starting Siril...")
            
            app.Open()
            cmd = Wrapper(app)
            
            if progress_callback:
                progress_callback(40, 100, "Setting up working directory...")
            
            # Create working directory
            working_dir = os.path.dirname(output_path)
            temp_dir = os.path.join(working_dir, 'temp_pysiril')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Set working directory in Siril
            cmd.cd(temp_dir)
            cmd.setext('fits')
            
            if progress_callback:
                progress_callback(50, 100, f"Processing {len(file_paths)} {cal_type} frames...")
            
            # Copy files to working directory with sequential naming
            for i, file_path in enumerate(file_paths):
                dest_file = os.path.join(temp_dir, f"{cal_type}_{i+1:05d}.fits")
                shutil.copy2(file_path, dest_file)
            
            # Convert to sequence
            sequence_name = f"{cal_type}_seq"
            cmd.convert(cal_type, out=".", fitseq=True)
            
            if progress_callback:
                progress_callback(70, 100, f"Stacking {cal_type} frames...")
            
            # Stack based on calibration type  
            output_name = os.path.splitext(os.path.basename(output_path))[0]
            
            if cal_type == 'bias':
                # Stack bias frames without normalization using rejection
                cmd.stack(f"{cal_type}", type="rej", sigma_low=3, sigma_high=3, norm="no")
            elif cal_type == 'dark':
                # Stack dark frames without normalization using rejection  
                cmd.stack(f"{cal_type}", type="rej", sigma_low=3, sigma_high=3, norm="no")
            elif cal_type == 'flat':
                # Stack flat frames with multiplicative normalization using rejection
                cmd.stack(f"{cal_type}", type="rej", sigma_low=3, sigma_high=3, norm="mul")
            
            if progress_callback:
                progress_callback(80, 100, "Saving master frame...")
            
            # Check if output file was created (Siril creates files with _stacked suffix)
            stacked_file = os.path.join(temp_dir, f"{cal_type}_stacked.fits")
            if os.path.exists(stacked_file):
                shutil.move(stacked_file, output_path)
                success = True
                logger.info(f"PySiril master {cal_type} creation successful")
            else:
                # Try alternative naming patterns
                alt_files = [
                    os.path.join(temp_dir, f"{cal_type}.fits"),
                    os.path.join(temp_dir, f"{cal_type}_seq_stacked.fits"),
                    os.path.join(temp_dir, f"stacked.fits")
                ]
                success = False
                for alt_file in alt_files:
                    if os.path.exists(alt_file):
                        shutil.move(alt_file, output_path)
                        success = True
                        logger.info(f"PySiril master {cal_type} creation successful (found: {os.path.basename(alt_file)})")
                        break
                
                if not success:
                    logger.warning(f"PySiril stacking completed but output file not found. Expected: {stacked_file}")
                    # List files in temp dir for debugging
                    try:
                        temp_files = os.listdir(temp_dir)
                        logger.info(f"Files in temp dir: {temp_files}")
                    except:
                        pass
            
            # Close PySiril
            app.Close()
            del app
            
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            if progress_callback:
                progress_callback(90, 100, "PySiril processing completed")
            
            if success:
                return True
            else:
                logger.info(f"Falling back to simple averaging for {cal_type} master")
                return self._create_master_simple_average(file_paths, output_path)
                
        except Exception as e:
            logger.warning(f"Error in PySiril master creation, falling back to simple averaging: {e}")
            return self._create_master_simple_average(file_paths, output_path)
    
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
                header['TELESCOP'] = session.fitsSessionTelescope
                header['INSTRUME'] = session.fitsSessionImager
                header['SESSID'] = str(session.fitsSessionId)
                
                # Equipment settings
                if session.fitsSessionExposure:
                    header['EXPTIME'] = session.fitsSessionExposure
                if session.fitsSessionFilter:
                    header['FILTER'] = session.fitsSessionFilter
                if session.fitsSessionBinningX:
                    header['XBINNING'] = session.fitsSessionBinningX
                if session.fitsSessionBinningY:
                    header['YBINNING'] = session.fitsSessionBinningY
                if session.fitsSessionCCDTemp:
                    header['CCD-TEMP'] = session.fitsSessionCCDTemp
                if session.fitsSessionGain:
                    header['GAIN'] = session.fitsSessionGain
                if session.fitsSessionOffset:
                    header['OFFSET'] = session.fitsSessionOffset
                
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
                if master.file_count:
                    total_frame_count += master.file_count
                
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