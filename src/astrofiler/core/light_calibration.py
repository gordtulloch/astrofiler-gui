#!/usr/bin/env python3
"""
Light Frame Calibration Module for AstroFiler

This module handles the calibration of light frames using master calibration frames.
It applies bias, dark, and flat corrections to produce calibrated light frames
suitable for stacking and further processing.

Key Features:
- Comprehensive calibration pipeline (bias, dark, flat)
- Robust error handling and validation
- Detailed FITS header metadata
- Progress callbacks for GUI integration
- Professional astronomy-standard processing
"""

import os
import logging
import hashlib
import numpy as np
from datetime import datetime
from typing import Optional, Callable, Dict, List
from astropy.io import fits
from ..models import fitsFile as FitsFileModel, fitsSession as FitsSessionModel
from ..models.masters import Masters
from .utils import normalize_file_path

logger = logging.getLogger(__name__)

def calibrate_light_frame(light_path: str, dark_master: Optional[str] = None, 
                         flat_master: Optional[str] = None, bias_master: Optional[str] = None, 
                         output_path: Optional[str] = None, progress_callback: Optional[Callable] = None) -> Dict:
    """
    Calibrate a single light frame using master calibration frames.
    
    This function applies the standard astronomical calibration pipeline:
    1. Bias subtraction (if bias master available)
    2. Dark subtraction (if dark master available)
    3. Flat field correction with normalization (if flat master available)
    
    Args:
        light_path (str): Path to the light frame FITS file
        dark_master (str, optional): Path to master dark frame
        flat_master (str, optional): Path to master flat frame  
        bias_master (str, optional): Path to master bias frame
        output_path (str, optional): Path for calibrated output file (auto-generated if not provided)
        progress_callback (callable, optional): Callback for progress updates
        
    Returns:
        dict: Calibration result with success status, output path, and metadata
        
    Example:
        >>> result = calibrate_light_frame(
        ...     light_path='light_001.fits',
        ...     bias_master='master_bias.fits',
        ...     dark_master='master_dark_300s.fits',
        ...     flat_master='master_flat_V.fits'
        ... )
        >>> if result.get('success'):
        ...     print(f"Calibrated frame saved: {result['output_path']}")
    """
    try:
        if progress_callback:
            progress_callback(f"Starting calibration of {os.path.basename(light_path)}")
            
        # Validate input file
        if not os.path.exists(light_path):
            return {"error": f"Light frame file not found: {light_path}"}
            
        # Load light frame
        with fits.open(light_path) as hdul:
            light_data = hdul[0].data.astype(np.float32)
            light_header = hdul[0].header.copy()
        
        if light_data is None or light_data.size == 0:
            return {"error": "No image data found in light frame"}
            
        calibrated_data = light_data.copy()
        calibration_steps = []
        
        # Apply bias correction first
        if bias_master and os.path.exists(bias_master):
            if progress_callback:
                progress_callback("Applying bias correction...")
            try:
                with fits.open(bias_master) as hdul:
                    bias_data = hdul[0].data.astype(np.float32)
                calibrated_data -= bias_data
                calibration_steps.append(f"BIAS: {os.path.basename(bias_master)}")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Warning: Failed to apply bias correction: {e}")
        
        # Apply dark correction
        if dark_master and os.path.exists(dark_master):
            if progress_callback:
                progress_callback("Applying dark correction...")
            try:
                with fits.open(dark_master) as hdul:
                    dark_data = hdul[0].data.astype(np.float32)
                    
                calibration_steps.append(f"DARK: {os.path.basename(dark_master)}")
                calibrated_data -= dark_data
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Warning: Failed to apply dark correction: {e}")
        
        # Apply flat correction
        if flat_master and os.path.exists(flat_master):
            if progress_callback:
                progress_callback("Applying flat correction...")
            try:
                with fits.open(flat_master) as hdul:
                    flat_data = hdul[0].data.astype(np.float32)
                    
                # Normalize flat field (avoid division by zero)
                flat_mean = np.mean(flat_data[flat_data > 0])
                flat_normalized = flat_data / flat_mean
                flat_normalized[flat_normalized <= 0] = 1.0  # Avoid division by zero
                
                calibrated_data /= flat_normalized
                calibration_steps.append(f"FLAT: {os.path.basename(flat_master)}")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Warning: Failed to apply flat correction: {e}")
        
        # Generate output path if not provided
        if not output_path:
            base_dir = os.path.dirname(light_path)
            base_name = os.path.splitext(os.path.basename(light_path))[0]
            output_path = os.path.join(base_dir, f"{base_name}_calibrated.fits")
            
        # Update FITS header with comprehensive calibration information
        _update_calibrated_frame_header(light_header, calibration_steps, 
                                      bias_master, dark_master, flat_master, 
                                      calibrated_data, light_path)
        
        if progress_callback:
            progress_callback("Saving calibrated frame...")
            
        # Save calibrated frame
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Ensure data is in appropriate range and type
        calibrated_data = np.clip(calibrated_data, 0, None)  # Remove negative values
        
        hdu = fits.PrimaryHDU(data=calibrated_data.astype(np.float32), header=light_header)
        hdu.writeto(output_path, overwrite=True)
        
        if progress_callback:
            progress_callback(f"Calibration complete: {os.path.basename(output_path)}")
            
        return {
            "success": True,
            "output_path": output_path,
            "input_path": light_path,
            "calibration_steps": calibration_steps,
            "noise_level": float(np.std(calibrated_data)),
            "mean_level": float(np.mean(calibrated_data)),
            "dynamic_range": float(np.max(calibrated_data) - np.min(calibrated_data))
        }
        
    except Exception as e:
        return {"error": f"Failed to calibrate light frame: {str(e)}"}


def calibrate_session_lights(session_id: str, progress_callback: Optional[Callable] = None, 
                            force_recalibrate: bool = False) -> Dict:
    """
    Calibrate all light frames in a session using available master frames.
    
    Args:
        session_id (str): Database ID of the session to calibrate
        progress_callback (callable, optional): Callback for progress updates
        force_recalibrate (bool): If True, recalibrate even if already calibrated
        
    Returns:
        dict: Calibration results with statistics
    """
    try:
        if progress_callback:
            progress_callback(f"Starting calibration for session {session_id}")
            
        # Get session and check if it exists
        try:
            session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session_id)
        except FitsSessionModel.DoesNotExist:
            return {"error": f"Session {session_id} not found"}
            
        # Check for master frames
        master_frames = get_session_master_frames(session_id)
        if not any(master_frames.values()):
            return {"error": "No master calibration frames available for this session"}
            
        # Get light frames from session
        light_files = FitsFileModel.select().where(
            (FitsFileModel.fitsFileSession == session_id) & 
            (~FitsFileModel.fitsFileType.contains('BIAS')) &
            (~FitsFileModel.fitsFileType.contains('DARK')) &
            (~FitsFileModel.fitsFileType.contains('FLAT'))
        )
        
        if not light_files.exists():
            return {"error": "No light frames found in session"}
            
        total_lights = light_files.count()
        calibrated_count = 0
        skipped_count = 0
        error_count = 0
        results = []
        
        for i, light_file in enumerate(light_files, 1):
            if progress_callback:
                progress_callback(f"Processing light frame {i}/{total_lights}: {os.path.basename(light_file.fitsFileName or '')}")
                
            # Check if already calibrated (unless forcing recalibration)
            if not force_recalibrate and light_file.fitsFileCalibrated == 1:
                if progress_callback:
                    progress_callback(f"Skipping already calibrated: {os.path.basename(light_file.fitsFileName or '')}")
                skipped_count += 1
                continue
                    
            # Calibrate the light frame
            result = calibrate_light_frame(
                light_path=light_file.fitsFileName,
                dark_master=master_frames['dark'],
                flat_master=master_frames['flat'],
                bias_master=master_frames['bias'],
                progress_callback=progress_callback
            )
            
            if result.get('success'):
                calibrated_count += 1
                
                # Update database record
                try:
                    light_file.fitsFileCalibrated = 1
                    light_file.fitsFileCalibrationDate = datetime.now()
                    light_file.save()
                except Exception as e:
                    logger.warning(f"Failed to update database for calibrated file {light_file.fitsFileName}: {e}")
                
                results.append({
                    "light_file": os.path.basename(light_file.fitsFileName or ''),
                    "output_file": os.path.basename(result['output_path']),
                    "calibration_steps": result['calibration_steps'],
                    "noise_level": result['noise_level']
                })
            else:
                error_count += 1
                if progress_callback:
                    progress_callback(f"Error calibrating {os.path.basename(light_file.fitsFileName or '')}: {result.get('error', 'Unknown error')}")
                    
        if progress_callback:
            progress_callback(f"Calibration complete: {calibrated_count} processed, {skipped_count} skipped, {error_count} errors")
            
        return {
            "success": True,
            "session_id": session_id,
            "total_lights": total_lights,
            "calibrated_count": calibrated_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "results": results,
            "master_frames_used": {k: os.path.basename(v) if v else None for k, v in master_frames.items()}
        }
        
    except Exception as e:
        return {"error": f"Failed to calibrate session lights: {str(e)}"}


def get_session_master_frames(session_id: str) -> Dict[str, Optional[str]]:
    """
    Get the paths to master calibration frames for a session.
    
    This function looks for master frames that match the session's characteristics
    (telescope, instrument, binning, etc.) and returns their file paths.
    
    Args:
        session_id (str): Database ID of the session
        
    Returns:
        dict: Paths to master frames (dark, flat, bias) or None if not available
    """
    try:
        session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session_id)
        
        masters = {"dark": None, "flat": None, "bias": None}
        
        # Get session characteristics for matching
        criteria = session.get_calibration_criteria()
        
        # Look for matching master frames based on session characteristics
        for master_type in ['dark', 'flat', 'bias']:
            master_query = Masters.select().where(
                (Masters.master_type == master_type) &
                (Masters.telescope == criteria.get('telescope')) &
                (Masters.instrument == criteria.get('instrument')) &
                (Masters.binning_x == criteria.get('binning_x')) &
                (Masters.binning_y == criteria.get('binning_y'))
            )
            
            # Additional criteria for specific master types
            if master_type == 'dark':
                master_query = master_query.where(Masters.exposure_time == criteria.get('exposure_time'))
            elif master_type == 'flat':
                master_query = master_query.where(Masters.filter_name == criteria.get('filter_name'))
            
            # Get the most recent master
            master_query = master_query.order_by(Masters.creation_date.desc())
            
            if master_query.exists():
                master = master_query.first()
                if master.master_path and os.path.exists(master.master_path):
                    masters[master_type] = master.master_path
                    
    except Exception as e:
        logger.error(f"Error getting session master frames: {e}")
        
    return masters


def _update_calibrated_frame_header(header, calibration_steps: List[str], bias_master: Optional[str], 
                                   dark_master: Optional[str], flat_master: Optional[str], 
                                   calibrated_data: np.ndarray, light_path: str) -> None:
    """
    Update FITS header of calibrated light frame with comprehensive metadata.
    
    Adds astronomy-standard headers for calibrated light frames including:
    - Calibration identification and status
    - Master frame references with full paths and checksums
    - Processing history and timestamps
    - Quality metrics and statistics
    - Software version and processing parameters
    
    Args:
        header: FITS header object to update
        calibration_steps: List of calibration steps applied
        bias_master: Path to bias master (or None)
        dark_master: Path to dark master (or None)
        flat_master: Path to flat master (or None)
        calibrated_data: Calibrated image data array
        light_path: Original light frame path
    """
    
    # =================================================================
    # PRIMARY CALIBRATION IDENTIFICATION
    # =================================================================
    
    header['CALIBRAT'] = (True, 'Frame has been calibrated')
    header['CALDATE'] = (datetime.now().isoformat(), 'Calibration processing date/time')
    header['CALSOFTW'] = ('AstroFiler', 'Calibration software name')
    header['CALVER'] = ('1.2.0', 'Calibration software version')
    
    # Processing history
    header['HISTORY'] = f'Calibrated by AstroFiler on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    header['HISTORY'] = f'Original file: {os.path.basename(light_path)}'
    
    # =================================================================
    # CALIBRATION STEPS AND MASTER FRAME REFERENCES
    # =================================================================
    
    # Count masters used and create summary
    master_count = 0
    masters_used = []
    
    if bias_master and os.path.exists(bias_master):
        master_count += 1
        masters_used.append("BIAS")
        header['BIASMAST'] = (os.path.basename(bias_master), 'Master bias frame filename')
        header['BIASREF'] = (bias_master, 'Full path to master bias frame')
        
        # Add bias master hash for verification
        try:
            with open(bias_master, 'rb') as f:
                bias_hash = hashlib.md5(f.read()).hexdigest()[:16]  # Truncate for FITS
            header['BIASMD5'] = (bias_hash, 'MD5 checksum of bias master (truncated)')
        except:
            pass
    
    if dark_master and os.path.exists(dark_master):
        master_count += 1
        masters_used.append("DARK")
        header['DARKMAST'] = (os.path.basename(dark_master), 'Master dark frame filename')
        header['DARKREF'] = (dark_master, 'Full path to master dark frame')
        
        try:
            with open(dark_master, 'rb') as f:
                dark_hash = hashlib.md5(f.read()).hexdigest()[:16]
            header['DARKMD5'] = (dark_hash, 'MD5 checksum of dark master (truncated)')
        except:
            pass
    
    if flat_master and os.path.exists(flat_master):
        master_count += 1
        masters_used.append("FLAT")
        header['FLATMAST'] = (os.path.basename(flat_master), 'Master flat frame filename')
        header['FLATREF'] = (flat_master, 'Full path to master flat frame')
        
        try:
            with open(flat_master, 'rb') as f:
                flat_hash = hashlib.md5(f.read()).hexdigest()[:16]
            header['FLATMD5'] = (flat_hash, 'MD5 checksum of flat master (truncated)')
        except:
            pass
    
    # Summary information
    header['CALMAST'] = (master_count, 'Number of master frames used')
    header['CALSTEPS'] = (' + '.join(masters_used), 'Calibration steps applied')
    
    # =================================================================
    # IMAGE STATISTICS AND QUALITY METRICS
    # =================================================================
    
    # Calculate comprehensive statistics
    header['DATAMIN'] = (float(np.min(calibrated_data)), 'Minimum pixel value after calibration')
    header['DATAMAX'] = (float(np.max(calibrated_data)), 'Maximum pixel value after calibration')
    header['DATAMEAN'] = (float(np.mean(calibrated_data)), 'Mean pixel value after calibration')
    header['DATASTD'] = (float(np.std(calibrated_data)), 'Standard deviation after calibration')
    header['DATAMEDIAN'] = (float(np.median(calibrated_data)), 'Median pixel value after calibration')
    
    # Calculate percentiles for dynamic range assessment
    try:
        p1, p99 = np.percentile(calibrated_data, [1, 99])
        header['DATARANG'] = (float(p99 - p1), 'Dynamic range (99th - 1st percentile)')
        header['DATAP01'] = (float(p1), '1st percentile pixel value')
        header['DATAP99'] = (float(p99), '99th percentile pixel value')
    except:
        pass
    
    # =================================================================
    # PROCESSING METADATA
    # =================================================================
    
    # Add calibration step details to history
    for step in calibration_steps:
        header['HISTORY'] = f'Applied {step}'
    
    # Processing environment info
    header['PROCENV'] = ('Python/AstroFiler', 'Processing environment')
    
    # Mark as processed
    header['PROCTYPE'] = ('CALIBRATED', 'Type of processing applied')
    header['PROCSTAT'] = ('COMPLETE', 'Processing status')


def find_light_sessions_for_calibration() -> List[str]:
    """
    Find all light frame sessions that could benefit from calibration.
    
    Returns:
        list: List of session IDs for light frame sessions
    """
    try:
        # Light sessions are those that don't have calibration object names
        calibration_types = ['bias', 'Bias', 'BIAS', 'dark', 'Dark', 'DARK', 'flat', 'Flat', 'FLAT']
        light_sessions = FitsSessionModel.select().where(
            ~FitsSessionModel.fitsSessionObjectName.in_(calibration_types)
        )
        
        return [session.fitsSessionId for session in light_sessions]
        
    except Exception as e:
        logger.error(f"Error finding light sessions: {e}")
        return []


def get_calibration_statistics() -> Dict:
    """
    Get statistics about light frame calibration status.
    
    Returns:
        dict: Statistics about calibrated vs uncalibrated light frames
    """
    try:
        # Get all light frames (non-calibration frames)
        calibration_types = ['BIAS', 'DARK', 'FLAT']
        all_lights = FitsFileModel.select().where(
            ~FitsFileModel.fitsFileType.in_(calibration_types)
        )
        
        total_lights = all_lights.count()
        
        # Count calibrated frames
        calibrated_lights = FitsFileModel.select().where(
            (~FitsFileModel.fitsFileType.in_(calibration_types)) &
            (FitsFileModel.fitsFileCalibrated == 1)
        )
        
        calibrated_count = calibrated_lights.count()
        uncalibrated_count = total_lights - calibrated_count
        
        return {
            "total_light_frames": total_lights,
            "calibrated_frames": calibrated_count,
            "uncalibrated_frames": uncalibrated_count,
            "calibration_percentage": (calibrated_count / total_lights * 100) if total_lights > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting calibration statistics: {e}")
        return {
            "total_light_frames": 0,
            "calibrated_frames": 0,
            "uncalibrated_frames": 0,
            "calibration_percentage": 0
        }