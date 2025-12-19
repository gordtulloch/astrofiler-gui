"""
Base database model and configuration for AstroFiler.
"""

import peewee as pw
import logging

# Add a logger
logger = logging.getLogger(__name__)

# Create a database proxy with Write-Ahead Logging for better concurrency
db = pw.SqliteDatabase('astrofiler.db', pragmas={
    'journal_mode': 'wal',  # Write-Ahead Logging enables concurrent reads/writes
    'busy_timeout': 5000    # 5 second timeout for locked database
})

class BaseModel(pw.Model):
    """Base model class for all AstroFiler database models."""
    
    class Meta:
        database = db