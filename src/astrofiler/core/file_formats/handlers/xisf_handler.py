"""
XISF file format handler for AstroFiler.

Converts XISF files to FITS format for processing.
"""

import os
import logging
from typing import List
from ....types import FilePath
from ....exceptions import FileProcessingError
from .. import BaseFileFormatHandler

logger = logging.getLogger(__name__)


class XisfFileHandler(BaseFileFormatHandler):
    """Handler for XISF format files."""
    
    def _get_supported_extensions(self) -> List[str]:
        """XISF file extensions."""
        return ['.xisf']
    
    def get_format_name(self) -> str:
        """Format name for XISF files."""
        return "XISF"
    
    def _process_file_internal(self, file_path: FilePath) -> FilePath:
        """
        Convert XISF file to FITS format.
        
        Args:
            file_path: Path to XISF file
            
        Returns:
            Path to converted FITS file
            
        Raises:
            FileProcessingError: If conversion fails or XISF support not available
        """
        try:
            from ....file_formats.xisfFile import XISFConverter
        except ImportError:
            raise FileProcessingError(
                "XISF conversion not available. Install xisfFile package.",
                file_path=str(file_path),
                error_code="XISF_SUPPORT_MISSING"
            )
        
        try:
            # Create output path
            fits_path = os.path.splitext(file_path)[0] + '.fits'
            
            # Convert the file
            converter = XISFConverter()
            success = converter.convert_to_fits(file_path, fits_path)
            
            if success:
                logger.info(f"Successfully converted XISF to FITS: {fits_path}")
                return fits_path
            else:
                raise FileProcessingError(
                    "XISF conversion failed - converter returned False",
                    file_path=str(file_path),
                    error_code="XISF_CONVERSION_FAILED"
                )
                
        except FileProcessingError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise FileProcessingError(
                f"Error during XISF conversion: {e}",
                file_path=str(file_path),
                error_code="XISF_CONVERSION_ERROR"
            )