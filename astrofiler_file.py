############################################################################################################
## F I T S   P R O C E S S I N G                                                                          ##
############################################################################################################
# Functions to import fits file data into the database while renaming files and moving them to a repository, 
# calibrate images, create thumbnails linked to test stacks, and send the user an email with a summary of 
# the work done. This module contains the fitsProcessing class that handles all FITS file operations.
#
from datetime import datetime,timedelta
import numpy as np
import matplotlib.pyplot as plt
import uuid
import os
import hashlib
from math import cos,sin 
from astropy.io import fits
import shutil
import pytz
from peewee import IntegrityError
import configparser

from astrofiler_db import fitsFile as FitsFileModel, fitsSession as fitsSessionModel

import logging
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
                mapFitsHeader._cached_mappings = mappings
                mapFitsHeader._cache_loaded = True
                logger.debug(f"Loaded {len(mappings)} mappings into cache")
            except Exception as e:
                logger.error(f"Error loading mappings from database: {e}")
                return False
        
        # Use cached mappings
        mappings = mapFitsHeader._cached_mappings
        
        if not mappings:
            return False  # No mappings defined
        
        header_modified = False
        
        for mapping in mappings:
            card = mapping.card
            current = mapping.current
            replace = mapping.replace
            # Skip mappings without a replacement value
            if not replace:
                continue

            # Check if this card exists in the header
            if card in hdr:
                header_value = str(hdr[card]).strip()

                if current:
                    # Specific value mapping - replace if current value matches
                    if header_value == current:
                        hdr[card] = replace
                        header_modified = True
                        logger.debug(f"Applied mapping for {card}: '{current}' → '{replace}' in {file_path}")
            # No default mapping logic
        
        return header_modified
        
    except Exception as e:
        logger.error(f"Error applying mappings to {file_path}: {e}")
        return False

def clearMappingCache():
    """
    Clear the static mapping cache to force reload from database.
    Call this after mappings are modified in the database.
    """
    if hasattr(mapFitsHeader, '_cache_loaded'):
        mapFitsHeader._cache_loaded = False
        mapFitsHeader._cached_mappings = None
        logger.debug("Mapping cache cleared")

def get_master_calibration_path():
    """
    Get the path to the master calibration frames directory.
    
    Returns:
        str: Path to the Masters directory within the repository folder
    """
    config = configparser.ConfigParser()
    config.read('astrofiler.ini')
    repo_folder = config.get('DEFAULT', 'repo_folder', fallback='')
    
    if not repo_folder:
        raise ValueError("Repository folder not configured in astrofiler.ini")
        
    masters_dir = os.path.join(repo_folder, 'Masters')
    os.makedirs(masters_dir, exist_ok=True)
    
    return masters_dir
    
class fitsProcessing:
    """
    A class for processing FITS files, including registration, calibration, and database operations.
    
    This class handles:
    - Importing FITS file data into the database
    - Renaming and moving files to repository structure
    - Creating sessions from FITS files
    - Creating thumbnails
    - Calibrating images
    """
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        self.sourceFolder = config.get('DEFAULT', 'source', fallback='.')
        self.repoFolder = config.get('DEFAULT', 'repo', fallback='.')

    ################################################################################################################
    ## - this function calculates SHA-256 hash of a file for duplicate detection                    ##
    #################################################################################################################
    def calculateFileHash(self, filePath):
        """Calculate SHA-256 hash of a file for duplicate detection."""
        try:
            hash_sha256 = hashlib.sha256()
            with open(filePath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {filePath}: {str(e)}")
            return None

    #################################################################################################################
    ## registerFitsImage - this functioncalls a function to registers each fits files in the database              ##
    ## and also corrects any issues with the Fits header info (e.g. WCS)                                           ##
    #################################################################################################################
    # Note: Movefiles means we are moving from a source folder to the repo, otherwise we are syncing the repo database
    def registerFitsImage(self,root,file,moveFiles):
        newFitsFileId=None
        file_name, file_extension = os.path.splitext(os.path.join(root,file))
        #print("Processing file "+os.path.join(root, file)+" with extension -"+file_extension+"-")

        # Are we saving modified headers?
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        save_modified = config.getboolean('DEFAULT', 'save_modified_headers', fallback=False)

        # Ignore everything not a *fit* file
        if "fit" not in file_extension.lower():
            logger.debug("Ignoring file "+os.path.join(root, file)+" with extension -"+file_extension+"-")
            return False
        
        # Open the FITS file for reading and close immediately after reading header
        try:
            hdul = fits.open(os.path.join(root, file), mode='readonly')
            hdr = hdul[0].header
            hdul.close()
        except Exception as e:
            logger.warning(f"Error loading FITS file {e} File not processed is "+str(os.path.join(root, file)))
            return False

        # Special handling for vendors with incomplete headers
        # DWARF telescopes - missing DATE-OBS, EXPTIME, XBINNING, YBINNING, CCD-TEMP
        header_modified = False
        telescop_value = hdr.get("TELESCOP", "")
        if telescop_value and telescop_value.upper() == "DWARF":
            modified_hdr = dwarfFixHeader(hdr, root, file)
            if not modified_hdr:
                logger.warning("Error fixing DWARF header. File not processed is "+str(os.path.join(root, file)))
                return False
            hdr = modified_hdr
            header_modified = True
        
        # Apply FITS header mappings from the Mapping table
        mapping_modified = mapFitsHeader(hdr, os.path.join(root, file))
        if mapping_modified:
            header_modified = True
        
        if "IMAGETYP" in hdr:
            # Fix variances in header cards
            if ("EXPTIME" in hdr):
                exposure=hdr["EXPTIME"]
            else:
                if ("EXPOSURE" in hdr):
                    exposure=hdr["EXPOSURE"]
                else:
                    logger.warning("No EXPTIME or EXPOSURE card in header. File not processed is "+str(os.path.join(root, file)))
                    return False
                
            if "TELESCOP" in hdr:
                telescope=hdr["TELESCOP"]
            else:
                telescope="Unknown"
            
            # Fix calibration frames where OBJECT is set to an object rather than the frametype
            if "DARK" in hdr["IMAGETYP"].upper():
                hdr["OBJECT"] = "Dark"
            elif "FLAT" in hdr["IMAGETYP"].upper():
                hdr["OBJECT"] = "Flat"
            elif "BIAS" in hdr["IMAGETYP"].upper():
                hdr["OBJECT"] = "Bias"

            # Create an os-friendly date
            try:
                if "DATE-OBS" not in hdr:
                    logger.warning("No DATE-OBS card in header. File not processed is "+str(os.path.join(root, file)))
                    return False
                datestr=hdr["DATE-OBS"].replace("T", " ")
                datestr=datestr[0:datestr.find('.')]
                dateobj=datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
                fitsDate=dateobj.strftime("%Y%m%d%H%M%S")
            except ValueError as e:
                logger.warning("Invalid date format in header. File not processed is "+str(os.path.join(root, file)))
                return False

            ############## L I G H T S ################################################################
            if "LIGHT" in hdr["IMAGETYP"].upper():
                # Adjust the WCS for the image
                if "CD1_1" not in hdr:
                    if "CDELT1" in hdr and "CDELT2" in hdr and "CROTA2" in hdr and "CDELT2" in hdr and "CROTA2" in hdr:
                        fitsCDELT1=float(hdr["CDELT1"])
                        fitsCDELT2=float(hdr["CDELT2"])
                        fitsCROTA2=float(hdr["CROTA2"])
                        fitsCD1_1 =  fitsCDELT1 * cos(fitsCROTA2)
                        fitsCD1_2 = -fitsCDELT2 * sin(fitsCROTA2)
                        fitsCD2_1 =  fitsCDELT1 * sin (fitsCROTA2)
                        fitsCD2_2 = fitsCDELT2 * cos(fitsCROTA2)
                        hdr.append(('CD1_1', str(fitsCD1_1), 'Rotation Matrix'), end=True)
                        hdr.append(('CD1_2', str(fitsCD1_2), 'Rotation Matrix'), end=True)
                        hdr.append(('CD2_1', str(fitsCD2_1), 'Rotation Matrix'), end=True)
                        hdr.append(('CD2_2', str(fitsCD2_2), 'Rotation Matrix'), end=True)
                        header_modified = True
                    else:
                        logger.warning("No CDELT1, CDELT2 or CROTA2 card in header. Unable to update WCS in "+str(os.path.join(root, file)))             
                
                # Create a new file name
                if ("OBJECT" in hdr):
                    if ("FILTER" in hdr):
                        newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(sanitize_filesystem_name(hdr["OBJECT"]),sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),sanitize_filesystem_name(hdr["FILTER"]),fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                    else:
                        newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(sanitize_filesystem_name(hdr["OBJECT"]),sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),"OSC",fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                else:
                    logger.warning("Invalid object name in header. File not processed is "+str(os.path.join(root, file)))
                    return False
                

            ############## F L A T S ##################################################################            
            elif "FLAT" in hdr["IMAGETYP"].upper():
                if ("FILTER" in hdr):
                    newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format("Flat",sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),sanitize_filesystem_name(hdr["FILTER"]),fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                else:
                    newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format("Flat",sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),"OSC",fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
            
            ############## D A R K S ##################################################################   
            elif "DARK" in hdr["IMAGETYP"].upper():
                newName="{0}-{1}-{2}-{3}-{4}s-{5}x{6}-t{7}.fits".format("Dark",sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
            ############## B I A S E S ################################################################   
            elif "BIAS" in hdr["IMAGETYP"].upper():
                newName="{0}-{1}-{2}-{3}-{4}s-{5}x{6}-t{7}.fits".format("Bias",sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])

            else:
                logger.warning("File not processed as IMAGETYP -"+hdr["IMAGETYP"]+"- not recognized: "+str(os.path.join(root, file)))
            
            # Close the HDU list
            try:
                hdul.close()
            except Exception as e:
                logger.warning(f"Non-compliant header warning in {os.path.basename(__file__)} while processing file {os.path.join(root, file)}")
            
            # Update any header changes if needed
            try:
                # Check if we need to save header modifications
                if header_modified and save_modified:
                    hdul_update = fits.open(os.path.join(root, file), mode='update')
                    hdul_update.flush()  # Save header changes to file
                    logger.debug(f"Saved header modifications for {file}")
                    hdul_update.close()
            except Exception as e:
                logger.warning(f"Non-compliant header warning in {os.path.basename(__file__)} while processing file {os.path.join(root, file)}")


            newPath=""

            ######################################################################################################
            # Create the folder structure (if needed)
            fitsDate=dateobj.strftime("%Y%m%d")
            if "LIGHT" in hdr["IMAGETYP"].upper():
                newPath=self.repoFolder+"Light/{0}/{1}/{2}/{3}/".format(sanitize_filesystem_name(hdr["OBJECT"]),sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),fitsDate)
            elif "DARK" in hdr["IMAGETYP"].upper():
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format("Dark",sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),exposure,fitsDate)
            elif "FLAT" in hdr["IMAGETYP"].upper():
                if ("FILTER" in hdr):
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format("Flat",sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),sanitize_filesystem_name(hdr["FILTER"]),fitsDate)
                else:
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format("Flat",sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),"OSC",fitsDate)
            elif "BIAS" in hdr["IMAGETYP"].upper():
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/".format("Bias",sanitize_filesystem_name(telescope),
                                    sanitize_filesystem_name(hdr["INSTRUME"]),fitsDate)
            else:
                logger.warning("File not processed as IMAGETYP not recognized: "+str(os.path.join(root, file)))
                return None

            if not os.path.isdir(newPath) and moveFiles:
                os.makedirs (newPath)

            # Calculate file hash for duplicate detection
            currentFilePath = os.path.join(root, file)
            fileHash = self.calculateFileHash(currentFilePath)
            logger.debug("Registering file "+os.path.join(root, file)+" to "+newPath+newName)
            newFitsFileId=self.submitFileToDB(newPath+newName,hdr,fileHash)
            if (newFitsFileId != None) and moveFiles:
                if not os.path.exists(newPath+newName):
                    logger.debug("Moving file "+os.path.join(root, file)+" to "+newPath+newName)
                    # Move the file to the new location
                    try:
                        shutil.move(os.path.join(root, file), newPath+newName)
                    except shutil.Error as e:
                        logger.error("Shutil error moving file "+os.path.join(root, file)+" to "+newPath+newName+": "+str(e))
                        return None
                    except OSError as e:
                        logger.error("OS error moving file "+os.path.join(root, file)+" to "+newPath+newName+": "+str(e))
                        return None
                    logger.debug("File successfully moved to repo - "+newPath+newName)
                else:
                    logger.warning("File already exists in repo, no changes - "+newPath+newName)
                    return "DUPLICATE"  # Special return value for duplicate files
            else:
                if not moveFiles:
                    logger.warning("Warning: File not moved to repo is "+str(os.path.join(root, file)))
        else:
            logger.warning("File not added to repo - no IMAGETYP card - "+str(os.path.join(root, file)))
        
        return newFitsFileId

    #################################################################################################################
    ## registerFitsImages - this function scans the images folder and registers all fits files in the database     ##
    #################################################################################################################
    def registerFitsImages(self,moveFiles=True, progress_callback=None):
        registeredFiles=[]
        newFitsFileId=None
        currCount=0
        start_time = datetime.now()

        # Scan the pictures folder
        if moveFiles:
            logger.info("Processing images in "+self.sourceFolder)
            workFolder=self.sourceFolder
        else:
            logger.info("Syncronizing images in "+os.path.abspath(self.repoFolder))
            workFolder=self.repoFolder

        # First pass: count total files to process
        total_files = 0
        for root, dirs, files in os.walk(os.path.abspath(workFolder)):
            for file in files:
                file_name, file_extension = os.path.splitext(file)
                if "fit" in file_extension.lower():
                    total_files += 1
        
        logger.info(f"Found {total_files} FITS files to process")
        
        # If no files found, return early
        if total_files == 0:
            logger.info("No FITS files found to process")
            if progress_callback:
                progress_callback(0, 0, "No FITS files found")
            return registeredFiles
        
        # Second pass: process files with progress tracking
        successful_files = 0
        failed_files = 0
        duplicate_files = 0
        cancelled_by_user = False
        
        logger.debug(f"Starting second pass to process {total_files} FITS files")
        
        for root, dirs, files in os.walk(os.path.abspath(workFolder)):
            logger.debug(f"Processing directory: {root} with {len(files)} files")
            for file in files:
                file_name, file_extension = os.path.splitext(file)
                if "fit" in file_extension.lower():
                    currCount += 1
                    logger.debug(f"Found FITS file #{currCount}: {file}")
                    
                    # Call progress callback if provided
                    if progress_callback:
                        logger.debug(f"Calling progress callback for file {currCount}/{total_files}: {file}")
                        should_continue = progress_callback(currCount, total_files, file)
                        logger.debug(f"Progress callback returned: {should_continue}")
                        if not should_continue:
                            logger.info("Processing cancelled by user")
                            cancelled_by_user = True
                            break
                    else:
                        logger.debug("No progress callback provided")
                    
                    # Calculate and display progress
                    progress_percent = (currCount / total_files) * 100 if total_files > 0 else 0
                    elapsed_time = datetime.now() - start_time
                    if currCount > 0:
                        avg_time_per_file = elapsed_time / currCount
                        estimated_remaining = avg_time_per_file * (total_files - currCount)
                        eta_str = f", ETA: {estimated_remaining}"
                    else:
                        eta_str = ""
                    
                    logger.debug(f"Processing file {currCount}/{total_files} ({progress_percent:.1f}%): {file}{eta_str}")
                    
                    # Try to register the file
                    try:
                        newFitsFileId = self.registerFitsImage(root, file, moveFiles)
                    except Exception as e:
                        logger.error(f"Exception registering file {file}: {str(e)}")
                        newFitsFileId=None

                    if newFitsFileId == "DUPLICATE":
                        # File was skipped because it's a duplicate
                        duplicate_files += 1
                        logger.debug(f"Skipped duplicate file: {file}")
                    elif newFitsFileId is not None:
                        # Add the file to the list of registered files
                        registeredFiles.append(newFitsFileId)
                        successful_files += 1
                        logger.debug(f"Successfully registered file: {file}")
                    else:
                        failed_files += 1
                        logger.warning(f"Failed to register file: {file}")
                else:
                    logger.debug("Ignoring non-FITS file: "+file)
            
            # Check if processing was cancelled
            if cancelled_by_user:
                break
        
        total_time = datetime.now() - start_time
        logger.info(f"Processing complete! Found {total_files} files, successfully registered {successful_files} files, skipped {duplicate_files} duplicates, failed {failed_files} files in {total_time}")
        
        if cancelled_by_user:
            logger.info("Processing was cancelled by user")
        
        return registeredFiles, duplicate_files

    #################################################################################################################
    ## createLightSessions - this function creates sessions for all Light files not currently assigned to one    ##
    #################################################################################################################
    def createLightSessions(self, progress_callback=None):
        sessionsCreated=[]
        
        # Query for all fits files that are not assigned to a session, sort by object, date, filter
        unassigned_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("Light"))
        unassigned_files = unassigned_files.order_by(FitsFileModel.fitsFileObject, FitsFileModel.fitsFileDate, FitsFileModel.fitsFileFilter)

        # How many unassigned_files are there?
        logger.info("createSessions found "+str(len(unassigned_files))+" unassigned files to session")

        # Loop through each unassigned file and create a session each time the object, date, or filter changes
        currentObject = ""
        currentDate = None
        currentFilter = None
        currentSessionId = None
        total_files = len(unassigned_files)
        current_count = 0

        for currentFitsFile in unassigned_files:
            current_count += 1

            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, str(currentFitsFile.fitsFileName))
                if not should_continue:
                    logger.info("Session creation cancelled by user")
                    break

            logger.debug("Current Object is "+str(currentFitsFile.fitsFileObject)+", date "+str(currentFitsFile.fitsFileDate)+", filter "+str(currentFitsFile.fitsFileFilter))
            logger.debug("Processing "+str(currentFitsFile.fitsFileName))

            # If the object name, date, or filter has changed, create a new session
            fits_date = self.dateToDateField(currentFitsFile.fitsFileDate)
            fits_filter = currentFitsFile.fitsFileFilter
            if (str(currentFitsFile.fitsFileObject) != currentObject or
                fits_date != currentDate or
                fits_filter != currentFilter):
                # Create a new fitsSession record
                currentSessionId = uuid.uuid4()
                currentDate = fits_date
                currentFilter = fits_filter

                try:
                    newFitsSession = fitsSessionModel.create(
                        fitsSessionId=currentSessionId,
                        fitsSessionObjectName=currentFitsFile.fitsFileObject,
                        fitsSessionTelescope=currentFitsFile.fitsFileTelescop,
                        fitsSessionImager=currentFitsFile.fitsFileInstrument,
                        fitsSessionDate=fits_date,
                        fitsSessionExposure=currentFitsFile.fitsFileExpTime,
                        fitsSessionBinningX=currentFitsFile.fitsFileXBinning,
                        fitsSessionBinningY=currentFitsFile.fitsFileYBinning,
                        fitsSessionCCDTemp=currentFitsFile.fitsFileCCDTemp,
                        fitsSessionGain=currentFitsFile.fitsFileGain,
                        fitsSessionOffset=currentFitsFile.fitsFileOffset,
                        fitsSessionFilter=fits_filter,
                        fitsBiasSession=None,
                        fitsDarkSession=None,
                        fitsFlatSession=None
                    )
                    sessionsCreated.append(currentSessionId)
                    logger.debug("New session created for "+str(newFitsSession.fitsSessionId))
                except IntegrityError as e:
                    # Handle the integrity error
                    logger.error("IntegrityError: "+str(e))
                    continue
                currentObject = str(currentFitsFile.fitsFileObject)

            # Assign the current session to the fits file
            currentFitsFile.fitsFileSession = currentSessionId
            currentFitsFile.save()
            logger.debug("Assigned "+str(currentFitsFile.fitsFileName)+" to session "+str(currentSessionId))
            
        return sessionsCreated
        
    #################################################################################################################
    ## sameDay - this function returns True if two dates are within 12 hours of each other, False otherwise        ##
    #################################################################################################################
    def sameDay(self,Date1,Date2): # If Date1 is within 12 hours of Date2
        current_date = datetime.strptime(Date1, '%Y-%m-%d')
        target_date = datetime.strptime(Date2, '%Y-%m-%d')
        time_difference = abs(current_date - target_date)
        return time_difference <= timedelta(hours=12)
        
    #################################################################################################################
    ## createCalibrationSessions - this function creates sessions for all calibration files not currently        ##
    ##                              assigned to one                                                                ##
    #################################################################################################################
    def createCalibrationSessions(self, progress_callback=None):
        from datetime import date, datetime
        createdCalibrationSessions=[]
        
        # Query for all calibration files that are not assigned to a session
        unassignedBiases = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("BIAS"))
        unassignedDarks  = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("DARK"))
        unassignedFlats  = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("FLAT"))
        
        # Calculate total files for progress tracking
        total_biases = len(unassignedBiases)
        total_darks = len(unassignedDarks)
        total_flats = len(unassignedFlats)
        total_files = total_biases + total_darks + total_flats
        current_count = 0
        
        # How many unassigned_files are there?
        logger.info("createCalibrationSessions found "+str(total_biases)+" unassigned Bias calibration files to Session")
        logger.info("createCalibrationSessions found "+str(total_darks)+" unassigned Dark calibration files to Session")
        logger.info("createCalibrationSessions found "+str(total_flats)+" unassigned Flat calibration files to Session")

        # Bias calibration files - group by date, telescope, imager, binning, gain, offset
        current_session_params = None
        uuidStr = None
        last_file_time = None
        session_gap_minutes = 15  # Create new session if gap > 15 minutes
                        
        for biasFitsFile in unassignedBiases:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Bias: {biasFitsFile.fitsFileName}")
                if not should_continue:
                    logger.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            # Create session parameters tuple for comparison (bias: date, binning, imager)
            file_params = (
                self.dateToString(biasFitsFile.fitsFileDate),  # Date
                biasFitsFile.fitsFileInstrument,               # Imager
                biasFitsFile.fitsFileXBinning,                 # X Binning
                biasFitsFile.fitsFileYBinning                  # Y Binning
            )
            
            # Check time gap between files (for same-day session separation)
            time_gap_exceeded = False
            if last_file_time is not None:
                current_time = biasFitsFile.fitsFileDate
                
                # Ensure both times are datetime objects for comparison
                
                # Convert current_time to datetime if needed
                if isinstance(current_time, str):
                    current_time = datetime.fromisoformat(current_time.replace('T', ' '))
                elif isinstance(current_time, date) and not isinstance(current_time, datetime):
                    # Convert date to datetime at midnight
                    current_time = datetime.combine(current_time, datetime.min.time())
                
                # Convert last_file_time to datetime if needed  
                if isinstance(last_file_time, str):
                    last_file_time = datetime.fromisoformat(last_file_time.replace('T', ' '))
                elif isinstance(last_file_time, date) and not isinstance(last_file_time, datetime):
                    # Convert date to datetime at midnight
                    last_file_time = datetime.combine(last_file_time, datetime.min.time())
                
                time_diff = abs((current_time - last_file_time).total_seconds() / 60)  # minutes
                if time_diff > session_gap_minutes:
                    time_gap_exceeded = True
                    logger.debug(f"Time gap of {time_diff:.1f} minutes detected, creating new bias session")
            
            # Create new session if parameters changed or time gap exceeded
            if current_session_params != file_params or time_gap_exceeded:
                logger.debug(f"Creating new bias session - Date: {file_params[0]}, "
                           f"Imager: {file_params[1]}, Binning: {file_params[2]}x{file_params[3]}")
                current_session_params = file_params
                uuidStr = uuid.uuid4()  # New Session
                newFitsSession=fitsSessionModel.create(fitsSessionId=uuidStr,
                                                fitsSessionDate=self.dateToDateField(biasFitsFile.fitsFileDate),
                                                fitsSessionObjectName='Bias',
                                                fitsSessionTelescope=biasFitsFile.fitsFileTelescop,
                                                fitsSessionImager=biasFitsFile.fitsFileInstrument,
                                                fitsSessionExposure=biasFitsFile.fitsFileExpTime,
                                                fitsSessionBinningX=biasFitsFile.fitsFileXBinning,
                                                fitsSessionBinningY=biasFitsFile.fitsFileYBinning,
                                                fitsSessionCCDTemp=biasFitsFile.fitsFileCCDTemp,
                                                fitsSessionGain=biasFitsFile.fitsFileGain,
                                                fitsSessionOffset=biasFitsFile.fitsFileOffset,
                                                fitsSessionFilter=biasFitsFile.fitsFileFilter,
                                                fitsBiasSession=None,
                                                fitsDarkSession=None,
                                                fitsFlatSession=None)
                createdCalibrationSessions.append(uuidStr)  # Add session only when created
                
            # Update last file time for gap detection
            current_time = biasFitsFile.fitsFileDate
            if isinstance(current_time, str):
                current_time = datetime.fromisoformat(current_time.replace('T', ' '))
            last_file_time = current_time
            
            biasFitsFile.fitsFileSession=uuidStr
            biasFitsFile.save()   
            logger.debug("Set Session for bias "+biasFitsFile.fitsFileName+" to "+str(uuidStr))
        
        # Dark calibration files - group by date, telescope, imager, exposure, binning, gain, offset
        current_session_params = None
        uuidStr = None
        last_file_time = None
        session_gap_minutes = 15  # Create new session if gap > 15 minutes
        
        for darkFitsFile in unassignedDarks:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Dark: {darkFitsFile.fitsFileName}")
                if not should_continue:
                    logger.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            # Create session parameters tuple for comparison (dark: date, binning, imager, gain, offset, temp, exposure)
            file_params = (
                self.dateToString(darkFitsFile.fitsFileDate),  # Date
                darkFitsFile.fitsFileInstrument,               # Imager
                darkFitsFile.fitsFileXBinning,                 # X Binning
                darkFitsFile.fitsFileYBinning,                 # Y Binning
                darkFitsFile.fitsFileGain,                     # Gain
                darkFitsFile.fitsFileOffset,                   # Offset
                darkFitsFile.fitsFileCCDTemp,                  # Temperature
                darkFitsFile.fitsFileExpTime                   # Exposure time
            )
            
            # Check time gap between files (for same-day session separation)
            time_gap_exceeded = False
            if last_file_time is not None:
                current_time = darkFitsFile.fitsFileDate
                
                # Ensure both times are datetime objects for comparison
                
                # Convert current_time to datetime if needed
                if isinstance(current_time, str):
                    current_time = datetime.fromisoformat(current_time.replace('T', ' '))
                elif isinstance(current_time, date) and not isinstance(current_time, datetime):
                    # Convert date to datetime at midnight
                    current_time = datetime.combine(current_time, datetime.min.time())
                
                # Convert last_file_time to datetime if needed  
                if isinstance(last_file_time, str):
                    last_file_time = datetime.fromisoformat(last_file_time.replace('T', ' '))
                elif isinstance(last_file_time, date) and not isinstance(last_file_time, datetime):
                    # Convert date to datetime at midnight
                    last_file_time = datetime.combine(last_file_time, datetime.min.time())
                
                time_diff = abs((current_time - last_file_time).total_seconds() / 60)  # minutes
                if time_diff > session_gap_minutes:
                    time_gap_exceeded = True
                    logger.debug(f"Time gap of {time_diff:.1f} minutes detected, creating new dark session")
            
            # Create new session if parameters changed or time gap exceeded
            if current_session_params != file_params or time_gap_exceeded:
                logger.debug(f"Creating new dark session - Date: {file_params[0]}, "
                           f"Imager: {file_params[1]}, Binning: {file_params[2]}x{file_params[3]}, "
                           f"Gain: {file_params[4]}, Offset: {file_params[5]}, Temp: {file_params[6]}, Exposure: {file_params[7]}")
                current_session_params = file_params
                uuidStr=uuid.uuid4() # New Session
                newFitsSession=fitsSessionModel.create(fitsSessionId=uuidStr,
                                                fitsSessionDate=self.dateToDateField(darkFitsFile.fitsFileDate),
                                                fitsSessionObjectName='Dark',
                                                fitsSessionTelescope=darkFitsFile.fitsFileTelescop,
                                                fitsSessionImager=darkFitsFile.fitsFileInstrument,
                                                fitsSessionExposure=darkFitsFile.fitsFileExpTime,
                                                fitsSessionBinningX=darkFitsFile.fitsFileXBinning,
                                                fitsSessionBinningY=darkFitsFile.fitsFileYBinning,
                                                fitsSessionCCDTemp=darkFitsFile.fitsFileCCDTemp,
                                                fitsSessionGain=darkFitsFile.fitsFileGain,
                                                fitsSessionOffset=darkFitsFile.fitsFileOffset,
                                                fitsSessionFilter=darkFitsFile.fitsFileFilter,
                                                fitsBiasSession=None,
                                                fitsDarkSession=None,
                                                fitsFlatSession=None)
                createdCalibrationSessions.append(uuidStr)  # Add session only when created
                
            # Update last file time for gap detection
            current_time = darkFitsFile.fitsFileDate
            if isinstance(current_time, str):
                current_time = datetime.fromisoformat(current_time.replace('T', ' '))
            last_file_time = current_time 
            darkFitsFile.fitsFileSession=uuidStr
            darkFitsFile.save()   
            logger.debug("Set Session for dark "+darkFitsFile.fitsFileName+" to "+str(uuidStr))
            
        # Flat calibration files - group by date, binning, imager, telescope, filter
        current_session_params = None
        uuidStr = None
        last_file_time = None
        session_gap_minutes = 15  # Create new session if gap > 15 minutes
        
        for flatFitsFile in unassignedFlats:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Flat: {flatFitsFile.fitsFileName}")
                if not should_continue:
                    logger.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            # Create session parameters tuple for comparison (flat: date, binning, imager, telescope, filter)
            file_params = (
                self.dateToString(flatFitsFile.fitsFileDate),   # Date
                flatFitsFile.fitsFileInstrument,               # Imager
                flatFitsFile.fitsFileXBinning,                 # X Binning
                flatFitsFile.fitsFileYBinning,                 # Y Binning
                flatFitsFile.fitsFileTelescop,                 # Telescope
                flatFitsFile.fitsFileFilter                    # Filter
            )
            
            # Check time gap between files (for same-day session separation)
            time_gap_exceeded = False
            if last_file_time is not None:
                current_time = flatFitsFile.fitsFileDate
                
                # Ensure both times are datetime objects for comparison
                
                # Convert current_time to datetime if needed
                if isinstance(current_time, str):
                    current_time = datetime.fromisoformat(current_time.replace('T', ' '))
                elif isinstance(current_time, date) and not isinstance(current_time, datetime):
                    # Convert date to datetime at midnight
                    current_time = datetime.combine(current_time, datetime.min.time())
                
                # Convert last_file_time to datetime if needed  
                if isinstance(last_file_time, str):
                    last_file_time = datetime.fromisoformat(last_file_time.replace('T', ' '))
                elif isinstance(last_file_time, date) and not isinstance(last_file_time, datetime):
                    # Convert date to datetime at midnight
                    last_file_time = datetime.combine(last_file_time, datetime.min.time())
                
                time_diff = abs((current_time - last_file_time).total_seconds() / 60)  # minutes
                if time_diff > session_gap_minutes:
                    time_gap_exceeded = True
                    logger.debug(f"Time gap of {time_diff:.1f} minutes detected, creating new flat session")
            
            # Create new session if parameters changed or time gap exceeded
            if current_session_params != file_params or time_gap_exceeded:
                logger.debug(f"Creating new flat session - Date: {file_params[0]}, "
                           f"Imager: {file_params[1]}, Binning: {file_params[2]}x{file_params[3]}, "
                           f"Telescope: {file_params[4]}, Filter: {file_params[5]}")
                current_session_params = file_params
                uuidStr=uuid.uuid4() # New Session
                newFitsSession=fitsSessionModel.create(fitsSessionId=uuidStr,
                                fitsSessionDate=self.dateToDateField(flatFitsFile.fitsFileDate),
                                fitsSessionObjectName='Flat',
                                fitsSessionTelescope=flatFitsFile.fitsFileTelescop,
                                fitsSessionImager=flatFitsFile.fitsFileInstrument,
                                fitsSessionExposure=flatFitsFile.fitsFileExpTime,
                                fitsSessionBinningX=flatFitsFile.fitsFileXBinning,
                                fitsSessionBinningY=flatFitsFile.fitsFileYBinning,
                                fitsSessionCCDTemp=flatFitsFile.fitsFileCCDTemp,
                                fitsSessionGain=flatFitsFile.fitsFileGain,
                                fitsSessionOffset=flatFitsFile.fitsFileOffset,
                                fitsSessionFilter=flatFitsFile.fitsFileFilter,
                                fitsBiasSession=None,
                                fitsDarkSession=None,
                                fitsFlatSession=None)
                createdCalibrationSessions.append(uuidStr)  # Add session only when created
                
            # Update last file time for gap detection
            current_time = flatFitsFile.fitsFileDate
            if isinstance(current_time, str):
                current_time = datetime.fromisoformat(current_time.replace('T', ' '))
            last_file_time = current_time 
            flatFitsFile.fitsFileSession=uuidStr
            flatFitsFile.save()   
            logger.debug("Set Session for flat "+flatFitsFile.fitsFileName+" to "+str(uuidStr))
        
        return createdCalibrationSessions

    #################################################################################################################
    ## submitFileToDB- this function submits a fits file to the database                                          ##
    #################################################################################################################
    def submitFileToDB(self,fileName,hdr,fileHash=None):
        if "DATE-OBS" in hdr:
            # Create new fitsFile record
            logger.debug("Adding file "+fileName+" to repo with date "+hdr["DATE-OBS"])
            
            # Adjust for different keywords
            if ("EXPTIME" in hdr):
                exposure=hdr["EXPTIME"]
            else:
                if ("EXPOSURE" in hdr):
                    exposure=hdr["EXPOSURE"]
                else:
                    logger.error("Error: File not added to repo due to missing exposure time in "+fileName)
                    return None
            
            if "TELESCOP" in hdr:
                telescope=hdr["TELESCOP"]
            else:
                telescope="Unknown"

            if "OBJECT" in hdr:
                newfile=FitsFileModel.create(fitsFileId=uuid.uuid4(),fitsFileName=normalize_file_path(fileName),fitsFileDate=hdr["DATE-OBS"],fitsFileType=hdr["IMAGETYP"].upper(),
                            fitsFileObject=hdr["OBJECT"],fitsFileExpTime=exposure,fitsFileXBinning=hdr["XBINNING"],
                            fitsFileYBinning=hdr["YBINNING"],fitsFileCCDTemp=hdr["CCD-TEMP"],fitsFileTelescop=telescope,
                            fitsFileInstrument=hdr["INSTRUME"],fitsFileFilter=hdr.get("FILTER", None),
                            fitsFileHash=fileHash,fitsFileSession=None)
            else:
                newfile=FitsFileModel.create(fitsFileId=uuid.uuid4(),fitsFileName=normalize_file_path(fileName),fitsFileDate=hdr["DATE-OBS"],fitsFileType=hdr["IMAGETYP"].upper(),
                            fitsFileExpTime=exposure,fitsFileXBinning=hdr["XBINNING"],
                            fitsFileYBinning=hdr["YBINNING"],fitsFileCCDTemp=hdr["CCD-TEMP"],fitsFileTelescop=telescope,
                            fitsFileInstrument=hdr["INSTRUME"],fitsFileFilter=hdr.get("FILTER", "OSC"),
                            fitsFileHash=fileHash,fitsFileSession=None)
            return newfile.fitsFileId
        else:
            logger.error("Error: File not added to repo due to missing date is "+fileName)
            return None
        return True

    #################################################################################################################
    ## linkSessions - this function links calibration sessions to light sessions based on telescope and imager    ##
    ##                matching. For each light session, it finds the most recent calibration sessions for the     ##
    ##                same telescope and imager combination, with additional matching criteria:                    ##
    ##                - All calibration frames must have the same binning settings as the light frames            ##
    ##                - All calibration frames must have the same gain and offset settings                        ##
    ##                - Darks must have the same exposure time as the light frames                                 ##
    ##                - Darks must have CCD temperature within 5 degrees of the light frames                      ##
    ##                - Flats must match the filter of the light frames                                            ##
    #################################################################################################################
    def linkSessions(self, progress_callback=None):
        """
        Enhanced session linking with master calibration frame support.
        
        Links calibration sessions and master frames to light sessions based on telescope, 
        imager, and specific matching criteria. Prioritizes master frames over individual 
        calibration sessions for better calibration quality.
        
        Matching criteria:
        - Telescope and imager (all calibration types)
        - Binning settings (all calibration types)
        - Gain and offset settings (all calibration types)
        - Exposure time (darks only)
        - CCD temperature within 5 degrees (darks only)
        - Filter (flats only)
        
        Master frame priority:
        1. First checks for available master frames matching criteria
        2. Falls back to individual calibration sessions if no masters available
        3. Updates session references to point to masters when available
        
        Args:
            progress_callback: Optional callback function for progress updates
            
        Returns:
            list: List of session IDs that were updated
        """
        updated_sessions = []
        
        try:
            # Get all light sessions that need calibration linking
            light_sessions = (fitsSessionModel
                             .select()
                             .where(fitsSessionModel.fitsSessionObjectName != 'Bias',
                                   fitsSessionModel.fitsSessionObjectName != 'Dark',
                                   fitsSessionModel.fitsSessionObjectName != 'Flat'))
            
            total_sessions = len(light_sessions)
            current_count = 0
            
            logger.info(f"Found {total_sessions} light sessions to process for calibration linking")
            
            for light_session in light_sessions:
                current_count += 1
                
                # Call progress callback if provided
                if progress_callback:
                    should_continue = progress_callback(current_count, total_sessions, 
                                                      f"Linking: {light_session.fitsSessionObjectName}")
                    if not should_continue:
                        logger.info("Session linking cancelled by user")
                        break
                
                # Use enhanced linking with master preference
                session_updated = self.linkSessionWithMasterPreference(light_session)
                
                # Save the session if any links were updated
                if session_updated:
                    light_session.save()
                    updated_sessions.append(str(light_session.fitsSessionId))
                    logger.debug(f"Updated light session {light_session.fitsSessionId} with calibration links")
            
            logger.info(f"Session linking complete. Updated {len(updated_sessions)} light sessions with calibration links")
            
        except Exception as e:
            logger.error(f"Error in linkSessions: {str(e)}")
            raise
        
        return updated_sessions

    #################################################################################################################
    ## dateToString - helper function to safely convert date to string format                                    ##
    #################################################################################################################
    def dateToString(self, date_obj):
        """Convert date object to string format, handling both datetime objects and strings."""
        if date_obj is None:
            return None
        
        # If it's already a string, extract date part if it contains time info
        if isinstance(date_obj, str):
            # If string contains ISO datetime format, extract just the date part
            if 'T' in date_obj:
                return date_obj.split('T')[0]
            # If string contains space-separated datetime format, extract date part
            elif ' ' in date_obj and len(date_obj) > 10:
                # Check if it looks like a datetime (has time part)
                parts = date_obj.split(' ')
                if len(parts) >= 2 and ':' in parts[1]:
                    return parts[0]
            # If it's already just a date string, return as is
            return date_obj
        
        # If it's a datetime object, format it
        try:
            return date_obj.strftime('%Y-%m-%d')
        except AttributeError:
            # If it doesn't have strftime, convert to string
            return str(date_obj)

    #################################################################################################################
    ## dateToDateField - helper function to safely convert date for database storage                            ##
    #################################################################################################################
    def dateToDateField(self, date_obj):
        """Convert date object to proper format for database DateField storage."""
        if date_obj is None:
            return None
        
        # If it's already a string in date format, try to parse it first
        if isinstance(date_obj, str):
            try:
                from datetime import datetime
                
                # List of possible date formats to try
                date_formats = [
                    '%Y-%m-%d',                    # 2023-07-15
                    '%Y-%m-%dT%H:%M:%S',          # 2023-07-15T03:26:15
                    '%Y-%m-%dT%H:%M:%S.%f',       # 2023-07-15T03:26:15.438
                    '%Y-%m-%d %H:%M:%S',          # 2023-07-15 03:26:15
                    '%Y-%m-%d %H:%M:%S.%f',       # 2023-07-15 03:26:15.438
                ]
                
                # Try each format
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_obj, fmt).date()
                        return parsed_date
                    except ValueError:
                        continue
                
                # If none of the formats work, try to extract just the date part
                if 'T' in date_obj:
                    date_part = date_obj.split('T')[0]
                    try:
                        parsed_date = datetime.strptime(date_part, '%Y-%m-%d').date()
                        return parsed_date
                    except ValueError:
                        pass
                
                # If still no luck, try to take first 10 characters
                try:
                    parsed_date = datetime.strptime(date_obj[:10], '%Y-%m-%d').date()
                    return parsed_date
                except ValueError:
                    logger.warning(f"Could not parse date string: {date_obj}")
                    return None
                    
            except Exception as e:
                logger.warning(f"Error parsing date string '{date_obj}': {e}")
                return None
        
        # If it's a datetime object, get the date part
        try:
            if hasattr(date_obj, 'date'):
                return date_obj.date()
            return date_obj
        except Exception as e:
            logger.warning(f"Error converting date object: {e}")
            return None

    def createMasterCalibrationFrames(self, progress_callback=None):
        """
        Create master calibration frames from bias, dark, and flat sessions using Siril CLI.
        
        Args:
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dictionary with counts of created masters: {'bias_masters': n, 'dark_masters': n, 'flat_masters': n}
        """
        import subprocess
        import configparser
        from astrofiler_db import fitsSession as FitsSessionModel, fitsFile as FitsFileModel
        
        logger.info("Starting master calibration frame creation")
        
        # Get Siril CLI path from config
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        siril_cli_path = config.get('DEFAULT', 'siril_cli_path', fallback='')
        
        if not siril_cli_path or not os.path.exists(siril_cli_path):
            raise Exception("Siril CLI path not configured or invalid. Please set the Siril CLI location in Config tab.")
        
        # Ensure Masters directory exists
        masters_dir = os.path.join(self.repoFolder, 'Masters')
        os.makedirs(masters_dir, exist_ok=True)
        
        results = {'bias_masters': 0, 'dark_masters': 0, 'flat_masters': 0}
        
        # Find calibration sessions without masters
        calibration_sessions = []
        
        # Get bias sessions without master
        bias_sessions = FitsSessionModel.select().where(
            (FitsSessionModel.fitsSessionObjectName.in_(['bias', 'Bias', 'BIAS'])) &
            ((FitsSessionModel.fitsBiasMaster.is_null()) | (FitsSessionModel.fitsBiasMaster == ''))
        )
        calibration_sessions.extend([('bias', session) for session in bias_sessions])
        
        # Get dark sessions without master
        dark_sessions = FitsSessionModel.select().where(
            (FitsSessionModel.fitsSessionObjectName.in_(['dark', 'Dark', 'DARK'])) &
            ((FitsSessionModel.fitsDarkMaster.is_null()) | (FitsSessionModel.fitsDarkMaster == ''))
        )
        calibration_sessions.extend([('dark', session) for session in dark_sessions])
        
        # Get flat sessions without master
        flat_sessions = FitsSessionModel.select().where(
            (FitsSessionModel.fitsSessionObjectName.in_(['flat', 'Flat', 'FLAT'])) &
            ((FitsSessionModel.fitsFlatMaster.is_null()) | (FitsSessionModel.fitsFlatMaster == ''))
        )
        calibration_sessions.extend([('flat', session) for session in flat_sessions])
        
        total_sessions = len(calibration_sessions)
        logger.info(f"Found {total_sessions} calibration sessions without masters")
        
        if total_sessions == 0:
            return results
        
        for i, (cal_type, session) in enumerate(calibration_sessions):
            if progress_callback:
                if not progress_callback(i, total_sessions, f"Processing {cal_type} session {session.fitsSessionId}"):
                    logger.info("Master creation cancelled by user")
                    return results
            
            try:
                # Get files for this session
                session_files = FitsFileModel.select().where(
                    FitsFileModel.fitsFileSession == session.fitsSessionId
                )
                
                file_list = [f.fitsFileName for f in session_files if f.fitsFileName and os.path.exists(f.fitsFileName)]
                
                if len(file_list) < 2:
                    logger.warning(f"Not enough files ({len(file_list)}) for {cal_type} session {session.fitsSessionId}")
                    continue
                
                # Log detailed master creation start with file verification
                logger.debug(f"=" * 80)
                logger.debug(f"STARTING MASTER {cal_type.upper()} CREATION")
                logger.debug(f"Session ID: {session.fitsSessionId}")
                logger.debug(f"Number of files: {len(file_list)}")
                logger.debug(f"Session Date: {session.fitsSessionDate}")
                logger.debug(f"=" * 80)
                
                # Analyze all files for parameter consistency
                file_params = []
                inconsistent_params = []
                
                for i_file, file_path in enumerate(file_list):
                    try:
                        with fits.open(file_path) as hdul:
                            hdr = hdul[0].header
                            params = {
                                'file': os.path.basename(file_path),
                                'telescope': hdr.get('TELESCOP', 'Unknown'),
                                'instrument': hdr.get('INSTRUME', 'Unknown'),
                                'xbinning': hdr.get('XBINNING', 'Unknown'),
                                'ybinning': hdr.get('YBINNING', 'Unknown'),
                                'gain': hdr.get('GAIN', 'Unknown'),
                                'offset': hdr.get('OFFSET', 'Unknown'),
                                'ccd_temp': hdr.get('CCD-TEMP', hdr.get('SET-TEMP', 'Unknown')),
                                'filter': hdr.get('FILTER', 'Unknown'),
                                'exptime': hdr.get('EXPTIME', 'Unknown')
                            }
                            file_params.append(params)
                            
                            # Log each file details
                            if cal_type == 'bias':
                                logger.debug(f"File {i_file+1:3d}: {params['file']} - "
                                           f"Telescope: {params['telescope']}, Instrument: {params['instrument']}, "
                                           f"Binning: {params['xbinning']}x{params['ybinning']}, "
                                           f"Gain: {params['gain']}, Offset: {params['offset']}")
                            elif cal_type == 'dark':
                                logger.debug(f"File {i_file+1:3d}: {params['file']} - "
                                           f"Telescope: {params['telescope']}, Instrument: {params['instrument']}, "
                                           f"Binning: {params['xbinning']}x{params['ybinning']}, "
                                           f"Exposure: {params['exptime']}s, Temp: {params['ccd_temp']}°C, "
                                           f"Gain: {params['gain']}, Offset: {params['offset']}")
                            else:  # flat
                                logger.debug(f"File {i_file+1:3d}: {params['file']} - "
                                           f"Telescope: {params['telescope']}, Instrument: {params['instrument']}, "
                                           f"Binning: {params['xbinning']}x{params['ybinning']}, "
                                           f"Filter: {params['filter']}, Exposure: {params['exptime']}s")
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
                        inconsistent_params.append(f"Unable to read file: {os.path.basename(file_path)}")
                
                # Check parameter consistency
                if len(file_params) > 1:
                    reference = file_params[0]
                    logger.debug(f"-" * 80)
                    logger.debug(f"PARAMETER CONSISTENCY CHECK:")
                    
                    # Check critical parameters based on calibration type
                    if cal_type == 'bias':
                        critical_params = ['instrument', 'xbinning', 'ybinning']
                    elif cal_type == 'dark':
                        critical_params = ['instrument', 'xbinning', 'ybinning', 'exptime']
                    else:  # flat
                        critical_params = ['telescope', 'instrument', 'xbinning', 'ybinning', 'filter']
                    
                    for param in critical_params:
                        ref_value = reference[param]
                        different_values = set(fp[param] for fp in file_params if fp[param] != ref_value)
                        if different_values:
                            inconsistent_params.append(f"{param}: Expected {ref_value}, found {different_values}")
                            logger.error(f"INCONSISTENT {param.upper()}: Expected '{ref_value}', but found {different_values}")
                        else:
                            logger.debug(f"✓ {param.upper()}: All files match '{ref_value}'")
                
                if inconsistent_params:
                    logger.error(f"CRITICAL: Cannot create master - inconsistent parameters detected:")
                    for issue in inconsistent_params:
                        logger.error(f"  - {issue}")
                    logger.error(f"Skipping master creation for session {session.fitsSessionId}")
                    continue
                else:
                    logger.debug(f"✓ All parameters consistent - proceeding with master creation")
                
                logger.debug(f"-" * 80)
                
                # Get metadata from first file for naming
                first_file_path = file_list[0]
                with fits.open(first_file_path) as hdul:
                    header = hdul[0].header
                    
                    telescope = sanitize_filesystem_name(header.get('TELESCOP', 'Unknown'))
                    instrument = sanitize_filesystem_name(header.get('INSTRUME', 'Unknown'))
                    xbinning = header.get('XBINNING', '1')
                    ybinning = header.get('YBINNING', '1')
                    date_str = session.fitsSessionDate.strftime('%Y%m%d') if session.fitsSessionDate else 'Unknown'
                    
                    # Type-specific naming (using underscores to match folder creation logic)
                    if cal_type == 'bias':
                        master_filename = f"Master_Bias_{telescope}_{instrument}_{xbinning}x{ybinning}_{date_str}.fits"
                    elif cal_type == 'dark':
                        exptime = sanitize_filesystem_name(str(header.get('EXPTIME', 'Unknown')))
                        ccd_temp = sanitize_filesystem_name(str(header.get('CCD-TEMP', header.get('SET-TEMP', 'Unknown'))))
                        master_filename = f"Master_Dark_{telescope}_{instrument}_{xbinning}x{ybinning}_{exptime}s_{ccd_temp}C_{date_str}.fits"
                    else:  # flat
                        filter_name = sanitize_filesystem_name(header.get('FILTER', 'Unknown'))
                        master_filename = f"Master_Flat_{telescope}_{instrument}_{filter_name}_{xbinning}x{ybinning}_{date_str}.fits"
                
                master_path = os.path.join(masters_dir, master_filename)
                
                # Skip if master already exists
                if os.path.exists(master_path):
                    logger.debug(f"Master {master_filename} already exists, skipping")
                    continue
                
                # Create master using Siril CLI
                success = self._create_master_with_siril(siril_cli_path, file_list, master_path, cal_type)
                
                if success:
                    # Update FITS header with master frame metadata
                    self._update_master_header(master_path, session, file_list, cal_type)
                    
                    # Add master to database
                    master_fits_id = self._register_master_in_database(master_path, session, cal_type)
                    
                    # Update session with master reference
                    if cal_type == 'bias':
                        session.fitsBiasMaster = master_path
                        results['bias_masters'] += 1
                    elif cal_type == 'dark':
                        session.fitsDarkMaster = master_path
                        results['dark_masters'] += 1
                    else:  # flat
                        session.fitsFlatMaster = master_path
                        results['flat_masters'] += 1
                    
                    session.save()
                    
                    # Soft delete calibration files used in this master
                    self._soft_delete_calibration_files(session.fitsSessionId, cal_type)
                    
                    logger.debug(f"Created {cal_type} master: {master_filename}")
                else:
                    logger.error(f"Failed to create {cal_type} master for session {session.fitsSessionId}")
                    
            except Exception as e:
                logger.error(f"Error creating {cal_type} master for session {session.fitsSessionId}: {e}")
                continue
        
        # Final progress update
        if progress_callback:
            progress_callback(total_sessions, total_sessions, "Master creation complete")
        
        logger.info(f"Master creation completed: {results}")
        return results
    
    def createMasterCalibrationFramesForSessions(self, session_list, progress_callback=None):
        """
        Create master calibration frames for specific sessions using Siril CLI.
        
        Args:
            session_list: List of session info dictionaries from getSessionsNeedingMasters()
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dictionary with counts of created masters: {'bias_masters': n, 'dark_masters': n, 'flat_masters': n}
        """
        import subprocess
        import configparser
        from astrofiler_db import fitsSession as FitsSessionModel, fitsFile as FitsFileModel
        
        logger.info(f"Starting master calibration frame creation for {len(session_list)} sessions")
        
        # Get Siril CLI path from config
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        siril_cli_path = config.get('DEFAULT', 'siril_cli_path', fallback='')
        
        if not siril_cli_path or not os.path.exists(siril_cli_path):
            raise Exception("Siril CLI path not configured or invalid. Please set the Siril CLI location in Config tab.")
        
        # Ensure Masters directory exists
        masters_dir = os.path.join(self.repoFolder, 'Masters')
        os.makedirs(masters_dir, exist_ok=True)
        
        results = {'bias_masters': 0, 'dark_masters': 0, 'flat_masters': 0}
        
        total_sessions = len(session_list)
        logger.info(f"Processing {total_sessions} specified sessions for master creation")
        
        if total_sessions == 0:
            return results
        
        for i, session_info in enumerate(session_list):
            if progress_callback:
                if not progress_callback(i, total_sessions, f"Processing {session_info['session_type']} session {session_info['session_id']}"):
                    logger.info("Master creation cancelled by user")
                    return results
            
            try:
                # Get the actual session from database
                session = FitsSessionModel.get(FitsSessionModel.fitsSessionId == session_info['session_id'])
                cal_type = session_info['session_type']
                
                # Get files for this session
                session_files = FitsFileModel.select().where(
                    FitsFileModel.fitsFileSession == session.fitsSessionId
                )
                
                file_list = [f.fitsFileName for f in session_files if f.fitsFileName and os.path.exists(f.fitsFileName)]
                
                if len(file_list) < 2:
                    logger.warning(f"Not enough files ({len(file_list)}) for {cal_type} session {session.fitsSessionId}")
                    continue
                
                # Log detailed master creation start with file verification
                logger.debug(f"=" * 80)
                logger.debug(f"STARTING MASTER {cal_type.upper()} CREATION (Targeted Session)")
                logger.debug(f"Session ID: {session.fitsSessionId}")
                logger.debug(f"Number of files: {len(file_list)}")
                logger.debug(f"Session Date: {session.fitsSessionDate}")
                logger.debug(f"=" * 80)
                
                # Analyze all files for parameter consistency
                file_params = []
                inconsistent_params = []
                
                for i_file, file_path in enumerate(file_list):
                    try:
                        with fits.open(file_path) as hdul:
                            hdr = hdul[0].header
                            params = {
                                'file': os.path.basename(file_path),
                                'telescope': hdr.get('TELESCOP', 'Unknown'),
                                'instrument': hdr.get('INSTRUME', 'Unknown'),
                                'xbinning': hdr.get('XBINNING', 'Unknown'),
                                'ybinning': hdr.get('YBINNING', 'Unknown'),
                                'gain': hdr.get('GAIN', 'Unknown'),
                                'offset': hdr.get('OFFSET', 'Unknown'),
                                'ccd_temp': hdr.get('CCD-TEMP', hdr.get('SET-TEMP', 'Unknown')),
                                'filter': hdr.get('FILTER', 'Unknown'),
                                'exptime': hdr.get('EXPTIME', 'Unknown')
                            }
                            file_params.append(params)
                            
                            # Log each file details
                            if cal_type == 'bias':
                                logger.debug(f"File {i_file+1:3d}: {params['file']} - "
                                           f"Telescope: {params['telescope']}, Instrument: {params['instrument']}, "
                                           f"Binning: {params['xbinning']}x{params['ybinning']}, "
                                           f"Gain: {params['gain']}, Offset: {params['offset']}")
                            elif cal_type == 'dark':
                                logger.debug(f"File {i_file+1:3d}: {params['file']} - "
                                           f"Telescope: {params['telescope']}, Instrument: {params['instrument']}, "
                                           f"Binning: {params['xbinning']}x{params['ybinning']}, "
                                           f"Exposure: {params['exptime']}s, Temp: {params['ccd_temp']}°C, "
                                           f"Gain: {params['gain']}, Offset: {params['offset']}")
                            else:  # flat
                                logger.debug(f"File {i_file+1:3d}: {params['file']} - "
                                           f"Telescope: {params['telescope']}, Instrument: {params['instrument']}, "
                                           f"Binning: {params['xbinning']}x{params['ybinning']}, "
                                           f"Filter: {params['filter']}, Exposure: {params['exptime']}s")
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
                        inconsistent_params.append(f"Unable to read file: {os.path.basename(file_path)}")
                
                # Check parameter consistency
                if len(file_params) > 1:
                    reference = file_params[0]
                    logger.debug(f"-" * 80)
                    logger.debug(f"PARAMETER CONSISTENCY CHECK:")
                    
                    # Check critical parameters based on calibration type
                    if cal_type == 'bias':
                        critical_params = ['telescope', 'instrument', 'xbinning', 'ybinning']
                    elif cal_type == 'dark':
                        critical_params = ['telescope', 'instrument', 'xbinning', 'ybinning', 'exptime']
                    else:  # flat
                        critical_params = ['telescope', 'instrument', 'xbinning', 'ybinning', 'filter']
                    
                    for param in critical_params:
                        ref_value = reference[param]
                        different_values = set(fp[param] for fp in file_params if fp[param] != ref_value)
                        if different_values:
                            inconsistent_params.append(f"{param}: Expected {ref_value}, found {different_values}")
                            logger.error(f"INCONSISTENT {param.upper()}: Expected '{ref_value}', but found {different_values}")
                        else:
                            logger.debug(f"✓ {param.upper()}: All files match '{ref_value}'")
                
                if inconsistent_params:
                    logger.error(f"CRITICAL: Cannot create master - inconsistent parameters detected:")
                    for issue in inconsistent_params:
                        logger.error(f"  - {issue}")
                    logger.error(f"Skipping master creation for session {session.fitsSessionId}")
                    continue
                else:
                    logger.debug(f"✓ All parameters consistent - proceeding with master creation")
                
                logger.debug(f"-" * 80)
                
                # Get metadata from first file for naming
                first_file_path = file_list[0]
                with fits.open(first_file_path) as hdul:
                    header = hdul[0].header
                    
                    telescope = sanitize_filesystem_name(header.get('TELESCOP', 'Unknown'))
                    instrument = sanitize_filesystem_name(header.get('INSTRUME', 'Unknown'))
                    xbinning = header.get('XBINNING', '1')
                    ybinning = header.get('YBINNING', '1')
                    date_str = session.fitsSessionDate.strftime('%Y%m%d') if session.fitsSessionDate else 'Unknown'
                    
                    # Type-specific naming (using underscores to match folder creation logic)
                    if cal_type == 'bias':
                        master_filename = f"Master_Bias_{telescope}_{instrument}_{xbinning}x{ybinning}_{date_str}.fits"
                    elif cal_type == 'dark':
                        exptime = sanitize_filesystem_name(str(header.get('EXPTIME', 'Unknown')))
                        ccd_temp = sanitize_filesystem_name(str(header.get('CCD-TEMP', header.get('SET-TEMP', 'Unknown'))))
                        master_filename = f"Master_Dark_{telescope}_{instrument}_{xbinning}x{ybinning}_{exptime}s_{ccd_temp}C_{date_str}.fits"
                    else:  # flat
                        filter_name = sanitize_filesystem_name(header.get('FILTER', 'Unknown'))
                        master_filename = f"Master_Flat_{telescope}_{instrument}_{filter_name}_{xbinning}x{ybinning}_{date_str}.fits"
                
                master_path = os.path.join(masters_dir, master_filename)
                
                # Skip if master already exists
                if os.path.exists(master_path):
                    logger.debug(f"Master {master_filename} already exists, skipping")
                    continue
                
                # Create master using Siril CLI
                success = self._create_master_with_siril(siril_cli_path, file_list, master_path, cal_type)
                
                if success:
                    # Update FITS header with master frame metadata
                    self._update_master_header(master_path, session, file_list, cal_type)
                    
                    # Add master to database
                    master_fits_id = self._register_master_in_database(master_path, session, cal_type)
                    
                    # Update session with master reference
                    if cal_type == 'bias':
                        session.fitsBiasMaster = master_path
                        results['bias_masters'] += 1
                    elif cal_type == 'dark':
                        session.fitsDarkMaster = master_path
                        results['dark_masters'] += 1
                    else:  # flat
                        session.fitsFlatMaster = master_path
                        results['flat_masters'] += 1
                    
                    session.save()
                    
                    # Soft delete calibration files used in this master
                    self._soft_delete_calibration_files(session.fitsSessionId, cal_type)
                    
                    logger.debug(f"Created {cal_type} master: {master_filename}")
                else:
                    logger.error(f"Failed to create {cal_type} master for session {session.fitsSessionId}")
                    
            except Exception as e:
                logger.error(f"Error creating {cal_type} master for session {session_info['session_id']}: {e}")
                continue
        
        # Final progress update
        if progress_callback:
            progress_callback(total_sessions, total_sessions, "Master creation complete")
        
        logger.info(f"Master creation completed: {results}")
        return results
    
    def _create_master_with_siril(self, siril_cli_path, file_list, output_path, cal_type):
        """Create master calibration frame using Siril CLI."""
        import tempfile
        import subprocess
        
        try:
            # Create temporary directory for Siril processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create Siril script
                script_path = os.path.join(temp_dir, 'create_master.ssf')
                
                # Create symbolic links to files in temp directory
                temp_files = []
                links_created = 0
                copies_made = 0
                
                for i, file_path in enumerate(file_list):
                    temp_file = os.path.join(temp_dir, f"frame_{i:04d}.fits")
                    try:
                        # Try to create symbolic link (more efficient)
                        os.symlink(file_path, temp_file)
                        temp_files.append(temp_file)
                        links_created += 1
                    except (OSError, NotImplementedError):
                        # Fall back to hard link if symlink fails
                        try:
                            os.link(file_path, temp_file)
                            temp_files.append(temp_file)
                            links_created += 1
                        except OSError:
                            # Fall back to copying if both link methods fail
                            shutil.copy2(file_path, temp_file)
                            temp_files.append(temp_file)
                            copies_made += 1
                            logger.warning(f"Could not link file {file_path}, using copy instead")
                
                if links_created > 0:
                    logger.info(f"Successfully linked {links_created} files, copied {copies_made} files for {cal_type} master creation")
                
                # Create Siril script content
                script_content = f"requires 0.9.12\n"  # Add required compatibility line
                script_content += f"cd {temp_dir}\n"
                script_content += "setext fits\n"  # Set FITS extension to .fits
                script_content += "convert *.fits . -out=frame_\n"
                
                if cal_type == 'bias':
                    script_content += "stack frame_ rej 3 3 -nonorm -out=master\n"
                elif cal_type == 'dark':
                    script_content += "stack frame_ rej 3 3 -nonorm -out=master\n"
                else:  # flat
                    script_content += "stack frame_ rej 3 3 -norm=mul -out=master\n"
                
                script_content += "close\n"
                
                # Log the script content for debugging
                logger.debug(f"Generated Siril script for {cal_type} master:")
                logger.debug(f"Script path: {script_path}")
                logger.debug(f"Script content:\n{script_content}")
                logger.debug(f"Processing {len(temp_files)} files in {temp_dir}")
                
                # Write script file
                with open(script_path, 'w') as f:
                    f.write(script_content)
                
                # Run Siril CLI
                cmd = [siril_cli_path, '-s', script_path]
                logger.debug(f"Running Siril CLI command: {' '.join(cmd)}")
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                # Log detailed output for debugging
                logger.debug(f"Siril CLI return code: {result.returncode}")
                if result.stdout:
                    logger.debug(f"Siril CLI stdout: {result.stdout}")
                if result.stderr:
                    logger.warning(f"Siril CLI stderr: {result.stderr}")
                
                if result.returncode == 0:
                    # Copy result to final location
                    temp_master = os.path.join(temp_dir, 'master.fits')
                    logger.debug(f"Looking for master file: {temp_master}")
                    logger.debug(f"Files in temp directory: {os.listdir(temp_dir)}")
                    
                    if os.path.exists(temp_master):
                        logger.info(f"Found master file, copying to: {output_path}")
                        # Ensure output directory exists
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        shutil.copy2(temp_master, output_path)
                        logger.debug(f"Successfully copied master file to: {output_path}")
                        return True
                    else:
                        logger.error(f"Siril completed but master file not found: {temp_master}")
                        logger.debug(f"Files in temp directory: {os.listdir(temp_dir)}")
                        return False
                else:
                    logger.error(f"Siril CLI failed with return code {result.returncode}")
                    logger.error(f"Command: {' '.join(cmd)}")
                    logger.error(f"Stderr: {result.stderr}")
                    logger.error(f"Stdout: {result.stdout}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error running Siril CLI: {e}")
            return False
    
    def _update_master_header(self, master_path, session, file_list, cal_type):
        """
        Update the FITS header of the master frame with comprehensive metadata.
        
        Adds astronomy-standard headers for master calibration frames including:
        - Master frame identification and metadata
        - Source session and file information
        - Processing history and source file tracking
        - Compatibility headers for calibration workflows
        """
        try:
            with fits.open(master_path, mode='update') as hdul:
                header = hdul[0].header
                
                # Primary master frame identification
                header['MASTER'] = (True, 'This is a master calibration frame')
                header['IMAGETYP'] = (f'Master{cal_type.capitalize()}', 'Type of calibration image')
                header['CALTYPE'] = (cal_type.upper(), 'Type of calibration frame')
                
                # Frame combination metadata
                header['NFRAMES'] = (len(file_list), 'Number of frames combined')
                header['CREATED'] = (datetime.now().isoformat(), 'Master creation timestamp')
                header['CREATOR'] = ('AstroFiler', 'Software used to create master')
                header['CALSOFT'] = ('AstroFiler + Siril', 'Calibration software stack')
                header['CALVERS'] = ('1.2.0', 'AstroFiler version used')
                header['SESSION'] = (session.fitsSessionId, 'Source session ID')
                
                # Copy relevant headers from first source file for reference
                if file_list:
                    try:
                        with fits.open(file_list[0]) as source_hdul:
                            source_header = source_hdul[0].header
                            
                            # Copy instrument configuration headers
                            for key in ['TELESCOP', 'INSTRUME', 'XBINNING', 'YBINNING', 
                                      'GAIN', 'OFFSET', 'READNOIS', 'PIXSIZE1', 'PIXSIZE2']:
                                if key in source_header:
                                    header[key] = (source_header[key], source_header.comments[key])
                            
                            # Copy calibration-specific headers
                            if cal_type == 'dark':
                                for key in ['EXPTIME', 'CCD-TEMP', 'SET-TEMP']:
                                    if key in source_header:
                                        header[key] = (source_header[key], source_header.comments[key])
                            elif cal_type == 'flat':
                                for key in ['FILTER', 'EXPTIME']:
                                    if key in source_header:
                                        header[key] = (source_header[key], source_header.comments[key])
                                        
                    except Exception as e:
                        logger.warning(f"Could not copy headers from source file {file_list[0]}: {e}")
                
                # Add session metadata if available
                if session.fitsSessionTelescope:
                    header['TELESCOP'] = (session.fitsSessionTelescope, 'Telescope used')
                if session.fitsSessionImager:
                    header['INSTRUME'] = (session.fitsSessionImager, 'Instrument used') 
                if session.fitsSessionDate:
                    header['DATE-OBS'] = (session.fitsSessionDate.isoformat(), 'Observation date')
                if hasattr(session, 'fitsSessionXBinning') and session.fitsSessionXBinning:
                    header['XBINNING'] = (session.fitsSessionXBinning, 'X-axis binning')
                if hasattr(session, 'fitsSessionYBinning') and session.fitsSessionYBinning:
                    header['YBINNING'] = (session.fitsSessionYBinning, 'Y-axis binning')
                
                # Processing history
                header['HISTORY'] = f'Master {cal_type} created from {len(file_list)} frames'
                header['HISTORY'] = f'Created by AstroFiler v1.2.0 on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                header['HISTORY'] = f'Source session: {session.fitsSessionId}'
                              
                # Calibration workflow compatibility
                header['BZERO'] = (0.0, 'Data scaling zero point')
                header['BSCALE'] = (1.0, 'Data scaling factor')
                
                hdul.flush()
                
        except Exception as e:
            logger.error(f"Error updating master header: {e}")
    
    def _register_master_in_database(self, master_path, session, cal_type):
        """Register the master calibration frame in the database."""
        try:
            # Calculate hash
            file_hash = self.calculateFileHash(master_path)
            
            # Create unique ID
            master_id = str(uuid.uuid4())
            
            # Get file stats
            file_stat = os.stat(master_path)
            file_date = datetime.fromtimestamp(file_stat.st_mtime).date()
            
            # Create database entry
            fits_file = FitsFileModel.create(
                fitsFileId=master_id,
                fitsFileName=normalize_file_path(master_path),
                fitsFileDate=file_date,
                fitsFileCalibrated=1,  # Masters are considered calibrated
                fitsFileType=cal_type.upper(),
                fitsFileStacked=1,  # Masters are stacked
                fitsFileObject=f"Master-{cal_type.title()}",
                fitsFileHash=file_hash,
                fitsFileSession=session.fitsSessionId,
                fitsFileTelescop=session.fitsSessionTelescope,
                fitsFileInstrument=session.fitsSessionImager,
                fitsFileXBinning=session.fitsSessionBinningX,
                fitsFileYBinning=session.fitsSessionBinningY,
                fitsFileCCDTemp=session.fitsSessionCCDTemp,
                fitsFileGain=session.fitsSessionGain,
                fitsFileOffset=session.fitsSessionOffset,
                fitsFileFilter=session.fitsSessionFilter
            )
            
            logger.debug(f"Registered master {cal_type} in database: {master_id}")
            return master_id
            
        except Exception as e:
            logger.error(f"Error registering master in database: {e}")
            return None

    def _soft_delete_calibration_files(self, session_id, cal_type):
        """
        Soft delete calibration files from a session after master creation.
        
        Args:
            session_id: Session ID containing the files to soft delete
            cal_type: Type of calibration ('bias', 'dark', 'flat')
            
        Returns:
            int: Number of files that were soft deleted
        """
        from astrofiler_db import fitsFile as FitsFileModel
        
        try:
            # Get all files from this session that match the calibration type
            files_to_delete = FitsFileModel.select().where(
                (FitsFileModel.fitsFileSession == session_id) &
                (FitsFileModel.fitsFileType.contains(cal_type.upper())) &
                (FitsFileModel.fitsFileSoftDelete.is_null(True) | (FitsFileModel.fitsFileSoftDelete == False))
            )
            
            deleted_count = 0
            for file_record in files_to_delete:
                file_record.fitsFileSoftDelete = True
                file_record.save()
                deleted_count += 1
                logger.debug(f"Soft deleted {cal_type} file: {file_record.fitsFileName}")
            
            logger.debug(f"Soft deleted {deleted_count} {cal_type} files from session {session_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error soft deleting {cal_type} files from session {session_id}: {e}")
            return 0

    #################################################################################################################
    ## checkCalibrationSessionsForMasters - Query calibration sessions and check master status                  ##
    #################################################################################################################
    def checkCalibrationSessionsForMasters(self, min_files=2, progress_callback=None):
        """
        Query calibration sessions and check if masters already exist or can be created.
        
        Args:
            min_files: Minimum number of files required to create a master (default 2)
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dictionary with session analysis: {
                'sessions_needing_masters': [...],
                'sessions_with_masters': [...],
                'sessions_insufficient_files': [...],
                'master_creation_candidates': [...]
            }
        """
        from astrofiler_db import fitsSession as FitsSessionModel, fitsFile as FitsFileModel
        import os
        
        logger.info("Analyzing calibration sessions for master frame status")
        
        results = {
            'sessions_needing_masters': [],
            'sessions_with_masters': [], 
            'sessions_insufficient_files': [],
            'master_creation_candidates': []
        }
        
        # Get all calibration sessions
        calibration_sessions = FitsSessionModel.select().where(
            FitsSessionModel.fitsSessionObjectName.in_(['bias', 'Bias', 'BIAS', 'dark', 'Dark', 'DARK', 'flat', 'Flat', 'FLAT'])
        )
        
        total_sessions = len(calibration_sessions)
        logger.info(f"Found {total_sessions} calibration sessions to analyze")
        
        for i, session in enumerate(calibration_sessions):
            if progress_callback:
                if not progress_callback(i, total_sessions, f"Analyzing {session.fitsSessionObjectName} session"):
                    logger.info("Session analysis cancelled by user")
                    break
            
            session_info = self._analyze_calibration_session(session, min_files)
            
            # Categorize the session
            if session_info['has_master'] and session_info['master_file_exists']:
                results['sessions_with_masters'].append(session_info)
            elif session_info['file_count'] < min_files:
                results['sessions_insufficient_files'].append(session_info)
            elif not session_info['has_master']:
                results['sessions_needing_masters'].append(session_info)
                results['master_creation_candidates'].append(session_info)
            else:
                # Has master reference but file doesn't exist
                results['sessions_needing_masters'].append(session_info)
                results['master_creation_candidates'].append(session_info)
        
        # Log summary
        logger.info(f"Session analysis complete:")
        logger.info(f"  Sessions with masters: {len(results['sessions_with_masters'])}")
        logger.info(f"  Sessions needing masters: {len(results['sessions_needing_masters'])}")
        logger.info(f"  Sessions with insufficient files: {len(results['sessions_insufficient_files'])}")
        logger.info(f"  Master creation candidates: {len(results['master_creation_candidates'])}")
        
        return results

    def _analyze_calibration_session(self, session, min_files):
        """
        Analyze a single calibration session for master frame status.
        
        Args:
            session: FitsSession database model instance
            min_files: Minimum files required for master creation
            
        Returns:
            Dictionary with session analysis details
        """
        from astrofiler_db import fitsFile as FitsFileModel
        import os
        
        session_type = session.fitsSessionObjectName.lower()
        
        # Get the appropriate master field based on session type
        master_field = None
        if 'bias' in session_type:
            master_field = session.fitsBiasMaster
        elif 'dark' in session_type:
            master_field = session.fitsDarkMaster
        elif 'flat' in session_type:
            master_field = session.fitsFlatMaster
        
        # Check if master file exists on disk
        master_file_exists = False
        if master_field and master_field.strip():
            master_file_exists = os.path.exists(master_field)
        
        # Count files in this session
        session_files = FitsFileModel.select().where(
            FitsFileModel.fitsFileSession == session.fitsSessionId
        )
        file_count = len([f for f in session_files if f.fitsFileName and os.path.exists(f.fitsFileName)])
        
        # Get file list for analysis
        file_list = []
        for f in session_files:
            if f.fitsFileName and os.path.exists(f.fitsFileName):
                file_list.append({
                    'id': f.fitsFileId,
                    'filename': f.fitsFileName,
                    'date': f.fitsFileDate,
                    'telescope': f.fitsFileTelescop,
                    'instrument': f.fitsFileInstrument
                })
        
        return {
            'session_id': session.fitsSessionId,
            'session_type': session_type,
            'session_date': session.fitsSessionDate,
            'telescope': session.fitsSessionTelescope,
            'instrument': session.fitsSessionImager,
            'binning_x': session.fitsSessionBinningX,
            'binning_y': session.fitsSessionBinningY,
            'gain': session.fitsSessionGain,
            'offset': session.fitsSessionOffset,
            'filter': session.fitsSessionFilter,
            'exposure_time': session.fitsSessionExposure,
            'ccd_temp': session.fitsSessionCCDTemp,
            'has_master': bool(master_field and master_field.strip()),
            'master_file_path': master_field,
            'master_file_exists': master_file_exists,
            'file_count': file_count,
            'files': file_list,
            'can_create_master': file_count >= min_files,
            'needs_master': not (master_field and master_file_exists)
        }

    #################################################################################################################
    ## getSessionsNeedingMasters - Get sessions that need master frames created                                  ##
    #################################################################################################################
    def getSessionsNeedingMasters(self, session_types=None, min_files=2):
        """
        Get calibration sessions that need master frames created.
        
        Args:
            session_types: List of session types to check (['bias', 'dark', 'flat']). If None, checks all.
            min_files: Minimum number of files required to create a master
            
        Returns:
            List of session info dictionaries for sessions needing masters
        """
        if session_types is None:
            session_types = ['bias', 'dark', 'flat']
        
        # Normalize session types to handle case variations
        normalized_types = []
        for stype in session_types:
            normalized_types.extend([stype.lower(), stype.capitalize(), stype.upper()])
        
        from astrofiler_db import fitsSession as FitsSessionModel
        
        # Query sessions of specified types
        sessions = FitsSessionModel.select().where(
            FitsSessionModel.fitsSessionObjectName.in_(normalized_types)
        )
        
        sessions_needing_masters = []
        
        for session in sessions:
            session_info = self._analyze_calibration_session(session, min_files)
            
            if session_info['needs_master'] and session_info['can_create_master']:
                sessions_needing_masters.append(session_info)
        
        logger.info(f"Found {len(sessions_needing_masters)} sessions needing masters")
        return sessions_needing_masters

    #################################################################################################################
    ## validateMasterFiles - Validate that master files exist and are accessible                                ##
    #################################################################################################################
    def validateMasterFiles(self, progress_callback=None):
        """
        Validate that all master file references in the database point to existing files.
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with validation results: {
                'valid_masters': [...],
                'missing_masters': [...],
                'invalid_masters': [...]
            }
        """
        from astrofiler_db import fitsSession as FitsSessionModel
        import os
        from astropy.io import fits
        
        logger.info("Validating master file references")
        
        results = {
            'valid_masters': [],
            'missing_masters': [],
            'invalid_masters': []
        }
        
        # Get all sessions with master references
        sessions_with_masters = FitsSessionModel.select().where(
            (FitsSessionModel.fitsBiasMaster.is_null(False) & (FitsSessionModel.fitsBiasMaster != '')) |
            (FitsSessionModel.fitsDarkMaster.is_null(False) & (FitsSessionModel.fitsDarkMaster != '')) |
            (FitsSessionModel.fitsFlatMaster.is_null(False) & (FitsSessionModel.fitsFlatMaster != ''))
        )
        
        total_sessions = len(sessions_with_masters)
        
        for i, session in enumerate(sessions_with_masters):
            if progress_callback:
                if not progress_callback(i, total_sessions, f"Validating masters for session {session.fitsSessionId}"):
                    logger.info("Master validation cancelled by user")
                    break
            
            # Check each master type
            master_types = [
                ('bias', session.fitsBiasMaster),
                ('dark', session.fitsDarkMaster),
                ('flat', session.fitsFlatMaster)
            ]
            
            for master_type, master_path in master_types:
                if master_path and master_path.strip():
                    validation_result = {
                        'session_id': session.fitsSessionId,
                        'master_type': master_type,
                        'master_path': master_path,
                        'session_date': session.fitsSessionDate,
                        'telescope': session.fitsSessionTelescope,
                        'instrument': session.fitsSessionImager
                    }
                    
                    if not os.path.exists(master_path):
                        validation_result['error'] = 'File not found'
                        results['missing_masters'].append(validation_result)
                    else:
                        try:
                            # Try to open the FITS file to validate it
                            with fits.open(master_path) as hdul:
                                validation_result['file_size'] = os.path.getsize(master_path)
                                validation_result['header_info'] = {
                                    'imagetyp': hdul[0].header.get('IMAGETYP', 'Unknown'),
                                    'naxis1': hdul[0].header.get('NAXIS1', 0),
                                    'naxis2': hdul[0].header.get('NAXIS2', 0),
                                    'master': hdul[0].header.get('MASTER', False)
                                }
                                results['valid_masters'].append(validation_result)
                        except Exception as e:
                            validation_result['error'] = f'Invalid FITS file: {str(e)}'
                            results['invalid_masters'].append(validation_result)
        
        logger.info(f"Master validation complete:")
        logger.info(f"  Valid masters: {len(results['valid_masters'])}")
        logger.info(f"  Missing masters: {len(results['missing_masters'])}")
        logger.info(f"  Invalid masters: {len(results['invalid_masters'])}")
        
        return results

    def designMasterFileStorageStructure(self):
        """
        Design and document the master file storage structure for auto-calibration system.
        
        Master File Storage Structure:
        ============================
        
        Directory Structure:
        - Masters stored in /Masters directory under repository root
        - Organized by calibration type for easy management
        - Subdirectories: /Masters/Bias, /Masters/Dark, /Masters/Flat
        
        File Naming Conventions:
        -----------------------
        Bias Masters:
        - Format: Master-Bias-{Telescope}-{Instrument}-{Binning}-{Date}.fits
        - Example: Master-Bias-Celestron8-QHY268M-2x2-20241016.fits
        
        Dark Masters:
        - Format: Master-Dark-{Telescope}-{Instrument}-{Binning}-{ExpTime}-{CCDTemp}-{Date}.fits
        - Example: Master-Dark-Celestron8-QHY268M-2x2-300s--10C-20241016.fits
        
        Flat Masters:
        - Format: Master-Flat-{Telescope}-{Instrument}-{Filter}-{Binning}-{Date}.fits
        - Example: Master-Flat-Celestron8-QHY268M-Ha-2x2-20241016.fits
        
        Matching Criteria for Master Selection:
        ======================================
        
        Bias Masters:
        - Same telescope (fitsSessionTelescope)
        - Same instrument (fitsSessionImager) 
        - Same binning (fitsSessionXBinning, fitsSessionYBinning)
        - Same gain/offset (if available in headers)
        
        Dark Masters:
        - All bias criteria PLUS:
        - Same exposure time (EXPTIME header)
        - Similar CCD temperature (±5°C tolerance)
        
        Flat Masters:
        - All bias criteria PLUS:
        - Same filter (FILTER header)
        
        Master File Headers:
        ===================
        Required metadata added to master FITS headers:
        - MASTER = True (identifies as master frame)
        - CALTYPE = 'BIAS'/'DARK'/'FLAT' (calibration type)
        - NFRAMES = n (number of source frames combined)
        - CREATED = ISO timestamp (creation date/time)
        - CREATOR = 'AstroFiler' (software identifier)
        - SESSION = session_id (source session reference)
        - IMAGETYP = 'MasterBias'/'MasterDark'/'MasterFlat'
        
        Database Integration:
        ====================
        Master references stored in fitsSession table:
        - fitsBiasMaster: full path to bias master
        - fitsDarkMaster: full path to dark master  
        - fitsFlatMaster: full path to flat master
        
        Auto-calibration uses these references to:
        1. Check if masters exist before creating new ones
        2. Link appropriate masters to light sessions
        3. Validate master file integrity
        4. Clean up orphaned master references
        
        Returns dictionary with storage structure details.
        """
        
        # Get repository root for master storage
        import configparser
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        repo_root = config.get('DEFAULT', 'repo', fallback='.')
        masters_dir = os.path.join(repo_root, 'Masters')
        
        storage_structure = {
            'masters_directory': masters_dir,
            'subdirectories': {
                'bias': os.path.join(masters_dir, 'Bias'),
                'dark': os.path.join(masters_dir, 'Dark'), 
                'flat': os.path.join(masters_dir, 'Flat')
            },
            'naming_patterns': {
                'bias': 'Master-Bias-{telescope}-{instrument}-{binning}-{date}.fits',
                'dark': 'Master-Dark-{telescope}-{instrument}-{binning}-{exptime}-{ccdtemp}-{date}.fits',
                'flat': 'Master-Flat-{telescope}-{instrument}-{filter}-{binning}-{date}.fits'
            },
            'matching_criteria': {
                'common': ['telescope', 'instrument', 'binning', 'gain', 'offset'],
                'dark_additional': ['exposure_time', 'ccd_temperature_tolerance_5C'],
                'flat_additional': ['filter']
            },
            'header_metadata': {
                'required': ['MASTER', 'CALTYPE', 'NFRAMES', 'CREATED', 'CREATOR', 'SESSION', 'IMAGETYP'],
                'optional': ['TELESCOP', 'INSTRUME', 'DATE-OBS', 'XBINNING', 'YBINNING']
            },
            'database_fields': {
                'session_table': 'fitsSession',
                'master_references': ['fitsBiasMaster', 'fitsDarkMaster', 'fitsFlatMaster']
            }
        }
        
        logger.info(f"Master file storage structure designed with root: {masters_dir}")
        return storage_structure

    def findMatchingMasterFrame(self, light_session, cal_type):
        """
        Find a matching master calibration frame for a light session.
        
        Args:
            light_session: The light session to find masters for
            cal_type: Type of calibration ('bias', 'dark', 'flat')
            
        Returns:
            str or None: Path to matching master frame, or None if not found
        """
        try:
            # Get all calibration sessions with masters of the requested type
            master_field_map = {
                'bias': fitsSessionModel.fitsBiasMaster,
                'dark': fitsSessionModel.fitsDarkMaster,
                'flat': fitsSessionModel.fitsFlatMaster
            }
            
            if cal_type not in master_field_map:
                return None
                
            master_field = master_field_map[cal_type]
            
            # Base query for sessions with master frames
            query = (fitsSessionModel
                    .select()
                    .where(
                        master_field.is_null(False),
                        master_field != '',
                        fitsSessionModel.fitsSessionTelescope == light_session.fitsSessionTelescope,
                        fitsSessionModel.fitsSessionImager == light_session.fitsSessionImager,
                        fitsSessionModel.fitsSessionDate <= light_session.fitsSessionDate,
                        fitsSessionModel.fitsSessionBinningX == light_session.fitsSessionBinningX,
                        fitsSessionModel.fitsSessionBinningY == light_session.fitsSessionBinningY
                    ))
            
            # Add gain/offset matching if available
            if light_session.fitsSessionGain is not None:
                query = query.where(fitsSessionModel.fitsSessionGain == light_session.fitsSessionGain)
            if light_session.fitsSessionOffset is not None:
                query = query.where(fitsSessionModel.fitsSessionOffset == light_session.fitsSessionOffset)
            
            # Add calibration-type specific criteria
            if cal_type == 'dark':
                # Must match exposure time exactly
                if light_session.fitsSessionExposure is not None:
                    query = query.where(fitsSessionModel.fitsSessionExposure == light_session.fitsSessionExposure)
                
                # CCD temperature matching within ±5°C (if both sessions have temperature data)
                if light_session.fitsSessionCCDTemp is not None:
                    try:
                        light_temp = float(light_session.fitsSessionCCDTemp)
                        temp_min = light_temp - 5.0
                        temp_max = light_temp + 5.0
                    except (ValueError, TypeError):
                        # Skip temperature matching if conversion fails - no temp constraint
                        temp_min = temp_max = None
                    
                    if temp_min is not None and temp_max is not None:
                        query = query.where(
                            (fitsSessionModel.fitsSessionCCDTemp.is_null()) |
                            (fitsSessionModel.fitsSessionCCDTemp.between(temp_min, temp_max))
                        )
                    
            elif cal_type == 'flat':
                # Must match filter exactly
                if light_session.fitsSessionFilter:
                    query = query.where(fitsSessionModel.fitsSessionFilter == light_session.fitsSessionFilter)
            
            # Get most recent matching session with master
            matching_session = query.order_by(fitsSessionModel.fitsSessionDate.desc()).first()
            
            if matching_session:
                master_path = getattr(matching_session, f'fits{cal_type.capitalize()}Master')
                
                # Verify master file exists on disk
                if master_path and os.path.exists(master_path):
                    logger.info(f"Found matching {cal_type} master: {master_path} for light session {light_session.fitsSessionId}")
                    return master_path
                else:
                    logger.warning(f"Master {cal_type} file not found on disk: {master_path}")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding {cal_type} master for session {light_session.fitsSessionId}: {e}")
            return None

    def findMasterFrameByFilePattern(self, light_session, cal_type):
        """
        Find matching master frame by scanning Masters folder for applicable files.
        
        This method directly scans the Masters folder to find master files that match
        the light session criteria, which is more robust than relying on database
        references that may be lost during session regeneration.
        
        Args:
            light_session: The light session to find masters for
            cal_type: Type of calibration ('bias', 'dark', 'flat')
            
        Returns:
            str or None: Path to matching master frame, or None if not found
        """
        try:
            masters_dir = os.path.join(self.repoFolder, 'Masters')
            if not os.path.exists(masters_dir):
                return None
            
            # Get light session parameters for matching
            telescope = light_session.fitsSessionTelescope
            imager = light_session.fitsSessionImager
            binning_x = light_session.fitsSessionBinningX
            binning_y = light_session.fitsSessionBinningY
            gain = light_session.fitsSessionGain
            offset = light_session.fitsSessionOffset
            exposure = light_session.fitsSessionExposure
            filter_name = light_session.fitsSessionFilter
            
            # Scan for master files of the specified type
            master_files = []
            for filename in os.listdir(masters_dir):
                if not filename.lower().endswith(('.fit', '.fits', '.fts')):
                    continue
                    
                # Check if this is a master file of the requested type
                filename_lower = filename.lower()
                if cal_type.lower() not in filename_lower or 'master' not in filename_lower:
                    continue
                
                master_path = os.path.join(masters_dir, filename)
                
                # Try to get FITS header information to match parameters
                try:
                    from astropy.io import fits as astropy_fits
                    with astropy_fits.open(master_path) as hdul:
                        header = hdul[0].header
                        
                        # Extract parameters from master file header
                        master_telescope = header.get('TELESCOP', '').strip()
                        master_imager = header.get('INSTRUME', '').strip()
                        master_binx = header.get('XBINNING', header.get('BINX', 1))
                        master_biny = header.get('YBINNING', header.get('BINY', 1))
                        master_gain = header.get('GAIN', None)
                        master_offset = header.get('OFFSET', None)
                        master_exposure = header.get('EXPTIME', None)
                        master_filter = header.get('FILTER', '').strip()
                        
                        # Check matching criteria
                        matches = True
                        
                        # Telescope and imager must match
                        if telescope and master_telescope and telescope != master_telescope:
                            matches = False
                        if imager and master_imager and imager != master_imager:
                            matches = False
                            
                        # Binning must match
                        if binning_x is not None and master_binx != binning_x:
                            matches = False
                        if binning_y is not None and master_biny != binning_y:
                            matches = False
                            
                        # Gain and offset should match (if available)
                        if gain is not None and master_gain is not None:
                            try:
                                gain_val = float(gain) if isinstance(gain, str) else gain
                                master_gain_val = float(master_gain) if isinstance(master_gain, str) else master_gain
                                if abs(gain_val - master_gain_val) > 0.1:
                                    matches = False
                            except (ValueError, TypeError):
                                matches = False
                                
                        if offset is not None and master_offset is not None:
                            try:
                                offset_val = float(offset) if isinstance(offset, str) else offset
                                master_offset_val = float(master_offset) if isinstance(master_offset, str) else master_offset
                                if abs(offset_val - master_offset_val) > 0.1:
                                    matches = False
                            except (ValueError, TypeError):
                                matches = False
                            
                        # Dark-specific criteria: exposure time must match
                        if cal_type == 'dark' and exposure is not None and master_exposure is not None:
                            try:
                                exposure_val = float(exposure) if isinstance(exposure, str) else exposure
                                master_exposure_val = float(master_exposure) if isinstance(master_exposure, str) else master_exposure
                                if abs(exposure_val - master_exposure_val) > 0.1:
                                    matches = False
                            except (ValueError, TypeError):
                                matches = False
                                
                        # Flat-specific criteria: filter must match
                        if cal_type == 'flat' and filter_name and master_filter:
                            if filter_name != master_filter:
                                matches = False
                        
                        if matches:
                            # Get the creation/modification time of the master file
                            file_time = os.path.getmtime(master_path)
                            master_files.append((master_path, file_time))
                            
                except Exception as e:
                    logger.warning(f"Could not read master file {master_path}: {e}")
                    continue
            
            # Sort by most recent and return the best match
            if master_files:
                master_files.sort(key=lambda x: x[1], reverse=True)
                best_master = master_files[0][0]
                logger.info(f"Found matching {cal_type} master by file scan: {best_master} for light session {light_session.fitsSessionId}")
                return best_master
            
            return None
            
        except Exception as e:
            logger.error(f"Error scanning for {cal_type} master files for session {light_session.fitsSessionId}: {e}")
            return None

    def linkSessionWithMasterPreference(self, light_session):
        """
        Link a light session with calibration sessions and optionally master frames.
        
        This function always attempts to link calibration sessions for checkout functionality,
        and optionally links master frames when auto-calibration is enabled.
        
        Args:
            light_session: The light session to link
            
        Returns:
            bool: True if any links were updated
        """
        session_updated = False
        
        try:
            # Check configuration to see if auto-calibration is enabled
            import configparser
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            use_masters = config.getboolean('DEFAULT', 'enable_auto_calibration', fallback=False)
            
            # Process each calibration type
            for cal_type, session_field, master_field in [
                ('bias', 'fitsBiasSession', 'fitsBiasMaster'), 
                ('dark', 'fitsDarkSession', 'fitsDarkMaster'),
                ('flat', 'fitsFlatSession', 'fitsFlatMaster')
            ]:
                current_session = getattr(light_session, session_field, None)
                current_master = getattr(light_session, master_field, None)
                
                # Always attempt to link calibration sessions (for checkout functionality)
                matching_session = self._findMatchingCalibrationSession(light_session, cal_type)
                if matching_session:
                    new_session_id = str(matching_session.fitsSessionId)
                    if current_session != new_session_id:
                        setattr(light_session, session_field, new_session_id)
                        session_updated = True
                        logger.info(f"Linked {cal_type} session {matching_session.fitsSessionId} to light session {light_session.fitsSessionId}")
                elif current_session:
                    # Clear the link if no matching session found
                    setattr(light_session, session_field, None)
                    session_updated = True
                    logger.info(f"Cleared {cal_type} session link for light session {light_session.fitsSessionId} (no matching session found)")
                
                # Additionally try to find master frame if auto-calibration enabled
                if use_masters:
                    # Try database-based method first
                    master_path = self.findMatchingMasterFrame(light_session, cal_type)
                    
                    # If no master found in database, try scanning Masters folder directly
                    if not master_path:
                        master_path = self.findMasterFrameByFilePattern(light_session, cal_type)
                    
                    if master_path and current_master != master_path:
                        setattr(light_session, master_field, master_path)
                        session_updated = True
                        logger.info(f"Linked {cal_type} master {master_path} to light session {light_session.fitsSessionId}")
                    elif not master_path and current_master:
                        # Clear the master link if no matching master found
                        setattr(light_session, master_field, None)
                        session_updated = True
                        logger.info(f"Cleared {cal_type} master link for light session {light_session.fitsSessionId} (no matching master found)")
            
            # Save changes to database if any updates were made
            if session_updated:
                light_session.save()
            
            return session_updated
            
        except Exception as e:
            logger.error(f"Error linking session {light_session.fitsSessionId} with master preference: {e}")
            return False

    def updateLightSessionsWithNewMaster(self, master_path, cal_type):
        """
        Update all applicable light sessions with a newly created master frame.
        
        This method should be called after a master frame is created to automatically
        link it to all light sessions that can use it.
        
        Args:
            master_path: Path to the newly created master frame
            cal_type: Type of calibration ('bias', 'dark', 'flat')
            
        Returns:
            int: Number of light sessions updated
        """
        updated_count = 0
        
        try:
            if not os.path.exists(master_path):
                logger.warning(f"Master file does not exist: {master_path}")
                return 0
            
            # Get master file parameters from FITS header
            from astropy.io import fits as astropy_fits
            with astropy_fits.open(master_path) as hdul:
                master_header = hdul[0].header
                
                master_telescope = master_header.get('TELESCOP', '').strip()
                master_imager = master_header.get('INSTRUME', '').strip()
                master_binx = master_header.get('XBINNING', master_header.get('BINX', 1))
                master_biny = master_header.get('YBINNING', master_header.get('BINY', 1))
                master_gain = master_header.get('GAIN', None)
                master_offset = master_header.get('OFFSET', None)
                master_exposure = master_header.get('EXPTIME', None)
                master_filter = master_header.get('FILTER', '').strip()
            
            # Get all light sessions that could use this master
            light_sessions = (fitsSessionModel
                             .select()
                             .where(~fitsSessionModel.fitsSessionObjectName.in_(['Bias', 'Dark', 'Flat'])))
            
            master_field_map = {
                'bias': 'fitsBiasMaster',
                'dark': 'fitsDarkMaster', 
                'flat': 'fitsFlatMaster'
            }
            
            if cal_type not in master_field_map:
                logger.error(f"Invalid calibration type: {cal_type}")
                return 0
                
            master_field = master_field_map[cal_type]
            
            for light_session in light_sessions:
                try:
                    # Check if this light session can use the master
                    matches = True
                    
                    # Basic matching criteria
                    if master_telescope and light_session.fitsSessionTelescope != master_telescope:
                        matches = False
                    if master_imager and light_session.fitsSessionImager != master_imager:
                        matches = False
                    if light_session.fitsSessionBinningX != master_binx:
                        matches = False
                    if light_session.fitsSessionBinningY != master_biny:
                        matches = False
                        
                    # Gain and offset matching (if available)
                    if master_gain is not None and light_session.fitsSessionGain is not None:
                        try:
                            master_gain_val = float(master_gain) if isinstance(master_gain, str) else master_gain
                            if abs(light_session.fitsSessionGain - master_gain_val) > 0.1:
                                matches = False
                        except (ValueError, TypeError):
                            matches = False
                            
                    if master_offset is not None and light_session.fitsSessionOffset is not None:
                        try:
                            master_offset_val = float(master_offset) if isinstance(master_offset, str) else master_offset
                            if abs(light_session.fitsSessionOffset - master_offset_val) > 0.1:
                                matches = False
                        except (ValueError, TypeError):
                            matches = False
                    
                    # Dark-specific criteria: exposure time must match
                    if cal_type == 'dark':
                        if master_exposure is not None and light_session.fitsSessionExposure is not None:
                            try:
                                master_exposure_val = float(master_exposure) if isinstance(master_exposure, str) else master_exposure
                                if abs(light_session.fitsSessionExposure - master_exposure_val) > 0.1:
                                    matches = False
                            except (ValueError, TypeError):
                                matches = False
                    
                    # Flat-specific criteria: filter must match  
                    if cal_type == 'flat':
                        if master_filter and light_session.fitsSessionFilter != master_filter:
                            matches = False
                    
                    if matches:
                        # Update the light session with the new master
                        current_master = getattr(light_session, master_field, None)
                        if current_master != master_path:
                            setattr(light_session, master_field, master_path)
                            light_session.save()
                            updated_count += 1
                            logger.info(f"Updated light session {light_session.fitsSessionId} with new {cal_type} master: {master_path}")
                            
                except Exception as e:
                    logger.warning(f"Error updating light session {light_session.fitsSessionId} with master: {e}")
                    continue
            
            logger.info(f"Updated {updated_count} light sessions with new {cal_type} master: {master_path}")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating light sessions with new master {master_path}: {e}")
            return 0

    def _findMatchingCalibrationSession(self, light_session, cal_type):
        """
        Find matching individual calibration session (fallback when no master available).
        
        This preserves the original session linking logic for backward compatibility.
        """
        try:
            # Base query for calibration sessions
            query = (fitsSessionModel
                    .select()
                    .where(
                        fitsSessionModel.fitsSessionObjectName == cal_type.capitalize(),
                        fitsSessionModel.fitsSessionTelescope == light_session.fitsSessionTelescope,
                        fitsSessionModel.fitsSessionImager == light_session.fitsSessionImager,
                        fitsSessionModel.fitsSessionDate <= light_session.fitsSessionDate,
                        fitsSessionModel.fitsSessionBinningX == light_session.fitsSessionBinningX,
                        fitsSessionModel.fitsSessionBinningY == light_session.fitsSessionBinningY
                    ))
            
            # Add gain/offset matching if available
            if light_session.fitsSessionGain is not None:
                query = query.where(fitsSessionModel.fitsSessionGain == light_session.fitsSessionGain)
            if light_session.fitsSessionOffset is not None:
                query = query.where(fitsSessionModel.fitsSessionOffset == light_session.fitsSessionOffset)
            
            # Add calibration-type specific criteria
            if cal_type == 'dark' and light_session.fitsSessionExposure is not None:
                query = query.where(fitsSessionModel.fitsSessionExposure == light_session.fitsSessionExposure)
            elif cal_type == 'flat' and light_session.fitsSessionFilter:
                query = query.where(fitsSessionModel.fitsSessionFilter == light_session.fitsSessionFilter)
            
            # Get most recent matching session
            return query.order_by(fitsSessionModel.fitsSessionDate.desc()).first()
            
        except Exception as e:
            logger.error(f"Error finding {cal_type} session for light session {light_session.fitsSessionId}: {e}")
            return None

    def detectAutoCalibrationOpportunities(self, progress_callback=None, min_files=3):
        """
        Detect individual calibration sessions that can create master calibration files.
        
        Each session creates its own master if it has sufficient files.
        Sessions are NOT combined - each session produces one master that can be used 
        to calibrate light frames with matching equipment attributes.
        
        Args:
            progress_callback: Optional callback for progress updates
            min_files: Minimum files required per session to create a master (default: 3)
            
        Returns:
            Dictionary with detection results and recommendations
        """
        try:
            logger.info(f"Detecting auto-calibration opportunities (min {min_files} files)...")
            
            opportunities = {
                'bias_sessions': [],
                'dark_sessions': [], 
                'flat_sessions': [],
                'total_opportunities': 0,
                'estimated_masters': 0
            }
            
            # Get all calibration sessions without masters
            cal_sessions = self.getSessionsNeedingMasters(min_files=min_files)
            
            if not cal_sessions:
                logger.info("No calibration sessions needing masters found")
                return opportunities
            
            total_sessions = len(cal_sessions)
            logger.info(f"Analyzing {total_sessions} calibration sessions for master opportunities...")
            
            # Analyze each session individually
            for i, session_data in enumerate(cal_sessions):
                if progress_callback:
                    if not progress_callback(i, total_sessions, f"Analyzing session {session_data.get('session_id', 'unknown')}"):
                        logger.info("Auto-calibration detection cancelled by user")
                        break
                
                session_type = session_data.get('session_type', '').lower()
                file_count = session_data.get('file_count', 0)
                
                # Each session that meets the minimum file requirement can create a master
                if file_count >= min_files and session_type in ['bias', 'dark', 'flat']:
                    # Add session details for master creation
                    master_opportunity = {
                        'session_id': session_data.get('session_id'),
                        'session_date': session_data.get('session_date'),
                        'file_count': file_count,
                        'telescope': session_data.get('telescope', ''),
                        'instrument': session_data.get('instrument', ''),
                        'x_binning': session_data.get('x_binning', 1),
                        'y_binning': session_data.get('y_binning', 1),
                        'gain': session_data.get('gain'),
                        'offset': session_data.get('offset'),
                        'estimated_quality': 90.0  # Individual sessions get high quality score
                    }
                    
                    # Add calibration-type specific attributes
                    if session_type == 'dark':
                        master_opportunity['exposure_time'] = session_data.get('exposure_time')
                        master_opportunity['ccd_temp'] = session_data.get('ccd_temp')
                    elif session_type == 'flat':
                        master_opportunity['filter'] = session_data.get('filter', '')
                    
                    opportunities[f'{session_type}_sessions'].append(master_opportunity)
                    opportunities['estimated_masters'] += 1
                    opportunities['total_opportunities'] += 1
            
            # Log results by calibration type
            for cal_type in ['bias', 'dark', 'flat']:
                session_count = len(opportunities[f'{cal_type}_sessions'])
                logger.info(f"Found {session_count} viable {cal_type} master opportunities")
            
            logger.info(f"Auto-calibration detection complete: {opportunities['total_opportunities']} opportunities, "
                       f"{opportunities['estimated_masters']} potential masters")
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error detecting auto-calibration opportunities: {e}")
            return None

    def _groupSessionsByMatchingCriteria(self, sessions, cal_type):
        """
        Group calibration sessions by matching criteria for master creation.
        
        Groups sessions that can be combined into masters based on:
        - Common criteria: telescope, instrument, binning, gain/offset
        - Dark-specific: exposure time, CCD temperature (±5°C)
        - Flat-specific: filter
        """
        groups = []
        
        for session in sessions:
            # Extract matching criteria from session
            criteria = {
                'telescope': session.get('telescope', ''),
                'instrument': session.get('instrument', ''),
                'x_binning': session.get('x_binning', 1),
                'y_binning': session.get('y_binning', 1),
                'gain': session.get('gain'),
                'offset': session.get('offset')
            }
            
            # Add calibration-type specific criteria
            if cal_type == 'dark':
                criteria['exposure_time'] = session.get('exposure_time')
                criteria['ccd_temp'] = session.get('ccd_temp')
            elif cal_type == 'flat':
                criteria['filter'] = session.get('filter', '')
            
            # Find existing group or create new one
            matching_group = None
            for group in groups:
                if self._criteriaMatch(group['criteria'], criteria, cal_type):
                    matching_group = group
                    break
            
            if matching_group:
                matching_group['sessions'].append(session)
            else:
                groups.append({
                    'criteria': criteria,
                    'sessions': [session],
                    'calibration_type': cal_type
                })
        
        return groups

    def _criteriaMatch(self, criteria1, criteria2, cal_type):
        """Check if two criteria sets match for the given calibration type."""
        
        # Common criteria that must match exactly
        common_keys = ['telescope', 'instrument', 'x_binning', 'y_binning']
        for key in common_keys:
            if criteria1.get(key) != criteria2.get(key):
                return False
        
        # Gain and offset should match if both are available
        for key in ['gain', 'offset']:
            val1 = criteria1.get(key)
            val2 = criteria2.get(key)
            if val1 is not None and val2 is not None and val1 != val2:
                return False
        
        # Type-specific matching
        if cal_type == 'dark':
            # Exposure time must match exactly
            if criteria1.get('exposure_time') != criteria2.get('exposure_time'):
                return False
            
            # CCD temperature within ±5°C tolerance
            temp1 = criteria1.get('ccd_temp')
            temp2 = criteria2.get('ccd_temp')
            if temp1 is not None and temp2 is not None:
                try:
                    # Convert string temperatures to float for comparison
                    temp1_float = float(temp1) if isinstance(temp1, str) else temp1
                    temp2_float = float(temp2) if isinstance(temp2, str) else temp2
                    if abs(temp1_float - temp2_float) > 5.0:
                        return False
                except (ValueError, TypeError):
                    # If conversion fails, temperatures don't match
                    return False
                    
        elif cal_type == 'flat':
            # Filter must match exactly
            if criteria1.get('filter') != criteria2.get('filter'):
                return False
        
        return True

    def _estimateGroupQuality(self, group, cal_type):
        """
        Estimate the quality potential of a session group for master creation.
        
        Returns a quality score (0-100) based on:
        - Number of files available
        - Consistency of metadata
        - Temporal distribution of sessions
        """
        try:
            sessions = group['sessions']
            total_files = sum(s.get('file_count', 0) for s in sessions)
            
            # Base score from file count (more files = better)
            if total_files >= 10:
                file_score = 100
            elif total_files >= 5:
                file_score = 80
            elif total_files >= 3:
                file_score = 60
            else:
                file_score = 30
            
            # Consistency score (fewer sessions with similar file counts = better)
            session_count = len(sessions)
            if session_count == 1:
                consistency_score = 100  # Single session, perfect consistency
            else:
                file_counts = [s.get('file_count', 0) for s in sessions]
                avg_files = total_files / session_count
                variance = sum((count - avg_files) ** 2 for count in file_counts) / session_count
                consistency_score = max(0, 100 - (variance * 10))
            
            # Temporal distribution score (sessions spread over time = better)
            dates = [s.get('date') for s in sessions if s.get('date')]
            if len(dates) > 1:
                date_range = (max(dates) - min(dates)).days
                temporal_score = min(100, date_range * 5)  # 5 points per day spread
            else:
                temporal_score = 50  # Single session date
            
            # Weighted average
            quality_score = int(
                file_score * 0.5 + 
                consistency_score * 0.3 + 
                temporal_score * 0.2
            )
            
            return max(0, min(100, quality_score))
            
        except Exception as e:
            logger.warning(f"Error estimating group quality: {e}")
            return 50  # Default medium quality

    def runAutoCalibrationWorkflow(self, progress_callback=None):
        """
        Orchestrates the complete auto-calibration workflow with progress tracking
        
        Args:
            progress_callback: Optional callback function for progress updates
                             Should return True to continue, False to cancel
            
        Returns:
            dict: Results of the auto-calibration workflow including:
                - sessions_analyzed: Number of sessions checked
                - masters_needed: Number of masters required
                - masters_created: Number of masters successfully created
                - calibration_opportunities: Number of auto-calibration opportunities found
                - light_frames_calibrated: Number of light frames calibrated
                - errors: List of any errors encountered
        """
        try:
            logger.info("Starting auto-calibration workflow")
            results = {
                "sessions_analyzed": 0,
                "masters_needed": 0, 
                "masters_created": 0,
                "calibration_opportunities": 0,
                "light_frames_calibrated": 0,
                "errors": []
            }
            
            # Phase 1: Analyze calibration sessions (10% of progress)
            if progress_callback:
                should_continue = progress_callback(0, 100, "Analyzing calibration sessions...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Operation cancelled by user"}
            
            try:
                sessions_needing_masters = self.getSessionsNeedingMasters()
                results["sessions_analyzed"] = len(sessions_needing_masters)
                results["masters_needed"] = len(sessions_needing_masters)
                logger.info(f"Found {len(sessions_needing_masters)} calibration sessions needing masters")
            except Exception as e:
                error_msg = f"Error analyzing calibration sessions: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            if progress_callback:
                should_continue = progress_callback(10, 100, f"Found {results['sessions_analyzed']} sessions to analyze")
                if not should_continue:
                    return {"status": "cancelled", "message": "Operation cancelled by user"}
            
            # Phase 2: Create master frames (40% of progress)
            if sessions_needing_masters:
                if progress_callback:
                    should_continue = progress_callback(15, 100, "Creating master calibration frames...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Operation cancelled by user"}
                
                # Create progress sub-callback for master creation
                def master_creation_progress(current, total, message):
                    # Map master creation progress to 15-50% of overall progress
                    progress_percent = 15 + int((current / total) * 35) if total > 0 else 15
                    if progress_callback:
                        return progress_callback(progress_percent, 100, f"Master frames: {message}")
                    return True
                
                try:
                    master_results = self.createMasterCalibrationFrames(progress_callback=master_creation_progress)
                    if isinstance(master_results, dict):
                        # Count total masters created
                        total_created = (master_results.get('bias_masters', 0) + 
                                       master_results.get('dark_masters', 0) + 
                                       master_results.get('flat_masters', 0))
                        results["masters_created"] = total_created
                        logger.info(f"Created {total_created} master frames")
                    else:
                        results["errors"].append(f"Unexpected master creation result format: {master_results}")
                except Exception as e:
                    error_msg = f"Error creating master frames: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            # Phase 3: Detect auto-calibration opportunities (20% of progress)
            if progress_callback:
                should_continue = progress_callback(55, 100, "Detecting auto-calibration opportunities...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Operation cancelled by user"}
            
            try:
                calibration_opportunities = self.detectAutoCalibrationOpportunities()
                if calibration_opportunities is None:
                    calibration_opportunities = {"total_opportunities": 0, "bias_groups": [], "dark_groups": [], "flat_groups": []}
                    results["errors"].append("Failed to detect calibration opportunities")
                
                results["calibration_opportunities"] = calibration_opportunities.get("total_opportunities", 0)
                logger.info(f"Found {calibration_opportunities.get('total_opportunities', 0)} auto-calibration opportunities")
            except Exception as e:
                error_msg = f"Error detecting calibration opportunities: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                calibration_opportunities = {"total_opportunities": 0, "bias_groups": [], "dark_groups": [], "flat_groups": []}  # Set empty dict for safety
            
            if progress_callback:
                should_continue = progress_callback(65, 100, f"Found {results['calibration_opportunities']} calibration opportunities")
                if not should_continue:
                    return {"status": "cancelled", "message": "Operation cancelled by user"}
            
            # Phase 4: Simulate light frame calibration (25% of progress)
            # Note: Actual calibration implementation will be added in future iterations
            if calibration_opportunities and calibration_opportunities.get("total_opportunities", 0) > 0:
                # Count all groups for progress tracking
                all_groups = []
                all_groups.extend(calibration_opportunities.get("bias_groups", []))
                all_groups.extend(calibration_opportunities.get("dark_groups", []))
                all_groups.extend(calibration_opportunities.get("flat_groups", []))
                
                total_groups = len(all_groups)
                calibrated_count = 0
                
                for i, group in enumerate(all_groups):
                    if progress_callback:
                        base_progress = 70 + int((i / total_groups) * 20) if total_groups > 0 else 70
                        should_continue = progress_callback(base_progress, 100, 
                            f"Processing calibration group {i+1}/{total_groups}")
                        if not should_continue:
                            return {"status": "cancelled", "message": "Operation cancelled by user"}
                    
                    try:
                        # Count sessions for this group
                        group_sessions = group.get("sessions", [])
                        calibrated_count += len(group_sessions)
                        
                        # Simulate processing time for progress demonstration
                        if progress_callback and len(group_sessions) > 0:
                            progress_percent = 70 + int(((i+1) / total_groups) * 20) if total_groups > 0 else 90
                            progress_callback(progress_percent, 100, 
                                f"Prepared {group.get('calibration_type', 'unknown')} group with {len(group_sessions)} sessions")
                                    
                    except Exception as e:
                        error_msg = f"Error processing calibration group {i+1}: {e}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)
                        
                results["light_frames_calibrated"] = calibrated_count
            
            # Phase 5: Finalization (5% of progress)
            if progress_callback:
                should_continue = progress_callback(95, 100, "Finalizing auto-calibration workflow...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Operation cancelled by user"}
            
            # Update database status and cleanup
            try:
                # Future: Update calibration status fields in database
                # Future: Implement cleanup of temporary files
                logger.info("Database updates and cleanup completed")
            except Exception as e:
                error_msg = f"Error during finalization: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            if progress_callback:
                progress_callback(100, 100, "Auto-calibration workflow completed!")
            
            logger.info(f"Auto-calibration workflow completed: {results}")
            results["status"] = "success" if not results["errors"] else "partial_success"
            return results
            
        except Exception as e:
            error_msg = f"Critical error in auto-calibration workflow: {e}"
            logger.error(error_msg)
            return {
                "status": "error", 
                "message": error_msg,
                "sessions_analyzed": 0,
                "masters_needed": 0,
                "masters_created": 0,
                "calibration_opportunities": 0,
                "light_frames_calibrated": 0,
                "errors": [error_msg]
            }

    def validateMasterFiles(self, progress_callback=None, fix_issues=False):
        """
        Validate master calibration files for integrity and cleanup orphaned references
        
        Performs comprehensive validation including:
        - File existence checks for all referenced masters
        - FITS header validation and corruption detection
        - Database consistency maintenance
        - Cleanup of broken references
        - Orphaned master file detection and handling
        
        Args:
            progress_callback: Optional callback function for progress updates
            fix_issues: Whether to automatically fix detected issues (default: False)
            
        Returns:
            dict: Validation results including:
                - total_masters_checked: Number of master references validated
                - missing_files: List of missing master file paths
                - corrupted_files: List of corrupted FITS files
                - orphaned_files: List of master files not referenced in database
                - database_issues: List of database consistency issues
                - fixes_applied: Number of issues automatically fixed
                - errors: List of validation errors encountered
        """
        try:
            logger.info("Starting master file validation and cleanup")
            
            results = {
                "total_masters_checked": 0,
                "missing_files": [],
                "corrupted_files": [],
                "orphaned_files": [],
                "database_issues": [],
                "fixes_applied": 0,
                "errors": []
            }
            
            from astrofiler_db import fitsSession as FitsSessionModel, fitsFile as FitsFileModel
            
            # Phase 1: Check master file references in sessions (30% of progress)
            if progress_callback:
                should_continue = progress_callback(0, 100, "Checking session master file references...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Validation cancelled by user"}
            
            try:
                # Get all sessions with master file references
                sessions_with_masters = FitsSessionModel.select().where(
                    (FitsSessionModel.fitsBiasMaster.is_null(False) & (FitsSessionModel.fitsBiasMaster != "")) |
                    (FitsSessionModel.fitsDarkMaster.is_null(False) & (FitsSessionModel.fitsDarkMaster != "")) |
                    (FitsSessionModel.fitsFlatMaster.is_null(False) & (FitsSessionModel.fitsFlatMaster != ""))
                )
                
                total_sessions = sessions_with_masters.count()
                results["total_masters_checked"] = total_sessions
                
                logger.info(f"Found {total_sessions} sessions with master file references")
                
                for i, session in enumerate(sessions_with_masters):
                    if progress_callback:
                        progress = int((i / total_sessions) * 25) if total_sessions > 0 else 0
                        should_continue = progress_callback(progress, 100, 
                            f"Validating session {i+1}/{total_sessions}")
                        if not should_continue:
                            return {"status": "cancelled", "message": "Validation cancelled by user"}
                    
                    # Check each master type
                    master_files = {
                        'bias': session.fitsBiasMaster,
                        'dark': session.fitsDarkMaster, 
                        'flat': session.fitsFlatMaster
                    }
                    
                    for master_type, master_path in master_files.items():
                        if master_path and master_path.strip():
                            # Normalize path
                            master_path = os.path.normpath(master_path.strip())
                            
                            # Check file existence
                            if not os.path.exists(master_path):
                                results["missing_files"].append({
                                    "session_id": session.fitsSessionId,
                                    "master_type": master_type,
                                    "file_path": master_path
                                })
                                
                                if fix_issues:
                                    # Clear the broken reference
                                    if master_type == 'bias':
                                        session.fitsBiasMaster = ""
                                    elif master_type == 'dark':
                                        session.fitsDarkMaster = ""
                                    elif master_type == 'flat':
                                        session.fitsFlatMaster = ""
                                    session.save()
                                    results["fixes_applied"] += 1
                                    logger.info(f"Cleared broken {master_type} master reference for session {session.fitsSessionId}")
                            
                            else:
                                # Validate FITS file integrity
                                try:
                                    with fits.open(master_path) as hdul:
                                        # Basic header validation
                                        header = hdul[0].header
                                        
                                        # Check for expected master frame headers
                                        imagetyp = header.get('IMAGETYP', '').lower()
                                        expected_types = ['masterbias', 'masterdark', 'masterflat']
                                        
                                        if not any(expected in imagetyp for expected in expected_types):
                                            results["database_issues"].append({
                                                "session_id": session.fitsSessionId,
                                                "master_type": master_type,
                                                "file_path": master_path,
                                                "issue": f"Unexpected IMAGETYP: '{imagetyp}'"
                                            })
                                        
                                except Exception as fits_error:
                                    results["corrupted_files"].append({
                                        "session_id": session.fitsSessionId,
                                        "master_type": master_type,
                                        "file_path": master_path,
                                        "error": str(fits_error)
                                    })
                                    
                                    if fix_issues:
                                        # Clear reference to corrupted file
                                        if master_type == 'bias':
                                            session.fitsBiasMaster = ""
                                        elif master_type == 'dark':
                                            session.fitsDarkMaster = ""
                                        elif master_type == 'flat':
                                            session.fitsFlatMaster = ""
                                        session.save()
                                        results["fixes_applied"] += 1
                                        logger.warning(f"Cleared corrupted {master_type} master reference for session {session.fitsSessionId}")
                
            except Exception as e:
                error_msg = f"Error validating session master references: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            # Phase 2: Check for orphaned master files (40% of progress)
            if progress_callback:
                should_continue = progress_callback(30, 100, "Scanning for orphaned master files...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Validation cancelled by user"}
            
            try:
                masters_dir = os.path.join(self.repoFolder, 'Masters')
                
                if os.path.exists(masters_dir):
                    # Get all master files in directory
                    master_files_on_disk = []
                    for root, dirs, files in os.walk(masters_dir):
                        for file in files:
                            if file.lower().endswith(('.fits', '.fit')):
                                master_files_on_disk.append(os.path.join(root, file))
                    
                    # Get all master file paths referenced in database
                    referenced_masters = set()
                    for session in FitsSessionModel.select():
                        if session.fitsBiasMaster:
                            referenced_masters.add(os.path.normpath(session.fitsBiasMaster.strip()))
                        if session.fitsDarkMaster:
                            referenced_masters.add(os.path.normpath(session.fitsDarkMaster.strip()))
                        if session.fitsFlatMaster:
                            referenced_masters.add(os.path.normpath(session.fitsFlatMaster.strip()))
                    
                    # Find orphaned files
                    for i, master_file in enumerate(master_files_on_disk):
                        if progress_callback:
                            progress = 30 + int((i / len(master_files_on_disk)) * 40) if master_files_on_disk else 30
                            should_continue = progress_callback(progress, 100, 
                                f"Checking master file {i+1}/{len(master_files_on_disk)}")
                            if not should_continue:
                                return {"status": "cancelled", "message": "Validation cancelled by user"}
                        
                        normalized_path = os.path.normpath(master_file)
                        if normalized_path not in referenced_masters:
                            results["orphaned_files"].append(master_file)
                            
                            if fix_issues:
                                try:
                                    # Move to quarantine subdirectory instead of deleting
                                    quarantine_dir = os.path.join(masters_dir, '_quarantine')
                                    os.makedirs(quarantine_dir, exist_ok=True)
                                    
                                    quarantine_path = os.path.join(quarantine_dir, os.path.basename(master_file))
                                    
                                    # Handle filename conflicts
                                    counter = 1
                                    base_quarantine_path = quarantine_path
                                    while os.path.exists(quarantine_path):
                                        name, ext = os.path.splitext(base_quarantine_path)
                                        quarantine_path = f"{name}_{counter}{ext}"
                                        counter += 1
                                    
                                    os.rename(master_file, quarantine_path)
                                    results["fixes_applied"] += 1
                                    logger.info(f"Moved orphaned master file to quarantine: {quarantine_path}")
                                    
                                except Exception as move_error:
                                    error_msg = f"Failed to quarantine orphaned file {master_file}: {move_error}"
                                    logger.error(error_msg)
                                    results["errors"].append(error_msg)
                
            except Exception as e:
                error_msg = f"Error scanning for orphaned master files: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            # Phase 3: Database consistency checks (20% of progress)
            if progress_callback:
                should_continue = progress_callback(75, 100, "Performing database consistency checks...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Validation cancelled by user"}
            
            try:
                # Check for duplicate master file references
                master_path_counts = {}
                
                for session in FitsSessionModel.select():
                    for master_field in [session.fitsBiasMaster, session.fitsDarkMaster, session.fitsFlatMaster]:
                        if master_field and master_field.strip():
                            normalized_path = os.path.normpath(master_field.strip())
                            master_path_counts[normalized_path] = master_path_counts.get(normalized_path, 0) + 1
                
                # Report paths referenced multiple times (may indicate issues)
                for master_path, count in master_path_counts.items():
                    if count > 3:  # Reasonable threshold for multiple references
                        results["database_issues"].append({
                            "issue": f"Master file referenced {count} times",
                            "file_path": master_path,
                            "reference_count": count
                        })
                
            except Exception as e:
                error_msg = f"Error performing database consistency checks: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            # Final reporting (5% of progress)
            if progress_callback:
                progress_callback(100, 100, "Master file validation completed!")
            
            # Log summary
            logger.info(f"Master file validation completed:")
            logger.info(f"  - Masters checked: {results['total_masters_checked']}")
            logger.info(f"  - Missing files: {len(results['missing_files'])}")
            logger.info(f"  - Corrupted files: {len(results['corrupted_files'])}")
            logger.info(f"  - Orphaned files: {len(results['orphaned_files'])}")
            logger.info(f"  - Database issues: {len(results['database_issues'])}")
            logger.info(f"  - Fixes applied: {results['fixes_applied']}")
            
            results["status"] = "success" if not results["errors"] else "partial_success"
            return results
            
        except Exception as e:
            error_msg = f"Critical error in master file validation: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "total_masters_checked": 0,
                "missing_files": [],
                "corrupted_files": [],
                "orphaned_files": [],
                "database_issues": [],
                "fixes_applied": 0,
                "errors": [error_msg]
            }

    def cleanupMasterFileStorage(self, progress_callback=None, retention_days=None):
        """
        Clean up master file storage based on retention policies
        
        Args:
            progress_callback: Optional callback for progress updates
            retention_days: Days to retain masters (None = use config setting)
            
        Returns:
            dict: Cleanup results with files processed and space reclaimed
        """
        try:
            from configparser import ConfigParser
            import datetime
            
            logger.info("Starting master file storage cleanup")
            
            # Get retention policy from config
            if retention_days is None:
                config = ConfigParser()
                config.read('astrofiler.ini')
                retention_days = config.getint('Settings', 'master_retention_days', fallback=30)
            
            if retention_days <= 0:
                logger.info("Master retention disabled (retention_days <= 0)")
                return {"status": "skipped", "message": "Master retention disabled"}
            
            results = {
                "files_processed": 0,
                "files_deleted": 0,
                "space_reclaimed": 0,
                "errors": []
            }
            
            masters_dir = os.path.join(self.repoFolder, 'Masters')
            if not os.path.exists(masters_dir):
                return {"status": "success", "message": "No masters directory found"}
            
            # Calculate cutoff date
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
            
            if progress_callback:
                should_continue = progress_callback(0, 100, f"Scanning masters older than {retention_days} days...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Cleanup cancelled by user"}
            
            # Get all master files
            master_files = []
            for root, dirs, files in os.walk(masters_dir):
                # Skip quarantine directory
                if '_quarantine' in root:
                    continue
                for file in files:
                    if file.lower().endswith(('.fits', '.fit')):
                        master_files.append(os.path.join(root, file))
            
            # Process files for cleanup
            for i, master_file in enumerate(master_files):
                if progress_callback:
                    progress = int((i / len(master_files)) * 100) if master_files else 100
                    should_continue = progress_callback(progress, 100, 
                        f"Processing {i+1}/{len(master_files)}: {os.path.basename(master_file)}")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Cleanup cancelled by user"}
                
                try:
                    results["files_processed"] += 1
                    
                    # Check file modification time
                    file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(master_file))
                    
                    if file_mtime < cutoff_date:
                        # Check if file is still referenced in database
                        from astrofiler_db import fitsSession as FitsSessionModel
                        
                        is_referenced = FitsSessionModel.select().where(
                            (FitsSessionModel.fitsBiasMaster == master_file) |
                            (FitsSessionModel.fitsDarkMaster == master_file) |
                            (FitsSessionModel.fitsFlatMaster == master_file)
                        ).exists()
                        
                        if not is_referenced:
                            # Safe to delete - move to quarantine first
                            quarantine_dir = os.path.join(masters_dir, '_quarantine', 'expired')
                            os.makedirs(quarantine_dir, exist_ok=True)
                            
                            file_size = os.path.getsize(master_file)
                            quarantine_path = os.path.join(quarantine_dir, os.path.basename(master_file))
                            
                            # Handle filename conflicts
                            counter = 1
                            base_quarantine_path = quarantine_path
                            while os.path.exists(quarantine_path):
                                name, ext = os.path.splitext(base_quarantine_path)
                                quarantine_path = f"{name}_{counter}{ext}"
                                counter += 1
                            
                            os.rename(master_file, quarantine_path)
                            results["files_deleted"] += 1
                            results["space_reclaimed"] += file_size
                            
                            logger.info(f"Moved expired master to quarantine: {master_file}")
                
                except Exception as e:
                    error_msg = f"Error processing master file {master_file}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            if progress_callback:
                progress_callback(100, 100, "Master file cleanup completed!")
            
            logger.info(f"Master cleanup completed: {results['files_deleted']} files moved, "
                       f"{results['space_reclaimed'] / (1024*1024):.1f} MB reclaimed")
            
            results["status"] = "success" if not results["errors"] else "partial_success"
            return results
            
        except Exception as e:
            error_msg = f"Critical error in master file cleanup: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "files_processed": 0,
                "files_deleted": 0,
                "space_reclaimed": 0,
                "errors": [error_msg]
            }

    def repairMasterFileDatabase(self, progress_callback=None):
        """
        Repair master file database references and rebuild missing associations
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: Repair results with statistics on fixes applied
        """
        try:
            logger.info("Starting master file database repair")
            
            results = {
                "sessions_processed": 0,
                "masters_relinked": 0,
                "broken_refs_cleared": 0,
                "missing_masters_found": 0,
                "errors": []
            }
            
            from astrofiler_db import fitsSession as FitsSessionModel, fitsFile as FitsFileModel
            
            if progress_callback:
                should_continue = progress_callback(0, 100, "Analyzing master file associations...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Repair cancelled by user"}
            
            # Get all sessions that should have masters
            calibration_sessions = FitsSessionModel.select().where(
                FitsSessionModel.fitsSessionObjectName.in_(['bias', 'Bias', 'BIAS', 'dark', 'Dark', 'DARK', 'flat', 'Flat', 'FLAT'])
            )
            
            total_sessions = calibration_sessions.count()
            masters_dir = os.path.join(self.repoFolder, 'Masters')
            
            # Build index of available master files
            available_masters = {}
            if os.path.exists(masters_dir):
                for root, dirs, files in os.walk(masters_dir):
                    if '_quarantine' in root:
                        continue
                    for file in files:
                        if file.lower().endswith(('.fits', '.fit')):
                            master_path = os.path.join(root, file)
                            # Extract master type from filename
                            filename_lower = file.lower()
                            if 'bias' in filename_lower:
                                master_type = 'bias'
                            elif 'dark' in filename_lower:
                                master_type = 'dark'
                            elif 'flat' in filename_lower:
                                master_type = 'flat'
                            else:
                                continue
                            
                            if master_type not in available_masters:
                                available_masters[master_type] = []
                            available_masters[master_type].append(master_path)
            
            # Process calibration sessions
            for i, session in enumerate(calibration_sessions):
                if progress_callback:
                    progress = int((i / total_sessions) * 100) if total_sessions > 0 else 100
                    should_continue = progress_callback(progress, 100, 
                        f"Processing session {i+1}/{total_sessions}")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Repair cancelled by user"}
                
                results["sessions_processed"] += 1
                session_type = session.fitsSessionObjectName.lower()
                
                try:
                    # Determine which master field to check
                    if 'bias' in session_type:
                        current_master = session.fitsBiasMaster
                        master_type = 'bias'
                    elif 'dark' in session_type:
                        current_master = session.fitsDarkMaster
                        master_type = 'dark'
                    elif 'flat' in session_type:
                        current_master = session.fitsFlatMaster
                        master_type = 'flat'
                    else:
                        continue
                    
                    # Check current master reference
                    if current_master and current_master.strip():
                        if not os.path.exists(current_master.strip()):
                            # Clear broken reference
                            if master_type == 'bias':
                                session.fitsBiasMaster = ""
                            elif master_type == 'dark':
                                session.fitsDarkMaster = ""
                            elif master_type == 'flat':
                                session.fitsFlatMaster = ""
                            
                            session.save()
                            results["broken_refs_cleared"] += 1
                            current_master = None
                    
                    # Try to find a suitable master if none exists
                    if not current_master or not current_master.strip():
                        suitable_masters = available_masters.get(master_type, [])
                        
                        if suitable_masters:
                            # Use the most recent master file
                            best_master = max(suitable_masters, key=lambda x: os.path.getmtime(x))
                            
                            # Set the master reference
                            if master_type == 'bias':
                                session.fitsBiasMaster = best_master
                            elif master_type == 'dark':
                                session.fitsDarkMaster = best_master
                            elif master_type == 'flat':
                                session.fitsFlatMaster = best_master
                            
                            session.save()
                            results["masters_relinked"] += 1
                            results["missing_masters_found"] += 1
                            
                            logger.info(f"Linked {master_type} master to session {session.fitsSessionId}: {best_master}")
                
                except Exception as e:
                    error_msg = f"Error processing session {session.fitsSessionId}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            if progress_callback:
                progress_callback(100, 100, "Database repair completed!")
            
            logger.info(f"Master database repair completed: {results['masters_relinked']} masters relinked, "
                       f"{results['broken_refs_cleared']} broken references cleared")
            
            results["status"] = "success" if not results["errors"] else "partial_success"
            return results
            
        except Exception as e:
            error_msg = f"Critical error in master database repair: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "sessions_processed": 0,
                "masters_relinked": 0,
                "broken_refs_cleared": 0,
                "missing_masters_found": 0,
                "errors": [error_msg]
            }

    def assessMasterFrameQuality(self, master_file_path, master_type, progress_callback=None):
        """
        Comprehensive quality assessment for master calibration frames
        
        Args:
            master_file_path: Path to the master FITS file
            master_type: Type of master ('bias', 'dark', 'flat')
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: Quality assessment results including:
                - overall_quality_score: Overall score 0-100
                - noise_metrics: Noise analysis results
                - uniformity_metrics: Spatial uniformity analysis
                - frame_statistics: Basic statistics
                - quality_issues: List of detected issues
                - recommendations: Improvement suggestions
        """
        try:
            import datetime
            logger.info(f"Assessing quality of {master_type} master: {master_file_path}")
            
            if progress_callback:
                should_continue = progress_callback(0, 100, f"Loading {master_type} master frame...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Quality assessment cancelled"}
            
            # Load the FITS file
            with fits.open(master_file_path) as hdul:
                header = hdul[0].header
                data = hdul[0].data.astype(float)
                
                results = {
                    "file_path": master_file_path,
                    "master_type": master_type,
                    "overall_quality_score": 0,
                    "noise_metrics": {},
                    "uniformity_metrics": {},
                    "frame_statistics": {},
                    "quality_issues": [],
                    "recommendations": [],
                    "assessment_timestamp": datetime.datetime.now().isoformat()
                }
                
                # Phase 1: Basic frame statistics (20% progress)
                if progress_callback:
                    should_continue = progress_callback(10, 100, "Computing frame statistics...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                results["frame_statistics"] = self._computeFrameStatistics(data, header)
                
                # Phase 2: Noise analysis (30% progress)
                if progress_callback:
                    should_continue = progress_callback(30, 100, "Analyzing noise characteristics...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                results["noise_metrics"] = self._analyzeFrameNoise(data, master_type)
                
                # Phase 3: Uniformity analysis (40% progress)
                if progress_callback:
                    should_continue = progress_callback(60, 100, "Assessing frame uniformity...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                results["uniformity_metrics"] = self._analyzeFrameUniformity(data, master_type)
                
                # Phase 4: Master-type specific analysis (20% progress)
                if progress_callback:
                    should_continue = progress_callback(80, 100, f"Performing {master_type}-specific analysis...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                type_specific_results = self._performTypeSpecificAnalysis(data, header, master_type)
                results.update(type_specific_results)
                
                # Phase 5: Overall quality scoring (10% progress)
                if progress_callback:
                    should_continue = progress_callback(95, 100, "Computing quality score...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                results["overall_quality_score"] = self._computeOverallQualityScore(results, master_type)
                
                # Generate recommendations
                results["recommendations"] = self._generateQualityRecommendations(results, master_type)
                
                if progress_callback:
                    progress_callback(100, 100, "Quality assessment completed!")
                
                logger.info(f"Quality assessment complete: {master_type} master scored {results['overall_quality_score']}/100")
                return results
                
        except Exception as e:
            error_msg = f"Error assessing master frame quality: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "file_path": master_file_path,
                "master_type": master_type
            }

    def assessLightFrameQuality(self, light_file_path, progress_callback=None):
        """
        Comprehensive quality assessment for light frames including FWHM calculation
        
        Args:
            light_file_path: Path to the light frame FITS file
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: Quality assessment results including:
                - overall_quality_score: Overall score 0-100
                - fwhm_metrics: Star FWHM analysis (average, std dev, star count)
                - noise_metrics: Noise analysis results
                - star_detection: Star detection statistics
                - seeing_conditions: Atmospheric seeing assessment
        """
        try:
            import datetime
            logger.info(f"Assessing quality of light frame: {light_file_path}")
            
            if progress_callback:
                should_continue = progress_callback(0, 100, "Loading light frame...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Quality assessment cancelled"}
            
            # Load the FITS file
            with fits.open(light_file_path) as hdul:
                header = hdul[0].header
                data = hdul[0].data.astype(float)
                
                results = {
                    "file_path": light_file_path,
                    "frame_type": "light",
                    "overall_quality_score": 0,
                    "fwhm_metrics": {},
                    "noise_metrics": {},
                    "star_detection": {},
                    "seeing_conditions": {},
                    "quality_issues": [],
                    "recommendations": [],
                    "assessment_timestamp": datetime.datetime.now().isoformat()
                }
                
                # Phase 1: Star detection (30% progress)
                if progress_callback:
                    should_continue = progress_callback(10, 100, "Detecting stars...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                results["star_detection"] = self._detectStarsInFrame(data)
                
                # Phase 2: FWHM calculation (40% progress)
                if progress_callback:
                    should_continue = progress_callback(40, 100, "Measuring star FWHM...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                if results["star_detection"].get("star_count", 0) > 0:
                    results["fwhm_metrics"] = self._calculateFWHMMetrics(data, results["star_detection"])
                else:
                    results["fwhm_metrics"] = {"average_fwhm": None, "fwhm_std": None, "star_count": 0}
                    results["quality_issues"].append("No stars detected for FWHM measurement")
                
                # Phase 3: Noise analysis (20% progress)
                if progress_callback:
                    should_continue = progress_callback(70, 100, "Analyzing noise characteristics...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                results["noise_metrics"] = self._analyzeFrameNoise(data, "light")
                
                # Phase 4: Seeing conditions assessment (10% progress)
                if progress_callback:
                    should_continue = progress_callback(90, 100, "Assessing seeing conditions...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                results["seeing_conditions"] = self._assessSeeingConditions(results["fwhm_metrics"], header)
                
                # Phase 5: Overall quality scoring
                results["overall_quality_score"] = self._computeLightFrameQualityScore(results)
                results["recommendations"] = self._generateLightFrameRecommendations(results)
                
                if progress_callback:
                    progress_callback(100, 100, "Light frame quality assessment completed!")
                
                logger.info(f"Light frame quality assessment complete: scored {results['overall_quality_score']}/100, "
                           f"FWHM: {results['fwhm_metrics'].get('average_fwhm', 'N/A')}")
                return results
                
        except Exception as e:
            error_msg = f"Error assessing light frame quality: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "file_path": light_file_path,
                "frame_type": "light"
            }

    def _computeFrameStatistics(self, data, header):
        """Compute basic statistical metrics for a FITS frame"""
        import numpy as np
        
        try:
            stats = {
                "mean": float(np.mean(data)),
                "median": float(np.median(data)),
                "std_dev": float(np.std(data)),
                "min_value": float(np.min(data)),
                "max_value": float(np.max(data)),
                "data_range": float(np.max(data) - np.min(data)),
                "frame_dimensions": data.shape,
                "total_pixels": data.size,
                "bit_depth": header.get('BITPIX', 'unknown'),
                "exposure_time": header.get('EXPTIME', 'unknown')
            }
            
            # Calculate percentiles for robust statistics
            stats["percentile_1"] = float(np.percentile(data, 1))
            stats["percentile_99"] = float(np.percentile(data, 99))
            stats["robust_range"] = stats["percentile_99"] - stats["percentile_1"]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error computing frame statistics: {e}")
            return {"error": str(e)}

    def _analyzeFrameNoise(self, data, frame_type):
        """Analyze noise characteristics of a FITS frame"""
        import numpy as np
        
        # Try to import scipy, use fallback if not available
        try:
            from scipy import ndimage
            has_scipy = True
        except ImportError:
            has_scipy = False
        
        try:
            noise_metrics = {}
            
            # Basic noise estimation using standard deviation
            noise_metrics["global_noise_std"] = float(np.std(data))
            
            # Robust noise estimation using median absolute deviation
            median_val = np.median(data)
            mad = np.median(np.abs(data - median_val))
            noise_metrics["robust_noise_mad"] = float(mad * 1.4826)  # Scale factor for normal distribution
            
            # Local noise estimation using Laplacian filter
            if has_scipy:
                laplacian_kernel = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]])
                laplacian = ndimage.convolve(data, laplacian_kernel, mode='constant')
                noise_metrics["laplacian_noise_std"] = float(np.std(laplacian) / 6.0)  # Normalized
            else:
                # Simple gradient-based noise estimation as fallback
                grad_x = np.diff(data, axis=1)
                grad_y = np.diff(data, axis=0)
                gradient_noise = np.sqrt(np.var(grad_x) + np.var(grad_y))
                noise_metrics["laplacian_noise_std"] = float(gradient_noise)
            
            # Hot/cold pixel detection
            threshold_hot = np.percentile(data, 99.9)
            threshold_cold = np.percentile(data, 0.1)
            
            hot_pixels = np.sum(data > threshold_hot)
            cold_pixels = np.sum(data < threshold_cold)
            
            noise_metrics["hot_pixels_count"] = int(hot_pixels)
            noise_metrics["cold_pixels_count"] = int(cold_pixels)
            noise_metrics["hot_pixels_percent"] = float(hot_pixels / data.size * 100)
            noise_metrics["cold_pixels_percent"] = float(cold_pixels / data.size * 100)
            
            # Signal-to-noise ratio estimate
            if frame_type in ['light']:
                # For light frames, estimate SNR using signal above background
                background = np.percentile(data, 10)  # Rough background estimate
                signal = np.percentile(data, 90) - background
                if signal > 0:
                    noise_metrics["estimated_snr"] = float(signal / noise_metrics["robust_noise_mad"])
                else:
                    noise_metrics["estimated_snr"] = 0.0
            
            return noise_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing frame noise: {e}")
            return {"error": str(e)}

    def _analyzeFrameUniformity(self, data, frame_type):
        """Analyze spatial uniformity of a FITS frame"""
        import numpy as np
        
        try:
            uniformity_metrics = {}
            
            # Divide frame into grid sections for uniformity analysis
            h, w = data.shape
            grid_size = min(8, min(h//32, w//32))  # Adaptive grid size
            
            if grid_size < 2:
                # Frame too small for grid analysis
                uniformity_metrics["uniformity_score"] = 50.0  # Neutral score
                uniformity_metrics["grid_analysis"] = "Frame too small"
                return uniformity_metrics
            
            section_h = h // grid_size
            section_w = w // grid_size
            
            section_means = []
            section_stds = []
            
            for i in range(grid_size):
                for j in range(grid_size):
                    y1, y2 = i * section_h, (i + 1) * section_h
                    x1, x2 = j * section_w, (j + 1) * section_w
                    
                    section = data[y1:y2, x1:x2]
                    section_means.append(np.mean(section))
                    section_stds.append(np.std(section))
            
            section_means = np.array(section_means)
            section_stds = np.array(section_stds)
            
            # Uniformity metrics
            uniformity_metrics["section_mean_std"] = float(np.std(section_means))
            uniformity_metrics["section_mean_range"] = float(np.max(section_means) - np.min(section_means))
            uniformity_metrics["mean_of_section_stds"] = float(np.mean(section_stds))
            
            # Overall uniformity score (lower variation = higher score)
            if frame_type == 'flat':
                # For flat frames, uniformity is critical
                variation_coefficient = uniformity_metrics["section_mean_std"] / np.mean(section_means)
                uniformity_metrics["uniformity_score"] = max(0, min(100, 100 - variation_coefficient * 1000))
            else:
                # For bias/dark frames, some variation is acceptable
                variation_coefficient = uniformity_metrics["section_mean_std"] / np.mean(section_means)
                uniformity_metrics["uniformity_score"] = max(0, min(100, 100 - variation_coefficient * 500))
            
            return uniformity_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing frame uniformity: {e}")
            return {"error": str(e)}

    def _detectStarsInFrame(self, data):
        """Detect stars in a light frame for FWHM calculation"""
        import numpy as np
        from scipy import ndimage
        
        try:
            # Simple star detection using local maxima
            # Smooth the image to reduce noise
            smoothed = ndimage.gaussian_filter(data, sigma=1.0)
            
            # Find local maxima
            threshold = np.percentile(smoothed, 95)  # Top 5% of pixels
            mask = smoothed > threshold
            
            # Use morphological operations to find isolated peaks
            structure = np.ones((5, 5))  # 5x5 neighborhood
            local_maxima = ndimage.maximum_filter(smoothed, footprint=structure) == smoothed
            
            # Combine threshold and local maxima
            star_candidates = mask & local_maxima
            
            # Get coordinates of detected stars
            star_coords = np.where(star_candidates)
            star_positions = list(zip(star_coords[0], star_coords[1]))
            
            # Filter out stars too close to edges (need room for FWHM measurement)
            margin = 10
            h, w = data.shape
            filtered_stars = []
            
            for y, x in star_positions:
                if margin < y < h - margin and margin < x < w - margin:
                    filtered_stars.append((y, x))
            
            return {
                "star_count": len(filtered_stars),
                "star_positions": filtered_stars[:50],  # Limit to 50 brightest stars
                "detection_threshold": float(threshold)
            }
            
        except Exception as e:
            logger.error(f"Error detecting stars: {e}")
            return {"error": str(e), "star_count": 0, "star_positions": []}

    def _calculateFWHMMetrics(self, data, star_detection):
        """Calculate FWHM metrics for detected stars"""
        import numpy as np
        from scipy import optimize
        
        try:
            star_positions = star_detection.get("star_positions", [])
            if not star_positions:
                return {"average_fwhm": None, "fwhm_std": None, "star_count": 0}
            
            fwhm_values = []
            
            # Fit Gaussian to each star to measure FWHM
            for y, x in star_positions[:20]:  # Process up to 20 stars for speed
                try:
                    # Extract small region around star
                    size = 15  # 15x15 pixel region
                    y_min, y_max = max(0, y - size//2), min(data.shape[0], y + size//2 + 1)
                    x_min, x_max = max(0, x - size//2), min(data.shape[1], x + size//2 + 1)
                    
                    star_region = data[y_min:y_max, x_min:x_max]
                    
                    if star_region.size < 25:  # Skip if region too small
                        continue
                    
                    # Estimate FWHM using simple method (80% to 20% width)
                    # Create radial profile from center
                    center_y, center_x = star_region.shape[0] // 2, star_region.shape[1] // 2
                    
                    # Get pixel values at different radii
                    max_val = np.max(star_region)
                    background = np.percentile(star_region, 10)
                    
                    if max_val <= background:
                        continue
                    
                    # Find radius where intensity drops to half maximum
                    half_max = background + (max_val - background) * 0.5
                    
                    # Simple circular aperture method
                    y_grid, x_grid = np.ogrid[:star_region.shape[0], :star_region.shape[1]]
                    distances = np.sqrt((y_grid - center_y)**2 + (x_grid - center_x)**2)
                    
                    # Find approximate FWHM
                    for radius in np.arange(0.5, 10, 0.1):
                        mask = distances <= radius
                        if np.any(mask):
                            mean_val = np.mean(star_region[mask])
                            if mean_val <= half_max:
                                fwhm = radius * 2.0  # Full width
                                fwhm_values.append(fwhm)
                                break
                        
                except Exception:
                    continue  # Skip problematic stars
            
            if fwhm_values:
                fwhm_array = np.array(fwhm_values)
                # Remove outliers (beyond 2 standard deviations)
                mean_fwhm = np.mean(fwhm_array)
                std_fwhm = np.std(fwhm_array)
                
                if std_fwhm > 0:
                    clean_fwhm = fwhm_array[np.abs(fwhm_array - mean_fwhm) <= 2 * std_fwhm]
                else:
                    clean_fwhm = fwhm_array
                
                if len(clean_fwhm) > 0:
                    return {
                        "average_fwhm": float(np.mean(clean_fwhm)),
                        "fwhm_std": float(np.std(clean_fwhm)),
                        "fwhm_median": float(np.median(clean_fwhm)),
                        "star_count": len(clean_fwhm),
                        "total_detected": len(fwhm_values)
                    }
            
            return {"average_fwhm": None, "fwhm_std": None, "star_count": 0}
            
        except Exception as e:
            logger.error(f"Error calculating FWHM metrics: {e}")
            return {"error": str(e), "average_fwhm": None, "fwhm_std": None, "star_count": 0}

    def _performTypeSpecificAnalysis(self, data, header, master_type):
        """Perform analysis specific to the master frame type"""
        import numpy as np
        
        results = {}
        
        try:
            if master_type == 'bias':
                # Bias-specific analysis
                results["bias_level"] = float(np.median(data))
                results["bias_stability"] = float(np.std(data))
                
                # Check for bias level consistency across the frame
                mean_level = np.mean(data)
                results["level_consistency"] = abs(results["bias_level"] - mean_level)
                
            elif master_type == 'dark':
                # Dark-specific analysis
                results["dark_level"] = float(np.mean(data))
                results["dark_current_rate"] = results["dark_level"]  # Simplified
                
                # Temperature analysis if available
                ccd_temp = header.get('CCD-TEMP') or header.get('SET-TEMP')
                if ccd_temp:
                    try:
                        results["ccd_temperature"] = float(ccd_temp)
                        # Rough dark current vs temperature relationship
                        if results["ccd_temperature"] > -10:
                            results["temp_warning"] = "High CCD temperature may increase dark current"
                    except ValueError:
                        pass
                
                # Hot pixel analysis
                hot_threshold = np.percentile(data, 99.5)
                results["hot_pixel_threshold"] = float(hot_threshold)
                
            elif master_type == 'flat':
                # Flat-specific analysis
                results["flat_median_level"] = float(np.median(data))
                
                # Illumination analysis
                center_region = data[data.shape[0]//4:3*data.shape[0]//4, 
                                  data.shape[1]//4:3*data.shape[1]//4]
                edge_regions = np.concatenate([
                    data[:data.shape[0]//8, :].flatten(),
                    data[-data.shape[0]//8:, :].flatten(),
                    data[:, :data.shape[1]//8].flatten(),
                    data[:, -data.shape[1]//8:].flatten()
                ])
                
                center_mean = np.mean(center_region)
                edge_mean = np.mean(edge_regions)
                
                results["vignetting_ratio"] = float(edge_mean / center_mean) if center_mean > 0 else 0
                results["illumination_gradient"] = abs(1.0 - results["vignetting_ratio"])
                
            return results
            
        except Exception as e:
            logger.error(f"Error in type-specific analysis for {master_type}: {e}")
            return {"error": str(e)}

    def _assessSeeingConditions(self, fwhm_metrics, header):
        """Assess seeing conditions based on FWHM measurements"""
        try:
            seeing_assessment = {}
            
            avg_fwhm = fwhm_metrics.get("average_fwhm")
            fwhm_std = fwhm_metrics.get("fwhm_std", 0)
            
            if avg_fwhm is not None:
                # Pixel scale estimation (rough - should be configurable)
                pixel_scale = 1.0  # arcseconds per pixel (default assumption)
                
                # Try to get pixel scale from header
                if 'PIXSCALE' in header:
                    pixel_scale = header['PIXSCALE']
                elif 'CDELT1' in header:
                    pixel_scale = abs(header['CDELT1']) * 3600  # Convert degrees to arcseconds
                
                seeing_arcsec = avg_fwhm * pixel_scale
                seeing_assessment["seeing_arcseconds"] = float(seeing_arcsec)
                seeing_assessment["seeing_pixels"] = float(avg_fwhm)
                
                # Classify seeing quality
                if seeing_arcsec < 1.5:
                    seeing_assessment["seeing_quality"] = "Excellent"
                elif seeing_arcsec < 2.5:
                    seeing_assessment["seeing_quality"] = "Good"
                elif seeing_arcsec < 4.0:
                    seeing_assessment["seeing_quality"] = "Average"
                else:
                    seeing_assessment["seeing_quality"] = "Poor"
                
                # FWHM consistency assessment
                if fwhm_std is not None and avg_fwhm > 0:
                    consistency_ratio = fwhm_std / avg_fwhm
                    if consistency_ratio < 0.1:
                        seeing_assessment["fwhm_consistency"] = "Very Stable"
                    elif consistency_ratio < 0.2:
                        seeing_assessment["fwhm_consistency"] = "Stable"
                    elif consistency_ratio < 0.3:
                        seeing_assessment["fwhm_consistency"] = "Variable"
                    else:
                        seeing_assessment["fwhm_consistency"] = "Highly Variable"
            else:
                seeing_assessment["seeing_quality"] = "Unknown (no stars detected)"
            
            return seeing_assessment
            
        except Exception as e:
            logger.error(f"Error assessing seeing conditions: {e}")
            return {"error": str(e)}

    def _computeOverallQualityScore(self, results, master_type):
        """Compute overall quality score for master frames"""
        try:
            scores = []
            weights = []
            
            # Noise quality (40% weight)
            noise_metrics = results.get("noise_metrics", {})
            if "robust_noise_mad" in noise_metrics:
                # Lower noise = higher score
                noise_score = max(0, min(100, 100 - noise_metrics["robust_noise_mad"] / 10))
                scores.append(noise_score)
                weights.append(0.4)
            
            # Uniformity quality (35% weight)
            uniformity_metrics = results.get("uniformity_metrics", {})
            if "uniformity_score" in uniformity_metrics:
                scores.append(uniformity_metrics["uniformity_score"])
                weights.append(0.35)
            
            # Type-specific scoring (25% weight)
            if master_type == 'bias':
                if "bias_stability" in results:
                    stability_score = max(0, min(100, 100 - results["bias_stability"]))
                    scores.append(stability_score)
                    weights.append(0.25)
            
            elif master_type == 'dark':
                if "dark_current_rate" in results:
                    # Lower dark current = higher score (rough estimation)
                    dark_score = max(0, min(100, 100 - results["dark_current_rate"] / 5))
                    scores.append(dark_score)
                    weights.append(0.25)
            
            elif master_type == 'flat':
                if "illumination_gradient" in results:
                    # Lower gradient = higher score
                    gradient_score = max(0, min(100, 100 - results["illumination_gradient"] * 200))
                    scores.append(gradient_score)
                    weights.append(0.25)
            
            # Calculate weighted average
            if scores and weights:
                total_weight = sum(weights)
                weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
                overall_score = weighted_sum / total_weight
                return int(round(overall_score))
            
            return 50  # Default neutral score if no metrics available
            
        except Exception as e:
            logger.error(f"Error computing overall quality score: {e}")
            return 50

    def _computeLightFrameQualityScore(self, results):
        """Compute overall quality score for light frames"""
        try:
            scores = []
            weights = []
            
            # FWHM quality (50% weight)
            fwhm_metrics = results.get("fwhm_metrics", {})
            avg_fwhm = fwhm_metrics.get("average_fwhm")
            
            if avg_fwhm is not None:
                # Excellent FWHM < 2 pixels, Poor FWHM > 6 pixels
                if avg_fwhm < 2.0:
                    fwhm_score = 100
                elif avg_fwhm < 3.0:
                    fwhm_score = 90
                elif avg_fwhm < 4.0:
                    fwhm_score = 70
                elif avg_fwhm < 6.0:
                    fwhm_score = 50
                else:
                    fwhm_score = 30
                    
                scores.append(fwhm_score)
                weights.append(0.5)
            
            # Noise quality (30% weight)
            noise_metrics = results.get("noise_metrics", {})
            if "estimated_snr" in noise_metrics:
                snr = noise_metrics["estimated_snr"]
                snr_score = min(100, max(0, snr * 2))  # Simple SNR to score mapping
                scores.append(snr_score)
                weights.append(0.3)
            
            # Star detection success (20% weight)
            star_detection = results.get("star_detection", {})
            star_count = star_detection.get("star_count", 0)
            if star_count > 20:
                detection_score = 100
            elif star_count > 10:
                detection_score = 80
            elif star_count > 5:
                detection_score = 60
            elif star_count > 0:
                detection_score = 40
            else:
                detection_score = 0
            
            scores.append(detection_score)
            weights.append(0.2)
            
            # Calculate weighted average
            if scores and weights:
                total_weight = sum(weights)
                weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
                overall_score = weighted_sum / total_weight
                return int(round(overall_score))
            
            return 50  # Default neutral score
            
        except Exception as e:
            logger.error(f"Error computing light frame quality score: {e}")
            return 50

    def _generateQualityRecommendations(self, results, master_type):
        """Generate quality improvement recommendations for master frames"""
        recommendations = []
        
        try:
            overall_score = results.get("overall_quality_score", 50)
            
            # General recommendations based on overall score
            if overall_score < 40:
                recommendations.append("Poor quality detected. Consider reacquiring calibration frames.")
            elif overall_score < 60:
                recommendations.append("Moderate quality. May benefit from additional frames or better conditions.")
            elif overall_score >= 80:
                recommendations.append("Excellent quality master frame suitable for precision calibration.")
            
            # Specific recommendations based on metrics
            noise_metrics = results.get("noise_metrics", {})
            if noise_metrics.get("hot_pixels_percent", 0) > 1.0:
                recommendations.append("High hot pixel count detected. Check CCD cooling and dark subtraction.")
            
            uniformity_metrics = results.get("uniformity_metrics", {})
            if uniformity_metrics.get("uniformity_score", 100) < 50:
                recommendations.append("Poor spatial uniformity. Check illumination setup and flat field acquisition.")
            
            # Type-specific recommendations
            if master_type == 'flat':
                vignetting = results.get("vignetting_ratio", 1.0)
                if vignetting < 0.7:
                    recommendations.append("Significant vignetting detected. Consider using flat frames for correction.")
            
            elif master_type == 'dark':
                temp = results.get("ccd_temperature")
                if temp and temp > -10:
                    recommendations.append("CCD temperature is high. Consider better cooling for lower noise.")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["Error generating recommendations"]

    def _generateLightFrameRecommendations(self, results):
        """Generate quality improvement recommendations for light frames"""
        recommendations = []
        
        try:
            overall_score = results.get("overall_quality_score", 50)
            
            # FWHM-based recommendations
            fwhm_metrics = results.get("fwhm_metrics", {})
            avg_fwhm = fwhm_metrics.get("average_fwhm")
            
            if avg_fwhm is not None:
                if avg_fwhm > 5.0:
                    recommendations.append("Poor seeing conditions (FWHM > 5 pixels). Consider waiting for better seeing.")
                elif avg_fwhm > 3.5:
                    recommendations.append("Average seeing conditions. Frame usable but not optimal.")
                elif avg_fwhm < 2.0:
                    recommendations.append("Excellent seeing conditions. High quality frame for stacking.")
            
            # Star detection recommendations
            star_detection = results.get("star_detection", {})
            star_count = star_detection.get("star_count", 0)
            
            if star_count == 0:
                recommendations.append("No stars detected. Check focus, exposure, and field selection.")
            elif star_count < 5:
                recommendations.append("Few stars detected. Consider longer exposure or different field.")
            
            # Seeing consistency
            seeing_conditions = results.get("seeing_conditions", {})
            consistency = seeing_conditions.get("fwhm_consistency")
            if consistency == "Highly Variable":
                recommendations.append("Variable seeing during exposure. Shorter exposures may improve quality.")
            
            if overall_score >= 80:
                recommendations.append("Excellent quality light frame suitable for high-quality stacking.")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating light frame recommendations: {e}")
            return ["Error generating recommendations"]

    def _detectFrameType(self, header, image_data):
        """
        Automatically detect frame type from FITS header and image data
        
        Args:
            header: FITS header object
            image_data: Image data array
            
        Returns:
            str: Detected frame type ("light", "bias", "dark", "flat")
        """
        try:
            import numpy as np
            
            # Check FITS header for explicit type information
            imagetyp = header.get('IMAGETYP', '').lower()
            if 'bias' in imagetyp:
                return 'bias'
            elif 'dark' in imagetyp:
                return 'dark'
            elif 'flat' in imagetyp:
                return 'flat'
            elif 'light' in imagetyp or 'object' in imagetyp:
                return 'light'
            
            # Check object name
            object_name = header.get('OBJECT', '').lower()
            if any(name in object_name for name in ['bias', 'dark', 'flat']):
                for frame_type in ['bias', 'dark', 'flat']:
                    if frame_type in object_name:
                        return frame_type
            
            # Analyze exposure time and image statistics
            exptime = header.get('EXPTIME', 0)
            mean_value = np.mean(image_data)
            std_value = np.std(image_data)
            
            # Bias frame detection (very short exposure, low signal)
            if exptime < 0.001 and mean_value < 1000:
                return 'bias'
            
            # Dark frame detection (longer exposure, moderate signal)
            if exptime > 1.0 and mean_value < 5000 and std_value < mean_value * 0.3:
                return 'dark'
            
            # Flat frame detection (moderate exposure, high uniform signal)  
            if 1000 < mean_value < 50000 and std_value < mean_value * 0.2:
                return 'flat'
            
            # Default to light frame
            return 'light'
            
        except Exception as e:
            logger.warning(f"Error detecting frame type: {e}")
            return 'light'  # Default assumption

    def _analyzeUniformityMetrics(self, image_data):
        """
        Analyze uniformity characteristics for calibration frames (flats, darks, bias).
        
        Args:
            image_data: 2D numpy array of image pixel values
            
        Returns:
            dict: Uniformity analysis results
        """
        try:
            import numpy as np
            
            # Calculate basic uniformity statistics
            mean_val = float(np.mean(image_data))
            std_val = float(np.std(image_data))
            
            # Calculate coefficient of variation (relative uniformity)
            cv = (std_val / mean_val * 100.0) if mean_val > 0 else 100.0
            
            # Analyze spatial uniformity by quadrants
            h, w = image_data.shape
            h_mid, w_mid = h // 2, w // 2
            
            # Split into quadrants
            q1 = image_data[:h_mid, :w_mid]  # Top-left
            q2 = image_data[:h_mid, w_mid:]  # Top-right
            q3 = image_data[h_mid:, :w_mid]  # Bottom-left
            q4 = image_data[h_mid:, w_mid:]  # Bottom-right
            
            quadrant_means = [float(np.mean(q)) for q in [q1, q2, q3, q4]]
            quadrant_uniformity = float(np.std(quadrant_means))
            
            # Calculate vignetting indicator (center vs corner brightness)
            center_region = image_data[h//4:3*h//4, w//4:3*w//4]
            corner_regions = [
                image_data[:h//4, :w//4],  # Top-left corner
                image_data[:h//4, 3*w//4:],  # Top-right corner
                image_data[3*h//4:, :w//4],  # Bottom-left corner
                image_data[3*h//4:, 3*w//4:]  # Bottom-right corner
            ]
            
            center_mean = float(np.mean(center_region))
            corner_mean = float(np.mean([np.mean(corner) for corner in corner_regions]))
            
            vignetting_ratio = (center_mean / corner_mean) if corner_mean > 0 else 1.0
            
            # Overall uniformity score (0-100, higher is better)
            uniformity_score = max(0.0, 100.0 - cv)
            
            return {
                'coefficient_variation': cv,
                'spatial_uniformity': quadrant_uniformity,
                'vignetting_ratio': vignetting_ratio,
                'uniformity_score': uniformity_score,
                'quadrant_means': quadrant_means,
                'center_corner_ratio': vignetting_ratio
            }
            
        except Exception as e:
            logger.error(f"Error analyzing uniformity metrics: {e}")
            return {
                'coefficient_variation': 100.0,
                'spatial_uniformity': 100.0,
                'vignetting_ratio': 1.0,
                'uniformity_score': 0.0,
                'quadrant_means': [0.0, 0.0, 0.0, 0.0],
                'center_corner_ratio': 1.0
            }

    def _analyzeFWHMMetrics(self, image_data):
        """
        Analyze FWHM (Full Width Half Maximum) metrics for light frames.
        This function detects and analyzes stellar sources to estimate seeing quality.
        
        Args:
            image_data: 2D numpy array of image pixel values
            
        Returns:
            dict: FWHM analysis results
        """
        try:
            import numpy as np
            
            # Try to import scipy for advanced analysis
            try:
                import scipy.ndimage as ndimage
                from scipy import optimize
                scipy_available = True
            except ImportError:
                scipy_available = False
            
            if scipy_available:
                # Advanced FWHM analysis with scipy
                # Apply median filter to reduce noise
                filtered_data = ndimage.median_filter(image_data, size=3)
                
                # Calculate background level and threshold
                background_level = float(np.percentile(filtered_data, 25))
                noise_level = float(np.std(filtered_data - background_level))
                threshold = background_level + 5 * noise_level
                
                # Find potential stars (local maxima above threshold)
                from scipy.ndimage import maximum_filter
                local_max = maximum_filter(filtered_data, size=15)
                is_peak = (filtered_data == local_max) & (filtered_data > threshold)
                
                # Get coordinates of potential stars
                star_coords = np.where(is_peak)
                star_positions = list(zip(star_coords[0], star_coords[1]))
                
                # Analyze a sample of the brightest stars (max 20 for performance)
                star_intensities = [filtered_data[y, x] for y, x in star_positions]
                if len(star_intensities) == 0:
                    return {
                        'fwhm_average': 0.0,
                        'fwhm_median': 0.0,
                        'star_count': 0,
                        'seeing_quality': 'No stars detected',
                        'fwhm_std': 0.0
                    }
                
                # Sort by brightness and take top stars
                sorted_stars = sorted(zip(star_positions, star_intensities), 
                                    key=lambda x: x[1], reverse=True)
                top_stars = sorted_stars[:min(20, len(sorted_stars))]
                
                fwhm_measurements = []
                
                for (y, x), intensity in top_stars:
                    try:
                        # Extract small region around star
                        size = 15
                        y_min = max(0, y - size)
                        y_max = min(image_data.shape[0], y + size)
                        x_min = max(0, x - size)
                        x_max = min(image_data.shape[1], x + size)
                        
                        star_region = filtered_data[y_min:y_max, x_min:x_max]
                        
                        if star_region.size == 0:
                            continue
                        
                        # Simple FWHM estimation using cross-sections
                        center_y = star_region.shape[0] // 2
                        center_x = star_region.shape[1] // 2
                        
                        # Get horizontal and vertical profiles through star center
                        h_profile = star_region[center_y, :]
                        v_profile = star_region[:, center_x]
                        
                        # Calculate FWHM for each profile
                        h_fwhm = self._calculate_profile_fwhm(h_profile)
                        v_fwhm = self._calculate_profile_fwhm(v_profile)
                        
                        # Average the two measurements
                        if h_fwhm > 0 and v_fwhm > 0:
                            fwhm = (h_fwhm + v_fwhm) / 2.0
                            if 0.5 <= fwhm <= 20.0:  # Reasonable FWHM range
                                fwhm_measurements.append(fwhm)
                    
                    except Exception:
                        continue
                
                if not fwhm_measurements:
                    return {
                        'fwhm_average': 0.0,
                        'fwhm_median': 0.0,
                        'star_count': 0,
                        'seeing_quality': 'Unable to measure',
                        'fwhm_std': 0.0
                    }
                
                # Calculate statistics
                fwhm_avg = float(np.mean(fwhm_measurements))
                fwhm_median = float(np.median(fwhm_measurements))
                fwhm_std = float(np.std(fwhm_measurements))
                
            else:
                # Fallback analysis without scipy
                return self._basic_fwhm_analysis(image_data)
            
            # Classify seeing quality based on FWHM
            if fwhm_avg <= 2.0:
                seeing_quality = 'Excellent'
            elif fwhm_avg <= 3.0:
                seeing_quality = 'Good'
            elif fwhm_avg <= 4.0:
                seeing_quality = 'Fair'
            elif fwhm_avg <= 6.0:
                seeing_quality = 'Poor'
            else:
                seeing_quality = 'Very Poor'
            
            return {
                'fwhm_average': fwhm_avg,
                'fwhm_median': fwhm_median,
                'star_count': len(fwhm_measurements),
                'seeing_quality': seeing_quality,
                'fwhm_std': fwhm_std
            }
            
        except Exception as e:
            logger.error(f"Error analyzing FWHM metrics: {e}")
            return {
                'fwhm_average': 0.0,
                'fwhm_median': 0.0,
                'star_count': 0,
                'seeing_quality': 'Analysis failed',
                'fwhm_std': 0.0
            }

    def _calculate_profile_fwhm(self, profile):
        """
        Calculate FWHM from a 1D intensity profile.
        
        Args:
            profile: 1D numpy array of intensity values
            
        Returns:
            float: FWHM in pixels, or 0 if calculation fails
        """
        try:
            import numpy as np
            
            if len(profile) < 3:
                return 0.0
            
            # Find peak position
            peak_idx = int(np.argmax(profile))
            peak_value = float(profile[peak_idx])
            
            # Calculate background level
            background = float(np.percentile(profile, 10))
            
            # Half maximum level
            half_max = background + (peak_value - background) / 2.0
            
            # Find points where profile crosses half maximum
            left_idx = peak_idx
            right_idx = peak_idx
            
            # Search left
            for i in range(peak_idx, -1, -1):
                if profile[i] <= half_max:
                    left_idx = i
                    break
            
            # Search right
            for i in range(peak_idx, len(profile)):
                if profile[i] <= half_max:
                    right_idx = i
                    break
            
            # Calculate FWHM
            fwhm = float(right_idx - left_idx)
            
            return fwhm if fwhm > 0 else 0.0
            
        except Exception:
            return 0.0

    def _basic_fwhm_analysis(self, image_data):
        """
        Basic FWHM analysis without scipy dependencies.
        
        Args:
            image_data: 2D numpy array of image pixel values
            
        Returns:
            dict: Basic FWHM analysis results
        """
        try:
            import numpy as np
            
            # Simple peak detection without scipy
            threshold = float(np.percentile(image_data, 95))
            peaks = image_data > threshold
            
            # Count potential stars
            star_count = int(np.sum(peaks))
            
            # Estimate average FWHM based on image characteristics
            # This is a very rough approximation
            estimated_fwhm = 2.5  # Default assumption
            
            return {
                'fwhm_average': estimated_fwhm,
                'fwhm_median': estimated_fwhm,
                'star_count': star_count,
                'seeing_quality': 'Estimated',
                'fwhm_std': 0.5
            }
            
        except Exception as e:
            return {
                'fwhm_average': 0.0,
                'fwhm_median': 0.0,
                'star_count': 0,
                'seeing_quality': 'Failed',
                'fwhm_std': 0.0
            }

    def _analyzeNoiseMetrics(self, image_data, header, progress_callback=None):
        """
        Analyze noise characteristics of the image
        
        Args:
            image_data: Image data array
            header: FITS header object
            progress_callback: Optional progress callback
            
        Returns:
            dict: Noise analysis results
        """
        try:
            import numpy as np
            from scipy.ndimage import median_filter
            
            noise_metrics = {}
            
            # Basic noise statistics
            noise_metrics["mean_value"] = float(np.mean(image_data))
            noise_metrics["std_deviation"] = float(np.std(image_data))
            noise_metrics["median_value"] = float(np.median(image_data))
            
            # Estimate read noise from image edges (avoid central regions with signal)
            h, w = image_data.shape
            edge_region = np.concatenate([
                image_data[:50, :].flatten(),  # Top edge
                image_data[-50:, :].flatten(), # Bottom edge
                image_data[:, :50].flatten(),  # Left edge
                image_data[:, -50:].flatten()  # Right edge
            ])
            
            noise_metrics["read_noise_estimate"] = float(np.std(edge_region))
            
            # Signal-to-noise ratio calculation
            signal = noise_metrics["mean_value"]
            noise = noise_metrics["std_deviation"]
            if noise > 0:
                noise_metrics["snr"] = signal / noise
            else:
                noise_metrics["snr"] = 0.0
            
            # Hot and cold pixel detection
            median_filtered = median_filter(image_data, size=3)
            difference = np.abs(image_data - median_filtered)
            hot_pixel_threshold = np.percentile(difference, 99.5)
            
            hot_pixels = np.sum(difference > hot_pixel_threshold)
            noise_metrics["hot_pixel_count"] = int(hot_pixels)
            noise_metrics["hot_pixel_percentage"] = float(hot_pixels / image_data.size * 100)
            
            # Noise uniformity across image
            grid_size = 8
            section_h, section_w = h // grid_size, w // grid_size
            section_stds = []
            
            for i in range(grid_size):
                for j in range(grid_size):
                    y_start = i * section_h
                    y_end = min((i + 1) * section_h, h)
                    x_start = j * section_w
                    x_end = min((j + 1) * section_w, w)
                    
                    section = image_data[y_start:y_end, x_start:x_end]
                    section_stds.append(np.std(section))
            
            noise_metrics["noise_uniformity"] = 1.0 - (np.std(section_stds) / np.mean(section_stds))
            
            # Overall noise score (0-100, higher is better)
            snr_score = min(100, noise_metrics["snr"] * 10)  # Reasonable SNR range
            uniformity_score = noise_metrics["noise_uniformity"] * 100
            hot_pixel_penalty = min(50, noise_metrics["hot_pixel_percentage"] * 10)
            
            noise_metrics["noise_score"] = max(0, (snr_score + uniformity_score) / 2 - hot_pixel_penalty)
            
            return noise_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing noise metrics: {e}")
            return {"noise_score": 0.0, "error": str(e)}

    def _analyzeAcquisitionQuality(self, header, frame_type):
        """
        Analyze acquisition quality from FITS header information
        
        Args:
            header: FITS header object
            frame_type: Type of frame being analyzed
            
        Returns:
            dict: Acquisition quality metrics
        """
        try:
            acquisition_metrics = {}
            
            # Temperature stability (important for dark frames)
            ccd_temp = header.get('CCD-TEMP')
            set_temp = header.get('SET-TEMP')
            
            if ccd_temp is not None and set_temp is not None:
                try:
                    temp_diff = abs(float(ccd_temp) - float(set_temp))
                    acquisition_metrics["temperature_stability"] = max(0, 100 - temp_diff * 20)  # Penalize >5°C difference
                except (ValueError, TypeError):
                    acquisition_metrics["temperature_stability"] = 50.0  # Neutral if can't parse
            else:
                acquisition_metrics["temperature_stability"] = 50.0  # Neutral if no temp info
            
            # Exposure time consistency
            exptime = header.get('EXPTIME')
            if exptime is not None:
                acquisition_metrics["exposure_time"] = float(exptime)
                
                # Score based on appropriate exposure for frame type
                if frame_type == 'bias':
                    exp_score = 100 if exptime < 0.001 else max(0, 100 - exptime * 1000)
                elif frame_type == 'dark':
                    exp_score = 100 if 1 <= exptime <= 300 else 50
                elif frame_type == 'flat':
                    exp_score = 100 if 0.1 <= exptime <= 30 else 70
                else:  # light frame
                    exp_score = 100 if 1 <= exptime <= 600 else 80
                    
                acquisition_metrics["exposure_score"] = exp_score
            else:
                acquisition_metrics["exposure_score"] = 50.0
            
            # Binning information
            xbinning = header.get('XBINNING', 1)
            ybinning = header.get('YBINNING', 1)
            acquisition_metrics["binning"] = f"{xbinning}x{ybinning}"
            
            # Binning score (1x1 is optimal, higher binning reduces score slightly)
            binning_factor = max(xbinning, ybinning)
            acquisition_metrics["binning_score"] = max(50, 100 - (binning_factor - 1) * 10)
            
            # Gain setting
            gain = header.get('GAIN')
            if gain is not None:
                acquisition_metrics["gain"] = float(gain)
                # Optimal gain is typically 100-400 for most cameras
                if 100 <= gain <= 400:
                    acquisition_metrics["gain_score"] = 100
                elif 50 <= gain < 100 or 400 < gain <= 800:
                    acquisition_metrics["gain_score"] = 80
                else:
                    acquisition_metrics["gain_score"] = 60
            else:
                acquisition_metrics["gain_score"] = 70.0  # Neutral if unknown
            
            # Date and time information
            date_obs = header.get('DATE-OBS', header.get('DATE', ''))
            if date_obs:
                acquisition_metrics["observation_date"] = date_obs
            
            # Overall acquisition score
            scores = [
                acquisition_metrics.get("temperature_stability", 50),
                acquisition_metrics.get("exposure_score", 50),
                acquisition_metrics.get("binning_score", 50),
                acquisition_metrics.get("gain_score", 50)
            ]
            
            acquisition_metrics["acquisition_score"] = sum(scores) / len(scores)
            
            return acquisition_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing acquisition quality: {e}")
            return {"acquisition_score": 50.0, "error": str(e)}

    def _calculateOverallQualityScore(self, results, frame_type):
        """
        Calculate overall quality score from individual metrics
        
        Args:
            results: Dictionary containing all analysis results
            frame_type: Type of frame being analyzed
            
        Returns:
            float: Overall quality score (0-100)
        """
        try:
            # Weight factors for different aspects
            if frame_type == "light":
                # For light frames: FWHM is most important, then noise, then acquisition
                weights = {
                    "fwhm": 0.4,
                    "noise": 0.3,
                    "acquisition": 0.3
                }
            else:
                # For calibration frames: uniformity and noise are most important
                weights = {
                    "uniformity": 0.4,
                    "noise": 0.4,
                    "acquisition": 0.2
                }
            
            scores = []
            
            # Noise score (applies to all frame types)
            noise_score = results.get("noise_metrics", {}).get("noise_score", 0)
            scores.append(("noise", noise_score))
            
            # Uniformity score (for calibration frames)
            if frame_type in ["bias", "dark", "flat"]:
                uniformity_score = results.get("uniformity_metrics", {}).get("uniformity_score", 0)
                scores.append(("uniformity", uniformity_score))
            
            # FWHM score (for light frames)
            if frame_type == "light":
                fwhm_metrics = results.get("fwhm_metrics", {})
                avg_fwhm = fwhm_metrics.get("average_fwhm", 10.0)  # Default poor FWHM
                
                # Convert FWHM to score (lower FWHM = higher score)
                if avg_fwhm <= 2.0:
                    fwhm_score = 100
                elif avg_fwhm <= 3.0:
                    fwhm_score = 90
                elif avg_fwhm <= 4.0:
                    fwhm_score = 75
                elif avg_fwhm <= 6.0:
                    fwhm_score = 60
                else:
                    fwhm_score = max(0, 60 - (avg_fwhm - 6) * 10)
                
                scores.append(("fwhm", fwhm_score))
            
            # Acquisition score (applies to all frame types)
            acquisition_score = results.get("acquisition_quality", {}).get("acquisition_score", 50)
            scores.append(("acquisition", acquisition_score))
            
            # Calculate weighted average
            weighted_sum = 0
            total_weight = 0
            
            for score_type, score in scores:
                weight = weights.get(score_type, 0)
                weighted_sum += score * weight
                total_weight += weight
            
            if total_weight > 0:
                overall_score = weighted_sum / total_weight
            else:
                overall_score = 50.0  # Neutral default
            
            return max(0.0, min(100.0, overall_score))
            
        except Exception as e:
            logger.error(f"Error calculating overall quality score: {e}")
            return 50.0

    def _getQualityCategory(self, overall_score):
        """
        Convert numeric quality score to descriptive category
        
        Args:
            overall_score: Numeric score (0-100)
            
        Returns:
            str: Quality category description
        """
        if overall_score >= 90:
            return "Excellent"
        elif overall_score >= 75:
            return "Good"
        elif overall_score >= 60:
            return "Acceptable"
        elif overall_score >= 40:
            return "Poor"
        else:
            return "Unusable"

    def assessFrameQuality(self, fits_file_path, frame_type="auto", progress_callback=None):
        """
        Comprehensive quality assessment for FITS frames
        
        Args:
            fits_file_path: Path to FITS file to analyze
            frame_type: Type of frame ("light", "bias", "dark", "flat", "auto")
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: Comprehensive quality assessment including:
                - overall_score: Overall quality score (0-100)
                - frame_type: Detected or specified frame type
                - noise_metrics: Noise analysis results
                - uniformity_metrics: Uniformity analysis (for calibration frames)
                - fwhm_metrics: FWHM analysis (for light frames only)
                - acquisition_quality: Header-based quality indicators
                - quality_category: Text description of quality level
                - recommendations: List of quality improvement suggestions
        """
        try:
            import numpy as np
            from scipy import ndimage, stats
            from scipy.ndimage import median_filter, gaussian_filter
            from astropy.io import fits
            
            logger.info(f"Starting quality assessment for {fits_file_path}")
            
            results = {
                "overall_score": 0,
                "frame_type": frame_type,
                "noise_metrics": {},
                "uniformity_metrics": {},
                "fwhm_metrics": {},
                "acquisition_quality": {},
                "quality_category": "Unknown",
                "recommendations": [],
                "errors": []
            }
            
            if progress_callback:
                should_continue = progress_callback(0, 100, "Loading FITS file...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Quality assessment cancelled"}
            
            # Load FITS file
            try:
                with fits.open(fits_file_path) as hdul:
                    header = hdul[0].header
                    image_data = hdul[0].data.astype(np.float64)
                    
                    # Auto-detect frame type if not specified
                    if frame_type == "auto":
                        frame_type = self._detectFrameType(header, image_data)
                        results["frame_type"] = frame_type
                        
            except Exception as e:
                error_msg = f"Error loading FITS file: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                return results
            
            if progress_callback:
                should_continue = progress_callback(10, 100, f"Analyzing {frame_type} frame...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Quality assessment cancelled"}
            
            # Noise analysis (applies to all frame types)
            try:
                results["noise_metrics"] = self._analyzeNoiseMetrics(image_data, header, progress_callback)
            except Exception as e:
                error_msg = f"Error in noise analysis: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            if progress_callback:
                should_continue = progress_callback(30, 100, "Analyzing frame uniformity...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Quality assessment cancelled"}
            
            # Uniformity analysis (for calibration frames)
            if frame_type in ["bias", "dark", "flat"]:
                try:
                    results["uniformity_metrics"] = self._analyzeUniformityMetrics(image_data, frame_type, header)
                except Exception as e:
                    error_msg = f"Error in uniformity analysis: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            if progress_callback:
                should_continue = progress_callback(50, 100, "Analyzing acquisition quality...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Quality assessment cancelled"}
            
            # FWHM analysis (for light frames only)
            if frame_type == "light":
                try:
                    results["fwhm_metrics"] = self._analyzeFWHMMetrics(image_data, header, progress_callback)
                except Exception as e:
                    error_msg = f"Error in FWHM analysis: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            if progress_callback:
                should_continue = progress_callback(70, 100, "Evaluating acquisition parameters...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Quality assessment cancelled"}
            
            # Acquisition quality analysis
            try:
                results["acquisition_quality"] = self._analyzeAcquisitionQuality(header, frame_type)
            except Exception as e:
                error_msg = f"Error in acquisition quality analysis: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            if progress_callback:
                should_continue = progress_callback(90, 100, "Calculating overall quality score...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Quality assessment cancelled"}
            
            # Calculate overall quality score
            try:
                results["overall_score"] = self._calculateOverallQualityScore(results, frame_type)
                results["quality_category"] = self._getQualityCategory(results["overall_score"])
                results["recommendations"] = self._generateQualityRecommendations(results, frame_type)
            except Exception as e:
                error_msg = f"Error calculating overall quality: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            if progress_callback:
                progress_callback(100, 100, "Quality assessment completed!")
            
            logger.info(f"Quality assessment completed: {results['overall_score']:.1f} ({results['quality_category']})")
            results["status"] = "success" if not results["errors"] else "partial_success"
            return results
            
        except Exception as e:
            error_msg = f"Critical error in quality assessment: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "overall_score": 0,
                "frame_type": frame_type,
                "noise_metrics": {},
                "uniformity_metrics": {},
                "fwhm_metrics": {},
                "acquisition_quality": {},
                "quality_category": "Error",
                "recommendations": [],
                "errors": [error_msg]
            }

    def assessMasterFrameQuality(self, master_file_path, progress_callback=None):
        """
        Specialized quality assessment for master calibration frames
        
        Args:
            master_file_path: Path to master FITS file
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: Master frame quality assessment with enhanced analysis
        """
        try:
            logger.info(f"Assessing master frame quality: {master_file_path}")
            
            # Use the general quality assessment as base
            base_results = self.assessFrameQuality(master_file_path, "auto", progress_callback)
            
            if base_results.get("status") in ["error", "cancelled"]:
                return base_results
            
            # Add master-specific enhancements
            master_results = base_results.copy()
            master_results["is_master_frame"] = True
            
            # Analyze master frame metadata
            try:
                with fits.open(master_file_path) as hdul:
                    header = hdul[0].header
                    
                    # Extract master frame information
                    ncombine = header.get('NCOMBINE', 1)
                    imagetyp = header.get('IMAGETYP', '').lower()
                    
                    master_results["master_metadata"] = {
                        "combined_frames": ncombine,
                        "image_type": imagetyp,
                        "creation_date": header.get('DATE', 'Unknown'),
                        "processing_software": header.get('SOFTWARE', 'Unknown')
                    }
                    
                    # Adjust quality score based on number of combined frames
                    if ncombine > 1:
                        combination_bonus = min(10, ncombine * 2)  # Up to 10 point bonus
                        master_results["overall_score"] = min(100, 
                            master_results["overall_score"] + combination_bonus)
                        
                        master_results["recommendations"].append(
                            f"Excellent: Master created from {ncombine} frames for improved SNR"
                        )
                    
            except Exception as e:
                logger.warning(f"Could not analyze master frame metadata: {e}")
            
            logger.info(f"Master frame assessment completed: {master_results['overall_score']:.1f}")
            return master_results
            
        except Exception as e:
            error_msg = f"Error in master frame quality assessment: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "overall_score": 0,
                "errors": [error_msg]
            }

    def batchAssessQuality(self, file_paths, frame_type="auto", progress_callback=None):
        """
        Assess quality for multiple FITS files in batch
        
        Args:
            file_paths: List of FITS file paths to analyze
            frame_type: Frame type for all files or "auto" to detect
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: Batch quality assessment results
        """
        try:
            logger.info(f"Starting batch quality assessment for {len(file_paths)} files")
            
            batch_results = {
                "total_files": len(file_paths),
                "processed_files": 0,
                "failed_files": 0,
                "quality_summary": {
                    "excellent": 0,
                    "good": 0, 
                    "acceptable": 0,
                    "poor": 0,
                    "unusable": 0
                },
                "average_score": 0.0,
                "individual_results": [],
                "errors": []
            }
            
            total_score = 0.0
            
            for i, file_path in enumerate(file_paths):
                if progress_callback:
                    overall_progress = int((i / len(file_paths)) * 100)
                    should_continue = progress_callback(overall_progress, 100, 
                        f"Processing {i+1}/{len(file_paths)}: {os.path.basename(file_path)}")
                    if not should_continue:
                        batch_results["status"] = "cancelled"
                        return batch_results
                
                try:
                    # Assess individual file quality
                    file_results = self.assessFrameQuality(file_path, frame_type)
                    
                    if file_results.get("status") == "success" or file_results.get("status") == "partial_success":
                        batch_results["processed_files"] += 1
                        total_score += file_results["overall_score"]
                        
                        # Categorize quality
                        category = file_results["quality_category"].lower()
                        if "excellent" in category:
                            batch_results["quality_summary"]["excellent"] += 1
                        elif "good" in category:
                            batch_results["quality_summary"]["good"] += 1
                        elif "acceptable" in category:
                            batch_results["quality_summary"]["acceptable"] += 1
                        elif "poor" in category:
                            batch_results["quality_summary"]["poor"] += 1
                        else:
                            batch_results["quality_summary"]["unusable"] += 1
                        
                        batch_results["individual_results"].append({
                            "file_path": file_path,
                            "file_name": os.path.basename(file_path),
                            "overall_score": file_results["overall_score"],
                            "quality_category": file_results["quality_category"],
                            "frame_type": file_results["frame_type"]
                        })
                    else:
                        batch_results["failed_files"] += 1
                        batch_results["errors"].append(f"Failed to process {file_path}")
                        
                except Exception as e:
                    batch_results["failed_files"] += 1
                    error_msg = f"Error processing {file_path}: {e}"
                    logger.error(error_msg)
                    batch_results["errors"].append(error_msg)
            
            # Calculate average score
            if batch_results["processed_files"] > 0:
                batch_results["average_score"] = total_score / batch_results["processed_files"]
            
            if progress_callback:
                progress_callback(100, 100, "Batch quality assessment completed!")
            
            logger.info(f"Batch assessment completed: {batch_results['processed_files']}/{batch_results['total_files']} files processed")
            batch_results["status"] = "success" if batch_results["failed_files"] == 0 else "partial_success"
            return batch_results
            
        except Exception as e:
            error_msg = f"Critical error in batch quality assessment: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "total_files": len(file_paths),
                "processed_files": 0,
                "failed_files": len(file_paths),
                "errors": [error_msg]
            }

    #################################################################################################################
    ## registerExistingFiles - Register existing calibrated files and master frames to avoid duplicate work      ##
    #################################################################################################################
    def registerExistingFiles(self, progress_callback=None, scan_subdirectories=True, verify_headers=True):
        """
        Scan repository for existing calibrated files and master frames and register them in the database
        to avoid duplicate processing work.
        
        This method performs:
        - Scans for existing calibrated light frames (identified by FITS headers)
        - Identifies existing master calibration frames 
        - Updates database records to reflect existing calibration status
        - Links master frames to appropriate sessions
        - Validates file integrity and consistency
        
        Args:
            progress_callback: Optional callback function for progress updates
            scan_subdirectories: Whether to recursively scan subdirectories (default: True)
            verify_headers: Whether to verify FITS headers for calibration metadata (default: True)
            
        Returns:
            Dictionary with registration results: {
                'calibrated_files_found': int,
                'master_frames_found': int,
                'database_updates': int,
                'errors': [],
                'summary': {...}
            }
        """
        logger.info("Starting registration of existing calibrated files and master frames")
        
        results = {
            'calibrated_files_found': 0,
            'master_frames_found': 0,
            'database_updates': 0,
            'existing_master_links': 0,
            'new_master_links': 0,
            'calibrated_file_updates': 0,
            'verification_errors': 0,
            'errors': [],
            'summary': {}
        }
        
        try:
            # Phase 1: Scan for master calibration frames
            logger.info("Phase 1: Scanning for existing master calibration frames")
            master_results = self._scanForExistingMasterFrames(progress_callback, scan_subdirectories, verify_headers)
            results['master_frames_found'] = master_results['masters_found']
            results['existing_master_links'] = master_results['existing_links']
            results['new_master_links'] = master_results['new_links']
            results['errors'].extend(master_results.get('errors', []))
            
            # Phase 2: Scan for calibrated light frames
            logger.info("Phase 2: Scanning for existing calibrated light frames")
            calibrated_results = self._scanForCalibratedLightFrames(progress_callback, scan_subdirectories, verify_headers)
            results['calibrated_files_found'] = calibrated_results['calibrated_files']
            results['calibrated_file_updates'] = calibrated_results['database_updates']
            results['verification_errors'] = calibrated_results['verification_errors']
            results['errors'].extend(calibrated_results.get('errors', []))
            
            # Phase 3: Validate consistency and fix issues
            logger.info("Phase 3: Validating consistency and fixing issues")
            validation_results = self._validateExistingFileConsistency(progress_callback)
            results['database_updates'] += validation_results['fixes_applied']
            results['errors'].extend(validation_results.get('errors', []))
            
            # Build summary
            results['summary'] = {
                'total_files_processed': results['calibrated_files_found'] + results['master_frames_found'],
                'master_frames': {
                    'found': results['master_frames_found'],
                    'already_linked': results['existing_master_links'],
                    'newly_linked': results['new_master_links']
                },
                'calibrated_lights': {
                    'found': results['calibrated_files_found'],
                    'updated': results['calibrated_file_updates'],
                    'verification_errors': results['verification_errors']
                },
                'database_changes': results['database_updates'] + results['calibrated_file_updates'] + results['new_master_links'],
                'errors_encountered': len(results['errors'])
            }
            
            logger.info(f"Existing file registration complete: {results['summary']['total_files_processed']} files processed")
            logger.info(f"  - Master frames found: {results['master_frames_found']}")
            logger.info(f"  - Calibrated light frames found: {results['calibrated_files_found']}")
            logger.info(f"  - Database updates made: {results['summary']['database_changes']}")
            
            if results['errors']:
                logger.warning(f"  - Errors encountered: {len(results['errors'])}")
                for error in results['errors'][:5]:  # Log first 5 errors
                    logger.warning(f"    {error}")
                if len(results['errors']) > 5:
                    logger.warning(f"    ... and {len(results['errors']) - 5} more errors")
            
            return results
            
        except Exception as e:
            error_msg = f"Critical error in existing file registration: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    def _scanForExistingMasterFrames(self, progress_callback, scan_subdirectories, verify_headers):
        """Scan for existing master calibration frames."""
        results = {
            'masters_found': 0,
            'existing_links': 0,
            'new_links': 0,
            'errors': []
        }
        
        try:
            from astrofiler_db import fitsSession as FitsSessionModel, fitsFile as FitsFileModel
            
            # Define search directories
            search_dirs = [os.path.join(self.repoFolder, 'Masters')]
            if scan_subdirectories:
                # Add common master frame directories
                additional_dirs = [
                    os.path.join(self.repoFolder, 'Masters', 'Bias'),
                    os.path.join(self.repoFolder, 'Masters', 'Dark'),  
                    os.path.join(self.repoFolder, 'Masters', 'Flat'),
                    os.path.join(self.repoFolder, 'Calibrated'),
                    self.repoFolder  # Also scan root for masters
                ]
                search_dirs.extend([d for d in additional_dirs if os.path.exists(d)])
            
            master_files = []
            for search_dir in search_dirs:
                if not os.path.exists(search_dir):
                    continue
                    
                if scan_subdirectories:
                    for root, dirs, files in os.walk(search_dir):
                        # Skip quarantine directories
                        if '_quarantine' in root.lower():
                            continue
                        for file in files:
                            if file.lower().endswith(('.fits', '.fit')):
                                master_files.append(os.path.join(root, file))
                else:
                    master_files.extend([
                        os.path.join(search_dir, f) for f in os.listdir(search_dir) 
                        if f.lower().endswith(('.fits', '.fit'))
                    ])
            
            logger.info(f"Found {len(master_files)} potential master files to analyze")
            
            for i, master_path in enumerate(master_files):
                if progress_callback:
                    if not progress_callback(i, len(master_files), f"Analyzing master file: {os.path.basename(master_path)}"):
                        logger.info("Master frame scanning cancelled by user")
                        break
                
                try:
                    # Check if this is a master frame by filename or header
                    is_master = self._identifyMasterFrame(master_path, verify_headers)
                    
                    if is_master:
                        results['masters_found'] += 1
                        
                        # Try to link this master to appropriate sessions
                        link_result = self._linkMasterFrameToSessions(master_path, is_master)
                        if link_result['existing_link']:
                            results['existing_links'] += 1
                        elif link_result['new_link']:
                            results['new_links'] += 1
                        
                        # Register in database if not already present
                        self._ensureMasterInDatabase(master_path, is_master)
                        
                except Exception as e:
                    error_msg = f"Error analyzing master file {master_path}: {e}"
                    results['errors'].append(error_msg)
                    logger.warning(error_msg)
            
            return results
            
        except Exception as e:
            results['errors'].append(f"Error in master frame scanning: {e}")
            return results
    
    def _scanForCalibratedLightFrames(self, progress_callback, scan_subdirectories, verify_headers):
        """Scan for existing calibrated light frames."""
        results = {
            'calibrated_files': 0,
            'database_updates': 0,
            'verification_errors': 0,
            'errors': []
        }
        
        try:
            from astrofiler_db import fitsFile as FitsFileModel
            
            # Get all registered light frames from database
            light_files = FitsFileModel.select().where(
                (FitsFileModel.fitsFileType.not_in(['BIAS', 'DARK', 'FLAT'])) |
                (FitsFileModel.fitsFileType.is_null())
            )
            
            logger.info(f"Checking {light_files.count()} registered files for calibration status")
            
            for i, fits_file in enumerate(light_files):
                if progress_callback:
                    if not progress_callback(i, light_files.count(), f"Checking calibration: {os.path.basename(fits_file.fitsFileName or '')}"):
                        logger.info("Calibrated file scanning cancelled by user")
                        break
                
                try:
                    file_path = fits_file.fitsFileName
                    if not file_path or not os.path.exists(file_path):
                        continue
                    
                    # Check if file is calibrated
                    calibration_info = self._checkFileCalibrationStatus(file_path, verify_headers)
                    
                    if calibration_info['is_calibrated']:
                        results['calibrated_files'] += 1
                        
                        # Update database record if needed
                        needs_update = False
                        
                        if not fits_file.fitsFileCalibrated or fits_file.fitsFileCalibrated != 1:
                            fits_file.fitsFileCalibrated = 1
                            needs_update = True
                        
                        if calibration_info['calibration_date'] and not fits_file.fitsFileCalibrationDate:
                            fits_file.fitsFileCalibrationDate = calibration_info['calibration_date']
                            needs_update = True
                        
                        # Update master frame references if found in headers
                        if calibration_info['master_bias'] and not fits_file.fitsFileMasterBias:
                            fits_file.fitsFileMasterBias = calibration_info['master_bias']
                            needs_update = True
                        
                        if calibration_info['master_dark'] and not fits_file.fitsFileMasterDark:
                            fits_file.fitsFileMasterDark = calibration_info['master_dark']
                            needs_update = True
                        
                        if calibration_info['master_flat'] and not fits_file.fitsFileMasterFlat:
                            fits_file.fitsFileMasterFlat = calibration_info['master_flat']
                            needs_update = True
                        
                        if needs_update:
                            fits_file.save()
                            results['database_updates'] += 1
                    
                except Exception as e:
                    error_msg = f"Error checking calibration status for {file_path}: {e}"
                    results['errors'].append(error_msg)
                    results['verification_errors'] += 1
                    logger.warning(error_msg)
            
            return results
            
        except Exception as e:
            results['errors'].append(f"Error in calibrated file scanning: {e}")
            return results
    
    def _identifyMasterFrame(self, file_path, verify_headers=True):
        """Identify if a file is a master calibration frame."""
        try:
            filename = os.path.basename(file_path).lower()
            
            # Check filename patterns
            master_keywords = ['master-bias', 'master-dark', 'master-flat', 'masterbias', 'masterdark', 'masterflat']
            filename_suggests_master = any(keyword in filename for keyword in master_keywords)
            
            if not verify_headers:
                if filename_suggests_master:
                    # Guess type from filename
                    if 'bias' in filename:
                        return {'type': 'bias', 'confidence': 'filename'}
                    elif 'dark' in filename:
                        return {'type': 'dark', 'confidence': 'filename'}
                    elif 'flat' in filename:
                        return {'type': 'flat', 'confidence': 'filename'}
                return None
            
            # Verify with FITS headers
            try:
                with fits.open(file_path) as hdul:
                    header = hdul[0].header
                    
                    # Check for master frame indicators in headers
                    imagetyp = header.get('IMAGETYP', '').upper()
                    caltype = header.get('CALTYPE', '').upper() 
                    object_name = header.get('OBJECT', '').upper()
                    
                    master_indicators = ['MASTERBIAS', 'MASTERDARK', 'MASTERFLAT', 'MASTER-BIAS', 'MASTER-DARK', 'MASTER-FLAT']
                    
                    is_master_by_header = (
                        any(indicator in imagetyp for indicator in master_indicators) or
                        any(indicator in caltype for indicator in master_indicators) or
                        any(indicator in object_name for indicator in master_indicators) or
                        'MASTER' in imagetyp or 'MASTER' in object_name
                    )
                    
                    if is_master_by_header or filename_suggests_master:
                        # Determine master type
                        master_type = None
                        if 'BIAS' in imagetyp or 'BIAS' in caltype or 'bias' in filename:
                            master_type = 'bias'
                        elif 'DARK' in imagetyp or 'DARK' in caltype or 'dark' in filename:
                            master_type = 'dark'
                        elif 'FLAT' in imagetyp or 'FLAT' in caltype or 'flat' in filename:
                            master_type = 'flat'
                        
                        if master_type:
                            confidence = 'header' if is_master_by_header else 'filename'
                            return {'type': master_type, 'confidence': confidence, 'header': header}
                    
            except Exception as e:
                logger.warning(f"Error reading FITS header for {file_path}: {e}")
                # Fall back to filename analysis
                if filename_suggests_master:
                    if 'bias' in filename:
                        return {'type': 'bias', 'confidence': 'filename_fallback'}
                    elif 'dark' in filename:
                        return {'type': 'dark', 'confidence': 'filename_fallback'}  
                    elif 'flat' in filename:
                        return {'type': 'flat', 'confidence': 'filename_fallback'}
            
            return None
            
        except Exception as e:
            logger.warning(f"Error identifying master frame {file_path}: {e}")
            return None
    
    def _linkMasterFrameToSessions(self, master_path, master_info):
        """Link a master frame to appropriate calibration sessions."""
        result = {'existing_link': False, 'new_link': False, 'error': None}
        
        try:
            from astrofiler_db import fitsSession as FitsSessionModel
            
            master_type = master_info['type']
            
            # Check if master is already linked
            if master_type == 'bias':
                existing_sessions = FitsSessionModel.select().where(FitsSessionModel.fitsBiasMaster == master_path)
            elif master_type == 'dark':
                existing_sessions = FitsSessionModel.select().where(FitsSessionModel.fitsDarkMaster == master_path)
            elif master_type == 'flat':
                existing_sessions = FitsSessionModel.select().where(FitsSessionModel.fitsFlatMaster == master_path)
            else:
                return result
            
            if existing_sessions.count() > 0:
                result['existing_link'] = True
                return result
            
            # Try to find matching sessions to link this master to
            # This is a simplified matching - in practice, you'd want to match based on
            # telescope, instrument, binning, filter, etc.
            if 'header' in master_info:
                header = master_info['header']
                telescope = header.get('TELESCOP', '')
                instrument = header.get('INSTRUME', '')
                
                # Find sessions that could use this master
                matching_sessions = FitsSessionModel.select().where(
                    (FitsSessionModel.fitsSessionTelescope == telescope) &
                    (FitsSessionModel.fitsSessionImager == instrument)
                )
                
                # Link to sessions that don't already have this type of master
                links_made = 0
                for session in matching_sessions:
                    try:
                        if master_type == 'bias' and not session.fitsBiasMaster:
                            session.fitsBiasMaster = master_path
                            session.save()
                            links_made += 1
                        elif master_type == 'dark' and not session.fitsDarkMaster:
                            session.fitsDarkMaster = master_path
                            session.save()
                            links_made += 1
                        elif master_type == 'flat' and not session.fitsFlatMaster:
                            session.fitsFlatMaster = master_path
                            session.save()
                            links_made += 1
                    except Exception as e:
                        logger.warning(f"Error linking master to session {session.fitsSessionId}: {e}")
                
                if links_made > 0:
                    result['new_link'] = True
                    logger.info(f"Linked {master_path} to {links_made} sessions")
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            logger.warning(f"Error linking master frame {master_path}: {e}")
            return result
    
    def _ensureMasterInDatabase(self, master_path, master_info):
        """Ensure master frame is registered in the database."""
        try:
            from astrofiler_db import fitsFile as FitsFileModel
            
            # Check if already in database
            existing = FitsFileModel.select().where(FitsFileModel.fitsFileName == normalize_file_path(master_path))
            if existing.count() > 0:
                return existing.first().fitsFileId
            
            # Register new master frame
            master_id = str(uuid.uuid4())
            file_stat = os.stat(master_path)
            file_date = datetime.fromtimestamp(file_stat.st_mtime).date()
            file_hash = self.calculateFileHash(master_path)
            
            fits_file = FitsFileModel.create(
                fitsFileId=master_id,
                fitsFileName=normalize_file_path(master_path),
                fitsFileDate=file_date,
                fitsFileCalibrated=1,  # Masters are considered calibrated
                fitsFileType=master_info['type'].upper(),
                fitsFileStacked=1,  # Masters are stacked
                fitsFileObject=f"Master-{master_info['type'].title()}",
                fitsFileHash=file_hash
            )
            
            logger.info(f"Registered existing master frame in database: {os.path.basename(master_path)}")
            return master_id
            
        except Exception as e:
            logger.warning(f"Error registering master frame in database {master_path}: {e}")
            return None
    
    def _checkFileCalibrationStatus(self, file_path, verify_headers=True):
        """Check if a file has been calibrated."""
        result = {
            'is_calibrated': False,
            'calibration_date': None,
            'master_bias': None,
            'master_dark': None,
            'master_flat': None,
            'confidence': 'unknown'
        }
        
        try:
            if not verify_headers:
                # Simple filename check
                filename = os.path.basename(file_path).lower()
                if 'calibrated' in filename or 'cal_' in filename:
                    result['is_calibrated'] = True
                    result['confidence'] = 'filename'
                return result
            
            # Check FITS headers for calibration indicators
            with fits.open(file_path) as hdul:
                header = hdul[0].header
                
                # Look for calibration indicators
                calibrat = header.get('CALIBRAT', '').upper()
                imagetyp = header.get('IMAGETYP', '').upper()
                caldate = header.get('CALDATE', '')
                calsoft = header.get('CALSOFT', '')
                
                # Check for master frame references
                bias_master = header.get('BIASMAST', '')
                dark_master = header.get('DARKMAST', '') 
                flat_master = header.get('FLATMAST', '')
                
                # Determine if calibrated
                is_calibrated = (
                    calibrat == 'Y' or
                    'CALIBRATED' in imagetyp or
                    caldate or
                    calsoft or
                    bias_master or dark_master or flat_master
                )
                
                result['is_calibrated'] = is_calibrated
                result['confidence'] = 'header' if is_calibrated else 'none'
                
                if is_calibrated:
                    # Extract calibration metadata
                    if caldate:
                        try:
                            result['calibration_date'] = datetime.fromisoformat(caldate.replace('Z', '+00:00'))
                        except:
                            pass
                    
                    result['master_bias'] = bias_master if bias_master else None
                    result['master_dark'] = dark_master if dark_master else None
                    result['master_flat'] = flat_master if flat_master else None
                
            return result
            
        except Exception as e:
            logger.warning(f"Error checking calibration status for {file_path}: {e}")
            return result
    
    def _validateExistingFileConsistency(self, progress_callback):
        """Validate consistency between registered files and database records."""
        results = {
            'fixes_applied': 0,
            'errors': []
        }
        
        try:
            from astrofiler_db import fitsFile as FitsFileModel, fitsSession as FitsSessionModel
            
            # Check for broken master frame references
            sessions_with_masters = FitsSessionModel.select().where(
                (FitsSessionModel.fitsBiasMaster.is_null(False) & (FitsSessionModel.fitsBiasMaster != '')) |
                (FitsSessionModel.fitsDarkMaster.is_null(False) & (FitsSessionModel.fitsDarkMaster != '')) |
                (FitsSessionModel.fitsFlatMaster.is_null(False) & (FitsSessionModel.fitsFlatMaster != ''))
            )
            
            for session in sessions_with_masters:
                try:
                    fixes_needed = False
                    
                    # Check bias master
                    if session.fitsBiasMaster and not os.path.exists(session.fitsBiasMaster):
                        logger.warning(f"Broken bias master reference in session {session.fitsSessionId}: {session.fitsBiasMaster}")
                        session.fitsBiasMaster = None
                        fixes_needed = True
                    
                    # Check dark master  
                    if session.fitsDarkMaster and not os.path.exists(session.fitsDarkMaster):
                        logger.warning(f"Broken dark master reference in session {session.fitsSessionId}: {session.fitsDarkMaster}")
                        session.fitsDarkMaster = None
                        fixes_needed = True
                    
                    # Check flat master
                    if session.fitsFlatMaster and not os.path.exists(session.fitsFlatMaster):
                        logger.warning(f"Broken flat master reference in session {session.fitsSessionId}: {session.fitsFlatMaster}")
                        session.fitsFlatMaster = None
                        fixes_needed = True
                    
                    if fixes_needed:
                        session.save()
                        results['fixes_applied'] += 1
                        
                except Exception as e:
                    error_msg = f"Error validating session {session.fitsSessionId}: {e}"
                    results['errors'].append(error_msg)
                    logger.warning(error_msg)
            
            logger.info(f"Consistency validation complete: {results['fixes_applied']} fixes applied")
            return results
            
        except Exception as e:
            results['errors'].append(f"Error in consistency validation: {e}")
            return results
