"""
Database module for AstroFiler.

This module provides database setup, migration management, and database utilities
integrated with the modern package structure.
"""

import peewee as pw
import logging
import os
from typing import Dict, List, Optional, Any
from peewee_migrate import Router

# Import types for better type safety
from .types import DatabaseConfig
from .exceptions import DatabaseError

# Import models from the models package within astrofiler
from .models import BaseModel, db, fitsFile, fitsSession, Mapping, Masters

# Add a logger
logger = logging.getLogger(__name__)

# Initialize migration router
router = Router(db, migrate_dir='migrations')

class DatabaseManager:
    """
    Modern database manager with type safety and error handling.
    
    Provides centralized database operations including setup, migrations,
    and connection management with proper error handling and logging.
    """
    
    def __init__(self, db_instance: pw.Database = db):
        self.db = db_instance
        self.router = Router(self.db, migrate_dir='migrations')
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
                
                # Ensure migrations directory exists
                os.makedirs('migrations', exist_ok=True)
                
                # Run any pending migrations
                self.router.run()
                
                # Create tables if they don't exist (initial setup)
                self.db.create_tables([fitsFile, fitsSession, Mapping, Masters], safe=True)
                
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
                if os.path.exists('migrations'):
                    migration_files = glob.glob('migrations/[0-9]*.py')
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

# Export commonly used items
__all__ = [
    'DatabaseManager',
    'get_db_manager',
    'setup_database',
    'create_migration',
    'run_migrations', 
    'get_migration_status',
    'db',
    'BaseModel',
    'fitsFile',
    'fitsSession',
    'Mapping',
    'Masters'
]