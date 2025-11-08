"""
Base database model and configuration for AstroFiler.
"""

import peewee as pw
import logging

# Add a logger
logger = logging.getLogger(__name__)

# Create a database proxy
db = pw.SqliteDatabase('astrofiler.db')

class BaseModel(pw.Model):
    """Base model class for all AstroFiler database models."""
    
    class Meta:
        database = db