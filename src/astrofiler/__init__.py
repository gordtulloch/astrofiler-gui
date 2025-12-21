"""
AstroFiler - Professional Astronomical Image Management and Processing Suite.

This package provides comprehensive tools for managing and processing astronomical 
FITS images, with features including:

- FITS file registration and database management
- Master calibration frame creation with Siril integration
- Quality analysis and image assessment
- Repository organization and file management
- Smart telescope integration and cloud synchronization

Main Components:
    core: Core processing modules (file processing, calibration, quality analysis)
    types: Type definitions and protocols
    exceptions: Exception hierarchy for error handling
    config: Configuration management with environment support
"""

__version__ = "1.2.0"
__author__ = "Gord Tulloch"
__email__ = "gord.tulloch@gmail.com"

# Import core functionality for convenient access
try:
    from .core import (
        fitsProcessing,
        FileProcessor,
        CalibrationProcessor,
        EnhancedQualityAnalyzer,
        RepositoryManager,
        MasterFrameManager,
        get_master_manager,
        normalize_file_path,
        sanitize_filesystem_name,
        dwarfFixHeader,
        mapFitsHeader,
        clearMappingCache,
        get_master_calibration_path
    )
except ImportError as e:
    # Core dependencies might not be available in all environments
    import warnings
    warnings.warn(f"Core modules not available: {e}", ImportWarning)

# Import type definitions
from .types import (
    FitsHeaderDict,
    FilePath,
    SessionId,
    FileId,
    QualityMetrics,
    ProcessingOptions,
    FitsFileInfo,
    QualityResult,
    SessionInfo,
    ProgressCallback,
    ProcessingResult,
    CalibrationResult
)

# Import exception classes
from .exceptions import (
    AstroFilerError,
    DatabaseError,
    FileProcessingError,
    FitsHeaderError,
    CalibrationError,
    RepositoryError,
    TelescopeConnectionError,
    CloudSyncError,
    ConfigurationError,
    ValidationError,
    QualityAnalysisError
)

# Import configuration
from .config import get_config, ConfigManager, AstroFilerConfig

# Import database functionality
try:
    from .database import (
        DatabaseManager,
        get_db_manager,
        setup_database,
        create_migration,
        run_migrations,
        get_migration_status
    )
except ImportError as e:
    # Database dependencies might not be available
    import warnings
    warnings.warn(f"Database modules not available: {e}", ImportWarning)

# Import database models
try:
    from .models import (
        BaseModel,
        db,
        fitsFile,
        fitsSession,
        Mapping,
        Masters
    )
except ImportError as e:
    # Model dependencies might not be available
    import warnings
    warnings.warn(f"Model modules not available: {e}", ImportWarning)

# Import UI components (optional, for applications that need GUI)
try:
    from . import ui
except ImportError:
    # UI dependencies might not be available in headless environments
    ui = None

# Import services (optional, for applications that need external integrations)
try:
    from . import services
except ImportError:
    # Service dependencies might not be available in all environments
    services = None

# Export main classes and functions
__all__ = [
    # Core processing
    'fitsProcessing',
    'FileProcessor',
    'CalibrationProcessor', 
    'EnhancedQualityAnalyzer',
    'RepositoryManager',
    'MasterFrameManager',
    'get_master_manager',
    
    # Utility functions
    'normalize_file_path',
    'sanitize_filesystem_name',
    'dwarfFixHeader',
    'mapFitsHeader',
    'clearMappingCache',
    'get_master_calibration_path',
    
    # Type definitions
    'FitsHeaderDict',
    'FilePath', 
    'SessionId',
    'FileId',
    'QualityMetrics',
    'ProcessingOptions',
    'FitsFileInfo',
    'QualityResult',
    'SessionInfo',
    'ProgressCallback',
    'ProcessingResult',
    'CalibrationResult',
    
    # Exceptions
    'AstroFilerError',
    'DatabaseError',
    'FileProcessingError',
    'FitsHeaderError', 
    'CalibrationError',
    'RepositoryError',
    'TelescopeConnectionError',
    'CloudSyncError',
    'ConfigurationError',
    'ValidationError',
    'QualityAnalysisError',
    
    # Configuration
    'get_config',
    'ConfigManager',
    'AstroFilerConfig',
    
    # Database management
    'DatabaseManager',
    'get_db_manager',
    'setup_database',
    'create_migration',
    'run_migrations',
    'get_migration_status',
    
    # Database models
    'BaseModel',
    'db',
    'fitsFile',
    'fitsSession',
    'Mapping',
    'Masters',
    
    # UI components
    'ui',
    
    # Services
    'services',
    
    # Package metadata
    '__version__',
    '__author__',
    '__email__'
]