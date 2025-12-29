"""
GZIP archive handler for AstroFiler.

Handles externally gzip-compressed FITS files (e.g. .fits.gz).

Behavior:
- Decompresses the *entire* FITS file to a normal FITS file (same folder, .gz removed).
- The normal import pipeline can then apply AstroFiler's standard FITS tile compression
  (fits_gzip2) to create a standard compressed FITS image.

Notes:
- We intentionally do not support .fz here (user requested not to accommodate).
"""

import gzip
import logging
import os
import shutil
from typing import List

from ....exceptions import FileProcessingError
from ....types import FilePath
from .. import BaseFileFormatHandler

logger = logging.getLogger(__name__)


class GzipFileHandler(BaseFileFormatHandler):
    """Handler for gzip-compressed FITS files (.fits.gz)."""

    def _get_supported_extensions(self) -> List[str]:
        return ['.gz']

    def get_format_name(self) -> str:
        return "GZIP"

    def can_handle(self, file_path: FilePath) -> bool:
        """Only handle .gz that wrap a FITS file (e.g. *.fits.gz)."""
        if not super().can_handle(file_path):
            return False
        return self._is_fits_gzip(file_path)

    def _is_fits_gzip(self, file_path: FilePath) -> bool:
        filename = os.path.basename(file_path).lower()
        return filename.endswith(('.fit.gz', '.fits.gz', '.fts.gz'))

    def _process_file_internal(self, file_path: FilePath) -> FilePath:
        """Decompress gzip-wrapped FITS to a normal FITS file."""
        if not self._is_fits_gzip(file_path):
            raise FileProcessingError(
                "GZIP file does not contain a FITS file",
                file_path=str(file_path),
                error_code="NO_FITS_IN_GZIP",
            )

        if not os.path.exists(file_path):
            raise FileProcessingError(
                "File does not exist",
                file_path=str(file_path),
                error_code="FILE_NOT_FOUND",
            )

        # Output path is the same name without the .gz suffix
        output_path = str(file_path)[:-3]

        # If we already decompressed it, reuse it.
        try:
            if os.path.exists(output_path):
                gz_mtime = os.path.getmtime(file_path)
                out_mtime = os.path.getmtime(output_path)
                if out_mtime >= gz_mtime:
                    logger.debug(f"Using existing decompressed FITS: {output_path}")
                    return output_path
        except Exception:
            # If stat fails, just proceed to decompress.
            pass

        try:
            logger.info(f"Decompressing gzip FITS: {file_path} -> {output_path}")
            with gzip.open(file_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return output_path
        except (OSError, IOError) as e:
            raise FileProcessingError(
                f"File system error during gzip decompression: {e}",
                file_path=str(file_path),
                error_code="GZIP_IO_ERROR",
            )
        except Exception as e:
            raise FileProcessingError(
                f"Unexpected error decompressing gzip FITS: {e}",
                file_path=str(file_path),
                error_code="GZIP_DECOMPRESS_ERROR",
            )
