#!/usr/bin/env python3
"""
Light Frame Calibration Module for AstroFiler

This module handles the calibration of light frames using master calibration frames.
It applies bias, dark, and flat corrections to produce calibrated light frames
suitable for stacking and further processing.

Key Features:
- Fast, reliable numpy-based calibration
- Comprehensive calibration pipeline (bias-corrected dark, flat)
- Proper bias handling: subtracts bias from dark masters before applying
- Force recalibrate option for already-calibrated frames
- Robust error handling and validation
- Detailed FITS header metadata
- Progress callbacks for GUI integration
- Professional astronomy-standard processing
- Consistent cal_ prefix naming convention

Calibration Formula:
    Calibrated = (Light - (Dark - Bias)) / NormalizedFlat

Note: Dark masters contain uncorrected bias signal, so bias is subtracted
from the dark master before applying it to light frames.
"""

import os
import logging
import hashlib
import numpy as np
from datetime import datetime
from typing import Optional, Callable, Dict, List, Any
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
    1. Bias correction of dark master (Dark - Bias) to remove bias signal from dark
    2. Dark subtraction (Light - BiasCorrectDark) to remove thermal noise
    3. Flat field correction with full-frame median normalization
    
    The calibration formula is: (Light - (Dark - Bias)) / (Flat / median(Flat))
    
    IMPORTANT: Dark masters created by AstroFiler contain uncorrected bias signal
    because bias is not subtracted during dark master creation. This function
    corrects for that by subtracting bias from the dark master before applying it.
    
    Args:
        light_path (str): Path to the light frame FITS file
        dark_master (str, optional): Path to master dark frame
        flat_master (str, optional): Path to master flat frame  
        bias_master (str, optional): Path to master bias frame (REQUIRED for proper dark correction)
        output_path (str, optional): Path for calibrated output file (auto-generated if not provided)
        progress_callback (callable, optional): Callback for progress updates
        
    Returns:
        dict: Calibration result with success status, output path, and metadata
        
    Example:
        >>> result = calibrate_light_frame(
        ...     light_path='light_001.fits',
        ...     dark_master='master_dark_300s.fits',
        ...     flat_master='master_flat_V.fits',
        ...     bias_master='master_bias.fits'  # Required for proper calibration!
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
        
        # Load light frame with proper data type preservation
        if progress_callback:
            progress_callback("Loading light frame...")
            
        with fits.open(light_path) as hdul:
            original_data = hdul[0].data
            light_header = hdul[0].header.copy()
            
            # Convert to float64 for precision during calibration
            light_data = original_data.astype(np.float64)
        
        if light_data is None or light_data.size == 0:
            return {"error": "No image data found in light frame"}
        
        # Get light frame exposure time for dark scaling
        light_exptime = float(light_header.get('EXPTIME', light_header.get('EXPOSURE', 1.0)))
        
        calibrated_data = light_data.copy()
        calibration_steps = []
        
        # =================================================================
        # STEP 1: DARK SUBTRACTION (or BIAS if no dark available)
        # =================================================================
        # CRITICAL FIX: Dark masters contain uncorrected bias signal because bias is not
        # subtracted during dark master creation. We must subtract bias from the dark master
        # before applying it to the light frame.
        # 
        # Correct formula: Light - (Dark - Bias) / Flat
        # Which equals:    (Light - Dark + Bias) / Flat
        
        if dark_master and os.path.exists(dark_master):
            if progress_callback:
                progress_callback("Applying dark correction...")
            try:
                with fits.open(dark_master) as hdul:
                    dark_data = hdul[0].data.astype(np.float64)
                    dark_header = hdul[0].header
                    
                    # Validate dimensions match
                    if dark_data.shape != calibrated_data.shape:
                        raise ValueError(f"Dark frame shape {dark_data.shape} doesn't match light frame {calibrated_data.shape}")
                    
                    # Get dark exposure time for scaling
                    dark_exptime = float(dark_header.get('EXPTIME', dark_header.get('EXPOSURE', light_exptime)))
                    
                    # DISABLED: Dark frame scaling - use closest matching dark instead
                    # # Scale dark frame if exposure times differ
                    # if abs(dark_exptime - light_exptime) > 0.01:  # Allow small floating point differences
                    #     scale_factor = light_exptime / dark_exptime
                    #     dark_scaled = dark_data * scale_factor
                    #     logger.info(f"Scaling dark frame: {dark_exptime}s -> {light_exptime}s (factor: {scale_factor:.3f})")
                    #     calibration_steps.append(f"DARK: {os.path.basename(dark_master)} (scaled {scale_factor:.3f}x)")
                    # else:
                    #     dark_scaled = dark_data
                    #     calibration_steps.append(f"DARK: {os.path.basename(dark_master)}")
                    
                    # Use dark directly without scaling - ensure dark exposure matches light
                    dark_scaled = dark_data
                    
                    # CRITICAL FIX: Subtract bias from dark master before applying
                    # Dark masters contain bias signal that must be removed
                    if bias_master and os.path.exists(bias_master):
                        try:
                            with fits.open(bias_master) as bias_hdul:
                                bias_data = bias_hdul[0].data.astype(np.float64)
                                
                                # Validate bias dimensions match
                                if bias_data.shape != dark_scaled.shape:
                                    logger.warning(f"Bias shape {bias_data.shape} doesn't match dark {dark_scaled.shape}, skipping bias correction")
                                else:
                                    # Remove bias from dark to get true thermal noise
                                    dark_scaled = dark_scaled - bias_data
                                    calibration_steps.append(f"DARK: {os.path.basename(dark_master)} ({dark_exptime}s) - BIAS corrected")
                                    logger.info(f"Bias-corrected dark frame: bias mean={np.mean(bias_data):.2f} ADU removed")
                        except Exception as e:
                            logger.warning(f"Failed to load bias for dark correction: {e}, using uncorrected dark")
                            calibration_steps.append(f"DARK: {os.path.basename(dark_master)} ({dark_exptime}s) - NO BIAS CORRECTION")
                    else:
                        logger.warning("No bias master available - dark correction will leave residual bias signal")
                        calibration_steps.append(f"DARK: {os.path.basename(dark_master)} ({dark_exptime}s) - NO BIAS CORRECTION")
                    
                    logger.info(f"Using dark frame: {dark_exptime}s (light exposure: {light_exptime}s)")
                    
                    # Apply: Light - (Dark - Bias) 
                    calibrated_data = calibrated_data - dark_scaled
                    logger.debug(f"Applied dark correction, data range: [{np.min(calibrated_data):.2f}, {np.max(calibrated_data):.2f}]")
                    
            except Exception as e:
                logger.error(f"Failed to apply dark correction: {e}")
                if progress_callback:
                    progress_callback(f"Warning: Failed to apply dark correction: {e}")
                    
        elif bias_master and os.path.exists(bias_master):
            # If we have bias but no dark, subtract bias from light
            if progress_callback:
                progress_callback("Applying bias correction...")
            try:
                with fits.open(bias_master) as hdul:
                    bias_data = hdul[0].data.astype(np.float64)
                    
                    # Validate dimensions match
                    if bias_data.shape != calibrated_data.shape:
                        raise ValueError(f"Bias frame shape {bias_data.shape} doesn't match light frame {calibrated_data.shape}")
                    
                    calibrated_data = calibrated_data - bias_data
                    calibration_steps.append(f"BIAS: {os.path.basename(bias_master)}")
                    logger.debug(f"Applied bias correction, data range: [{np.min(calibrated_data):.2f}, {np.max(calibrated_data):.2f}]")
                    
            except Exception as e:
                logger.error(f"Failed to apply bias correction: {e}")
                if progress_callback:
                    progress_callback(f"Warning: Failed to apply bias correction: {e}")
        
        # =================================================================
        # STEP 2: FLAT FIELD CORRECTION
        # =================================================================
        # Normalize flat by full-frame median and divide
        
        if flat_master and os.path.exists(flat_master):
            if progress_callback:
                progress_callback("Applying flat correction...")
            try:
                with fits.open(flat_master) as hdul:
                    flat_data = hdul[0].data.astype(np.float64)
                    
                    # Validate dimensions match
                    if flat_data.shape != calibrated_data.shape:
                        raise ValueError(f"Flat frame shape {flat_data.shape} doesn't match light frame {calibrated_data.shape}")
                    
                    # Normalize flat field by its FULL FRAME median (standard approach)
                    flat_median = np.median(flat_data)
                    
                    if flat_median <= 0:
                        raise ValueError("Flat frame median is zero or negative")
                    
                    flat_normalized = flat_data / flat_median
                    
                    # Protect against division by very small values
                    # Use a threshold of 10% of normalized median (0.1)
                    threshold = 0.1
                    mask = flat_normalized < threshold
                    if np.any(mask):
                        logger.warning(f"Flat frame has {np.sum(mask)} pixels below threshold, clamping to {threshold}")
                        flat_normalized = np.clip(flat_normalized, threshold, None)
                    
                    # Apply flat correction
                    calibrated_data = calibrated_data / flat_normalized
                    calibration_steps.append(f"FLAT: {os.path.basename(flat_master)} (median: {flat_median:.1f})")
                    logger.debug(f"Applied flat correction, data range: [{np.min(calibrated_data):.2f}, {np.max(calibrated_data):.2f}]")
                    
            except Exception as e:
                logger.error(f"Failed to apply flat correction: {e}")
                if progress_callback:
                    progress_callback(f"Warning: Failed to apply flat correction: {e}")
        
        # =================================================================
        # GENERATE OUTPUT PATH
        # =================================================================
        
        if not output_path:
            base_dir = os.path.dirname(light_path)
            base_name = os.path.basename(light_path)
            output_path = os.path.join(base_dir, f"cal_{base_name}")
        
        # =================================================================
        # UPDATE FITS HEADER
        # =================================================================
        
        if progress_callback:
            progress_callback("Updating FITS header...")
            
        _update_calibrated_frame_header(
            light_header, 
            calibration_steps, 
            bias_master, 
            dark_master, 
            flat_master, 
            calibrated_data, 
            light_path
        )
        light_header['CALMETOD'] = 'Numpy'
        
        # =================================================================
        # SAVE CALIBRATED FRAME
        # =================================================================
        
        if progress_callback:
            progress_callback("Saving calibrated frame...")
            
        # Calculate statistics for return
        data_min = float(np.min(calibrated_data))
        data_max = float(np.max(calibrated_data))
        data_range = data_max - data_min
        data_mean = float(np.mean(calibrated_data))
        data_std = float(np.std(calibrated_data))
        
        logger.info(f"Calibrated data statistics: min={data_min:.2f}, max={data_max:.2f}, mean={data_mean:.2f}, range={data_range:.2f}")
        
        # If data has negative values, shift it positive for proper display in FITS viewers
        # Many viewers (like ASIFitsView) don't handle negative values well
        bzero_offset = 0.0
        if data_min < 0:
            bzero_offset = abs(data_min) + 100  # Add 100 ADU safety margin
            calibrated_data = calibrated_data + bzero_offset
            logger.info(f"Applied BZERO offset of {bzero_offset:.2f} to shift negative values positive")
        
        # Save as float32 to preserve dynamic range while reducing file size
        output_data = calibrated_data.astype(np.float32)
        
        # Update BITPIX to indicate 32-bit float
        light_header['BITPIX'] = -32
        
        # Set BZERO and BSCALE for proper FITS scaling
        # BZERO tells viewers to subtract this value to get true calibrated data
        light_header['BZERO'] = bzero_offset
        light_header['BSCALE'] = 1.0
        
        if bzero_offset > 0:
            light_header['HISTORY'] = f'Applied BZERO offset of {bzero_offset:.2f} for viewer compatibility'
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Write calibrated frame
        hdu = fits.PrimaryHDU(data=output_data, header=light_header)
        hdu.writeto(output_path, overwrite=True)
        
        if progress_callback:
            progress_callback(f"Calibration complete: {os.path.basename(output_path)}")
            
        return {
            "success": True,
            "output_path": output_path,
            "input_path": light_path,
            "calibration_steps": calibration_steps,
            "method": "Numpy",
            "noise_level": data_std,
            "mean_level": data_mean,
            "dynamic_range": data_range,
            "data_min": data_min,
            "data_max": data_max
        }
        
    except Exception as e:
        logger.error(f"Failed to calibrate light frame: {e}")
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
                
                # Update database record with retry logic for locked database
                max_retries = 5
                retry_delay = 0.1  # seconds
                db_updated = False
                for attempt in range(max_retries):
                    try:
                        light_file.fitsFileCalibrated = 1
                        light_file.fitsFileCalibrationDate = datetime.now()
                        light_file.save()
                        db_updated = True
                        break  # Success, exit retry loop
                    except Exception as e:
                        if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                            import time
                            time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                            logger.debug(f"Database locked, retrying ({attempt + 1}/{max_retries})...")
                        else:
                            logger.error(f"Failed to update database for calibrated file {light_file.fitsFileName} after {max_retries} retries: {e}")
                            break
                
                if not db_updated:
                    raise RuntimeError(f"Database update failed for {light_file.fitsFileName} after {max_retries} retry attempts")
                
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