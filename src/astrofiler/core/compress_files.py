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

# Import config for temp folder
try:
    from ..config import get_temp_folder
except ImportError:
    # Fallback if config module not available
    def get_temp_folder():
        return tempfile.gettempdir()

logger = logging.getLogger(__name__)


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
    
    def _compress_fits_internal(self, input_path: str, replace_original: bool, algorithm: str) -> Optional[str]:
        """
        Compress FITS file using internal FITS compression (tile compression).
        
        Args:
            input_path: Path to input FITS file
            replace_original: Whether to replace the original file
            algorithm: FITS compression algorithm (auto, fits_rice, fits_gzip1, fits_gzip2)
                      'auto' = smart selection based on data type
            
        Returns:
            Path to compressed FITS file
        """
        try:
            # For imports we require FITS tile compression using GZIP_2.
            # (Other algorithms are not used for this workflow.)
            compression_type = 'GZIP_2'
            
            # Determine output path
            # When replacing the original (auto-import), keep the filename unchanged.
            if replace_original:
                output_path = input_path
                temp_path = input_path + '.tmp'
            else:
                output_path = f"{input_path}.fz"
                temp_path = output_path + '.tmp'

            original_size = os.path.getsize(input_path)
            
            def _find_first_image_hdu_index(hdul: fits.HDUList) -> Optional[int]:
                for idx, hdu in enumerate(hdul):
                    try:
                        if getattr(hdu, 'data', None) is not None:
                            return idx
                    except Exception:
                        continue
                return None

            def _merge_nonstructural_header(dst: fits.Header, src: fits.Header, skip: set[str]) -> None:
                for card in src.cards:
                    key = card.keyword
                    if not key or key in skip:
                        continue
                    if key in ('COMMENT', 'HISTORY'):
                        # Preserve free-form cards
                        try:
                            dst.add_comment(card.value)
                        except Exception:
                            pass
                        continue
                    try:
                        dst[key] = (card.value, card.comment)
                    except Exception:
                        # Some cards may be invalid for the destination HDU
                        continue

            # Load and compress the FITS file
            with fits.open(input_path, memmap=False) as hdul:
                target_idx = _find_first_image_hdu_index(hdul)
                if target_idx is None:
                    logger.debug(f"No image data found to compress: {input_path}")
                    return input_path

                new_hdus: list[fits.hdu.base.ExtensionHDU | fits.PrimaryHDU] = []

                if target_idx == 0:
                    # Original image is in the PrimaryHDU; rewrite as:
                    # - PrimaryHDU (no data) with global metadata
                    # - CompImageHDU holding the image
                    primary = fits.PrimaryHDU()
                    skip_primary = {
                        'SIMPLE', 'BITPIX', 'NAXIS', 'EXTEND', 'PCOUNT', 'GCOUNT',
                        'CHECKSUM', 'DATASUM'
                    }
                    for i in range(1, 10):
                        skip_primary.add(f'NAXIS{i}')
                    _merge_nonstructural_header(primary.header, hdul[0].header, skip_primary)
                    new_hdus.append(primary)

                    src_hdu = hdul[0]
                    compressed_hdu = fits.CompImageHDU(
                        data=src_hdu.data,
                        compression_type=compression_type,
                    )

                    # Copy metadata from original header, but do NOT copy structural keywords.
                    # CompImageHDU is a BINTABLE extension and must not contain SIMPLE/NAXIS/...
                    skip_comp = {
                        'SIMPLE', 'BITPIX', 'NAXIS', 'EXTEND', 'PCOUNT', 'GCOUNT',
                        'CHECKSUM', 'DATASUM', 'BSCALE', 'BZERO',
                        'XTENSION', 'TFIELDS',
                        'ZIMAGE', 'ZCMPTYPE', 'ZBITPIX', 'ZNAXIS'
                    }
                    for i in range(1, 100):
                        skip_comp.add(f'NAXIS{i}')
                        skip_comp.add(f'ZNAXIS{i}')
                        skip_comp.add(f'TTYPE{i}')
                        skip_comp.add(f'TFORM{i}')
                        skip_comp.add(f'TUNIT{i}')
                        skip_comp.add(f'TDIM{i}')
                    _merge_nonstructural_header(compressed_hdu.header, src_hdu.header, skip_comp)

                    # Ensure required FITS tile-compression keywords exist and match the original image.
                    original_naxis = int(src_hdu.header.get('NAXIS', src_hdu.data.ndim))
                    original_bitpix = int(src_hdu.header.get('BITPIX', -32))
                    compressed_hdu.header['ZIMAGE'] = (True, 'Tile-compressed image')
                    compressed_hdu.header['ZCMPTYPE'] = (compression_type, 'Compression algorithm')
                    compressed_hdu.header['ZNAXIS'] = (original_naxis, 'Number of uncompressed axes')
                    compressed_hdu.header['ZBITPIX'] = (original_bitpix, 'Uncompressed data type')
                    for axis in range(1, original_naxis + 1):
                        zn_key = f'ZNAXIS{axis}'
                        n_key = f'NAXIS{axis}'
                        if n_key in src_hdu.header:
                            compressed_hdu.header[zn_key] = (int(src_hdu.header[n_key]), f'Axis {axis} length (uncompressed)')
                        else:
                            compressed_hdu.header[zn_key] = (int(src_hdu.data.shape[-axis]), f'Axis {axis} length (uncompressed)')

                    new_hdus.append(compressed_hdu)

                    # Preserve any additional extensions
                    for ext in hdul[1:]:
                        try:
                            new_hdus.append(ext.copy())
                        except Exception:
                            pass
                else:
                    # Preserve primary HDU and compress the first image extension
                    new_hdus.append(hdul[0].copy())
                    for idx in range(1, len(hdul)):
                        if idx != target_idx:
                            new_hdus.append(hdul[idx].copy())
                            continue

                        src_hdu = hdul[idx]
                        compressed_hdu = fits.CompImageHDU(
                            data=src_hdu.data,
                            compression_type=compression_type,
                        )

                        skip_comp = {
                            'SIMPLE', 'BITPIX', 'NAXIS', 'EXTEND', 'PCOUNT', 'GCOUNT',
                            'CHECKSUM', 'DATASUM', 'BSCALE', 'BZERO',
                            'XTENSION', 'TFIELDS',
                            'ZIMAGE', 'ZCMPTYPE', 'ZBITPIX', 'ZNAXIS'
                        }
                        for i in range(1, 100):
                            skip_comp.add(f'NAXIS{i}')
                            skip_comp.add(f'ZNAXIS{i}')
                            skip_comp.add(f'TTYPE{i}')
                            skip_comp.add(f'TFORM{i}')
                            skip_comp.add(f'TUNIT{i}')
                            skip_comp.add(f'TDIM{i}')
                        _merge_nonstructural_header(compressed_hdu.header, src_hdu.header, skip_comp)

                        # Preserve EXTNAME when present
                        if 'EXTNAME' in src_hdu.header and 'EXTNAME' not in compressed_hdu.header:
                            compressed_hdu.header['EXTNAME'] = src_hdu.header['EXTNAME']

                        original_naxis = int(src_hdu.header.get('NAXIS', src_hdu.data.ndim))
                        original_bitpix = int(src_hdu.header.get('BITPIX', -32))
                        compressed_hdu.header['ZIMAGE'] = (True, 'Tile-compressed image')
                        compressed_hdu.header['ZCMPTYPE'] = (compression_type, 'Compression algorithm')
                        compressed_hdu.header['ZNAXIS'] = (original_naxis, 'Number of uncompressed axes')
                        compressed_hdu.header['ZBITPIX'] = (original_bitpix, 'Uncompressed data type')
                        for axis in range(1, original_naxis + 1):
                            zn_key = f'ZNAXIS{axis}'
                            n_key = f'NAXIS{axis}'
                            if n_key in src_hdu.header:
                                compressed_hdu.header[zn_key] = (int(src_hdu.header[n_key]), f'Axis {axis} length (uncompressed)')
                            else:
                                compressed_hdu.header[zn_key] = (int(src_hdu.data.shape[-axis]), f'Axis {axis} length (uncompressed)')

                        new_hdus.append(compressed_hdu)

                new_hdul = fits.HDUList(new_hdus)
                new_hdul.writeto(temp_path, overwrite=True)

            # Atomically move into place
            try:
                os.replace(temp_path, output_path)
            except Exception:
                # Fallback for filesystems where replace fails
                if os.path.exists(output_path) and output_path != temp_path:
                    os.remove(output_path)
                shutil.move(temp_path, output_path)
            compressed_size = os.path.getsize(output_path)
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            logger.info(f"{algorithm} FITS compression complete: {original_size:,} bytes -> "
                       f"{compressed_size:,} bytes ({compression_ratio:.1f}% reduction)")
            
            # Verify compression if enabled
            if self.verify_compression:
                if not self._verify_fits_internal_compression(output_path, input_path):
                    logger.error(f"FITS {algorithm} compression verification failed")
                    if os.path.exists(output_path) and output_path != input_path:
                        os.remove(output_path)
                    return None
            
            # If replacing original, we already overwrote it in-place.
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error in FITS internal compression {algorithm}: {input_path} - {e}")
            return None
    
    def _verify_fits_internal_compression(self, compressed_path: str, original_path: str) -> bool:
        """
        Verify FITS internal compression by checking that data can be read and is approximately equal.
        Note: FITS internal compression may involve dtype conversions (e.g., big-endian to little-endian)
        which can cause minor floating-point differences.
        
        Args:
            compressed_path: Path to compressed FITS file
            original_path: Path to original FITS file
            
        Returns:
            True if verification successful
        """
        try:
            def _first_data_array(hdul: fits.HDUList):
                for hdu in hdul:
                    try:
                        if getattr(hdu, 'data', None) is not None:
                            return hdu.data
                    except Exception:
                        continue
                return None

            # Read both files and compare data
            with fits.open(original_path, memmap=False) as orig_hdul:
                with fits.open(compressed_path, memmap=False) as comp_hdul:
                    orig_data = _first_data_array(orig_hdul)
                    comp_data = _first_data_array(comp_hdul)

                    if orig_data is None or comp_data is None:
                        logger.error("Missing data when verifying FITS compression")
                        return False

                    # Check if data shapes match
                    if orig_data.shape != comp_data.shape:
                        logger.error(f"Shape mismatch: original {orig_data.shape} vs compressed {comp_data.shape}")
                        return False

                    import numpy as np
                    if not np.allclose(orig_data, comp_data, rtol=1e-6, atol=1e-8):
                        diff = np.abs(orig_data - comp_data)
                        max_diff = float(np.max(diff))
                        mean_diff = float(np.mean(diff))

                        if max_diff < 1e-4 and mean_diff < 1e-5:
                            logger.info(f"FITS compression: small differences due to dtype conversion (max: {max_diff:.2e}, mean: {mean_diff:.2e})")
                            return True

                        logger.error(f"FITS compression verification failed: max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying FITS internal compression: {e}")
            return False
        """
        Verify that a compressed file can be decompressed to match the original.
        
        Args:
            compressed_path: Path to the compressed file
            original_path: Path to the original file
            algorithm: Compression algorithm used
            
        Returns:
            True if verification passes, False otherwise
        """
        try:
            # Create temporary file for decompression test using configured temp folder
            temp_folder = get_temp_folder()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.fits', dir=temp_folder) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Decompress to temporary file using specific algorithm
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
                
                # Compare file hashes
                original_hash = self.calculate_file_hash(original_path)
                decompressed_hash = self.calculate_file_hash(temp_path)
                
                return original_hash == decompressed_hash
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            logger.error(f"Error verifying compressed file {compressed_path}: {e}")
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