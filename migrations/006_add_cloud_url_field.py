"""
Migration 006: Add fitsFileCloudURL field to fitsFile table

This migration adds a new field to track cloud storage URLs for FITS files.
This will be used by the cloud sync analyze function to store the cloud
location of files that exist both locally and in cloud storage.
"""

import peewee as pw

def migrate(migrator, database, fake=False, **kwargs):
    """
    Add fitsFileCloudURL field to fitsFile table
    """
    # Check if the column already exists
    cursor = database.execute_sql("PRAGMA table_info(fitsfile)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    # Only add the column if it doesn't already exist
    if 'fitsFileCloudURL' not in existing_columns:
        migrator.add_columns('fitsfile', fitsFileCloudURL=pw.TextField(null=True))

def rollback(migrator, database, fake=False, **kwargs):
    """
    Remove fitsFileCloudURL field from fitsFile table
    """
    # Check if the column exists before trying to remove it
    cursor = database.execute_sql("PRAGMA table_info(fitsfile)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    # Only remove the column if it exists
    if 'fitsFileCloudURL' in existing_columns:
        migrator.drop_columns('fitsfile', 'fitsFileCloudURL')