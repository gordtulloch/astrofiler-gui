"""
Models package for AstroFiler.

This package contains all database model classes organized by functionality.
"""

from .base import BaseModel, db
from .fits_file import fitsFile
from .fits_session import fitsSession
from .mapping import Mapping
from .masters import Masters
from .variable_stars import VariableStars

__all__ = ['BaseModel', 'db', 'fitsFile', 'fitsSession', 'Mapping', 'Masters', 'VariableStars']