"""Peewee migrations -- 011_add_performance_indexes.py.

Legacy migration name expected by some existing databases.

Adds a small set of helpful indexes. All operations are best-effort and safe
to re-run.

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    # fitsfile indexes
    with suppress(Exception):
        migrator.add_index('fitsfile', 'fitsFileHash', unique=False)
    with suppress(Exception):
        migrator.add_index('fitsfile', 'fitsFileSession', unique=False)
    with suppress(Exception):
        migrator.add_index('fitsfile', 'fitsFileType', unique=False)

    # fitssession indexes
    with suppress(Exception):
        migrator.add_index('fitssession', 'fitsSessionDate', unique=False)
    with suppress(Exception):
        migrator.add_index('fitssession', 'fitsSessionObjectName', unique=False)


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    # Index rollback is intentionally omitted (best-effort forward-only).
    return
