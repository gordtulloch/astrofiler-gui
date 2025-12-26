"""
Core file processing module for AstroFiler.

This module handles FITS file registration, header processing, hash calculation,
compression, and database operations for importing astronomical images.
"""

import os
import hashlib
import logging
import uuid
import zipfile
import configparser
from datetime import datetime
from math import cos, sin
from typing import Optional, Dict, Any, List, Tuple, Union
from astropy.io import fits
from peewee import IntegrityError

from .utils import normalize_file_path, sanitize_filesystem_name, dwarfFixHeader, mapFitsHeader
from ..types import FilePath, FitsHeaderDict, ProcessingResult, QualityMetrics
from ..exceptions import (
    FileProcessingError, FitsHeaderError, DatabaseError, 
    ValidationError, AstroFilerError
)
from .file_formats import get_file_format_processor
from .services.file_hash_calculator import get_file_hash_calculator
from .compress_files import get_fits_compressor

logger = logging.getLogger(__name__)


class FileProcessor:
    """
    Handles FITS file processing operations including registration and database operations.
    """
    
    def __init__(self) -> None:
        """Initialize FileProcessor with configuration and services."""
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        self.sourceFolder: str = config.get('DEFAULT', 'source', fallback='.')
        self.repoFolder: str = config.get('DEFAULT', 'repo', fallback='.')
        
        # Initialize services following Dependency Inversion Principle
        self.format_processor = get_file_format_processor()
        self.hash_calculator = get_file_hash_calculator()
        self.compressor = get_fits_compressor()

    def calculateFileHash(self, filePath: FilePath) -> Optional[str]:
        """
        Calculate SHA-256 hash of a file for duplicate detection.
        
        Uses the dedicated FileHashCalculator service following Single Responsibility Principle.
        
        Args:
            filePath: Path to the file
            
        Returns:
            SHA-256 hash hex string, or None if error
            
        Raises:
            FileProcessingError: If file cannot be read or hash calculation fails
        """
        return self.hash_calculator.calculate_sha256(filePath)

    def _is_master_file(self, file_path: str) -> bool:
        """
        Check if a file is a master calibration frame that should be handled specially.
        
        Args:
            file_path: Full path to the file
            
        Returns:
            True if this is a master file
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
            str: Master ID if successful
            
        Raises:
            FileProcessingError: If file cannot be processed
            ValidationError: If master type cannot be determined
            DatabaseError: If database operations fail
        """
        try:
            # Import here to avoid circular imports
            try:
                from ..models import Masters
            except ImportError:
                raise DatabaseError(
                    "Masters table not available yet. Run migrations to create Masters table.",
                    error_code="MASTERS_TABLE_MISSING"
                )
            
            # Open the FITS file to read header
            try:
                with fits.open(file_path, mode='readonly') as hdul:
                    hdr = hdul[0].header
            except (OSError, IOError) as e:
                raise FileProcessingError(
                    f"Cannot read FITS file: {e}",
                    file_path=file_path,
                    error_code="FITS_READ_ERROR"
                )
            except Exception as e:
                raise FitsHeaderError(
                    f"Error reading FITS header: {e}",
                    file_path=file_path,
                    error_code="FITS_HEADER_ERROR"
                )
            
            # Determine master type from filename or header
            master_type = self._determine_master_type(file_path, hdr)
            if not master_type:
                raise ValidationError(
                    f"Could not determine master type for file {file_path}",
                    field="master_type",
                    file_path=file_path
                )
            
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
            try:
                master = Masters.create_master_record(
                    master_path=file_path,
                    session_data=session_data,
                    cal_type=master_type,
                    file_count=file_count
                )
            except Exception as e:
                raise DatabaseError(
                    f"Failed to create master record: {e}",
                    file_path=file_path,
                    error_code="MASTER_CREATE_ERROR"
                )
            
            # Validate the file
            try:
                if master.validate_and_mark():
                    logger.info(f"Successfully registered master {master_type}: {master.master_id}")
                    return master.master_id
                else:
                    logger.warning(f"Master file validation failed: {file_path}")
                    return master.master_id  # Still return ID even if validation failed
            except Exception as e:
                logger.error(f"Master validation error: {e}")
                return master.master_id  # Return ID anyway for partial success
                
        except (FileProcessingError, ValidationError, DatabaseError, FitsHeaderError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise FileProcessingError(
                f"Unexpected error registering master file: {e}",
                file_path=file_path,
                error_code="MASTER_REGISTER_ERROR"
            )

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

    def submitFileToDB(self, fileName: str, hdr: Any, fileHash: Optional[str] = None) -> Optional[str]:
        """
        Submit FITS file to database after processing.
        
        Args:
            fileName: Full path to the FITS file
            hdr: FITS header object
            fileHash: Pre-calculated file hash
            
        Returns:
            File ID if successful, None if failed
            
        Raises:
            DatabaseError: If database operations fail
            ValidationError: If required header fields are missing
            FileProcessingError: If file processing fails
        """
        try:
            from ..models import fitsFile as FitsFileModel
        except ImportError as e:
            raise DatabaseError(
                f"Cannot import database models: {e}",
                error_code="MODEL_IMPORT_ERROR"
            )
        
        try:
            # Calculate hash if not provided
            if fileHash is None:
                fileHash = self.calculateFileHash(fileName)
                if fileHash is None:
                    raise FileProcessingError(
                        "Could not calculate file hash",
                        file_path=fileName,
                        error_code="HASH_CALCULATION_FAILED"
                    )
            
            # Check for duplicate files by hash
            try:
                existing_file = FitsFileModel.get(FitsFileModel.fitsFileHash == fileHash)
                logger.warning(f"Duplicate file detected: {fileName} matches {existing_file.fitsFileName}")
                return existing_file.fitsFileId
            except FitsFileModel.DoesNotExist:
                pass  # File is unique, proceed with registration
            
            # Validate required header values
            date_obs = hdr.get("DATE-OBS")
            if not date_obs:
                raise ValidationError(
                    "Missing required DATE-OBS field in FITS header",
                    field="DATE-OBS",
                    file_path=fileName
                )
            
            image_type = hdr.get("IMAGETYP")
            if not image_type:
                raise ValidationError(
                    "Missing required IMAGETYP field in FITS header",
                    field="IMAGETYP", 
                    file_path=fileName
                )
            
            # Get exposure time
            exposure = hdr.get("EXPTIME", hdr.get("EXPOSURE"))
            if exposure is None:
                raise ValidationError(
                    "Missing required EXPTIME/EXPOSURE field in FITS header",
                    field="EXPTIME",
                    file_path=fileName
                )
            
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
                    fitsFileDate=date_obs,
                    fitsFileType=image_type.upper(),
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
                    fitsFileDate=date_obs,
                    fitsFileType=image_type.upper(),
                    fitsFileObject=image_type,  # Use image type as object for calibration frames
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
            raise DatabaseError(
                f"Database integrity constraint violated: {e}",
                file_path=fileName,
                error_code="DB_INTEGRITY_ERROR"
            )
        except (ValidationError, FileProcessingError, DatabaseError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise DatabaseError(
                f"Unexpected database error: {e}",
                file_path=fileName,
                error_code="DB_UNEXPECTED_ERROR"
            )

    def registerFitsImage(self, root: str, file: str, moveFiles: bool) -> Union[str, bool]:
        """
        Register a FITS image file, process headers, and move to repository structure.
        
        Args:
            root: Directory containing the file
            file: Filename
            moveFiles: Whether to move files to repository structure
            
        Returns:
            File ID if successful, False if failed
            
        Raises:
            FileProcessingError: If file processing fails
            ValidationError: If file validation fails
            FitsHeaderError: If FITS header processing fails
            DatabaseError: If database operations fail
        """
        try:
            return self._register_fits_image_internal(root, file, moveFiles)
        except (FileProcessingError, ValidationError, FitsHeaderError, DatabaseError) as e:
            logger.error(f"Error processing {os.path.join(root, file)}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error processing {os.path.join(root, file)}: {e}")
            raise FileProcessingError(
                f"Unexpected error during FITS registration: {e}",
                file_path=os.path.join(root, file),
                error_code="UNEXPECTED_REGISTRATION_ERROR"
            )
    
    def _register_fits_image_internal(self, root: str, file: str, moveFiles: bool) -> Union[str, bool]:
        """Internal implementation of FITS image registration with proper error handling."""
        newFitsFileId = None
        file_name, file_extension = os.path.splitext(os.path.join(root, file))
        
        # Read configuration
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        save_modified = config.getboolean('DEFAULT', 'save_modified_headers', fallback=False)

        # Process files through the FileFormatProcessor following Open/Closed Principle
        try:
            if self.format_processor.can_process(os.path.join(root, file)):
                processed_file_path = self.format_processor.process_file(os.path.join(root, file))
                
                # Update root and file to point to processed file
                root = os.path.dirname(processed_file_path)
                file = os.path.basename(processed_file_path)
                file_name, file_extension = os.path.splitext(processed_file_path)
                
                logger.info(f"Successfully processed file: {processed_file_path}")
            else:
                # If no handler available, check if it's a FITS file directly
                if "fit" not in file_extension.lower():
                    logger.debug(f"Ignoring unsupported file {os.path.join(root, file)}")
                    return False
        except FileProcessingError as e:
            # Re-raise file processing errors
            raise
        
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
        except (OSError, IOError) as e:
            raise FileProcessingError(
                f"Cannot read FITS file: {e}",
                file_path=os.path.join(root, file),
                error_code="FITS_FILE_READ_ERROR"
            )
        except Exception as e:
            raise FitsHeaderError(
                f"Error reading FITS header: {e}",
                file_path=os.path.join(root, file),
                error_code="FITS_HEADER_READ_ERROR"
            )

        # Special handling for vendors with incomplete headers
        header_modified = False
        telescop_value = hdr.get("TELESCOP", "")
        if telescop_value and telescop_value.upper() == "DWARF":
            modified_hdr = dwarfFixHeader(hdr, root, file)
            if not modified_hdr:
                raise FitsHeaderError(
                    "Error fixing DWARF header",
                    file_path=os.path.join(root, file),
                    error_code="DWARF_HEADER_FIX_FAILED"
                )
            hdr = modified_hdr
            header_modified = True
        
        # Apply FITS header mappings from the Mapping table
        mapping_modified = mapFitsHeader(hdr, os.path.join(root, file))
        if mapping_modified:
            header_modified = True
        
        # Validate required header fields
        if not (hdr.get("IMAGETYP") or hdr.get("FRAME")):
            raise ValidationError(
                "Missing required IMAGETYP or FRAME field in FITS header",
                field="IMAGETYP", 
                file_path=os.path.join(root, file)
            )
        
        # Fix header field variations
        if hdr.get("FRAME") and not hdr.get("IMAGETYP"):
            hdr["IMAGETYP"] = hdr["FRAME"]
            header_modified = True
        
        # Get exposure time
        exposure = hdr.get("EXPTIME", hdr.get("EXPOSURE"))
        if exposure is None:
            raise ValidationError(
                "Missing required EXPTIME/EXPOSURE field in FITS header",
                field="EXPTIME",
                file_path=os.path.join(root, file)
            )
                
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
        date_obs = hdr.get("DATE-OBS")
        if not date_obs:
            raise ValidationError(
                "Missing required DATE-OBS field in FITS header",
                field="DATE-OBS",
                file_path=os.path.join(root, file)
            )
        
        try:
            datestr = date_obs.replace("T", " ")
            datestr = datestr[0:datestr.find('.')] if '.' in datestr else datestr
            dateobj = datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
            fitsDate = dateobj.strftime("%Y%m%d%H%M%S")
        except ValueError as e:
            raise ValidationError(
                f"Invalid date format in DATE-OBS field: {date_obs}",
                field="DATE-OBS",
                file_path=os.path.join(root, file)
            )

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
                raise ValidationError(
                    "Missing or invalid object name in header for light frame",
                    field="OBJECT",
                    file_path=os.path.join(root, file)
                )

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
            raise ValidationError(
                f"Could not determine appropriate filename for file type {hdr.get('IMAGETYP', 'Unknown')}",
                field="IMAGETYP",
                file_path=os.path.join(root, file)
            )

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
            except (OSError, IOError) as e:
                logger.error(f"File I/O error saving modified header for {file}: {e}")
                # Continue processing despite header save failure
            except Exception as e:
                logger.error(f"Unexpected error saving modified header for {file}: {e}")
                # Continue processing despite header save failure

        # Process file for compression if enabled and appropriate
        current_file_path = os.path.join(root, file)
        try:
            compressed_file_path = self.compressor.process_file_for_compression(current_file_path)
            if compressed_file_path != current_file_path:
                # File was compressed, update path references
                root = os.path.dirname(compressed_file_path)
                file = os.path.basename(compressed_file_path)
                current_file_path = compressed_file_path
                logger.info(f"File compressed: {current_file_path} -> {compressed_file_path}")
        except Exception as e:
            logger.warning(f"Compression processing failed for {current_file_path}: {e}")
            # Continue with original file if compression fails

        # If requested, move/rename the file into the repository structure.
        # This is required for the Images view "Load New" workflow.
        if moveFiles:
            try:
                from .repository import RepositoryManager

                repo_manager = RepositoryManager()
                # Ensure the repository root folders exist (Light/Calibrate/Masters/Incoming/etc.)
                repo_manager.createRepositoryStructure()

                new_filename = newName

                moved_path = repo_manager.organizeFileByType(
                    current_file_path,
                    hdr,
                    new_filename=new_filename,
                )
                if not moved_path:
                    raise FileProcessingError(
                        "Failed to move file into repository structure",
                        file_path=current_file_path,
                        error_code="REPO_MOVE_FAILED",
                    )

                root = os.path.dirname(moved_path)
                file = os.path.basename(moved_path)
                current_file_path = moved_path
            except Exception as e:
                raise FileProcessingError(
                    f"Failed moving file into repository: {e}",
                    file_path=current_file_path,
                    error_code="REPO_MOVE_FAILED",
                )

        # Submit file to database (use the potentially compressed file path)
        fileHash = self.calculateFileHash(current_file_path)
        newFitsFileId = self.submitFileToDB(current_file_path, hdr, fileHash)
        
        return newFitsFileId if newFitsFileId else False

    # Legacy methods for backward compatibility - delegate to new services
    def extractZipFile(self, zip_path):
        """
        DEPRECATED: Extract FITS file from ZIP archive.
        
        This method is deprecated. Use FileFormatProcessor directly instead.
        Delegates to the ZIP handler in the format processor.
        
        Args:
            zip_path (str): Path to ZIP file
            
        Returns:
            str: Path to extracted FITS file
            
        Raises:
            FileProcessingError: If extraction fails
        """
        import warnings
        warnings.warn(
            "extractZipFile is deprecated. Use FileFormatProcessor instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        try:
            from .file_formats.handlers.zip_handler import ZipFileHandler
            handler = ZipFileHandler()
            return handler.process_file(zip_path)
        except Exception as e:
            # Convert any exception to the expected format for backward compatibility
            logger.error(f"Error extracting zip file {zip_path}: {e}")
            return None
    
    def convertXisfToFits(self, xisf_file_path):
        """
        DEPRECATED: Convert XISF file to FITS format.
        
        This method is deprecated. Use FileFormatProcessor directly instead.
        Delegates to the XISF handler in the format processor.
        
        Args:
            xisf_file_path (str): Path to XISF file
            
        Returns:
            str: Path to converted FITS file
            
        Raises:
            FileProcessingError: If conversion fails
        """
        import warnings
        warnings.warn(
            "convertXisfToFits is deprecated. Use FileFormatProcessor instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        try:
            from .file_formats.handlers.xisf_handler import XisfFileHandler
            handler = XisfFileHandler()
            return handler.process_file(xisf_file_path)
        except Exception as e:
            # Convert any exception to the expected format for backward compatibility
            logger.error(f"Error converting XISF file {xisf_file_path}: {e}")
            return None