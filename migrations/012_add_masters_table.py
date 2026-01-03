"""Peewee migrations -- 010_add_masters_table.py.

Adds the Masters table used to track created master calibration frames.

This migration is defensive: if the table already exists, it does nothing.

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Create the Masters table (if missing)."""

    try:
        existing_tables = set(database.get_tables())
    except Exception:
        existing_tables = set()

    # Older databases may already have this table (possibly created outside migrations).
    if any(t.lower() == 'masters' for t in existing_tables):
        return

    class Masters(pw.Model):
        id = pw.AutoField()
        master_id = pw.TextField(unique=True)
        master_type = pw.TextField()
        master_path = pw.TextField()
        creation_date = pw.DateTimeField()
        telescope = pw.TextField(null=True)
        instrument = pw.TextField(null=True)
        exposure_time = pw.TextField(null=True)
        binning_x = pw.TextField(null=True)
        binning_y = pw.TextField(null=True)
        ccd_temp = pw.TextField(null=True)
        gain = pw.TextField(null=True)
        offset = pw.TextField(null=True)
        filter_name = pw.TextField(null=True)
        source_session_id = pw.TextField(null=True)
        file_count = pw.IntegerField()
        quality_score = pw.FloatField(null=True)
        file_size = pw.IntegerField(null=True)
        hash_value = pw.TextField(null=True)
        cloud_url = pw.TextField(null=True)
        is_validated = pw.IntegerField(default=0)
        validation_date = pw.DateTimeField(null=True)
        notes = pw.TextField(null=True)
        soft_delete = pw.IntegerField(default=0)

        class Meta:
            table_name = 'Masters'

    migrator.create_model(Masters)

    # Add indexes to match the expected query patterns.
    migrator.add_index(
        'Masters',
        'telescope',
        'instrument',
        'master_type',
        'soft_delete',
        'binning_x',
        'binning_y',
        'exposure_time',
        'filter_name',
        unique=False,
    )
    migrator.add_index('Masters', 'master_type', 'soft_delete', unique=False)
    migrator.add_index('Masters', 'source_session_id', 'soft_delete', unique=False)


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Drop the Masters table."""

    with suppress(Exception):
        migrator.remove_model('Masters', cascade=True)
