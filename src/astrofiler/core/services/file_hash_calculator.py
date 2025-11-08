"""
File hash calculation service for AstroFiler.

Provides hash calculation functionality with multiple algorithms
following Single Responsibility Principle.
"""

import hashlib
import logging
from typing import Optional
from ...types import FilePath
from ...exceptions import FileProcessingError

logger = logging.getLogger(__name__)


class FileHashCalculator:
    """
    Service for calculating file hashes.
    
    Single responsibility: File hash calculation with various algorithms.
    """
    
    def __init__(self, buffer_size: int = 4096):
        """
        Initialize hash calculator.
        
        Args:
            buffer_size: Size of read buffer in bytes (default 4096)
        """
        self.buffer_size = buffer_size
    
    def calculate_sha256(self, file_path: FilePath) -> str:
        """
        Calculate SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-256 hash hex string
            
        Raises:
            FileProcessingError: If file cannot be read
        """
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(self.buffer_size), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except (OSError, IOError) as e:
            logger.error(f"Error reading file for SHA-256 calculation: {file_path}")
            raise FileProcessingError(
                f"Cannot read file for hash calculation: {e}",
                file_path=str(file_path),
                error_code="FILE_READ_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error calculating SHA-256 for {file_path}: {str(e)}")
            raise FileProcessingError(
                f"Hash calculation failed: {e}",
                file_path=str(file_path),
                error_code="HASH_CALC_ERROR"
            )
    
    def calculate_md5(self, file_path: FilePath) -> str:
        """
        Calculate MD5 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            MD5 hash hex string
            
        Raises:
            FileProcessingError: If file cannot be read
        """
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(self.buffer_size), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (OSError, IOError) as e:
            logger.error(f"Error reading file for MD5 calculation: {file_path}")
            raise FileProcessingError(
                f"Cannot read file for hash calculation: {e}",
                file_path=str(file_path),
                error_code="FILE_READ_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error calculating MD5 for {file_path}: {str(e)}")
            raise FileProcessingError(
                f"Hash calculation failed: {e}",
                file_path=str(file_path),
                error_code="HASH_CALC_ERROR"
            )
    
    def calculate_sha1(self, file_path: FilePath) -> str:
        """
        Calculate SHA-1 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-1 hash hex string
            
        Raises:
            FileProcessingError: If file cannot be read
        """
        try:
            hash_sha1 = hashlib.sha1()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(self.buffer_size), b""):
                    hash_sha1.update(chunk)
            return hash_sha1.hexdigest()
        except (OSError, IOError) as e:
            logger.error(f"Error reading file for SHA-1 calculation: {file_path}")
            raise FileProcessingError(
                f"Cannot read file for hash calculation: {e}",
                file_path=str(file_path),
                error_code="FILE_READ_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error calculating SHA-1 for {file_path}: {str(e)}")
            raise FileProcessingError(
                f"Hash calculation failed: {e}",
                file_path=str(file_path),
                error_code="HASH_CALC_ERROR"
            )
    
    def calculate_multiple_hashes(self, file_path: FilePath, algorithms: list[str] = None) -> dict[str, str]:
        """
        Calculate multiple hashes for a file in a single pass.
        
        Args:
            file_path: Path to the file
            algorithms: List of algorithms to use ['sha256', 'md5', 'sha1']
                       If None, defaults to ['sha256']
            
        Returns:
            Dictionary mapping algorithm names to hash values
            
        Raises:
            FileProcessingError: If file cannot be read
        """
        if algorithms is None:
            algorithms = ['sha256']
        
        # Validate algorithms
        valid_algorithms = {'sha256', 'md5', 'sha1'}
        invalid_algorithms = set(algorithms) - valid_algorithms
        if invalid_algorithms:
            raise FileProcessingError(
                f"Unsupported hash algorithms: {invalid_algorithms}",
                file_path=str(file_path),
                error_code="INVALID_HASH_ALGORITHM"
            )
        
        try:
            # Initialize hash objects
            hashers = {}
            for algorithm in algorithms:
                if algorithm == 'sha256':
                    hashers[algorithm] = hashlib.sha256()
                elif algorithm == 'md5':
                    hashers[algorithm] = hashlib.md5()
                elif algorithm == 'sha1':
                    hashers[algorithm] = hashlib.sha1()
            
            # Read file and update all hashers
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(self.buffer_size), b""):
                    for hasher in hashers.values():
                        hasher.update(chunk)
            
            # Return results
            return {algorithm: hasher.hexdigest() for algorithm, hasher in hashers.items()}
            
        except (OSError, IOError) as e:
            logger.error(f"Error reading file for hash calculation: {file_path}")
            raise FileProcessingError(
                f"Cannot read file for hash calculation: {e}",
                file_path=str(file_path),
                error_code="FILE_READ_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error calculating hashes for {file_path}: {str(e)}")
            raise FileProcessingError(
                f"Hash calculation failed: {e}",
                file_path=str(file_path),
                error_code="HASH_CALC_ERROR"
            )


# Global instance for convenience
_global_calculator: Optional[FileHashCalculator] = None


def get_file_hash_calculator() -> FileHashCalculator:
    """
    Get the global file hash calculator instance.
    
    Returns:
        Singleton FileHashCalculator instance
    """
    global _global_calculator
    if _global_calculator is None:
        _global_calculator = FileHashCalculator()
    return _global_calculator


def reset_file_hash_calculator() -> None:
    """Reset the global calculator (mainly for testing)."""
    global _global_calculator
    _global_calculator = None