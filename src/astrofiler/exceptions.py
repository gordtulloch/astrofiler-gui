"""
Custom exceptions for AstroFiler application.

Provides a hierarchy of exceptions for better error handling and debugging.
"""

from typing import Optional, Any, Dict


class AstroFilerError(Exception):
    """Base exception for all AstroFiler errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, **kwargs):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = kwargs

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class DatabaseError(AstroFilerError):
    """Raised when database operations fail."""
    pass


class FileProcessingError(AstroFilerError):
    """Raised when file processing operations fail."""
    
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.file_path = file_path


class FitsHeaderError(FileProcessingError):
    """Raised when FITS header processing fails."""
    pass


class CalibrationError(AstroFilerError):
    """Raised when calibration operations fail."""
    pass


class RepositoryError(AstroFilerError):
    """Raised when repository operations fail."""
    pass


class TelescopeConnectionError(AstroFilerError):
    """Raised when telescope connection operations fail."""
    
    def __init__(self, message: str, telescope_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.telescope_name = telescope_name


class CloudSyncError(AstroFilerError):
    """Raised when cloud synchronization operations fail."""
    pass


class ConfigurationError(AstroFilerError):
    """Raised when configuration is invalid or missing."""
    pass


class ValidationError(AstroFilerError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.field = field


class QualityAnalysisError(AstroFilerError):
    """Raised when quality analysis operations fail."""
    pass


# Context managers for better resource handling
class DatabaseTransaction:
    """Context manager for database transactions."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        
    def __enter__(self):
        self.db.begin()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.db.rollback()
            return False
        else:
            self.db.commit()
            return True


class FileOperation:
    """Context manager for file operations with cleanup."""
    
    def __init__(self, temp_files: list = None):
        self.temp_files = temp_files or []
        
    def add_temp_file(self, file_path: str):
        """Add a temporary file to be cleaned up."""
        self.temp_files.append(file_path)
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup temporary files
        import os
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                pass  # Best effort cleanup