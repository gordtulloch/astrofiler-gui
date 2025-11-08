"""
Type definitions for AstroFiler application.

This module provides type aliases and protocols for better type safety.
"""

from typing import Protocol, Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
from datetime import datetime
import numpy as np

# Type aliases for common data structures
FitsHeaderDict = Dict[str, Any]
FilePath = Union[str, Path]
SessionId = str
FileId = str
QualityMetrics = Dict[str, float]
ProcessingOptions = Dict[str, Any]

# Configuration types
class DatabaseConfig(Protocol):
    """Protocol for database configuration."""
    host: str
    database: str
    user: Optional[str]
    password: Optional[str]

class RepositoryConfig(Protocol):
    """Protocol for repository configuration."""
    repository_path: str
    incoming_path: str
    backup_enabled: bool

class TelescopeConfig(Protocol):
    """Protocol for telescope configuration."""
    name: str
    host: str
    protocol: str  # 'ftp', 'smb', etc.
    credentials: Dict[str, str]

# File processing types
class FitsFileInfo(Protocol):
    """Protocol for FITS file information."""
    file_path: FilePath
    file_hash: str
    header: FitsHeaderDict
    image_type: str
    telescope: str
    instrument: str
    object_name: Optional[str]
    exposure_time: float
    date_obs: datetime

# Quality analysis types
class QualityResult(Protocol):
    """Protocol for quality analysis results."""
    overall_score: float
    metrics: QualityMetrics
    recommendations: List[str]
    timestamp: datetime

# Session types
class SessionInfo(Protocol):
    """Protocol for session information."""
    session_id: SessionId
    object_name: str
    telescope: str
    instrument: str
    date: datetime
    file_count: int
    
# Processing callbacks
ProgressCallback = Protocol

class ProgressCallback(Protocol):
    """Protocol for progress reporting callbacks."""
    def __call__(self, current: int, total: int, message: str = "") -> None:
        """Report progress of an operation."""
        ...

# Result types
ProcessingResult = Tuple[bool, str, Optional[Dict[str, Any]]]
CalibrationResult = Tuple[bool, List[FilePath], Optional[str]]

# Cloud storage types
class CloudProvider(Protocol):
    """Protocol for cloud storage providers."""
    def upload_file(self, local_path: FilePath, remote_path: str) -> bool: ...
    def download_file(self, remote_path: str, local_path: FilePath) -> bool: ...
    def list_files(self, remote_path: str) -> List[str]: ...
    def file_exists(self, remote_path: str) -> bool: ...

# Telescope connection types
class TelescopeConnection(Protocol):
    """Protocol for telescope connections."""
    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def list_files(self, path: str) -> List[str]: ...
    def download_file(self, remote_path: str, local_path: FilePath) -> bool: ...