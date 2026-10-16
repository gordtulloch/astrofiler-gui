"""
FITS File Compression Module

This module provides lossless compression for FITS images. 
FITS tile-compressed files are written in-place (filename unchanged) when
`replace_original=True` (the default for auto-import). The resulting FITS file
stores the image using the FITS tile compression convention.

The compression system supports:
- Lossless compression using gzip or similar algorithms
- Transparent decompression when files are accessed
- Configuration-driven compression behavior
- Integration with file registration and download processes

Key Features:
- Preserves all FITS metadata and image data exactly
- Significant file size reduction (typically 30-70% smaller)
- Fast compression/decompression suitable for real-time processing
- Seamless integration with existing AstroFiler workflows

Configuration:
Set 'compress_fits=true' in astrofiler.ini to enable automatic compression
for new files during download and repository loading.
"""

from __future__ import annotations

import os
import gzip
import lzma
import bz2
import shutil
import logging
import configparser
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from astropy.io import fits
import hashlib
from collections import Counter

import numpy as np

# Import config for temp folder
try:
    from ..config import get_temp_folder
except ImportError:
    # Fallback if config module not available
    def get_temp_folder():
        return tempfile.gettempdir()

logger = logging.getLogger(__name__)

# The project convention for FITS tile compression; every ``fits_*`` setting maps to it.
_TILE_COMPRESSION = 'GZIP_2'

_STRUCTURAL_KEYWORDS = {'SIMPLE', 'BITPIX', 'NAXIS', 'EXTEND', 'PCOUNT', 'GCOUNT', 'CHECKSUM', 'DATASUM'}
# Keywords a CompImageHDU (a BINTABLE extension) must not inherit from the source image header.
_PRIMARY_SKIP = _STRUCTURAL_KEYWORDS | {f'NAXIS{i}' for i in range(1, 10)}
_COMP_SKIP = _STRUCTURAL_KEYWORDS | {
    'BSCALE', 'BZERO', 'XTENSION', 'TFIELDS', 'ZIMAGE', 'ZCMPTYPE', 'ZBITPIX', 'ZNAXIS',
} | {
    f'{prefix}{i}'
    for i in range(1, 100)
    for prefix in ('NAXIS', 'ZNAXIS', 'TTYPE', 'TFORM', 'TUNIT', 'TDIM')
}


def _compression_ratio(original_size: int, compressed_size: int) -> float:
    """Percentage reduction; 0 for an empty original rather than a ZeroDivisionError."""
    return (1 - compressed_size / original_size) * 100 if original_size else 0.0


def _remove_quietly(path: str) -> None:
    """Delete a temporary file, logging (not raising) if the OS refuses."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Could not remove temporary file %s: %s", path, exc)


def _find_image_hdu_index(hdul: fits.HDUList) -> int | None:
    """Index of the first uncompressed image HDU that holds data (tables and CompImageHDUs don't count)."""
    for idx, hdu in enumerate(hdul):
        if isinstance(hdu, fits.CompImageHDU) or not isinstance(hdu, (fits.PrimaryHDU, fits.ImageHDU)):
            continue
        try:
            if hdu.data is not None:
                return idx
        except Exception:  # an HDU whose data can't be read is not a candidate
            logger.debug("HDU %d has unreadable data", idx, exc_info=True)
    return None


def _copy_header_cards(dst: fits.Header, src: fits.Header, skip: set[str]) -> list[str]:
    """Copy every non-structural card from *src* to *dst*; return the keywords that could not be copied."""
    failed: list[str] = []
    for card in src.cards:
        key = card.keyword
        if not key or key in skip:
            continue
        try:
            if key == 'COMMENT':
                dst.add_comment(card.value)
            elif key == 'HISTORY':
                dst.add_history(card.value)
            else:
                dst[key] = (card.value, card.comment)
        except Exception:
            failed.append(key)
    return failed


def _tile_compress_hdu(src_hdu: fits.PrimaryHDU | fits.ImageHDU) -> fits.CompImageHDU:
    """Build a tile-compressed copy of an image HDU, keeping its non-structural header cards."""
    # quantize_level=0 disables quantization: astropy's default (16) makes floating-point
    # images lossy, which would silently corrupt the photometry.
    compressed_hdu = fits.CompImageHDU(
        data=src_hdu.data, compression_type=_TILE_COMPRESSION, quantize_level=0,
    )
    failed = _copy_header_cards(compressed_hdu.header, src_hdu.header, _COMP_SKIP)
    if failed:
        raise ValueError(f"header cards could not be copied to the compressed HDU: {sorted(set(failed))}")

    # Preserve EXTNAME when present
    if 'EXTNAME' in src_hdu.header and 'EXTNAME' not in compressed_hdu.header:
        compressed_hdu.header['EXTNAME'] = src_hdu.header['EXTNAME']

    # Older astropy exposes the raw table header, already holding the tile-compression (Z*)
    # keywords, and needs them to match the original image. Newer astropy derives them itself
    # and would write our copies as stray reserved keywords (a VerifyWarning on every read).
    if 'ZCMPTYPE' in compressed_hdu.header:
        naxis = int(src_hdu.header.get('NAXIS', src_hdu.data.ndim))
        compressed_hdu.header['ZIMAGE'] = (True, 'Tile-compressed image')
        compressed_hdu.header['ZCMPTYPE'] = (_TILE_COMPRESSION, 'Compression algorithm')
        compressed_hdu.header['ZNAXIS'] = (naxis, 'Number of uncompressed axes')
        compressed_hdu.header['ZBITPIX'] = (int(src_hdu.header.get('BITPIX', -32)), 'Uncompressed data type')
        for axis in range(1, naxis + 1):
            n_key = f'NAXIS{axis}'
            length = int(src_hdu.header[n_key]) if n_key in src_hdu.header else int(src_hdu.data.shape[-axis])
            compressed_hdu.header[f'ZNAXIS{axis}'] = (length, f'Axis {axis} length (uncompressed)')
    return compressed_hdu


def _rebuild_with_compressed_image(hdul: fits.HDUList, target_idx: int) -> list[fits.hdu.base._BaseHDU]:
    """The HDU list for the compressed file: *hdul* with its image at *target_idx* tile-compressed.

    Raises if any extension or header card can't be carried over — a compressed copy that
    silently lacks part of the original must never replace it.
    """
    if target_idx == 0:
        # The image is in the PrimaryHDU; rewrite as an empty PrimaryHDU with the global
        # metadata followed by a CompImageHDU holding the image.
        primary = fits.PrimaryHDU()
        failed = _copy_header_cards(primary.header, hdul[0].header, _PRIMARY_SKIP)
        if failed:
            raise ValueError(f"header cards could not be copied to the primary HDU: {sorted(set(failed))}")
        return [primary, _tile_compress_hdu(hdul[0]), *(ext.copy() for ext in hdul[1:])]

    return [
        _tile_compress_hdu(hdu) if idx == target_idx else hdu.copy()
        for idx, hdu in enumerate(hdul)
    ]


def _data_hdus(hdul: fits.HDUList) -> list[fits.hdu.base._BaseHDU]:
    return [hdu for hdu in hdul if hdu.data is not None]


def _data_equal(a: np.ndarray, b: np.ndarray) -> bool:
    """Exact equality (NaN == NaN); handles table (record) arrays column by column."""
    if a.shape != b.shape:
        return False
    names = a.dtype.names
    if names or b.dtype.names:
        if names is None or names != b.dtype.names:
            return False
        return all(_data_equal(np.asarray(a[name]), np.asarray(b[name])) for name in names)
    both_float = a.dtype.kind in 'fc' and b.dtype.kind in 'fc'
    return bool(np.array_equal(a, b, equal_nan=both_float))


def _commentary_counts(hdul: fits.HDUList) -> Counter:
    return Counter(
        card.keyword for hdu in hdul for card in hdu.header.cards if card.keyword in ('COMMENT', 'HISTORY')
    )


class FitsCompressor:
    """
    Handles FITS file compression and decompression using advanced lossless algorithms.
    """
    
    def __init__(self, config_path: str = 'astrofiler.ini'):
        """
        Initialize the FITS compressor.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        
        # Get compression settings
        self.compression_enabled = self.config.getboolean('DEFAULT', 'compress_fits', fallback=False)
        self.compression_algorithm = self.config.get('DEFAULT', 'compression_algorithm', fallback='gzip')
        self.compression_level = self.config.getint('DEFAULT', 'compression_level', fallback=6)
        self.verify_compression = self.config.getboolean('DEFAULT', 'verify_compression', fallback=True)
        
        # Algorithm-specific settings
        # FITS internal compression algorithms - optimized for data type
        # RICE: Lossless for integer data (NINA compatible)
        # GZIP: Lossless for floating-point data 
        self.algorithms = {
            'gzip': {'extension': '.gz', 'module': gzip, 'levels': (1, 9)},
            'lzma': {'extension': '.xz', 'module': lzma, 'levels': (0, 9)}, 
            'bzip2': {'extension': '.bz2', 'module': bz2, 'levels': (1, 9)},
            'fits_rice': {'extension': '.fits', 'module': None, 'levels': (1, 9)},
            'fits_gzip1': {'extension': '.fits', 'module': None, 'levels': (1, 9)},
            'fits_gzip2': {'extension': '.fits', 'module': None, 'levels': (1, 9)},
            'auto': {'extension': '.fits', 'module': None, 'levels': (1, 9)}  # Smart selection
        }
        
        logger.info(f"FITS compression initialized: enabled={self.compression_enabled}, "
                   f"algorithm={self.compression_algorithm}, level={self.compression_level}")
    
    def get_algorithm_info(self, algorithm: str = None):
        """Get information about compression algorithm."""
        algo = algorithm or self.compression_algorithm
        return self.algorithms.get(algo, self.algorithms['gzip'])
    
    def is_compressed(self, file_path: str) -> bool:
        """
        Check if a file is already compressed (external or internal FITS compression).
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if file appears to be compressed, False otherwise
        """
        # Check for common compression extensions
        # - .gz/.xz/.bz2 are external stream compression
        # - .fz is the conventional suffix for FITS tile-compression outputs (fpack)
        external_compressed_extensions = ['.gz', '.xz', '.bz2', '.fz']
        if any(file_path.lower().endswith(ext) for ext in external_compressed_extensions):
            return True
        
        # Check for FITS internal compression by examining the file structure
        if file_path.lower().endswith(('.fits', '.fit', '.fts', '.fits.fz', '.fit.fz', '.fts.fz', '.fz')):
            try:
                with fits.open(file_path) as hdul:
                    # Check if there are CompImageHDU (compressed image) extensions
                    for hdu in hdul:
                        if isinstance(hdu, fits.CompImageHDU):
                            return True
            except Exception:
                # If we can't read the file, assume it's not compressed
                pass
        
        return False
    
    def is_fits_file(self, file_path: str) -> bool:
        """
        Check if a file is a FITS file (compressed or uncompressed).
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if file is a FITS file, False otherwise
        """
        # Check for standard FITS extensions
        fits_extensions = ['.fits', '.fit', '.fts']
        
        # Check direct FITS extensions
        if any(file_path.lower().endswith(ext) for ext in fits_extensions):
            return True
            
        # Check for externally compressed FITS files
        external_compressed_extensions = ['.gz', '.xz', '.bz2', '.fz']
        for ext in external_compressed_extensions:
            if file_path.lower().endswith(ext):
                # Check if the base file (without compression extension) is a FITS file
                base_path = file_path[:-len(ext)]
                if any(base_path.lower().endswith(fits_ext) for fits_ext in fits_extensions):
                    return True
        
        return False
    
    def get_compressed_path(self, original_path: str, algorithm: str = None) -> str:
        """
        Get the compressed version path for an original file.
        
        Args:
            original_path: Path to the original file
            algorithm: Compression algorithm to use
            
        Returns:
            Path where the compressed file should be stored
        """
        algo_info = self.get_algorithm_info(algorithm)
        return f"{original_path}{algo_info['extension']}"
    
    def get_uncompressed_path(self, compressed_path: str) -> str:
        """
        Get the original file path from a compressed file path.
        
        Args:
            compressed_path: Path to the compressed file
            
        Returns:
            Path to the original uncompressed file
        """
        # Remove compression extensions
        if compressed_path.lower().endswith('.gz'):
            return compressed_path[:-3]
        elif compressed_path.lower().endswith('.xz'):
            return compressed_path[:-3]
        elif compressed_path.lower().endswith('.bz2'):
            return compressed_path[:-4]
        elif compressed_path.lower().endswith('.fz'):
            return compressed_path[:-3]
        else:
            return compressed_path
    
    def calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of a file for verification.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal hash string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def compress_fits_file(self, input_path: str, replace_original: bool = True, 
                          algorithm: str = None) -> Optional[str]:
        """
        Compress a FITS file using advanced lossless compression.
        
        Args:
            input_path: Path to the input FITS file
            replace_original: If True, replace the original file with compressed version
            algorithm: Compression algorithm ('gzip', 'lzma', 'bzip2', 'auto')
            
        Returns:
            Path to the compressed file if successful, None if failed
        """
        try:
            if not os.path.exists(input_path):
                logger.error(f"Input file does not exist: {input_path}")
                return None
            
            if self.is_compressed(input_path):
                logger.debug(f"File already compressed: {input_path}")
                return input_path
            
            # Verify it's a valid FITS file before compressing
            try:
                with fits.open(input_path, mode='readonly') as hdul:
                    # Just check if we can open it
                    pass
            except Exception as e:
                logger.error(f"Invalid FITS file, cannot compress: {input_path} - {e}")
                return None
            
            # Select compression algorithm
            selected_algorithm = algorithm or self.compression_algorithm

            # For auto-import, "auto" means FITS tile compression.
            # The required convention for this project is GZIP_2.
            if selected_algorithm == 'auto':
                selected_algorithm = 'fits_gzip2'
            
            # Ensure we have a valid algorithm (no auto-selection)
            if selected_algorithm not in self.algorithms:
                logger.error(f"Unsupported compression algorithm: {selected_algorithm}")
                return None
            
            return self._compress_with_algorithm(input_path, replace_original, selected_algorithm)
                
        except Exception as e:
            logger.error(f"Error compressing FITS file {input_path}: {e}")
            return None
    
    def _compress_with_algorithm(self, input_path: str, replace_original: bool, 
                                algorithm: str) -> Optional[str]:
        """
        Compress with a specific algorithm.
        
        Args:
            input_path: Path to input file
            replace_original: Whether to replace original
            algorithm: Specific algorithm to use
            
        Returns:
            Path to compressed file
        """
        try:
            algo_info = self.get_algorithm_info(algorithm)
            output_path = self.get_compressed_path(input_path, algorithm)
            
            original_size = os.path.getsize(input_path)
            
            logger.info(f"Compressing FITS file with {algorithm}: {input_path}")
            
            # Compress based on algorithm
            if algorithm == 'gzip':
                with open(input_path, 'rb') as f_in:
                    with gzip.open(output_path, 'wb', compresslevel=self.compression_level) as f_out:
                        shutil.copyfileobj(f_in, f_out)
            
            elif algorithm == 'lzma':
                with open(input_path, 'rb') as f_in:
                    with lzma.open(output_path, 'wb', preset=self.compression_level) as f_out:
                        shutil.copyfileobj(f_in, f_out)
            
            elif algorithm == 'bzip2':
                with open(input_path, 'rb') as f_in:
                    with bz2.open(output_path, 'wb', compresslevel=self.compression_level) as f_out:
                        shutil.copyfileobj(f_in, f_out)
            
            elif algorithm.startswith('fits_'):
                # FITS internal compression using astropy
                return self._compress_fits_internal(input_path, replace_original, algorithm)
            
            else:
                logger.error(f"Unsupported compression algorithm: {algorithm}")
                return None
            
            compressed_size = os.path.getsize(output_path)
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            logger.info(f"{algorithm} compression complete: {original_size:,} bytes -> "
                       f"{compressed_size:,} bytes ({compression_ratio:.1f}% reduction)")
            
            # Verify compression if enabled
            if self.verify_compression:
                if not self._verify_compression(output_path, input_path, algorithm):
                    logger.error(f"{algorithm} compression verification failed for {input_path}")
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    return None
                logger.debug(f"{algorithm} compression verification successful for {input_path}")
            
            # Replace original file if requested
            if replace_original:
                try:
                    os.remove(input_path)
                    logger.debug(f"Removed original file: {input_path}")
                except Exception as e:
                    logger.warning(f"Could not remove original file {input_path}: {e}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error compressing with {algorithm}: {input_path} - {e}")
            return None
    
    def decompress_fits_file(self, compressed_path: str, output_path: Optional[str] = None, 
                           replace_compressed: bool = False) -> Optional[str]:
        """
        Decompress a compressed FITS file (supports multiple algorithms).
        
        Args:
            compressed_path: Path to the compressed file
            output_path: Path for the decompressed file (auto-generated if None)
            replace_compressed: If True, remove the compressed file after decompression
            
        Returns:
            Path to the decompressed file if successful, None if failed
        """
        try:
            if not os.path.exists(compressed_path):
                logger.error(f"Compressed file does not exist: {compressed_path}")
                return None
            
            if not self.is_compressed(compressed_path):
                logger.debug(f"File is not compressed: {compressed_path}")
                return compressed_path
            
            if output_path is None:
                output_path = self.get_uncompressed_path(compressed_path)
            
            # Detect compression algorithm from extension
            algorithm = self._detect_compression_algorithm(compressed_path)
            
            logger.info(f"Decompressing FITS file with {algorithm}: {compressed_path}")
            
            compressed_size = os.path.getsize(compressed_path)
            
            # Decompress based on detected algorithm
            if algorithm == 'gzip':
                with gzip.open(compressed_path, 'rb') as f_in:
                    with open(output_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            
            elif algorithm == 'lzma':
                with lzma.open(compressed_path, 'rb') as f_in:
                    with open(output_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            
            elif algorithm == 'bzip2':
                with bz2.open(compressed_path, 'rb') as f_in:
                    with open(output_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

            elif algorithm == 'fits_internal':
                # FITS tile-compressed files (.fz) are still valid FITS files and can be read
                # directly by astropy/cfitsio. If an uncompressed copy is required, it can be
                # produced by opening with astropy and rewriting to a new .fits path.
                logger.error(
                    f"Tile-compressed FITS (.fz) does not use stream decompression: {compressed_path}"
                )
                return None
            
            else:
                logger.error(f"Unsupported compression format: {compressed_path}")
                return None
            
            decompressed_size = os.path.getsize(output_path)
            
            logger.info(f"{algorithm} decompression complete: {compressed_size:,} bytes -> {decompressed_size:,} bytes")
            
            # Verify decompressed file is valid FITS
            try:
                with fits.open(output_path, mode='readonly') as hdul:
                    # Just check if we can open it
                    pass
                logger.debug(f"Decompressed FITS file verification successful: {output_path}")
            except Exception as e:
                logger.error(f"Decompressed file is not valid FITS: {output_path} - {e}")
                # Clean up invalid decompressed file
                if os.path.exists(output_path):
                    os.remove(output_path)
                return None
            
            # Remove compressed file if requested
            if replace_compressed:
                try:
                    os.remove(compressed_path)
                    logger.debug(f"Removed compressed file: {compressed_path}")
                except Exception as e:
                    logger.warning(f"Could not remove compressed file {compressed_path}: {e}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error decompressing FITS file {compressed_path}: {e}")
            return None
    
    def _detect_compression_algorithm(self, file_path: str) -> str:
        """
        Detect compression algorithm from file extension.
        
        Args:
            file_path: Path to compressed file
            
        Returns:
            Algorithm name
        """
        file_lower = file_path.lower()
        
        if file_lower.endswith('.gz'):
            return 'gzip'
        elif file_lower.endswith('.xz'):
            return 'lzma'
        elif file_lower.endswith('.bz2'):
            return 'bzip2'
        elif file_lower.endswith('.fz'):
            return 'fits_internal'
        else:
            return 'gzip'  # Default fallback
    
    def _verify_compression(self, compressed_path: str, original_path: str, algorithm: str) -> bool:
        """
        Verify that compression was successful by decompressing and comparing.
        
        Args:
            compressed_path: Path to compressed file
            original_path: Path to original file
            algorithm: Compression algorithm used
            
        Returns:
            True if verification successful, False otherwise
        """
        try:
            # Create temporary file for decompression test using configured temp folder
            temp_folder = get_temp_folder()
            with tempfile.NamedTemporaryFile(delete=False, dir=temp_folder) as temp_file:
                temp_path = temp_file.name
            
            # Attempt decompression
            if algorithm == 'gzip':
                with gzip.open(compressed_path, 'rb') as f_in:
                    with open(temp_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            elif algorithm == 'lzma':
                with lzma.open(compressed_path, 'rb') as f_in:
                    with open(temp_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            elif algorithm == 'bzip2':
                with bz2.open(compressed_path, 'rb') as f_in:
                    with open(temp_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                return False
            
            # Verify file sizes match
            if os.path.getsize(temp_path) != os.path.getsize(original_path):
                return False
            
            # Verify it's a valid FITS file
            try:
                with fits.open(temp_path, mode='readonly') as hdul:
                    # Just check if we can open it
                    pass
            except Exception:
                return False
            
            return True
            
        except Exception:
            return False
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
    
    def _select_optimal_compression(self, fits_path: str) -> Optional[str]:
        """
        Select optimal compression algorithm based on FITS data type.
        
        Args:
            fits_path: Path to FITS file
            
        Returns:
            Optimal algorithm name, or None if unable to determine
        """
        try:
            with fits.open(fits_path) as hdul:
                # Find the primary data HDU
                data_hdu = None
                for hdu in hdul:
                    if hasattr(hdu, 'data') and hdu.data is not None:
                        data_hdu = hdu
                        break
                
                if data_hdu is None:
                    logger.warning("No data found in FITS file for compression analysis")
                    return 'fits_gzip2'  # Default fallback
                
                data_dtype = data_hdu.data.dtype
                logger.info(f"FITS data type detected: {data_dtype}")
                
                # Integer data: Use RICE (lossless, designed for integers, NINA compatible)
                if data_dtype.kind in ['i', 'u']:  # signed or unsigned integer
                    if data_dtype.itemsize <= 2:  # 8-bit or 16-bit integers
                        logger.info("Using RICE compression for integer data (NINA compatible)")
                        return 'fits_rice'
                    else:  # 32-bit+ integers - RICE may not be optimal
                        logger.info("Using GZIP-2 for large integer data") 
                        return 'fits_gzip2'
                
                # Floating-point data: Use GZIP-2 (best compression, lossless)
                elif data_dtype.kind == 'f':  # floating point
                    logger.info("Using GZIP-2 compression for floating-point data")
                    return 'fits_gzip2'
                
                # Complex or other data types: Use conservative GZIP-1
                else:
                    logger.info(f"Using GZIP-1 for unknown data type: {data_dtype}")
                    return 'fits_gzip1'
                
        except Exception as e:
            logger.error(f"Error analyzing FITS file for compression: {e}")
            return 'fits_gzip2'  # Safe fallback
    
    def _compress_fits_internal(self, input_path: str, replace_original: bool, algorithm: str) -> str | None:
        """
        Compress FITS file using internal FITS compression (tile compression).

        The compressed copy is written to a temporary file, verified against the untouched
        original, and only then moved into place, so the original survives any failure.

        Args:
            input_path: Path to input FITS file
            replace_original: Whether to replace the original file (keeping its name)
            algorithm: The ``fits_*`` setting; all of them produce GZIP_2 (the project convention)

        Returns:
            Path to compressed FITS file
        """
        # When replacing the original (auto-import), keep the filename unchanged.
        output_path = input_path if replace_original else f"{input_path}.fz"
        temp_path = f"{output_path}.tmp"
        try:
            original_size = os.path.getsize(input_path)

            with fits.open(input_path, memmap=False) as hdul:
                target_idx = _find_image_hdu_index(hdul)
                if target_idx is None:
                    logger.debug("No image data found to compress: %s", input_path)
                    return input_path
                fits.HDUList(_rebuild_with_compressed_image(hdul, target_idx)).writeto(temp_path, overwrite=True)

            if self.verify_compression and not self._verify_fits_internal_compression(temp_path, input_path):
                logger.error("FITS %s compression verification failed for %s; original left untouched",
                             algorithm, input_path)
                return None

            os.replace(temp_path, output_path)

            compressed_size = os.path.getsize(output_path)
            logger.info("%s FITS compression complete: %s bytes -> %s bytes (%.1f%% reduction)",
                        algorithm, f"{original_size:,}", f"{compressed_size:,}",
                        _compression_ratio(original_size, compressed_size))
            return output_path

        except Exception:  # reported and turned into a None result; original is untouched
            logger.exception("Error in FITS internal compression %s: %s", algorithm, input_path)
            return None
        finally:
            if os.path.exists(temp_path):
                _remove_quietly(temp_path)

    def _verify_fits_internal_compression(self, compressed_path: str, original_path: str) -> bool:
        """
        Verify FITS internal compression: every data HDU must decompress to exactly the
        original values (NaN == NaN) and no HISTORY/COMMENT card may be lost.

        Args:
            compressed_path: Path to compressed FITS file
            original_path: Path to original FITS file

        Returns:
            True if verification successful
        """
        try:
            with fits.open(original_path, memmap=False) as orig_hdul, \
                    fits.open(compressed_path, memmap=False) as comp_hdul:
                orig_hdus = _data_hdus(orig_hdul)
                comp_hdus = _data_hdus(comp_hdul)
                if len(orig_hdus) != len(comp_hdus):
                    logger.error("HDU count mismatch: original has %d data HDUs, compressed has %d",
                                 len(orig_hdus), len(comp_hdus))
                    return False

                for number, (orig, comp) in enumerate(zip(orig_hdus, comp_hdus, strict=True)):
                    if not _data_equal(np.asarray(orig.data), np.asarray(comp.data)):
                        logger.error("Data mismatch in data HDU %d after compression", number)
                        return False

                lost = _commentary_counts(orig_hdul) - _commentary_counts(comp_hdul)
                if lost:
                    logger.error("Header cards lost in compression: %s", dict(lost))
                    return False
            return True

        except Exception:  # any failure to verify counts as "not verified"
            logger.exception("Error verifying FITS internal compression")
            return False

    def should_compress_file(self, file_path: str) -> bool:
        """
        Determine if a file should be compressed based on configuration and file properties.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if file should be compressed, False otherwise
        """
        if not self.compression_enabled:
            return False
        
        if self.is_compressed(file_path):
            return False
        
        # Only compress FITS files
        if not file_path.lower().endswith(('.fits', '.fit', '.fts')):
            return False
        
        # Check if file exists and is readable
        if not os.path.exists(file_path) or not os.access(file_path, os.R_OK):
            return False
        
        # Check minimum file size (don't compress very small files)
        min_size = self.config.getint('DEFAULT', 'min_compression_size', fallback=1024)  # 1KB default
        if os.path.getsize(file_path) < min_size:
            return False
        
        return True
    
    def process_file_for_compression(self, file_path: str) -> Optional[str]:
        """
        Process a file for compression if appropriate.
        
        This is the main entry point for automatic compression during file processing.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            Path to the final file (compressed or original) if successful, None if failed
        """
        try:
            if not self.should_compress_file(file_path):
                logger.debug(f"Skipping compression for: {file_path}")
                return file_path
            
            compressed_path = self.compress_fits_file(file_path, replace_original=True)
            
            if compressed_path:
                logger.info(f"Successfully compressed: {file_path} -> {compressed_path}")
                return compressed_path
            else:
                logger.warning(f"Compression failed for: {file_path}")
                return file_path
                
        except Exception as e:
            logger.error(f"Error processing file for compression {file_path}: {e}")
            return file_path


# Global compressor instance
_compressor_instance = None

def get_fits_compressor(config_path: str = 'astrofiler.ini') -> FitsCompressor:
    """
    Get a global FitsCompressor instance.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        FitsCompressor instance
    """
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = FitsCompressor(config_path)
    return _compressor_instance


def compress_fits_file(file_path: str) -> Optional[str]:
    """
    Convenience function to compress a FITS file.
    
    Args:
        file_path: Path to the FITS file to compress
        
    Returns:
        Path to compressed file if successful, original path if compression not enabled/failed
    """
    compressor = get_fits_compressor()
    result = compressor.process_file_for_compression(file_path)
    return result if result else file_path


def is_compression_enabled() -> bool:
    """
    Check if FITS compression is enabled in configuration.
    
    Returns:
        True if compression is enabled, False otherwise
    """
    compressor = get_fits_compressor()
    return compressor.compression_enabled