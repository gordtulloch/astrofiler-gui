"""
ZIP archive handler for AstroFiler.

Extracts FITS files from ZIP archives.
"""

import os
import zipfile
import logging
from typing import List
from ....types import FilePath
from ....exceptions import FileProcessingError
from .. import BaseFileFormatHandler

logger = logging.getLogger(__name__)


class ZipFileHandler(BaseFileFormatHandler):
    """Handler for ZIP archives containing FITS files."""
    
    def _get_supported_extensions(self) -> List[str]:
        """ZIP file extensions."""
        return ['.zip']
    
    def get_format_name(self) -> str:
        """Format name for ZIP files."""
        return "ZIP Archive"
    
    def _process_file_internal(self, file_path: FilePath) -> FilePath:
        """
        Extract FITS file from ZIP archive.
        
        Args:
            file_path: Path to ZIP file
            
        Returns:
            Path to extracted FITS file
            
        Raises:
            FileProcessingError: If extraction fails or no FITS files found
        """
        # Only process ZIP files that contain FITS files
        if not self._is_fits_zip(file_path):
            raise FileProcessingError(
                "ZIP file does not contain FITS files",
                file_path=str(file_path),
                error_code="NO_FITS_IN_ZIP"
            )
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # List all files in the zip
                file_list = zip_ref.namelist()
                
                # Find FITS files
                fits_files = [f for f in file_list if f.lower().endswith(('.fit', '.fits', '.fts'))]
                
                if not fits_files:
                    raise FileProcessingError(
                        "No FITS files found in ZIP archive",
                        file_path=str(file_path),
                        error_code="NO_FITS_IN_ZIP"
                    )
                
                if len(fits_files) > 1:
                    logger.warning(f"Multiple FITS files found in {file_path}, using first one: {fits_files[0]}")
                
                fits_file = fits_files[0]
                
                # Extract to the same directory as the zip file
                extract_dir = os.path.dirname(file_path)
                extracted_path = zip_ref.extract(fits_file, extract_dir)
                
                logger.info(f"Extracted {fits_file} from {file_path} to {extracted_path}")
                return extracted_path
                
        except zipfile.BadZipFile as e:
            raise FileProcessingError(
                f"Invalid ZIP file: {e}",
                file_path=str(file_path),
                error_code="INVALID_ZIP"
            )
        except (OSError, IOError) as e:
            raise FileProcessingError(
                f"File system error during extraction: {e}",
                file_path=str(file_path),
                error_code="EXTRACTION_IO_ERROR"
            )
        except Exception as e:
            raise FileProcessingError(
                f"Unexpected error extracting zip file: {e}",
                file_path=str(file_path),
                error_code="EXTRACTION_ERROR"
            )
    
    def _is_fits_zip(self, file_path: FilePath) -> bool:
        """
        Check if ZIP file contains FITS files based on filename.
        
        Args:
            file_path: Path to ZIP file
            
        Returns:
            True if this appears to be a FITS ZIP file
        """
        filename = os.path.basename(file_path).lower()
        return filename.endswith(('.fit.zip', '.fits.zip'))
    
    def can_handle(self, file_path: FilePath) -> bool:
        """
        Check if this handler can process the ZIP file.
        
        Only handles ZIP files that contain FITS files.
        """
        if not super().can_handle(file_path):
            return False
        
        # Additional check for FITS ZIP files
        return self._is_fits_zip(file_path)