"""Create Masters table for master calibration frame management.

This migration creates a new Masters table to store master calibration frames
separately from the fitsFile and fitsSession models for better separation of concerns.
"""

def upgrade(migrator, database, fake=False, **kwargs):
    """Create the Masters table."""
    
    # Create Masters table
    migrator.create_table('masters', [
        ('id', migrator.auto_field()),
        ('master_id', migrator.text_field(primary_key=True)),
        ('master_type', migrator.text_field()),  # 'bias', 'dark', 'flat'
        ('master_path', migrator.text_field()),  # Full path to master file
        ('creation_date', migrator.datetime_field()),
        ('telescope', migrator.text_field(null=True)),
        ('instrument', migrator.text_field(null=True)),
        ('exposure_time', migrator.text_field(null=True)),  # For darks
        ('binning_x', migrator.text_field(null=True)),
        ('binning_y', migrator.text_field(null=True)),
        ('ccd_temp', migrator.text_field(null=True)),
        ('gain', migrator.text_field(null=True)),
        ('offset', migrator.text_field(null=True)),
        ('filter_name', migrator.text_field(null=True)),  # For flats
        ('source_session_id', migrator.text_field(null=True)),  # Original session that created this master
        ('file_count', migrator.integer_field(default=0)),  # Number of files stacked
        ('quality_score', migrator.real_field(null=True)),  # Quality assessment score
        ('file_size', migrator.integer_field(null=True)),  # File size in bytes
        ('hash_value', migrator.text_field(null=True)),  # File hash for integrity
        ('cloud_url', migrator.text_field(null=True)),  # Cloud storage URL
        ('is_validated', migrator.boolean_field(default=False)),  # Validation status
        ('validation_date', migrator.datetime_field(null=True)),
        ('notes', migrator.text_field(null=True)),  # Additional notes
        ('soft_delete', migrator.boolean_field(default=False)),  # Soft delete flag
    ])


def downgrade(migrator, database, fake=False, **kwargs):
    """Drop the Masters table."""
    migrator.drop_table('masters')