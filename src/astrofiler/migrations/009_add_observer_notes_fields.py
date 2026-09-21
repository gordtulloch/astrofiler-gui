"""Peewee migrations -- 009_add_observer_notes_fields.py.

Compatibility migration for databases created/used prior to V1.2.0.

Some 1.1.x databases record this migration name in `migratehistory`.
Newer code still expects the related columns for mappings/UI.

This migration is defensive/idempotent:
- If the table/columns already exist, it does nothing.

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


def _resolve_table_name(database: pw.Database, expected: str) -> str:
    try:
        tables = database.get_tables()
    except Exception:
        return expected

    expected_lower = expected.lower()
    for t in tables:
        if t.lower() == expected_lower:
            return t
    return expected


def _existing_columns(database: pw.Database, table_name: str) -> set[str]:
    try:
        cursor = database.execute_sql(f"PRAGMA table_info('{table_name}')")
        return {row[1] for row in cursor.fetchall()}
    except Exception:
        return set()


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False, **kwargs):
    table = _resolve_table_name(database, 'fitsFile')
    existing = _existing_columns(database, table)

    fields = {}
    if 'fitsFileObserver' not in existing:
        fields['fitsFileObserver'] = pw.TextField(null=True)
    if 'fitsFileNotes' not in existing:
        fields['fitsFileNotes'] = pw.TextField(null=True)

    if not fields:
        return

    with suppress(Exception):
        migrator.add_fields(table, **fields)


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False, **kwargs):
    table = _resolve_table_name(database, 'fitsFile')

    with suppress(Exception):
        migrator.remove_fields(table, 'fitsFileObserver', 'fitsFileNotes')
