"""Peewee migrations -- 008_remove_master_fields.py.

Legacy migration name expected by some existing databases.

Historically, some branches experimented with removing master reference fields.
The current schema keeps master references on `fitssession`/`fitsfile`, so this
migration is intentionally a no-op.

It exists purely to satisfy `migratehistory` entries and allow peewee-migrate
to proceed.

"""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    return


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    return
