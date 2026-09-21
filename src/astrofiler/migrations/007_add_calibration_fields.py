"""
Migration 007: Add calibration tracking fields to fitsFile table

This migration adds new fields to track calibration status and related
metadata for the auto-calibration system:
- fitsFileSoftDelete: Mark files for deletion after cloud backup
- fitsFileCalibrationDate: When the file was calibrated
- fitsFileMasterBias: Reference to master bias used for calibration
- fitsFileMasterDark: Reference to master dark used for calibration
- fitsFileMasterFlat: Reference to master flat used for calibration
- fitsFileOriginalFile: Reference to original uncalibrated file
- fitsFileOriginalCloudURL: Cloud URL of original file after local deletion
"""

import peewee as pw

def migrate(migrator, database, fake=False, **kwargs):
    """
    Add calibration tracking fields to fitsFile table
    """
    # Add calibration tracking fields
    migrator.add_fields('fitsfile', 
        fitsFileSoftDelete=pw.BooleanField(null=True, default=False),
        fitsFileCalibrationDate=pw.DateTimeField(null=True),
        fitsFileMasterBias=pw.TextField(null=True),
        fitsFileMasterDark=pw.TextField(null=True), 
        fitsFileMasterFlat=pw.TextField(null=True),
        fitsFileOriginalFile=pw.TextField(null=True),
        fitsFileOriginalCloudURL=pw.TextField(null=True)
    )

def rollback(migrator, database, fake=False, **kwargs):
    """
    Remove calibration tracking fields from fitsFile table
    """
    # Remove the calibration tracking fields
    migrator.remove_fields('fitsfile', 
        'fitsFileSoftDelete',
        'fitsFileCalibrationDate',
        'fitsFileMasterBias',
        'fitsFileMasterDark',
        'fitsFileMasterFlat', 
        'fitsFileOriginalFile',
        'fitsFileOriginalCloudURL'
    )