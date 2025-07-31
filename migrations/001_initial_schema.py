"""Peewee migrations -- 001_initial_schema.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""
    
    # Create fitsFile table
    @migrator.create_model
    class FitsFile(pw.Model):
        fitsFileId = pw.TextField(primary_key=True)
        fitsFileName = pw.TextField(null=True)
        fitsFileDate = pw.DateField(null=True)
        fitsFileCalibrated = pw.IntegerField(null=True)
        fitsFileType = pw.TextField(null=True)
        fitsFileStacked = pw.IntegerField(null=True)
        fitsFileObject = pw.TextField(null=True)
        fitsFileExpTime = pw.TextField(null=True)
        fitsFileXBinning = pw.TextField(null=True)
        fitsFileYBinning = pw.TextField(null=True)
        fitsFileCCDTemp = pw.TextField(null=True)
        fitsFileTelescop = pw.TextField(null=True)
        fitsFileInstrument = pw.TextField(null=True)
        fitsFileGain = pw.TextField(null=True)
        fitsFileOffset = pw.TextField(null=True)
        fitsFileFilter = pw.TextField(null=True)
        fitsFileHash = pw.TextField(null=True)
        fitsFileSession = pw.TextField(null=True)
        
        class Meta:
            table_name = "fitsfile"
    
    # Create fitsSession table
    @migrator.create_model
    class FitsSession(pw.Model):
        fitsSessionId = pw.TextField(primary_key=True)
        fitsSessionObjectName = pw.TextField(null=True)
        fitsSessionDate = pw.DateField(null=True)
        fitsSessionTelescope = pw.TextField(null=True)
        fitsSessionImager = pw.TextField(null=True)
        fitsSessionExposure = pw.TextField(null=True)
        fitsSessionBinningX = pw.TextField(null=True)
        fitsSessionBinningY = pw.TextField(null=True)
        fitsSessionCCDTemp = pw.TextField(null=True)
        fitsSessionGain = pw.TextField(null=True)
        fitsSessionOffset = pw.TextField(null=True)
        fitsSessionFilter = pw.TextField(null=True)
        fitsBiasSession = pw.TextField(null=True)
        fitsDarkSession = pw.TextField(null=True)
        fitsFlatSession = pw.TextField(null=True)
        
        class Meta:
            table_name = "fitssession"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    
    # Drop tables in reverse order
    migrator.remove_model('fitssession')
    migrator.remove_model('fitsfile')
    
