"""Remove master calibration fields from fitsFile and fitsSession models.

This migration removes master-related fields from the existing models since
they are now managed by the separate Masters table.
"""

def upgrade(migrator, database, fake=False, **kwargs):
    """Remove master calibration fields from existing tables."""
    
    # Remove master fields from fitsFile table
    try:
        migrator.drop_column('fitsfile', 'fitsFileMasterBias')
    except Exception:
        pass  # Field may not exist
        
    try:
        migrator.drop_column('fitsfile', 'fitsFileMasterDark')
    except Exception:
        pass  # Field may not exist
        
    try:
        migrator.drop_column('fitsfile', 'fitsFileMasterFlat')
    except Exception:
        pass  # Field may not exist
    
    # Remove master fields from fitsSession table
    try:
        migrator.drop_column('fitssession', 'fitsBiasMaster')
    except Exception:
        pass  # Field may not exist
        
    try:
        migrator.drop_column('fitssession', 'fitsDarkMaster')
    except Exception:
        pass  # Field may not exist
        
    try:
        migrator.drop_column('fitssession', 'fitsFlatMaster')
    except Exception:
        pass  # Field may not exist
        
    try:
        migrator.drop_column('fitssession', 'master_dark_created')
    except Exception:
        pass  # Field may not exist
        
    try:
        migrator.drop_column('fitssession', 'master_flat_created')
    except Exception:
        pass  # Field may not exist
        
    try:
        migrator.drop_column('fitssession', 'master_bias_created')
    except Exception:
        pass  # Field may not exist


def downgrade(migrator, database, fake=False, **kwargs):
    """Restore master calibration fields to existing tables."""
    
    # Restore master fields to fitsFile table
    migrator.add_column('fitsfile', 'fitsFileMasterBias', migrator.text_field(null=True))
    migrator.add_column('fitsfile', 'fitsFileMasterDark', migrator.text_field(null=True))
    migrator.add_column('fitsfile', 'fitsFileMasterFlat', migrator.text_field(null=True))
    
    # Restore master fields to fitsSession table
    migrator.add_column('fitssession', 'fitsBiasMaster', migrator.text_field(null=True))
    migrator.add_column('fitssession', 'fitsDarkMaster', migrator.text_field(null=True))
    migrator.add_column('fitssession', 'fitsFlatMaster', migrator.text_field(null=True))
    migrator.add_column('fitssession', 'master_dark_created', migrator.boolean_field(null=True, default=False))
    migrator.add_column('fitssession', 'master_flat_created', migrator.boolean_field(null=True, default=False))
    migrator.add_column('fitssession', 'master_bias_created', migrator.boolean_field(null=True, default=False))