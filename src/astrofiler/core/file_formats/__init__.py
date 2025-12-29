"""
File format processing abstractions for AstroFiler.

This module provides protocol definitions and base classes for handling
different astronomical image file formats in an extensible manner.
"""

from abc import ABC, abstractmethod
from typing import Protocol, Optional, Dict, Any
from ...types import FilePath
from ...exceptions import FileProcessingError


class FileFormatHandler(Protocol):
    """Protocol for file format handlers following Open/Closed Principle."""
    
    def can_handle(self, file_path: FilePath) -> bool:
        """
        Check if this handler can process the given file.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if this handler can process the file
        """
        ...
    
    def get_supported_extensions(self) -> list[str]:
        """
        Get list of file extensions supported by this handler.
        
        Returns:
            List of supported file extensions (with dots, e.g., ['.fits', '.fit'])
        """
        ...
    
    def process_file(self, file_path: FilePath) -> FilePath:
        """
        Process the file and return path to the processed/converted file.
        
        Args:
            file_path: Path to the input file
            
        Returns:
            Path to the processed file (may be same as input for native formats)
            
        Raises:
            FileProcessingError: If processing fails
        """
        ...
    
    def get_format_name(self) -> str:
        """
        Get human-readable name of the format handled.
        
        Returns:
            Format name (e.g., "FITS", "ZIP Archive", "XISF")
        """
        ...


class BaseFileFormatHandler(ABC):
    """Base class for file format handlers with common functionality."""
    
    def __init__(self):
        self._supported_extensions = self._get_supported_extensions()
    
    @abstractmethod
    def _get_supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        pass
    
    @abstractmethod
    def get_format_name(self) -> str:
        """Return human-readable format name."""
        pass
    
    @abstractmethod
    def _process_file_internal(self, file_path: FilePath) -> FilePath:
        """Internal file processing implementation."""
        pass
    
    def can_handle(self, file_path: FilePath) -> bool:
        """Check if this handler supports the file based on extension."""
        import os
        _, extension = os.path.splitext(file_path)
        return extension.lower() in [ext.lower() for ext in self._supported_extensions]
    
    def get_supported_extensions(self) -> list[str]:
        """Get list of supported extensions."""
        return self._supported_extensions.copy()
    
    def process_file(self, file_path: FilePath) -> FilePath:
        """
        Process file with error handling and validation.
        
        Args:
            file_path: Path to input file
            
        Returns:
            Path to processed file
            
        Raises:
            FileProcessingError: If file cannot be processed
        """
        if not self.can_handle(file_path):
            raise FileProcessingError(
                f"Handler {self.get_format_name()} cannot process file {file_path}",
                file_path=str(file_path),
                error_code="UNSUPPORTED_FORMAT"
            )
        
        import os
        if not os.path.exists(file_path):
            raise FileProcessingError(
                f"File does not exist: {file_path}",
                file_path=str(file_path),
                error_code="FILE_NOT_FOUND"
            )
        
        return self._process_file_internal(file_path)


class FileFormatProcessor:
    """
    Central processor for handling multiple file formats.
    
    Follows Open/Closed Principle - can be extended with new handlers
    without modifying existing code.
    """
    
    def __init__(self):
        self._handlers: list[FileFormatHandler] = []
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default file format handlers."""
        # Import handlers here to avoid circular imports
        from .handlers.fits_handler import FitsFileHandler
        from .handlers.gzip_handler import GzipFileHandler
        from .handlers.zip_handler import ZipFileHandler
        from .handlers.xisf_handler import XisfFileHandler
        
        self.register_handler(FitsFileHandler())
        self.register_handler(GzipFileHandler())
        self.register_handler(ZipFileHandler())
        self.register_handler(XisfFileHandler())
    
    def register_handler(self, handler: FileFormatHandler) -> None:
        """
        Register a new file format handler.
        
        Args:
            handler: File format handler to register
        """
        self._handlers.append(handler)
    
    def unregister_handler(self, format_name: str) -> bool:
        """
        Unregister a file format handler by name.
        
        Args:
            format_name: Name of the format handler to remove
            
        Returns:
            True if handler was found and removed
        """
        for i, handler in enumerate(self._handlers):
            if handler.get_format_name() == format_name:
                self._handlers.pop(i)
                return True
        return False
    
    def get_supported_formats(self) -> Dict[str, list[str]]:
        """
        Get dictionary of all supported formats and their extensions.
        
        Returns:
            Dict mapping format names to lists of supported extensions
        """
        formats = {}
        for handler in self._handlers:
            formats[handler.get_format_name()] = handler.get_supported_extensions()
        return formats
    
    def find_handler(self, file_path: FilePath) -> Optional[FileFormatHandler]:
        """
        Find the appropriate handler for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Handler that can process the file, or None if no handler found
        """
        for handler in self._handlers:
            if handler.can_handle(file_path):
                return handler
        return None
    
    def can_process(self, file_path: FilePath) -> bool:
        """
        Check if any registered handler can process the file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if a handler is available for the file
        """
        return self.find_handler(file_path) is not None
    
    def process_file(self, file_path: FilePath) -> FilePath:
        """
        Process a file using the appropriate handler.
        
        Args:
            file_path: Path to the input file
            
        Returns:
            Path to the processed file
            
        Raises:
            FileProcessingError: If no handler available or processing fails
        """
        handler = self.find_handler(file_path)
        if not handler:
            import os
            _, extension = os.path.splitext(file_path)
            raise FileProcessingError(
                f"No handler available for file format: {extension}",
                file_path=str(file_path),
                error_code="UNSUPPORTED_FORMAT"
            )
        
        return handler.process_file(file_path)
    
    def get_handler_count(self) -> int:
        """Get number of registered handlers."""
        return len(self._handlers)
    
    def list_handlers(self) -> list[str]:
        """Get list of registered handler format names."""
        return [handler.get_format_name() for handler in self._handlers]


# Global instance for convenience
_global_processor: Optional[FileFormatProcessor] = None


def get_file_format_processor() -> FileFormatProcessor:
    """
    Get the global file format processor instance.
    
    Returns:
        Singleton FileFormatProcessor instance
    """
    global _global_processor
    if _global_processor is None:
        _global_processor = FileFormatProcessor()
    return _global_processor


def reset_file_format_processor() -> None:
    """Reset the global processor (mainly for testing)."""
    global _global_processor
    _global_processor = None