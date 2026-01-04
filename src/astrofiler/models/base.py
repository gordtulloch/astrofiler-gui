"""Base database model and configuration for AstroFiler."""

import peewee as pw
import logging
import os
from pathlib import Path

# Add a logger
logger = logging.getLogger(__name__)


def _resolve_db_path() -> str:
    """Resolve the SQLite DB file path independent of current working directory.

    Order:
    - ASTROFILER_DB_PATH env var
    - Find an existing 'astrofiler.db' by walking up from this file
    - Default to 'astrofiler.db' in the current working directory
    """
    env_path = os.environ.get("ASTROFILER_DB_PATH")
    if env_path:
        return str(Path(env_path).expanduser().resolve())

    module_path = Path(__file__).resolve()
    for parent in [module_path.parent, *module_path.parents]:
        candidate = parent / "astrofiler.db"
        if candidate.exists():
            return str(candidate.resolve())

    return str((Path.cwd() / "astrofiler.db").resolve())

# Create a database proxy with Write-Ahead Logging for better concurrency
db = pw.SqliteDatabase(_resolve_db_path(), pragmas={
    'journal_mode': 'wal',  # Write-Ahead Logging enables concurrent reads/writes
    'busy_timeout': 5000    # 5 second timeout for locked database
})

class BaseModel(pw.Model):
    """Base model class for all AstroFiler database models."""
    
    class Meta:
        database = db