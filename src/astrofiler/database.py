"""
Database module for AstroFiler.

This module provides database setup, migration management, and database utilities
integrated with the modern package structure.
"""

import peewee as pw
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from peewee_migrate import Router

# Import types for better type safety
from .types import DatabaseConfig
from .exceptions import DatabaseError

# Import models from the models package within astrofiler
from .models import BaseModel, db, fitsFile, fitsSession, Mapping, Masters, VariableStars

# Add a logger
logger = logging.getLogger(__name__)

def _resolve_migrations_dir() -> Path:
    """Resolve the migrations directory independent of current working directory.

    Tries (in order):
    - ASTROFILER_MIGRATIONS_DIR env var
    - A 'migrations' folder found by walking up from this file
    - A 'migrations' folder under the current working directory
    """
    env_dir = os.environ.get("ASTROFILER_MIGRATIONS_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    module_path = Path(__file__).resolve()
    for parent in [module_path.parent, *module_path.parents]:
        candidate = parent / "migrations"
        if candidate.is_dir():
            return candidate

    cwd_candidate = Path.cwd() / "migrations"
    if cwd_candidate.is_dir():
        return cwd_candidate

    # Fall back to the expected repo layout when running from source:
    # <repo>/src/astrofiler/database.py -> <repo>/migrations
    repo_root_candidate = module_path.parents[2] / "migrations"
    return repo_root_candidate


MIGRATIONS_DIR = _resolve_migrations_dir()

# Initialize migration router (module-level convenience)
router = Router(db, migrate_dir=str(MIGRATIONS_DIR))

class DatabaseManager:
    """
    Modern database manager with type safety and error handling.
    
    Provides centralized database operations including setup, migrations,
    and connection management with proper error handling and logging.
    """
    
    def __init__(self, db_instance: pw.Database = db):
        self.db = db_instance
        self.migrations_dir = MIGRATIONS_DIR
        self.router = Router(self.db, migrate_dir=str(self.migrations_dir))
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def setup_database(self) -> bool:
        """
        Initialize database with peewee-migrate for version control and migrations.
        
        Returns:
            bool: True if setup successful, False otherwise
            
        Raises:
            DatabaseError: If database setup fails critically
        """
        import time
        import peewee as pw
        
        max_retries = 5
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Connect to database
                if not self.db.is_closed():
                    self.db.close()
                self.db.connect()

                # Helpful diagnostics: show exactly which DB and migrations folder are in use.
                try:
                    db_file = getattr(self.db, 'database', None)
                except Exception:
                    db_file = None
                self.logger.info(f"Database file: {db_file}")
                self.logger.info(f"Migrations dir: {self.migrations_dir}")

                # Ensure migrations directory exists and is discoverable.
                # Creating an empty relative 'migrations' directory can hide path issues
                # and cause confusing FileNotFoundError for expected migration files.
                if not self.migrations_dir.is_dir():
                    raise DatabaseError(
                        "Migrations directory not found. Expected one of:\n"
                        f"  - {self.migrations_dir}\n"
                        "Set ASTROFILER_MIGRATIONS_DIR to the folder containing migration files."
                    )
                
                # Run any pending migrations
                self.router.run()
                
                # Create tables if they don't exist (initial setup)
                self.db.create_tables([fitsFile, fitsSession, Mapping, Masters, VariableStars], safe=True)
                
                self.db.close()
                self.logger.info("Database setup complete with peewee-migrate. Tables created/updated.")
                return True
                
            except pw.OperationalError as e:
                # Handle database locked errors with retries
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        f"Database is locked (another process may be using it). "
                        f"Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})"
                    )
                    try:
                        if self.db.is_connection_usable():
                            self.db.close()
                    except:
                        pass
                    time.sleep(wait_time)
                    continue
                else:
                    # Final attempt failed or non-lock error
                    self.logger.error(f"Database operational error: {e}")
                    try:
                        if self.db.is_connection_usable():
                            self.db.close()
                    except:
                        pass
                    
                    error_msg = str(e)
                    if "database is locked" in error_msg.lower():
                        raise DatabaseError(
                            f"Database is locked after {max_retries} attempts. "
                            f"Another AstroFiler process may be running. "
                            f"Please close other instances and try again."
                        ) from e
                    else:
                        raise DatabaseError(f"Database operational error: {error_msg}") from e
                        
            except Exception as e:
                self.logger.error(f"Database setup error: {e}")
                error_msg = str(e)
                
                try:
                    if self.db.is_connection_usable():
                        self.db.close()
                except:
                    pass
                
                # Provide more helpful error messages
                if "no such table" in error_msg.lower():
                    raise DatabaseError(
                        f"Database tables not found. Please run migrations: python migrate.py"
                    ) from e
                elif "Model" in error_msg and "not found" in error_msg:
                    raise DatabaseError(
                        f"Model configuration error: {error_msg}. "
                        f"This may indicate a database structure mismatch. "
                        f"Try running: python migrate.py"
                    ) from e
                elif "unable to open database file" in error_msg.lower():
                    raise DatabaseError(
                        f"Cannot open database file. Check that:\n"
                        f"  1. The database path is correct in astrofiler.ini\n"
                        f"  2. You have read/write permissions\n"
                        f"  3. The directory exists"
                    ) from e
                else:
                    raise DatabaseError(f"Failed to setup database: {error_msg}") from e
        
        # Should never reach here, but just in case
        raise DatabaseError("Database setup failed after all retry attempts")
    
    def create_migration(self, name: str) -> bool:
        """
        Create a new migration file with the given name.
        
        Args:
            name: Name for the migration file
            
        Returns:
            bool: True if migration created successfully
            
        Raises:
            DatabaseError: If migration creation fails
        """
        try:
            if not name or not name.strip():
                raise ValueError("Migration name cannot be empty")
                
            # Connect to database
            if not self.db.is_closed():
                self.db.close()
            self.db.connect()
            
            # Create migration
            self.router.create(name)
            
            self.db.close()
            self.logger.info(f"Migration '{name}' created successfully.")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating migration '{name}': {e}")
            try:
                if self.db.is_connection_usable():
                    self.db.close()
            except:
                pass
            raise DatabaseError(f"Failed to create migration '{name}': {e}") from e
    
    def run_migrations(self) -> bool:
        """
        Run all pending migrations.
        
        Returns:
            bool: True if all migrations completed successfully
            
        Raises:
            DatabaseError: If migration execution fails
        """
        try:
            # Connect to database
            if not self.db.is_closed():
                self.db.close()
            self.db.connect()
            
            # Run migrations
            self.router.run()
            
            self.db.close()
            self.logger.info("All migrations completed successfully.")
            return True
            
        except Exception as e:
            self.logger.error(f"Error running migrations: {e}")
            try:
                if self.db.is_connection_usable():
                    self.db.close()
            except:
                pass
            raise DatabaseError(f"Failed to run migrations: {e}") from e

    def _resolve_db_file_path(self) -> Optional[Path]:
        """Return the on-disk SQLite file path if applicable."""
        db_name = getattr(self.db, "database", None)
        if not db_name or db_name == ":memory:":
            return None
        db_path = Path(db_name).expanduser()
        try:
            return db_path.resolve()
        except Exception:
            # If resolve fails (e.g. odd drive mapping), fall back to absolute
            return db_path.absolute()

    def backup_database(self, backup_dir: Optional[str] = None) -> Optional[Path]:
        """Create a timestamped copy of the SQLite DB file (and WAL/SHM if present)."""
        import shutil
        import datetime

        db_path = self._resolve_db_file_path()
        if db_path is None:
            return None
        if not db_path.exists():
            return None

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = Path(backup_dir).expanduser().resolve() if backup_dir else (db_path.parent / "backups")
        target_dir.mkdir(parents=True, exist_ok=True)

        base_name = f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"
        backup_path = target_dir / base_name

        shutil.copy2(db_path, backup_path)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(db_path) + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, target_dir / (base_name + suffix))

        return backup_path

    def reset_migration_history(self, *, backup: bool = True, backup_dir: Optional[str] = None) -> bool:
        """Drop peewee-migrate's history table so migrations can be re-evaluated.

        Note: If your schema already contains tables/columns that migrations create,
        rerunning migrations may fail unless migrations are idempotent.
        """
        try:
            if not self.db.is_closed():
                self.db.close()

            if backup:
                self.backup_database(backup_dir=backup_dir)

            self.db.connect()
            tables = set(self.db.get_tables())
            if "migratehistory" in tables:
                self.db.execute_sql("DROP TABLE migratehistory")
                self.logger.info("Dropped migratehistory table.")
            else:
                self.logger.info("No migratehistory table found; nothing to reset.")

            self.db.close()
            return True
        except Exception as e:
            self.logger.error(f"Error resetting migration history: {e}")
            try:
                if self.db.is_connection_usable():
                    self.db.close()
            except Exception:
                pass
            raise DatabaseError(f"Failed to reset migration history: {e}") from e

    def reset_database_file(self, *, backup: bool = True, backup_dir: Optional[str] = None) -> bool:
        """Delete the SQLite DB file (and WAL/SHM) so the app starts fresh."""
        try:
            if not self.db.is_closed():
                self.db.close()

            if backup:
                self.backup_database(backup_dir=backup_dir)

            db_path = self._resolve_db_file_path()
            if db_path is None:
                raise DatabaseError("Database is not a file-based SQLite database.")

            for path in [db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")]:
                try:
                    if path.exists():
                        path.unlink()
                except Exception as e:
                    raise DatabaseError(f"Failed to remove database file '{path}': {e}") from e

            self.logger.info("Database file removed.")
            return True
        except Exception as e:
            self.logger.error(f"Error resetting database file: {e}")
            raise DatabaseError(f"Failed to reset database file: {e}") from e
    
    def get_migration_status(self) -> Optional[Dict[str, Any]]:
        """
        Get the current migration status.
        
        Returns:
            Dict with 'done', 'undone', and 'current' migration information
            None if status cannot be determined
        """
        try:
            # Connect to database
            if not self.db.is_closed():
                self.db.close()
            self.db.connect()
            
            # Get migration history
            done_migrations: List[str] = []
            pending_migrations: List[str] = []
            
            try:
                # Check if migration history table exists
                tables = self.db.get_tables()
                if 'migratehistory' in tables:
                    # Query migration history directly
                    cursor = self.db.execute_sql("SELECT name FROM migratehistory ORDER BY id")
                    done_migrations = [row[0] for row in cursor.fetchall()]
                
                # Get available migration files
                import glob
                if self.migrations_dir.is_dir():
                    migration_files = glob.glob(str(self.migrations_dir / '[0-9]*.py'))
                    migration_names = []
                    for f in migration_files:
                        # Extract migration name from filename
                        basename = os.path.basename(f)
                        name = basename.replace('.py', '')
                        migration_names.append(name)
                    migration_names.sort()
                    
                    # Find pending migrations
                    pending_migrations = [m for m in migration_names if m not in done_migrations]
                
            except Exception as e:
                self.logger.debug(f"Could not get detailed migration info: {e}")
                # Fallback to basic info
                done_migrations = []
                pending_migrations = []
            
            self.db.close()
            
            return {
                'done': done_migrations,
                'undone': pending_migrations,
                'current': done_migrations[-1] if done_migrations else 'none'
            }
            
        except Exception as e:
            self.logger.error(f"Error getting migration status: {e}")
            try:
                if self.db.is_connection_usable():
                    self.db.close()
            except:
                pass
            return None
    
    def health_check(self) -> bool:
        """
        Perform a basic database health check.
        
        Returns:
            bool: True if database is accessible and responsive
        """
        try:
            if not self.db.is_closed():
                self.db.close()
            self.db.connect()
            
            # Simple query to test connectivity
            self.db.execute_sql("SELECT 1")
            
            self.db.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            try:
                if self.db.is_connection_usable():
                    self.db.close()
            except:
                pass
            return False

# Default database manager instance
_default_db_manager: Optional[DatabaseManager] = None

def get_db_manager() -> DatabaseManager:
    """Get the default database manager instance (singleton pattern)."""
    global _default_db_manager
    if _default_db_manager is None:
        _default_db_manager = DatabaseManager()
    return _default_db_manager

# Backwards compatibility functions
def setup_database() -> bool:
    """Initialize database with peewee-migrate for version control and migrations."""
    return get_db_manager().setup_database()

def create_migration(name: str) -> bool:
    """Create a new migration file with the given name."""
    return get_db_manager().create_migration(name)

def run_migrations() -> bool:
    """Run all pending migrations."""
    return get_db_manager().run_migrations()

def get_migration_status() -> Optional[Dict[str, Any]]:
    """Get the current migration status."""
    return get_db_manager().get_migration_status()

def reset_migration_history(*, backup: bool = True, backup_dir: Optional[str] = None) -> bool:
    """Drop the migratehistory table so migrations can be re-evaluated."""
    return get_db_manager().reset_migration_history(backup=backup, backup_dir=backup_dir)

def reset_database_file(*, backup: bool = True, backup_dir: Optional[str] = None) -> bool:
    """Delete the SQLite database file (and WAL/SHM) for a clean start."""
    return get_db_manager().reset_database_file(backup=backup, backup_dir=backup_dir)

# Export commonly used items
__all__ = [
    'DatabaseManager',
    'get_db_manager',
    'setup_database',
    'create_migration',
    'run_migrations', 
    'get_migration_status',
    'reset_migration_history',
    'reset_database_file',
    'db',
    'BaseModel',
    'fitsFile',
    'fitsSession',
    'Mapping',
    'Masters'
]