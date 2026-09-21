"""Peewee migrations -- 005_recreate_mapping_table_without_is_default.py.

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
    
    # Since SQLite doesn't support dropping columns, we need to recreate the table
    # First, save existing data
    migrator.sql("""
        CREATE TABLE mapping_temp AS 
        SELECT id, card, current, replace FROM mapping;
    """)
    
    # Drop the old table
    migrator.sql("DROP TABLE mapping;")
    
    # Recreate the table without is_default
    migrator.sql("""
        CREATE TABLE mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card VARCHAR(20),
            current VARCHAR(255),
            replace VARCHAR(255)
        );
    """)
    
    # Restore the data
    migrator.sql("""
        INSERT INTO mapping (id, card, current, replace)
        SELECT id, card, current, replace FROM mapping_temp;
    """)
    
    # Drop the temporary table
    migrator.sql("DROP TABLE mapping_temp;")


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    
    # Recreate with is_default field
    migrator.sql("""
        CREATE TABLE mapping_temp AS 
        SELECT id, card, current, replace FROM mapping;
    """)
    
    migrator.sql("DROP TABLE mapping;")
    
    migrator.sql("""
        CREATE TABLE mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card VARCHAR(20),
            current VARCHAR(255),
            replace VARCHAR(255),
            is_default INTEGER
        );
    """)
    
    migrator.sql("""
        INSERT INTO mapping (id, card, current, replace, is_default)
        SELECT id, card, current, replace, 0 FROM mapping_temp;
    """)
    
    migrator.sql("DROP TABLE mapping_temp;")
