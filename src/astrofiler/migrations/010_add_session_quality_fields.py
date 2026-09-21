"""Peewee migrations -- 010_add_session_quality_fields.py.

Legacy migration name expected by some existing databases.

Adds per-session aggregate image quality metrics to `fitssession`.

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
    existing = _column_names(database, 'fitssession')

    fields = {}
    if 'fitsSessionAvgFWHMArcsec' not in existing:
        fields['fitsSessionAvgFWHMArcsec'] = pw.FloatField(null=True)
    if 'fitsSessionAvgEccentricity' not in existing:
        fields['fitsSessionAvgEccentricity'] = pw.FloatField(null=True)
    if 'fitsSessionAvgHFRArcsec' not in existing:
        fields['fitsSessionAvgHFRArcsec'] = pw.FloatField(null=True)
    if 'fitsSessionImageSNR' not in existing:
        fields['fitsSessionImageSNR'] = pw.FloatField(null=True)
    if 'fitsSessionStarCount' not in existing:
        fields['fitsSessionStarCount'] = pw.IntegerField(null=True)
    if 'fitsSessionImageScale' not in existing:
        fields['fitsSessionImageScale'] = pw.FloatField(null=True)

    if fields:
        migrator.add_fields('fitssession', **fields)


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    existing = _column_names(database, 'fitssession')
    to_remove = [
        c for c in [
            'fitsSessionAvgFWHMArcsec',
            'fitsSessionAvgEccentricity',
            'fitsSessionAvgHFRArcsec',
            'fitsSessionImageSNR',
            'fitsSessionStarCount',
            'fitsSessionImageScale',
        ]
        if c in existing
    ]

    if to_remove:
        with suppress(Exception):
            migrator.remove_fields('fitssession', *to_remove)
