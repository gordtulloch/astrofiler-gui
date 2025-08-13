"""Peewee migrations -- 003_add_mapping_table.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['model_name']            # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.python(func, *args, **kwargs)       # Run python code
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(Model, cascade=True)    # Remove a model
    > migrator.add_fields(Model, **fields)         # Add fields to a model
    > migrator.change_fields(Model, **fields)      # Change fields
    > migrator.remove_fields(Model, *field_names, cascade=True)
    > migrator.rename_field(Model, old_field_name, new_field_name)
    > migrator.rename_table(Model, new_table_name)
    > migrator.add_index(Model, *col_names, unique=False)
    > migrator.drop_index(Model, *col_names)
    > migrator.add_not_null(Model, *field_names)
    > migrator.drop_not_null(Model, *field_names)
    > migrator.add_default(Model, field_name, default)

"""

import datetime as dt
import peewee as pw
from decimal import ROUND_HALF_EVEN

try:
    import playhouse.postgres_ext as pw_pext
except ImportError:
    pass

SQL = pw.SQL


def migrate(migrator, database, fake=False, **kwargs):
    """Write your migrations here."""
    
    # Define the Mapping model for migration
    @migrator.create_model
    class Mapping(pw.Model):
        id = pw.AutoField()
        card = pw.CharField(max_length=20)  # TELESCOP, INSTRUME, OBSERVER, NOTES
        current = pw.CharField(max_length=255, null=True)  # Current value (can be blank)
        replace = pw.CharField(max_length=255, null=True)  # Replacement value (can be blank)
        is_default = pw.BooleanField(default=False)  # Default checkbox
        
        class Meta:
            table_name = "mapping"


def rollback(migrator, database, fake=False, **kwargs):
    """Write your rollback migrations here."""
    
    migrator.remove_model('mapping')
