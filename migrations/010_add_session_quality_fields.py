"""
Migration 010: Add quality metric fields to fitsSession table.

Adds the same quality metric fields from fitsFile to fitsSession to store
average quality metrics for all files in a session:
- fitsSessionAvgFWHMArcsec: Average FWHM in arcseconds for session
- fitsSessionAvgEccentricity: Average star eccentricity (0-1 scale) for session
- fitsSessionAvgHFRArcsec: Average Half Flux Radius in arcseconds for session
- fitsSessionImageSNR: Average signal-to-noise ratio for session
- fitsSessionStarCount: Average star count for session
- fitsSessionImageScale: Image scale in arcsec/pixel for session
"""

import peewee as pw

def migrate(migrator, database, fake=False, **kwargs):
    """
    Add quality metric fields to fitsSession table
    """
    # Add quality metrics fields
    migrator.add_fields('fitssession', 
        fitsSessionAvgFWHMArcsec=pw.FloatField(null=True),
        fitsSessionAvgEccentricity=pw.FloatField(null=True),
        fitsSessionAvgHFRArcsec=pw.FloatField(null=True),
        fitsSessionImageSNR=pw.FloatField(null=True),
        fitsSessionStarCount=pw.IntegerField(null=True),
        fitsSessionImageScale=pw.FloatField(null=True)
    )

def rollback(migrator, database, fake=False, **kwargs):
    """
    Remove quality metrics fields from fitsSession table
    """
    # Remove the quality metrics fields
    migrator.remove_fields('fitssession', 
        'fitsSessionAvgFWHMArcsec',
        'fitsSessionAvgEccentricity', 
        'fitsSessionAvgHFRArcsec',
        'fitsSessionImageSNR',
        'fitsSessionStarCount',
        'fitsSessionImageScale'
    )
