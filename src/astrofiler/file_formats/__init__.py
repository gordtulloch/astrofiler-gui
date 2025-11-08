"""
File format support for AstroFiler.

This package contains file format handling functionality including:
- XISF file conversion support
- File format detection and processing
"""

# Re-export xisfFile package for backward compatibility
from .xisfFile import XISFConverter

__all__ = ['XISFConverter']