"""
Services module for AstroFiler application.

This module contains external service integrations including:
- Cloud storage services (Google Cloud Storage, etc.)
- Smart telescope integrations (SEESTAR, etc.)
- Other external API integrations

Main Components:
    cloud: Cloud storage service implementations
    telescope: Smart telescope communication and management
"""

# Import main service classes for convenient access
try:
    from .cloud import (
        _calculate_md5_hash,
        _get_cloud_file_hashes,
        sync_files_to_cloud
    )
except ImportError:
    # Cloud service dependencies might not be available
    pass

try:
    from .telescope import (
        smart_telescope_manager,
        TelescopeManager
    )
except ImportError:
    # Telescope service dependencies might not be available
    pass

__all__ = [
    # Cloud services
    '_calculate_md5_hash',
    '_get_cloud_file_hashes', 
    'sync_files_to_cloud',
    
    # Telescope services
    'smart_telescope_manager',
    'TelescopeManager'
]