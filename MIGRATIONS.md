# Database Migration Guide for AstroFiler

AstroFiler now uses peewee-migrate for database version control and schema migrations. This ensures that database changes are tracked and can be applied consistently across different installations.

## Overview

The migration system uses the following components:
- `peewee-migrate` package for migration management
- `migrations/` directory to store migration files
- `migrate.py` script for migration management
- Updated `astrofiler_db.py` with migration support

## Basic Usage

### Check Migration Status
```bash
python migrate.py status
```
This shows which migrations have been applied and which are pending.

### Run Pending Migrations
```bash
python migrate.py run
```
This applies all pending migrations to bring the database up to date.

### Initial Database Setup
```bash
python migrate.py setup
```
This performs the initial database setup and creates the migrations directory.

## For Developers: Creating Migrations

### Creating a New Migration
When you need to modify the database schema:

1. **Create a migration file:**
   ```bash
   python migrate.py create add_new_field
   ```
   This creates a new migration file in the `migrations/` directory.

2. **Edit the migration file** to define your changes. The file will be named something like `001_add_new_field.py` and will contain:
   ```python
   """
   Add new field migration
   """
   
   def migrate(migrator, database, fake=False, **kwargs):
       # Your forward migration code here
       pass
   
   def rollback(migrator, database, fake=False, **kwargs):
       # Your rollback code here (optional but recommended)
       pass
   ```

3. **Example migration for adding a field:**
   ```python
   def migrate(migrator, database, fake=False, **kwargs):
       # Add a new field to the fitsFile table
       migrator.add_column('fitsfile', 'fitsFileNewField', CharField(null=True))
   
   def rollback(migrator, database, fake=False, **kwargs):
       # Remove the field if rolling back
       migrator.drop_column('fitsfile', 'fitsFileNewField')
   ```

4. **Apply the migration:**
   ```bash
   python migrate.py run
   ```

### Common Migration Operations

#### Adding a Column
```python
def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_column('table_name', 'column_name', CharField(null=True))
```

#### Removing a Column
```python
def migrate(migrator, database, fake=False, **kwargs):
    migrator.drop_column('table_name', 'column_name')
```

#### Creating a New Table
```python
def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_column('new_table', 'id', AutoField(primary_key=True))
    migrator.add_column('new_table', 'name', CharField())
```

#### Adding an Index
```python
def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_index('table_name', ('column_name',), unique=False)
```

## Migration Best Practices

1. **Always test migrations** on a copy of your database first
2. **Include rollback functions** when possible
3. **Use descriptive migration names** that indicate what the migration does
4. **Keep migrations small and focused** - one logical change per migration
5. **Never edit existing migration files** - create new ones instead
6. **Backup your database** before applying migrations to production

## Troubleshooting

### Migration Fails
If a migration fails:
1. Check the error message in the logs
2. Verify your migration syntax
3. Ensure the database is accessible
4. Consider rolling back and fixing the migration

### Starting Fresh
If you need to start with a clean migration history:
1. Delete the `migrations/` directory
2. Delete the database file (`astrofiler.db`)
3. Run `python migrate.py setup`

### Migration Status Issues
If migration status seems incorrect:
1. Check that the `migrations/` directory exists
2. Verify database connectivity
3. Look for error messages in the logs

## Directory Structure

After setting up migrations, your project will have:
```
astrofiler-gui/
├── astrofiler_db.py          # Updated database models with migration support
├── migrate.py                # Migration management script
├── migrations/               # Migration files directory
│   ├── 001_initial.py       # Initial migration (auto-created)
│   ├── 002_add_field.py     # Example additional migration
│   └── ...
├── astrofiler.db            # SQLite database file
└── ...
```

## Integration with AstroFiler

The migration system is integrated into AstroFiler's startup process:
- `setup_database()` in `astrofiler_db.py` automatically runs pending migrations
- The GUI will work seamlessly with the migrated database
- No changes needed to existing application code

This ensures that users always have the correct database schema when they run AstroFiler.
