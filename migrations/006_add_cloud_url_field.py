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
    # Add the new cloud URL field
    migrator.add_columns('fitsfile', fitsFileCloudURL=pw.TextField(null=True))

def rollback(migrator, database, fake=False, **kwargs):
    """
    Remove fitsFileCloudURL field from fitsFile table
    """
    # Remove the cloud URL field
    migrator.drop_columns('fitsfile', 'fitsFileCloudURL')