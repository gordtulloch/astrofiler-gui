"""Base database model and configuration for AstroFiler."""

import peewee as pw
import logging
import os
from pathlib import Path

from ..paths import get_database_path

# Add a logger
logger = logging.getLogger(__name__)


def _resolve_db_path() -> str:
    """Resolve the SQLite DB file path independent of current working directory.

    Order (see astrofiler.paths):
    - ASTROFILER_DB_PATH env var
    - astrofiler.db in the application directory (ASTROFILER_HOME, the project root
      for a source checkout, else the per-user application directory)
    """
    return str(get_database_path())

# Create a database proxy with Write-Ahead Logging for better concurrency
db = pw.SqliteDatabase(_resolve_db_path(), pragmas={
    'journal_mode': 'wal',  # Write-Ahead Logging enables concurrent reads/writes
    'busy_timeout': 5000    # 5 second timeout for locked database
})

class BaseModel(pw.Model):
    """Base model class for all AstroFiler database models."""
    
    class Meta:
        database = db