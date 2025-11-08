"""
Core file processing module for AstroFiler.

This module handles FITS file registration, header processing, hash calculation,
and database operations for importing astronomical images.
"""

import os
import hashlib
import logging
import uuid
import zipfile
import configparser
from datetime import datetime
from math import cos, sin
from astropy.io import fits
from peewee import IntegrityError

from .utils import normalize_file_path, sanitize_filesystem_name, dwarfFixHeader, mapFitsHeader

logger = logging.getLogger(__name__)


class FileProcessor:
    """
    Handles FITS file processing operations including registration and database operations.
    """
    
    def __init__(self):
        """Initialize FileProcessor with configuration."""
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        self.sourceFolder = config.get('DEFAULT', 'source', fallback='.')
        self.repoFolder = config.get('DEFAULT', 'repo', fallback='.')

    def calculateFileHash(self, filePath):
        """
        Calculate SHA-256 hash of a file for duplicate detection.
        
        Args:
            filePath (str): Path to the file
            
        Returns:
            str or None: SHA-256 hash hex string, or None if error
        """
        try:
            hash_sha256 = hashlib.sha256()
            with open(filePath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {filePath}: {str(e)}")
            return None

    def _is_master_file(self, file_path):
        """
        Check if a file is a master calibration frame that should be handled specially.
        
        Args:
            file_path (str): Full path to the file
            
        Returns:
            bool: True if this is a master file
        """
        # Normalize path separators
        normalized_path = os.path.normpath(file_path)
        path_parts = normalized_path.split(os.sep)
        
        # Check if file is in a Masters directory
        if 'Masters' in path_parts:
            return True
        
        # Check for master-related naming patterns
        filename = os.path.basename(file_path).lower()
        master_patterns = [
            'master',
            'masterbias',
            'masterdark', 
            'masterflat',
            'master_bias',
            'master_dark',
            'master_flat',
            'bias_master',
            'dark_master', 
            'flat_master'
        ]
        
        for pattern in master_patterns:
            if pattern in filename:
                return True
        
        return False

    def _register_master_file(self, file_path):
        """
        Register a master calibration frame in the Masters table.
        
        Args:
            file_path (str): Full path to the master file
            
        Returns:
            str or None: Master ID if successful, None if failed
        """
        try:
            # Import here to avoid circular imports
            try:
                from astrofiler_db import Masters
            except ImportError:
                logger.warning("Masters table not available yet. Skipping master file registration.")
                return None
            
            # Open the FITS file to read header
            with fits.open(file_path, mode='readonly') as hdul:
                hdr = hdul[0].header
            
            # Determine master type from filename or header
            master_type = self._determine_master_type(file_path, hdr)
            if not master_type:
                logger.warning(f"Could not determine master type for {file_path}")
                return None
            
            # Extract session data from header
            session_data = {
                'telescope': hdr.get('TELESCOP', 'Unknown'),
                'instrument': hdr.get('INSTRUME', 'Unknown'),
                'binning_x': str(hdr.get('XBINNING', '1')),
                'binning_y': str(hdr.get('YBINNING', '1')),
                'ccd_temp': str(hdr.get('CCD-TEMP', '')),
                'gain': str(hdr.get('GAIN', '')),
                'offset': str(hdr.get('OFFSET', '')),
                'session_id': None  # No source session for existing masters
            }
            
            # Add type-specific data
            if master_type == 'dark':
                session_data['exposure_time'] = str(hdr.get('EXPTIME', hdr.get('EXPOSURE', '')))
            elif master_type == 'flat':
                session_data['filter_name'] = hdr.get('FILTER', '')
            
            # Get file count from header if available
            file_count = hdr.get('NCOMBINE', hdr.get('NIMAGES', 0))
            if isinstance(file_count, str):
                try:
                    file_count = int(file_count)
                except ValueError:
                    file_count = 0
            
            # Check if this master already exists
            existing_master = Masters.find_matching_master(
                session_data['telescope'],
                session_data['instrument'], 
                master_type,
                **{k: v for k, v in session_data.items() 
                   if k not in ['telescope', 'instrument', 'session_id'] and v}
            )
            
            if existing_master:
                logger.info(f"Master {master_type} already exists in database: {existing_master.master_id}")
                # Update path if different
                if existing_master.master_path != file_path:
                    existing_master.master_path = file_path
                    existing_master.save()
                    logger.info(f"Updated master path: {file_path}")
                return existing_master.master_id
            
            # Create new master record
            master = Masters.create_master_record(
                master_path=file_path,
                session_data=session_data,
                cal_type=master_type,
                file_count=file_count
            )
            
            # Validate the file
            if master.validate_and_mark():
                logger.info(f"Successfully registered master {master_type}: {master.master_id}")
                return master.master_id
            else:
                logger.warning(f"Master file validation failed: {file_path}")
                return master.master_id  # Still return ID even if validation failed
                
        except Exception as e:
            logger.error(f"Error registering master file {file_path}: {e}")
            # If it's a database error (table doesn't exist), provide more specific info
            if "no such table" in str(e).lower() or "masters" in str(e).lower():
                logger.info("Masters table not created yet. Run migrations to create Masters table.")
            return None

    def _determine_master_type(self, file_path, hdr):
        """
        Determine the type of master calibration frame.
        
        Args:
            file_path (str): Path to the file
            hdr: FITS header
            
        Returns:
            str or None: 'bias', 'dark', 'flat', or None if undetermined
        """
        # Check filename for master type indicators
        filename = os.path.basename(file_path).lower()
        
        if any(pattern in filename for pattern in ['bias', 'masterbias', 'master_bias', 'bias_master']):
            return 'bias'
        elif any(pattern in filename for pattern in ['dark', 'masterdark', 'master_dark', 'dark_master']):
            return 'dark'
        elif any(pattern in filename for pattern in ['flat', 'masterflat', 'master_flat', 'flat_master']):
            return 'flat'
        
        # Check FITS header
        imagetyp = hdr.get('IMAGETYP', '').upper()
        if 'BIAS' in imagetyp:
            return 'bias'
        elif 'DARK' in imagetyp:
            return 'dark'
        elif 'FLAT' in imagetyp:
            return 'flat'
        
        # Check OBJECT field for master indicators
        object_name = hdr.get('OBJECT', '').lower()
        if 'bias' in object_name or 'master-bias' in object_name:
            return 'bias'
        elif 'dark' in object_name or 'master-dark' in object_name:
            return 'dark'
        elif 'flat' in object_name or 'master-flat' in object_name:
            return 'flat'
        
        return None

    def extractZipFile(self, zip_path):
        """
        Extract FITS file from a zip archive.
        
        Args:
            zip_path (str): Path to the zip file
            
        Returns:
            str or None: Path to extracted FITS file, or None if failed
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # List all files in the zip
                file_list = zip_ref.namelist()
                
                # Find FITS files
                fits_files = [f for f in file_list if f.lower().endswith(('.fit', '.fits', '.fts'))]
                
                if not fits_files:
                    logger.error(f"No FITS files found in {zip_path}")
                    return None
                
                if len(fits_files) > 1:
                    logger.warning(f"Multiple FITS files found in {zip_path}, using first one: {fits_files[0]}")
                
                fits_file = fits_files[0]
                
                # Extract to the same directory as the zip file
                extract_dir = os.path.dirname(zip_path)
                extracted_path = zip_ref.extract(fits_file, extract_dir)
                
                logger.info(f"Extracted {fits_file} to {extracted_path}")
                return extracted_path
                
        except Exception as e:
            logger.error(f"Error extracting zip file {zip_path}: {e}")
            return None

    def convertXisfToFits(self, xisf_file_path):
        """
        Convert XISF file to FITS format.
        
        Args:
            xisf_file_path (str): Path to XISF file
            
        Returns:
            str or None: Path to converted FITS file, or None if failed
        """
        try:
            from xisfFile import XISFConverter
            
            # Create output path
            fits_path = os.path.splitext(xisf_file_path)[0] + '.fits'
            
            # Convert the file
            converter = XISFConverter()
            success = converter.convert_to_fits(xisf_file_path, fits_path)
            
            if success:
                logger.info(f"Successfully converted XISF to FITS: {fits_path}")
                return fits_path
            else:
                logger.error(f"Failed to convert XISF file: {xisf_file_path}")
                return None
                
        except ImportError:
            logger.error("XISF conversion not available. Install xisfFile package.")
            return None
        except Exception as e:
            logger.error(f"Error converting XISF file {xisf_file_path}: {e}")
            return None

    def submitFileToDB(self, fileName, hdr, fileHash=None):
        """
        Submit FITS file to database after processing.
        
        Args:
            fileName (str): Full path to the FITS file
            hdr: FITS header object
            fileHash (str, optional): Pre-calculated file hash
            
        Returns:
            str or None: File ID if successful, None if failed
        """
        try:
            from astrofiler_db import fitsFile as FitsFileModel
            
            # Calculate hash if not provided
            if fileHash is None:
                fileHash = self.calculateFileHash(fileName)
                if fileHash is None:
                    logger.error(f"Could not calculate file hash for {fileName}")
                    return None
            
            # Check for duplicate files by hash
            try:
                existing_file = FitsFileModel.get(FitsFileModel.fitsFileHash == fileHash)
                logger.warning(f"Duplicate file detected: {fileName} matches {existing_file.fitsFileName}")
                return existing_file.fitsFileId
            except FitsFileModel.DoesNotExist:
                pass  # File is unique, proceed with registration
            
            # Extract required header values
            if not hdr.get("DATE-OBS"):
                logger.error(f"Missing DATE-OBS in header for {fileName}")
                return None
            
            if not hdr.get("IMAGETYP"):
                logger.error(f"Missing IMAGETYP in header for {fileName}")
                return None
            
            # Get exposure time
            exposure = hdr.get("EXPTIME", hdr.get("EXPOSURE"))
            if exposure is None:
                logger.error(f"Missing EXPTIME/EXPOSURE in header for {fileName}")
                return None
            
            # Get telescope and instrument
            telescope = hdr.get("TELESCOP", "Unknown")
            instrument = hdr.get("INSTRUME", "Unknown")
            
            # Check if telescope is iTelescope or instrument is SeeStar - mark as calibrated
            is_precalibrated = False
            if (telescope and "itelescope" in telescope.lower()) or \
               (instrument and "seestar" in instrument.lower()):
                is_precalibrated = True
                if telescope and "itelescope" in telescope.lower():
                    logger.debug(f"Marking file as pre-calibrated from iTelescope: {telescope}")
                else:
                    logger.debug(f"Marking file as pre-calibrated from SeeStar instrument: {instrument}")
            
            # Create new file record
            if hdr.get("OBJECT"):
                newfile = FitsFileModel.create(
                    fitsFileId=str(uuid.uuid4()),
                    fitsFileName=normalize_file_path(fileName),
                    fitsFileDate=hdr["DATE-OBS"],
                    fitsFileType=hdr["IMAGETYP"].upper(),
                    fitsFileObject=hdr["OBJECT"],
                    fitsFileExpTime=exposure,
                    fitsFileXBinning=hdr.get("XBINNING", 1),
                    fitsFileYBinning=hdr.get("YBINNING", 1),
                    fitsFileCCDTemp=hdr.get("CCD-TEMP", 0),
                    fitsFileTelescop=telescope,
                    fitsFileInstrument=instrument,
                    fitsFileFilter=hdr.get("FILTER", None),
                    fitsFileHash=fileHash,
                    fitsFileSession=None,
                    fitsFileCalibrated=1 if is_precalibrated else 0
                )
            else:
                newfile = FitsFileModel.create(
                    fitsFileId=str(uuid.uuid4()),
                    fitsFileName=normalize_file_path(fileName),
                    fitsFileDate=hdr["DATE-OBS"],
                    fitsFileType=hdr["IMAGETYP"].upper(),
                    fitsFileObject=hdr["IMAGETYP"],  # Use image type as object for calibration frames
                    fitsFileExpTime=exposure,
                    fitsFileXBinning=hdr.get("XBINNING", 1),
                    fitsFileYBinning=hdr.get("YBINNING", 1),
                    fitsFileCCDTemp=hdr.get("CCD-TEMP", 0),
                    fitsFileTelescop=telescope,
                    fitsFileInstrument=instrument,
                    fitsFileFilter=hdr.get("FILTER", None),
                    fitsFileHash=fileHash,
                    fitsFileSession=None,
                    fitsFileCalibrated=1 if is_precalibrated else 0
                )
            
            logger.info(f"Successfully registered FITS file: {newfile.fitsFileId}")
            return newfile.fitsFileId
            
        except IntegrityError as e:
            logger.error(f"Database integrity error for {fileName}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error submitting file to database {fileName}: {e}")
            return None

    def registerFitsImage(self, root, file, moveFiles):
        """
        Register a FITS image file, process headers, and move to repository structure.
        
        Args:
            root (str): Directory containing the file
            file (str): Filename
            moveFiles (bool): Whether to move files to repository structure
            
        Returns:
            str or bool: File ID if successful, False if failed
        """
        newFitsFileId = None
        file_name, file_extension = os.path.splitext(os.path.join(root, file))
        
        # Read configuration
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        save_modified = config.getboolean('DEFAULT', 'save_modified_headers', fallback=False)

        # Check if this is a zip file containing FITS files
        if file_extension.lower() in ['.zip']:
            # Check if it's a FITS zip file based on the name
            if file.lower().endswith(('.fit.zip', '.fits.zip')):
                logger.info(f"Found FITS zip file: {file}")
                
                # Extract the zip file
                zip_path = os.path.join(root, file)
                extracted_fits_path = self.extractZipFile(zip_path)
                
                if extracted_fits_path:
                    # Update the file path to point to the extracted FITS file
                    root = os.path.dirname(extracted_fits_path)
                    file = os.path.basename(extracted_fits_path)
                    file_name, file_extension = os.path.splitext(os.path.join(root, file))
                    logger.info(f"Processing extracted FITS file: {file}")
                else:
                    logger.error(f"Failed to extract FITS file from {file}")
                    return False
            else:
                # Regular zip file, not a FITS zip
                logger.debug(f"Ignoring non-FITS zip file {os.path.join(root, file)}")
                return False

        # Check if this is an XISF file
        if file_extension.lower() in ['.xisf']:
            logger.info(f"Found XISF file: {file}")
            xisf_path = os.path.join(root, file)
            converted_fits_path = self.convertXisfToFits(xisf_path)
            
            if converted_fits_path:
                # Update the file path to point to the converted FITS file
                root = os.path.dirname(converted_fits_path)
                file = os.path.basename(converted_fits_path)
                file_name, file_extension = os.path.splitext(os.path.join(root, file))
                logger.info(f"Processing converted FITS file: {file}")
            else:
                logger.error(f"Failed to convert XISF file: {xisf_path}")
                return False

        # Ignore everything not a *fit* file (after potential zip extraction or XISF conversion)
        if "fit" not in file_extension.lower():
            logger.debug(f"Ignoring file {os.path.join(root, file)} with extension {file_extension}")
            return False
        
        # Check if this is a master calibration frame
        full_file_path = os.path.join(root, file)
        if self._is_master_file(full_file_path):
            logger.info(f"Detected master calibration frame: {file}")
            # Register in Masters table instead of regular file table
            return self._register_master_file(full_file_path)
        
        # Open the FITS file for reading and close immediately after reading header
        try:
            hdul = fits.open(os.path.join(root, file), mode='readonly')
            hdr = hdul[0].header
            hdul.close()
        except Exception as e:
            logger.warning(f"Error loading FITS file {e} File not processed is {os.path.join(root, file)}")
            return False

        # Special handling for vendors with incomplete headers
        header_modified = False
        telescop_value = hdr.get("TELESCOP", "")
        if telescop_value and telescop_value.upper() == "DWARF":
            modified_hdr = dwarfFixHeader(hdr, root, file)
            if not modified_hdr:
                logger.warning(f"Error fixing DWARF header. File not processed is {os.path.join(root, file)}")
                return False
            hdr = modified_hdr
            header_modified = True
        
        # Apply FITS header mappings from the Mapping table
        mapping_modified = mapFitsHeader(hdr, os.path.join(root, file))
        if mapping_modified:
            header_modified = True
        
        # Validate required header fields
        if not (hdr.get("IMAGETYP") or hdr.get("FRAME")):
            logger.warning(f"No IMAGETYP or FRAME card in header. File not processed: {os.path.join(root, file)}")
            return False
        
        # Fix header field variations
        if hdr.get("FRAME") and not hdr.get("IMAGETYP"):
            hdr["IMAGETYP"] = hdr["FRAME"]
            header_modified = True
        
        # Get exposure time
        exposure = hdr.get("EXPTIME", hdr.get("EXPOSURE"))
        if exposure is None:
            logger.warning(f"No EXPTIME or EXPOSURE card in header. File not processed: {os.path.join(root, file)}")
            return False
                
        # Get telescope
        telescope = hdr.get("TELESCOP", "Unknown")
        
        # Fix calibration frames where OBJECT is set to an object rather than the frame type
        if "DARK" in hdr["IMAGETYP"].upper():
            hdr["OBJECT"] = "Dark"
            header_modified = True
        elif "FLAT" in hdr["IMAGETYP"].upper():
            hdr["OBJECT"] = "Flat"
            header_modified = True
        elif "BIAS" in hdr["IMAGETYP"].upper():
            hdr["OBJECT"] = "Bias"
            header_modified = True

        # Validate date field
        if not hdr.get("DATE-OBS"):
            logger.warning(f"No DATE-OBS card in header. File not processed: {os.path.join(root, file)}")
            return False
        
        try:
            datestr = hdr["DATE-OBS"].replace("T", " ")
            datestr = datestr[0:datestr.find('.')] if '.' in datestr else datestr
            dateobj = datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
            fitsDate = dateobj.strftime("%Y%m%d%H%M%S")
        except ValueError as e:
            logger.warning(f"Invalid date format in header. File not processed: {os.path.join(root, file)}")
            return False

        # Process different image types
        newName = None
        
        if "LIGHT" in hdr["IMAGETYP"].upper():
            # Handle WCS transformation for light frames
            if "CD1_1" not in hdr and all(field in hdr for field in ["CDELT1", "CDELT2", "CROTA2"]):
                fitsCDELT1 = float(hdr["CDELT1"])
                fitsCDELT2 = float(hdr["CDELT2"])
                fitsCROTA2 = float(hdr["CROTA2"])
                fitsCD1_1 = fitsCDELT1 * cos(fitsCROTA2)
                fitsCD1_2 = -fitsCDELT2 * sin(fitsCROTA2)
                fitsCD2_1 = fitsCDELT1 * sin(fitsCROTA2)
                fitsCD2_2 = fitsCDELT2 * cos(fitsCROTA2)
                hdr.append(('CD1_1', str(fitsCD1_1), 'Rotation Matrix'), end=True)
                hdr.append(('CD1_2', str(fitsCD1_2), 'Rotation Matrix'), end=True)
                hdr.append(('CD2_1', str(fitsCD2_1), 'Rotation Matrix'), end=True)
                hdr.append(('CD2_2', str(fitsCD2_2), 'Rotation Matrix'), end=True)
                header_modified = True
            
            # Create filename for light frames
            if hdr.get("OBJECT"):
                filter_name = hdr.get("FILTER", "OSC")
                newName = "{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(
                    sanitize_filesystem_name(hdr["OBJECT"]),
                    sanitize_filesystem_name(telescope),
                    sanitize_filesystem_name(hdr.get("INSTRUME", "Unknown")),
                    sanitize_filesystem_name(filter_name),
                    fitsDate, exposure,
                    hdr.get("XBINNING", 1),
                    hdr.get("YBINNING", 1),
                    hdr.get("CCD-TEMP", 0)
                )
            else:
                logger.warning(f"Invalid object name in header. File not processed: {os.path.join(root, file)}")
                return False

        elif "FLAT" in hdr["IMAGETYP"].upper():
            # Create filename for flat frames
            filter_name = hdr.get("FILTER", "OSC")
            newName = "{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(
                "Flat",
                sanitize_filesystem_name(telescope),
                sanitize_filesystem_name(hdr.get("INSTRUME", "Unknown")),
                sanitize_filesystem_name(filter_name),
                fitsDate, exposure,
                hdr.get("XBINNING", 1),
                hdr.get("YBINNING", 1),
                hdr.get("CCD-TEMP", 0)
            )

        elif "DARK" in hdr["IMAGETYP"].upper():
            # Create filename for dark frames
            newName = "{0}-{1}-{2}-{3}-{4}s-{5}x{6}-t{7}.fits".format(
                "Dark",
                sanitize_filesystem_name(telescope),
                sanitize_filesystem_name(hdr.get("INSTRUME", "Unknown")),
                fitsDate, exposure,
                hdr.get("XBINNING", 1),
                hdr.get("YBINNING", 1),
                hdr.get("CCD-TEMP", 0)
            )

        elif "BIAS" in hdr["IMAGETYP"].upper():
            # Create filename for bias frames
            newName = "{0}-{1}-{2}-{3}-{4}x{5}-t{6}.fits".format(
                "Bias",
                sanitize_filesystem_name(telescope),
                sanitize_filesystem_name(hdr.get("INSTRUME", "Unknown")),
                fitsDate,
                hdr.get("XBINNING", 1),
                hdr.get("YBINNING", 1),
                hdr.get("CCD-TEMP", 0)
            )

        if not newName:
            logger.warning(f"Could not determine new filename for {file}")
            return False

        # Save modified header if required
        if header_modified and save_modified:
            try:
                # Create backup of original file
                backup_path = os.path.join(root, file + ".backup")
                import shutil
                shutil.copy2(os.path.join(root, file), backup_path)
                
                # Save modified header
                with fits.open(os.path.join(root, file), mode='update') as hdul:
                    hdul[0].header = hdr
                    hdul.flush()
                
                logger.info(f"Saved modified header for {file}")
            except Exception as e:
                logger.error(f"Error saving modified header for {file}: {e}")

        # Submit file to database
        fileHash = self.calculateFileHash(os.path.join(root, file))
        newFitsFileId = self.submitFileToDB(os.path.join(root, file), hdr, fileHash)
        
        return newFitsFileId if newFitsFileId else False