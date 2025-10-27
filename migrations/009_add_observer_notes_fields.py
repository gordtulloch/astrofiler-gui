"""Peewee migrations -- 007_add_observer_notes_fields.py.

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
    """Add OBSERVER and NOTES fields to fitsFile table."""
    
    # Check if columns already exist to avoid duplicate column error
    cursor = database.execute_sql("PRAGMA table_info(fitsfile)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    fields_to_add = {}
    if 'fitsFileObserver' not in existing_columns:
        fields_to_add['fitsFileObserver'] = pw.TextField(null=True)
    if 'fitsFileNotes' not in existing_columns:
        fields_to_add['fitsFileNotes'] = pw.TextField(null=True)
    
    # Only add fields if they don't already exist
    if fields_to_add:
        migrator.add_fields('fitsfile', **fields_to_add)


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Remove OBSERVER and NOTES fields from fitsFile table."""
    
    # Check if columns exist before trying to remove them
    cursor = database.execute_sql("PRAGMA table_info(fitsfile)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    fields_to_remove = []
    if 'fitsFileObserver' in existing_columns:
        fields_to_remove.append('fitsFileObserver')
    if 'fitsFileNotes' in existing_columns:
        fields_to_remove.append('fitsFileNotes')
    
    # Only remove fields if they exist
    if fields_to_remove:
        migrator.remove_fields('fitsfile', *fields_to_remove)