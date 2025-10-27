"""
Data conversion utilities for XISF to FITS conversion.

This module handles data type conversion, validation, and preparation for FITS format.
"""

import numpy as np
import logging
from typing import Tuple, Any, Optional, Union
from enum import Enum

logger = logging.getLogger(__name__)

def prepare_fits_data(data: np.ndarray, sample_format: Union[str, Enum]) -> Tuple[np.ndarray, int]:
    """
    Prepare image data for FITS format by ensuring correct data types and byte order.
    
    Args:
        data: The image data array
        sample_format: The original XISF sample format (string or enum)
        
    Returns:
        Tuple of (prepared_data, bitpix_value) for FITS format
    """
    try:
        # Ensure data is a numpy array
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        
        # Convert enum to string if needed
        if hasattr(sample_format, 'value'):
            format_str = sample_format.value
        else:
            format_str = str(sample_format)
        
        # Map XISF formats to appropriate FITS-compatible formats and BITPIX values
        if format_str in ['UInt8']:
            # Unsigned 8-bit data - keep as is for FITS
            data = data.astype(np.uint8)
            bitpix = 8
        elif format_str in ['UInt16']:
            # Unsigned 16-bit data - keep as is
            data = data.astype(np.uint16)
            bitpix = 16
        elif format_str in ['UInt32']:
            # FITS doesn't natively support uint32, convert to int32 if possible
            if np.max(data) <= np.iinfo(np.int32).max:
                data = data.astype(np.int32)
                bitpix = 32
            else:
                # Convert to float32 to preserve range
                data = data.astype(np.float32)
                bitpix = -32
                logger.warning("UInt32 data exceeded int32 range, converted to float32")
        elif format_str in ['UInt64']:
            # Convert to float64 to preserve large values
            data = data.astype(np.float64)
            bitpix = -64
            logger.warning("UInt64 data converted to float64 for FITS compatibility")
        elif format_str in ['Int16']:
            data = data.astype(np.int16)
            bitpix = 16
        elif format_str in ['Int32']:
            data = data.astype(np.int32)
            bitpix = 32
        elif format_str in ['Float32']:
            data = data.astype(np.float32)
            bitpix = -32
        elif format_str in ['Float64']:
            data = data.astype(np.float64)
            bitpix = -64
        elif format_str in ['Complex32']:
            # FITS doesn't support complex, take magnitude
            data = np.abs(data).astype(np.float32)
            bitpix = -32
            logger.warning("Complex32 data converted to magnitude (float32)")
        elif format_str in ['Complex64']:
            # FITS doesn't support complex, take magnitude
            data = np.abs(data).astype(np.float64)
            bitpix = -64
            logger.warning("Complex64 data converted to magnitude (float64)")
        else:
            logger.warning(f"Unknown sample format {format_str}, keeping as-is")
            # Default to current type
            if data.dtype == np.uint8:
                bitpix = 8
            elif data.dtype == np.int16:
                bitpix = 16
            elif data.dtype == np.int32:
                bitpix = 32
            elif data.dtype == np.float32:
                bitpix = -32
            elif data.dtype == np.float64:
                bitpix = -64
            else:
                data = data.astype(np.float32)
                bitpix = -32
        
        # Ensure native byte order for FITS
        if data.dtype.byteorder not in ('=', '|'):
            data = data.astype(data.dtype.newbyteorder('='))
        
        return data, bitpix
        
    except Exception as e:
        logger.error(f"Error preparing FITS data: {e}")
        raise

def validate_data_integrity(data: np.ndarray, expected_pixels: Optional[int] = None, sample_format: Optional[Union[str, Enum]] = None) -> bool:
    """
    Validate the integrity of image data.
    
    Args:
        data: The image data array
        expected_pixels: Expected total number of pixels, if known
        sample_format: The XISF sample format, if known
        
    Returns:
        True if data appears valid, False otherwise
    """
    try:
        if not isinstance(data, np.ndarray):
            logger.error("Data is not a numpy array")
            return False
        
        if data.size == 0:
            logger.error("Data array is empty")
            return False
        
        if expected_pixels is not None and data.size != expected_pixels:
            logger.error(f"Data size {data.size} doesn't match expected {expected_pixels} pixels")
            return False
        
        # Check for reasonable data ranges
        if np.issubdtype(data.dtype, np.floating):
            if np.any(np.isnan(data)):
                logger.warning("Data contains NaN values")
            if np.any(np.isinf(data)):
                logger.warning("Data contains infinite values")
        
        # Check if data is all zeros (might indicate a problem)
        if np.all(data == 0):
            logger.warning("All data values are zero")
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating data integrity: {e}")
        return False

def log_data_statistics(data: np.ndarray, sample_format: Union[str, Enum] = None) -> None:
    """
    Log statistical information about the data for debugging.
    
    Args:
        data: The image data array
        sample_format: The XISF sample format for additional context (string or enum)
    """
    try:
        if not isinstance(data, np.ndarray):
            logger.info(f"Data: Not a numpy array")
            return
        
        # Convert enum to string if needed
        if sample_format and hasattr(sample_format, 'value'):
            format_str = sample_format.value
        elif sample_format:
            format_str = str(sample_format)
        else:
            format_str = None
            
        label = f"Data ({format_str})" if format_str else "Data"
        logger.info(f"{label} statistics:")
        logger.info(f"  Shape: {data.shape}")
        logger.info(f"  Data type: {data.dtype}")
        logger.info(f"  Size: {data.size} elements")
        
        if data.size > 0:
            if np.issubdtype(data.dtype, np.number):
                logger.info(f"  Min: {np.min(data)}")
                logger.info(f"  Max: {np.max(data)}")
                logger.info(f"  Mean: {np.mean(data):.6f}")
                logger.info(f"  Std: {np.std(data):.6f}")
                
                # Check for special values
                if np.issubdtype(data.dtype, np.floating):
                    nan_count = np.sum(np.isnan(data))
                    inf_count = np.sum(np.isinf(data))
                    if nan_count > 0:
                        logger.info(f"  NaN values: {nan_count}")
                    if inf_count > 0:
                        logger.info(f"  Infinite values: {inf_count}")
                
                # Check for zero values
                zero_count = np.sum(data == 0)
                logger.info(f"  Zero values: {zero_count} ({zero_count/data.size*100:.2f}%)")
        
    except Exception as e:
        logger.error(f"Error logging data statistics: {e}")