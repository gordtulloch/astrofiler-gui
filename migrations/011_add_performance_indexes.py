"""Migration 011: Add performance indexes

Adds SQLite indexes on frequently queried columns to speed up UI views and
session processing. Targets:
- fitsfile counts/grouping by session and filtering out soft-deleted rows
- fitssession lookups by (objectName, date)
- masters lookups by source_session_id and find_matching_master criteria

Notes:
- Uses raw SQL with IF NOT EXISTS for robustness across historical migrations
  and table-name casing.
"""

def migrate(migrator, database, fake=False, **kwargs):
    # fitsfile
    migrator.sql(
        "CREATE INDEX IF NOT EXISTS idx_fitsfile_session ON fitsfile (fitsFileSession);"
    )
    migrator.sql(
        "CREATE INDEX IF NOT EXISTS idx_fitsfile_session_softdelete ON fitsfile (fitsFileSession, fitsFileSoftDelete);"
    )
    migrator.sql(
        "CREATE INDEX IF NOT EXISTS idx_fitsfile_hash ON fitsfile (fitsFileHash);"
    )
    migrator.sql(
        "CREATE INDEX IF NOT EXISTS idx_fitsfile_object ON fitsfile (fitsFileObject);"
    )
    migrator.sql(
        "CREATE INDEX IF NOT EXISTS idx_fitsfile_originalfile ON fitsfile (fitsFileOriginalFile);"
    )

    # fitssession
    migrator.sql(
        "CREATE INDEX IF NOT EXISTS idx_fitssession_object_date ON fitssession (fitsSessionObjectName, fitsSessionDate);"
    )

    # masters
    migrator.sql(
        "CREATE INDEX IF NOT EXISTS idx_masters_source_session_softdelete ON masters (source_session_id, soft_delete);"
    )
    migrator.sql(
        "CREATE INDEX IF NOT EXISTS idx_masters_type_softdelete ON masters (master_type, soft_delete);"
    )
    migrator.sql(
        "CREATE INDEX IF NOT EXISTS idx_masters_match_criteria ON masters (telescope, instrument, master_type, soft_delete, binning_x, binning_y, exposure_time, filter_name);"
    )


def rollback(migrator, database, fake=False, **kwargs):
    # Drop in reverse-ish order
    migrator.sql("DROP INDEX IF EXISTS idx_masters_match_criteria;")
    migrator.sql("DROP INDEX IF EXISTS idx_masters_type_softdelete;")
    migrator.sql("DROP INDEX IF EXISTS idx_masters_source_session_softdelete;")

    migrator.sql("DROP INDEX IF EXISTS idx_fitssession_object_date;")

    migrator.sql("DROP INDEX IF EXISTS idx_fitsfile_originalfile;")
    migrator.sql("DROP INDEX IF EXISTS idx_fitsfile_object;")
    migrator.sql("DROP INDEX IF EXISTS idx_fitsfile_hash;")
    migrator.sql("DROP INDEX IF EXISTS idx_fitsfile_session_softdelete;")
    migrator.sql("DROP INDEX IF EXISTS idx_fitsfile_session;")
