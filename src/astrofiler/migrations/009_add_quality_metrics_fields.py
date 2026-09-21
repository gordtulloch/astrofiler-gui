"""Peewee migrations -- 009_add_quality_metrics_fields.py.

Legacy migration name expected by some existing databases.

Adds per-file image quality metrics to `fitsfile`.

This migration is defensive: it only adds columns that are missing.

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


def _column_names(database: pw.Database, table: str) -> set[str]:
    try:
        cursor = database.execute_sql(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}
    except Exception:
        return set()


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    existing = _column_names(database, 'fitsfile')

    fields = {}
    if 'fitsFileAvgFWHMArcsec' not in existing:
        fields['fitsFileAvgFWHMArcsec'] = pw.FloatField(null=True)
    if 'fitsFileAvgEccentricity' not in existing:
        fields['fitsFileAvgEccentricity'] = pw.FloatField(null=True)
    if 'fitsFileAvgHFRArcsec' not in existing:
        fields['fitsFileAvgHFRArcsec'] = pw.FloatField(null=True)
    if 'fitsFileImageSNR' not in existing:
        fields['fitsFileImageSNR'] = pw.FloatField(null=True)
    if 'fitsFileStarCount' not in existing:
        fields['fitsFileStarCount'] = pw.IntegerField(null=True)
    if 'fitsFileImageScale' not in existing:
        fields['fitsFileImageScale'] = pw.FloatField(null=True)

    if fields:
        migrator.add_fields('fitsfile', **fields)


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    # Best-effort rollback: only drop columns if they exist.
    existing = _column_names(database, 'fitsfile')
    to_remove = [
        c for c in [
            'fitsFileAvgFWHMArcsec',
            'fitsFileAvgEccentricity',
            'fitsFileAvgHFRArcsec',
            'fitsFileImageSNR',
            'fitsFileStarCount',
            'fitsFileImageScale',
        ]
        if c in existing
    ]

    if to_remove:
        with suppress(Exception):
            migrator.remove_fields('fitsfile', *to_remove)
