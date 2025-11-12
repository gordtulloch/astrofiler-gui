"""
Configuration management for AstroFiler application.

Provides environment-aware configuration with validation and type safety.
"""

import os
import configparser
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from .exceptions import ConfigurationError


class LogLevel(Enum):
    """Enumeration for log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseType(Enum):
    """Enumeration for supported database types."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    type: DatabaseType = DatabaseType.SQLITE
    host: str = "localhost"
    port: int = 5432
    database: str = "astrofiler.db"
    user: Optional[str] = None
    password: Optional[str] = None
    
    def get_connection_string(self) -> str:
        """Get database connection string."""
        if self.type == DatabaseType.SQLITE:
            return f"sqlite:///{self.database}"
        elif self.type == DatabaseType.POSTGRESQL:
            auth = f"{self.user}:{self.password}@" if self.user and self.password else ""
            return f"postgresql://{auth}{self.host}:{self.port}/{self.database}"
        elif self.type == DatabaseType.MYSQL:
            auth = f"{self.user}:{self.password}@" if self.user and self.password else ""
            return f"mysql://{auth}{self.host}:{self.port}/{self.database}"
        else:
            raise ConfigurationError(f"Unsupported database type: {self.type}")


@dataclass
class RepositoryConfig:
    """Repository configuration settings."""
    repository_path: str = ""
    incoming_path: str = ""
    backup_enabled: bool = True
    max_file_size_mb: int = 1000
    supported_extensions: List[str] = field(default_factory=lambda: [".fits", ".fit", ".fts", ".xisf"])
    
    def __post_init__(self):
        """Validate repository paths."""
        if not self.repository_path:
            raise ConfigurationError("Repository path is required")
        
        # Convert to absolute paths
        self.repository_path = str(Path(self.repository_path).resolve())
        if self.incoming_path:
            self.incoming_path = str(Path(self.incoming_path).resolve())


@dataclass
class UIConfig:
    """UI configuration settings."""
    theme: str = "auto"  # "light", "dark", "auto"
    window_geometry: Optional[str] = None
    recent_files_count: int = 10
    auto_refresh_interval: int = 30  # seconds
    thumbnail_size: int = 150


@dataclass
class ProcessingConfig:
    """Processing configuration settings."""
    max_threads: int = 4
    temp_directory: Optional[str] = None
    keep_temp_files: bool = False
    quality_analysis_enabled: bool = True
    auto_calibration_enabled: bool = False


@dataclass
class CloudConfig:
    """Cloud synchronization configuration."""
    enabled: bool = False
    provider: str = "gcs"  # "gcs", "s3", "azure"
    bucket_name: str = ""
    credentials_path: Optional[str] = None
    sync_interval: int = 3600  # seconds


@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    level: LogLevel = LogLevel.INFO
    file_path: str = "astrofiler.log"
    max_file_size_mb: int = 5
    backup_count: int = 3
    console_output: bool = True
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class AstroFilerConfig:
    """Main application configuration."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    repository: RepositoryConfig = field(default_factory=RepositoryConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


class ConfigManager:
    """Configuration manager with environment support."""
    
    def __init__(self, config_file: Optional[str] = None, env_prefix: str = "ASTROFILER"):
        self.config_file = config_file or self._find_config_file()
        self.env_prefix = env_prefix
        self._config: Optional[AstroFilerConfig] = None
    
    def _find_config_file(self) -> str:
        """Find configuration file in standard locations."""
        possible_paths = [
            "astrofiler.ini",
            os.path.expanduser("~/.astrofiler/config.ini"),
            os.path.expanduser("~/.config/astrofiler.ini"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Return default path if none found
        return "astrofiler.ini"
    
    def load_config(self) -> AstroFilerConfig:
        """Load configuration from file and environment variables."""
        if self._config is not None:
            return self._config
        
        config = AstroFilerConfig()
        
        # Load from file if it exists
        if os.path.exists(self.config_file):
            self._load_from_file(config)
        
        # Override with environment variables
        self._load_from_env(config)
        
        # Validate configuration
        self._validate_config(config)
        
        self._config = config
        return config
    
    def _load_from_file(self, config: AstroFilerConfig):
        """Load configuration from INI file."""
        parser = configparser.ConfigParser()
        parser.read(self.config_file)
        
        # Database section
        if parser.has_section("database"):
            db_section = parser["database"]
            config.database.type = DatabaseType(db_section.get("type", "sqlite"))
            config.database.host = db_section.get("host", "localhost")
            config.database.port = int(db_section.get("port", "5432"))
            config.database.database = db_section.get("database", "astrofiler.db")
            config.database.user = db_section.get("user")
            config.database.password = db_section.get("password")
        
        # Repository section
        if parser.has_section("repository"):
            repo_section = parser["repository"]
            config.repository.repository_path = repo_section.get("repository_path", "")
            config.repository.incoming_path = repo_section.get("incoming_path", "")
            config.repository.backup_enabled = repo_section.getboolean("backup_enabled", True)
        
        # Add other sections as needed...
    
    def _load_from_env(self, config: AstroFilerConfig):
        """Load configuration from environment variables."""
        # Database environment variables
        if env_val := os.getenv(f"{self.env_prefix}_DB_HOST"):
            config.database.host = env_val
        if env_val := os.getenv(f"{self.env_prefix}_DB_PORT"):
            config.database.port = int(env_val)
        if env_val := os.getenv(f"{self.env_prefix}_DB_NAME"):
            config.database.database = env_val
        if env_val := os.getenv(f"{self.env_prefix}_DB_USER"):
            config.database.user = env_val
        if env_val := os.getenv(f"{self.env_prefix}_DB_PASSWORD"):
            config.database.password = env_val
        
        # Repository environment variables
        if env_val := os.getenv(f"{self.env_prefix}_REPOSITORY_PATH"):
            config.repository.repository_path = env_val
        
        # Add other environment variables as needed...
    
    def _validate_config(self, config: AstroFilerConfig):
        """Validate configuration settings."""
        # Validate repository path exists or can be created
        if config.repository.repository_path:
            repo_path = Path(config.repository.repository_path)
            if not repo_path.exists():
                try:
                    repo_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise ConfigurationError(f"Cannot create repository path: {e}")
        
        # Validate processing settings
        if config.processing.max_threads < 1:
            raise ConfigurationError("max_threads must be at least 1")
        
        # Add other validations as needed...
    
    def save_config(self, config: AstroFilerConfig):
        """Save configuration to file."""
        parser = configparser.ConfigParser()
        
        # Database section
        parser.add_section("database")
        parser["database"]["type"] = config.database.type.value
        parser["database"]["host"] = config.database.host
        parser["database"]["port"] = str(config.database.port)
        parser["database"]["database"] = config.database.database
        if config.database.user:
            parser["database"]["user"] = config.database.user
        if config.database.password:
            parser["database"]["password"] = config.database.password
        
        # Repository section
        parser.add_section("repository")
        parser["repository"]["repository_path"] = config.repository.repository_path
        parser["repository"]["incoming_path"] = config.repository.incoming_path
        parser["repository"]["backup_enabled"] = str(config.repository.backup_enabled)
        
        # Add other sections...
        
        # Write to file
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            parser.write(f)


# Global config manager instance
config_manager = ConfigManager()

def get_config() -> AstroFilerConfig:
    """Get the current application configuration."""
    return config_manager.load_config()


def get_temp_folder() -> str:
    """
    Get the configured temporary folder path.
    
    Returns:
        str: The configured temp folder path, or system default if not configured
    """
    import configparser
    import tempfile
    
    # Try to read from config file
    config = configparser.ConfigParser()
    config_file = 'astrofiler.ini'
    
    if os.path.exists(config_file):
        config.read(config_file)
        temp_folder = config.get('DEFAULT', 'temp_folder', fallback='').strip()
        
        if temp_folder:
            # Ensure the directory exists
            os.makedirs(temp_folder, exist_ok=True)
            return os.path.abspath(temp_folder)
    
    # Fall back to system temporary directory
    return tempfile.gettempdir()