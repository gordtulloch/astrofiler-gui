"""Peewee migrations -- 010_add_masters_table.py.

Compatibility migration.

Some databases (e.g. from 1.1.x) have `010_add_masters_table` recorded in
`migratehistory`. V1.2.0 must ship a file with this exact name so
peewee-migrate can continue.

This migration is defensive/idempotent:
- If the Masters table already exists (case-insensitive), it does nothing.
- Index creation is skipped if indexes already exist.

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake: bool = False, **kwargs):
    def _is_sqlite() -> bool:
        return database.__class__.__name__.lower().startswith('sqlite')

    def _create_index_if_not_exists(index_name: str, table_name: str, columns: list[str]) -> None:
        if _is_sqlite():
            cols_sql = ", ".join([f"\"{c}\"" for c in columns])
            database.execute_sql(
                f"CREATE INDEX IF NOT EXISTS \"{index_name}\" ON \"{table_name}\" ({cols_sql})"
            )
            return

        migrator.add_index(table_name, *columns, unique=False)

    try:
        existing_tables = set(database.get_tables())
    except Exception:
        existing_tables = set()

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

    with suppress(Exception):
        _create_index_if_not_exists(
            'idx_masters_match_criteria',
            'Masters',
            [
                'telescope',
                'instrument',
                'master_type',
                'soft_delete',
                'binning_x',
                'binning_y',
                'exposure_time',
                'filter_name',
            ],
        )

    with suppress(Exception):
        _create_index_if_not_exists(
            'Masters_master_type_soft_delete',
            'Masters',
            ['master_type', 'soft_delete'],
        )

    with suppress(Exception):
        _create_index_if_not_exists(
            'Masters_source_session_id_soft_delete',
            'Masters',
            ['source_session_id', 'soft_delete'],
        )


def rollback(migrator: Migrator, database: pw.Database, *, fake: bool = False, **kwargs):
    with suppress(Exception):
        migrator.remove_model('Masters', cascade=True)
