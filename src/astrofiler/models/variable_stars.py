"""Variable star targets.

This table is used to mark specific targets as variable-star photometry targets.
"""

import datetime

import peewee as pw

from .base import BaseModel


class VariableStars(BaseModel):
    """User-designated variable-star targets."""

    id = pw.AutoField()
    target_name = pw.TextField(unique=True)
    created_at = pw.DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "VariableStars"
