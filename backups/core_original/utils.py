"""
Utility functions for AstroFiler file processing.

This module contains common utility functions used throughout the application
for path normalization, string sanitization, and FITS header processing.
"""

import os
import logging
import configparser

logger = logging.getLogger(__name__)


def normalize_file_path(file_path):
    """
    Normalize file paths to use forward slashes consistently.
    
    Args:
        file_path: File path string that may contain backslashes
        
    Returns:
        Normalized path with forward slashes
    """
    if file_path:
        return file_path.replace('\\', '/')
    return file_path


def sanitize_filesystem_name(name):
    """
    Sanitize a string for use in filesystem paths and filenames.
    
    Replaces invalid filesystem characters with underscores to match
    the existing folder creation logic in registerFitsImage.
    
    Args:
        name: String that may contain invalid filesystem characters
        
    Returns:
        Sanitized string safe for filesystem use
    """
    if not name:
        return "Unknown"
    
    # Convert to string and strip whitespace
    sanitized = str(name).strip()
    
    # Replace invalid filesystem characters with underscores
    # This matches the existing logic: .replace(" ", "_").replace("\\", "_")
    invalid_chars = [' ', '\\', '/', ':', '*', '?', '"', '<', '>', '|', '\t', '\n', '\r']
    
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Remove multiple consecutive underscores
    while '__' in sanitized:
        sanitized = sanitized.replace('__', '_')
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Ensure we don't return empty string
    if not sanitized:
        sanitized = "Unknown"
    
    return sanitized


def dwarfFixHeader(hdr, root, file):
    """
    Fix FITS headers for DWARF telescope files based on folder structure and filenames.
    
    Args:
        hdr: FITS header object
        root: Root directory path containing the file
        file: Filename
    
    Returns:
        Modified header object or False if error
    """
    try:
        # Read configuration to check if we should save modified headers
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        save_modified = config.getboolean('DEFAULT', 'save_modified_headers', fallback=False)
        
        # Check if this is a DWARF telescope file
        telescop_value = hdr.get("TELESCOP", "")
        if not telescop_value or telescop_value.upper() != "DWARF":
            logger.warning(f"dwarfFixHeader called for non-DWARF file: {file}")
            return False
        
        # Skip failed images
        if file.startswith("failed_"):
            logger.info(f"Ignoring failed DWARF image: {file}")
            return False
        
        # Get the directory structure
        path_parts = os.path.normpath(root).split(os.sep)
        
        # Find the DWARF root directory by looking for required folders
        dwarf_root = None
        for i, part in enumerate(path_parts):
            if part.startswith("DWARF_RAW"):
                # Check if parent directory contains required DWARF folders
                parent_path = os.sep.join(path_parts[:i])
                required_folders = ["CALI_FRAME", "DWARF_DARK"]
                dwarf_raw_folders = [d for d in os.listdir(parent_path) if d.startswith("DWARF_RAW")]
                
                if (os.path.exists(os.path.join(parent_path, "CALI_FRAME")) and 
                    os.path.exists(os.path.join(parent_path, "DWARF_DARK")) and 
                    dwarf_raw_folders):
                    dwarf_root = parent_path
                    break
        
        if not dwarf_root:
            # Check if we're in CALI_FRAME or DWARF_DARK structure
            for i, part in enumerate(path_parts):
                if part in ["CALI_FRAME", "DWARF_DARK"]:
                    parent_path = os.sep.join(path_parts[:i])
                    if (os.path.exists(os.path.join(parent_path, "CALI_FRAME")) and 
                        os.path.exists(os.path.join(parent_path, "DWARF_DARK"))):
                        dwarf_root = parent_path
                        break
        
        if not dwarf_root:
            logger.error(f"Dwarf folder structure not recognized for file: {file}")
            return False
        
        # Determine file type based on path
        rel_path = os.path.relpath(root, dwarf_root)
        path_components = rel_path.split(os.sep)
        
        # Handle DWARF_RAW light files
        if path_components[0].startswith("DWARF_RAW"):
            folder_name = path_components[0]
            # Parse: DWARF_RAW_(INSTRUMEN)_(OBJECT)_EXP_(EXPTIME)_GAIN_(GAIN)_(DATE-OBS)
            parts = folder_name.split("_")
            if len(parts) >= 8:  # Minimum expected parts
                try:
                    instrument = parts[2]  # INSTRUMEN
                    object_name = parts[3]  # OBJECT
                    exptime = parts[5]  # EXPTIME (after EXP)
                    gain = parts[7]  # GAIN (after GAIN)
                    date_obs = "_".join(parts[8:])  # DATE-OBS (rest of string)
                    
                    # Update header
                    hdr['INSTRUME'] = instrument
                    hdr['OBJECT'] = object_name
                    hdr['EXPTIME'] = float(exptime)
                    hdr['GAIN'] = float(gain)
                    
                    # Add missing fields with defaults if not present
                    if 'XBINNING' not in hdr:
                        hdr['XBINNING'] = 1
                    if 'YBINNING' not in hdr:
                        hdr['YBINNING'] = 1
                    if 'CCD-TEMP' not in hdr:
                        hdr['CCD-TEMP'] = -10.0  # Default temperature
                    
                    # Parse and format date if needed
                    if date_obs and 'DATE-OBS' not in hdr:
                        # Assume date format needs to be converted to ISO format
                        hdr['DATE-OBS'] = date_obs
                    
                    # Set image type to LIGHT
                    hdr['IMAGETYP'] = 'LIGHT'
                    
                    logger.info(f"Fixed DWARF_RAW header for {file}: OBJECT={object_name}, INSTRUME={instrument}")
                    
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing DWARF_RAW folder name {folder_name}: {e}")
                    return False
        
        # Handle CALI_FRAME master calibration files
        elif "CALI_FRAME" in path_components:
            cali_index = path_components.index("CALI_FRAME")
            if len(path_components) > cali_index + 2:
                frame_type = path_components[cali_index + 1]  # bias, dark, or flat
                cam_folder = path_components[cali_index + 2]   # cam_0 or cam_1
                
                # Set IMAGETYP and OBJECT
                hdr['IMAGETYP'] = frame_type.upper()
                hdr['OBJECT'] = f"MASTER{frame_type.upper()}"
                
                # Add DATE-OBS if missing (use current date as fallback)
                if 'DATE-OBS' not in hdr:
                    from datetime import datetime
                    hdr['DATE-OBS'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                
                # Set INSTRUME based on camera folder
                if cam_folder == "cam_0":
                    hdr['INSTRUME'] = 'TELE'
                elif cam_folder == "cam_1":
                    hdr['INSTRUME'] = 'WIDE'
                else:
                    logger.warning(f"Unknown camera folder: {cam_folder}")
                
                # Parse filename for specific calibration parameters
                filename_base = os.path.splitext(file)[0]
                
                if frame_type.lower() == "bias":
                    # bias_gain_(GAIN)_bin_(BINNINGX)_*.fits
                    if filename_base.startswith("bias_gain_"):
                        parts = filename_base.split("_")
                        if len(parts) >= 5:
                            gain = parts[2]
                            binning = parts[4]
                            hdr['GAIN'] = float(gain)
                            hdr['XBINNING'] = int(binning)
                            hdr['YBINNING'] = int(binning)
                            if 'EXPTIME' not in hdr:
                                hdr['EXPTIME'] = 0.0  # Bias frames have zero exposure
                            if 'CCD-TEMP' not in hdr:
                                hdr['CCD-TEMP'] = -10.0  # Default temperature
                
                elif frame_type.lower() == "flat":
                    # flat_gain_(GAIN)_bin_(BINNINGX)_*.fits
                    if filename_base.startswith("flat_gain_"):
                        parts = filename_base.split("_")
                        if len(parts) >= 5:
                            gain = parts[2]
                            binning = parts[4]
                            hdr['GAIN'] = float(gain)
                            hdr['XBINNING'] = int(binning)
                            hdr['YBINNING'] = int(binning)
                            if 'EXPTIME' not in hdr:
                                hdr['EXPTIME'] = 1.0  # Default flat exposure
                            if 'CCD-TEMP' not in hdr:
                                hdr['CCD-TEMP'] = -10.0  # Default temperature
                            if 'FILTER' not in hdr:
                                hdr['FILTER'] = 'UNKNOWN'  # Will be set based on folder structure
                
                elif frame_type.lower() == "dark":
                    # dark_exp_(EXPTIME)_gain_(GAIN)_bin_(BINNINGX)_(CCD-TEMP)_*.fits
                    if filename_base.startswith("dark_exp_"):
                        parts = filename_base.split("_")
                        if len(parts) >= 8:
                            exptime = parts[2]
                            gain = parts[4]
                            binning = parts[6]
                            ccd_temp = parts[7]
                            hdr['EXPTIME'] = float(exptime)
                            hdr['GAIN'] = float(gain)
                            hdr['XBINNING'] = int(binning)
                            hdr['YBINNING'] = int(binning)
                            hdr['CCD-TEMP'] = float(ccd_temp)
                
                logger.debug(f"Fixed CALI_FRAME header for {file}: IMAGETYP={frame_type.upper()}, INSTRUME={hdr.get('INSTRUME')}")
        
        # Handle DWARF_DARK library files
        elif "DWARF_DARK" in path_components:
            # tele_exp_(EXPTIME)_gain_(GAIN)_bin_(BINNINGX)_OBS-DATE).fits
            filename_base = os.path.splitext(file)[0]
            if filename_base.startswith("tele_exp_"):
                parts = filename_base.split("_")
                if len(parts) >= 7:
                    exptime = parts[2]
                    gain = parts[4]
                    binning = parts[6]
                    obs_date = "_".join(parts[7:]) if len(parts) > 7 else ""
                    
                    hdr['INSTRUME'] = 'TELE'
                    hdr['IMAGETYP'] = 'DARKMASTER'
                    hdr['OBJECT'] = 'DARKMASTER'
                    hdr['EXPTIME'] = float(exptime)
                    hdr['GAIN'] = float(gain)
                    hdr['XBINNING'] = int(binning)
                    hdr['YBINNING'] = int(binning)
                    
                    # Add DATE-OBS if missing
                    if 'DATE-OBS' not in hdr:
                        if obs_date:
                            hdr['DATE-OBS'] = obs_date
                        else:
                            from datetime import datetime
                            hdr['DATE-OBS'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                    
                    logger.info(f"Fixed DWARF_DARK header for {file}: EXPTIME={exptime}, GAIN={gain}")
        
        else:
            logger.info(f"Ignoring DWARF file in unrecognized folder structure: {file}")
            return hdr  # Return unchanged header
             
        return hdr
        
    except Exception as e:
        logger.error(f"Error in dwarfFixHeader for {file}: {e}")
        return False


def mapFitsHeader(hdr, file_path):
    """
    Apply mappings from the Mapping table to FITS header fields.
    Uses static caching to avoid repeated database queries.
    
    Args:
        hdr: FITS header object to modify
        file_path: Full path to the FITS file (for logging)
    
    Returns:
        bool: True if any header changes were made, False otherwise
    """
    try:
        from astrofiler_db import Mapping
        
        # Static cache for mappings to avoid repeated database queries
        if not hasattr(mapFitsHeader, '_cached_mappings'):
            mapFitsHeader._cached_mappings = None
            mapFitsHeader._cache_loaded = False
        
        # Load mappings from database if not cached
        if not mapFitsHeader._cache_loaded:
            try:
                mappings = list(Mapping.select())
                mapFitsHeader._cached_mappings = {}
                for mapping in mappings:
                    key = (mapping.old_value.upper(), mapping.header_field.upper())
                    mapFitsHeader._cached_mappings[key] = mapping.new_value
                
                mapFitsHeader._cache_loaded = True
                logger.debug(f"Loaded {len(mappings)} header mappings from database")
            
            except Exception as e:
                logger.error(f"Failed to load header mappings: {e}")
                mapFitsHeader._cached_mappings = {}
                mapFitsHeader._cache_loaded = True  # Set to avoid repeated failures
                return False
        
        if not mapFitsHeader._cached_mappings:
            return False
        
        changes_made = False
        
        # Apply mappings to header fields
        for header_field, value in list(hdr.items()):
            if isinstance(value, str):
                key = (value.upper(), header_field.upper())
                if key in mapFitsHeader._cached_mappings:
                    new_value = mapFitsHeader._cached_mappings[key]
                    hdr[header_field] = new_value
                    logger.debug(f"Mapped {header_field} from '{value}' to '{new_value}' for {file_path}")
                    changes_made = True
        
        return changes_made
        
    except Exception as e:
        logger.error(f"Error in mapFitsHeader for {file_path}: {e}")
        return False


def clearMappingCache():
    """Clear the mapping cache to force reload from database."""
    if hasattr(mapFitsHeader, '_cache_loaded'):
        mapFitsHeader._cache_loaded = False
        mapFitsHeader._cached_mappings = None
        logger.info("Header mapping cache cleared")


def get_master_calibration_path():
    """
    Get the master calibration frames path from configuration.
    
    Returns:
        str: Path to master calibration frames directory
    """
    try:
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        repo_folder = config.get('DEFAULT', 'repo', fallback='.')
        return os.path.join(repo_folder, 'Masters')
    except Exception as e:
        logger.error(f"Error getting master calibration path: {e}")
        return os.path.join('.', 'Masters')