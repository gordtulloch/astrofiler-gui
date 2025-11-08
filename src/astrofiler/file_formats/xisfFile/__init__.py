"""
XISF File Package

This package provides functionality to read XISF (Extensible Image Serialization Format) files
and convert them to FITS format.

XISF is a file format used by PixInsight and other astronomical image processing software.
This package allows reading XISF files and converting them to the more widely supported FITS format.

Features:
- Complete XISF binary header parsing (signature, XML length, reserved fields)
- Support for all XISF sample formats (UInt8, UInt16, UInt32, UInt64, Int16, Int32, Float32, Float64, Complex32, Complex64)
- Comprehensive compression support (none, zlib, zlib+sh, lz4, lz4+sh, gzip)
- Byte shuffling/unshuffling for compressed data
- Proper endianness handling
- Attachment-based and inline data location support
- Detailed geometry parsing for multi-dimensional images
- FITS-compatible data type conversions with clipping for unsigned to signed conversion
- Extensive metadata preservation and XISF-specific FITS keywords
"""

from .xisf_converter import XISFConverter
from .xisf_types import XISFSampleFormat, XISFGeometry
from .data_conversion import prepare_fits_data, validate_data_integrity

__version__ = "2.0.0"
__author__ = "AstroFiler"

__all__ = [
    "XISFConverter", 
    "XISFSampleFormat", 
    "XISFGeometry",
    "prepare_fits_data",
    "validate_data_integrity"
]