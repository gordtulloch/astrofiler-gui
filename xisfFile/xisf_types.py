"""
XISF data types and enums.

This module contains the data type definitions used by the XISF converter
to avoid circular import issues.
"""

import struct
from enum import Enum
from typing import Tuple


class XISFSampleFormat(Enum):
    """Enumeration of XISF sample formats with conversion utilities."""
    
    UINT8 = "UInt8"
    UINT16 = "UInt16"
    UINT32 = "UInt32"
    UINT64 = "UInt64"
    INT16 = "Int16"
    INT32 = "Int32"
    FLOAT32 = "Float32"
    FLOAT64 = "Float64"
    COMPLEX32 = "Complex32"
    COMPLEX64 = "Complex64"
    
    def size(self) -> int:
        """Return the size in bytes for this sample format."""
        sizes = {
            self.UINT8: 1,
            self.UINT16: 2,
            self.UINT32: 4,
            self.UINT64: 8,
            self.INT16: 2,
            self.INT32: 4,
            self.FLOAT32: 4,
            self.FLOAT64: 8,
            self.COMPLEX32: 8,   # 2 * 4 bytes
            self.COMPLEX64: 16,  # 2 * 8 bytes
        }
        return sizes[self]
    
    def to_fits_bitpix(self) -> int:
        """Convert to FITS BITPIX value."""
        bitpix_map = {
            self.UINT8: 8,
            self.UINT16: 16,     # Will be converted to signed
            self.UINT32: 32,     # Will be converted to signed
            self.UINT64: 64,     # Will be converted to signed
            self.INT16: 16,
            self.INT32: 32,
            self.FLOAT32: -32,
            self.FLOAT64: -64,
            self.COMPLEX32: -32,  # Convert to magnitude
            self.COMPLEX64: -64,  # Convert to magnitude
        }
        return bitpix_map[self]
    
    def to_numpy_dtype(self) -> str:
        """Convert to NumPy dtype string for binary reading."""
        dtype_map = {
            self.UINT8: '<u1',
            self.UINT16: '<u2',
            self.UINT32: '<u4',
            self.UINT64: '<u8',
            self.INT16: '<i2',
            self.INT32: '<i4',
            self.FLOAT32: '<f4',
            self.FLOAT64: '<f8',
            self.COMPLEX32: '<c8',
            self.COMPLEX64: '<c16',
        }
        return dtype_map[self]
    
    def to_numpy_type(self):
        """Convert to NumPy type for array creation."""
        import numpy as np
        type_map = {
            self.UINT8: np.uint8,
            self.UINT16: np.uint16,
            self.UINT32: np.uint32,
            self.UINT64: np.uint64,
            self.INT16: np.int16,
            self.INT32: np.int32,
            self.FLOAT32: np.float32,
            self.FLOAT64: np.float64,
            self.COMPLEX32: np.complex64,  # NumPy uses 64-bit complex for compatibility
            self.COMPLEX64: np.complex128,
        }
        return type_map[self]
    
    def to_struct_format(self) -> str:
        """Convert to struct format string for binary reading."""
        struct_map = {
            self.UINT8: '<B',
            self.UINT16: '<H',
            self.UINT32: '<I',
            self.UINT64: '<Q',
            self.INT16: '<h',
            self.INT32: '<i',
            self.FLOAT32: '<f',
            self.FLOAT64: '<d',
            self.COMPLEX32: '<ff',  # Two floats
            self.COMPLEX64: '<dd',  # Two doubles
        }
        return struct_map[self]
    
    def is_unsigned(self) -> bool:
        """Check if this is an unsigned integer format."""
        return self in [self.UINT8, self.UINT16, self.UINT32, self.UINT64]
    
    def is_complex(self) -> bool:
        """Check if this is a complex number format."""
        return self in [self.COMPLEX32, self.COMPLEX64]
    
    def is_floating_point(self) -> bool:
        """Check if this is a floating-point format."""
        return self in [self.FLOAT32, self.FLOAT64, self.COMPLEX32, self.COMPLEX64]
    
    @classmethod
    def from_string(cls, value: str) -> 'XISFSampleFormat':
        """Create XISFSampleFormat from string value."""
        for format_type in cls:
            if format_type.value == value:
                return format_type
        raise ValueError(f"Unknown sample format: {value}")


class XISFGeometry:
    """Represents XISF image geometry parsed from colon-separated format."""
    
    def __init__(self, geometry_str: str):
        """
        Initialize from geometry string.
        
        Args:
            geometry_str: Colon-separated dimensions like "1024:1024" or "1024:1024:3"
        """
        self.geometry_str = geometry_str
        self.dimensions = [int(x) for x in geometry_str.split(':')]
        
        if len(self.dimensions) < 2:
            raise ValueError(f"Invalid geometry: {geometry_str} (need at least width:height)")
    
    @property
    def width(self) -> int:
        """Image width (first dimension)."""
        return self.dimensions[0]
    
    @property
    def height(self) -> int:
        """Image height (second dimension)."""
        return self.dimensions[1]
    
    @property
    def channels(self) -> int:
        """Number of channels (third dimension, default 1)."""
        return self.dimensions[2] if len(self.dimensions) > 2 else 1
    
    @property
    def depth(self) -> int:
        """Depth dimension (fourth dimension, default 1)."""
        return self.dimensions[3] if len(self.dimensions) > 3 else 1
    
    @property
    def total_pixels(self) -> int:
        """Total number of pixels across all dimensions."""
        result = 1
        for dim in self.dimensions:
            result *= dim
        return result
    
    @property
    def is_color(self) -> bool:
        """Check if this is a color image (channels > 1)."""
        return self.channels > 1
    
    @property
    def is_multidimensional(self) -> bool:
        """Check if this has more than 2 dimensions."""
        return len(self.dimensions) > 2
    
    def to_fits_shape(self) -> Tuple[int, ...]:
        """
        Convert to FITS array shape.
        
        FITS uses (height, width) for 2D and (channels, height, width) for 3D.
        """
        if self.channels == 1:
            return (self.height, self.width)
        else:
            return (self.channels, self.height, self.width)
    
    def channel_size(self) -> int:
        """Calculate size of a single channel in pixels."""
        size = 1
        for dim in self.dimensions:
            size *= dim
        return size
    
    def __str__(self) -> str:
        """String representation."""
        return f"XISFGeometry({self.geometry_str})"
    
    def __repr__(self) -> str:
        """Detailed representation."""
        return (f"XISFGeometry(width={self.width}, height={self.height}, "
                f"channels={self.channels}, total_pixels={self.total_pixels})")