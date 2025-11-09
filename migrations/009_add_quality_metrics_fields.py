"""
Migration 009: Add quality metrics fields to fitsFile table

This migration adds new fields to track advanced quality metrics for FITS files:
- fitsFileAvgFWHMArcsec: Average FWHM in arcseconds for detected stars
- fitsFileAvgEccentricity: Average star eccentricity (0-1, where 0=round, 1=elongated)
- fitsFileAvgHFRArcsec: Average Half Flux Radius in arcseconds
- fitsFileImageSNR: Signal-to-noise ratio for the entire image
- fitsFileStarCount: Number of stars detected in the image
- fitsFileImageScale: Image scale in arcseconds per pixel
"""

import peewee as pw

def migrate(migrator, database, fake=False, **kwargs):
    """
    Add quality metrics fields to fitsFile table
    """
    # Add quality metrics fields
    migrator.add_fields('fitsFile', 
        fitsFileAvgFWHMArcsec=pw.FloatField(null=True),
        fitsFileAvgEccentricity=pw.FloatField(null=True),
        fitsFileAvgHFRArcsec=pw.FloatField(null=True),
        fitsFileImageSNR=pw.FloatField(null=True),
        fitsFileStarCount=pw.IntegerField(null=True),
        fitsFileImageScale=pw.FloatField(null=True)
    )

def rollback(migrator, database, fake=False, **kwargs):
    """
    Remove quality metrics fields from fitsFile table
    """
    # Remove the quality metrics fields
    migrator.remove_fields('fitsFile', 
        'fitsFileAvgFWHMArcsec',
        'fitsFileAvgEccentricity', 
        'fitsFileAvgHFRArcsec',
        'fitsFileImageSNR',
        'fitsFileStarCount',
        'fitsFileImageScale'
    )