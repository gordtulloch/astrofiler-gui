"""
FITS file format handler for AstroFiler.

Handles native FITS files - the primary format for astronomical images.
"""

import logging
from typing import List
from ....types import FilePath
from ....exceptions import FileProcessingError
from .. import BaseFileFormatHandler

logger = logging.getLogger(__name__)


class FitsFileHandler(BaseFileFormatHandler):
    """Handler for FITS format files."""
    
    def _get_supported_extensions(self) -> List[str]:
        """FITS file extensions."""
        return ['.fits', '.fit', '.fts']
    
    def get_format_name(self) -> str:
        """Format name for FITS files."""
        return "FITS"
    
    def _process_file_internal(self, file_path: FilePath) -> FilePath:
        """
        Process FITS file - no conversion needed.
        
        Args:
            file_path: Path to FITS file
            
        Returns:
            Same path (no processing needed for native format)
            
        Raises:
            FileProcessingError: If file validation fails
        """
        # Validate that it's a readable FITS file
        try:
            from astropy.io import fits
            with fits.open(file_path, mode='readonly') as hdul:
                # Basic validation - ensure we can read the header
                hdr = hdul[0].header
                logger.debug(f"Successfully validated FITS file: {file_path}")
                return file_path
        except Exception as e:
            raise FileProcessingError(
                f"Invalid FITS file: {e}",
                file_path=str(file_path),
                error_code="INVALID_FITS_FILE"
            )