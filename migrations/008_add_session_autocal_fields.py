"""
Migration 008: Add auto-calibration tracking fields to fitsSession table

This migration adds new fields to track auto-calibration status and relationships
for sessions in the auto-calibration system:
- is_auto_calibration: Flag indicating if session uses auto-calibration
- auto_calibration_dark_session_id: ID of dark session used for calibration
- auto_calibration_flat_session_id: ID of flat session used for calibration  
- auto_calibration_bias_session_id: ID of bias session used for calibration
- master_dark_created: Flag indicating if master dark was created for this session
- master_flat_created: Flag indicating if master flat was created for this session
- master_bias_created: Flag indicating if master bias was created for this session
"""

import peewee as pw

def migrate(migrator, database, fake=False, **kwargs):
    """
    Add auto-calibration tracking fields to fitsSession table
    """
    # Add auto-calibration tracking fields
    migrator.add_columns('fitssession', 
        is_auto_calibration=pw.BooleanField(null=True, default=False),
        auto_calibration_dark_session_id=pw.TextField(null=True),
        auto_calibration_flat_session_id=pw.TextField(null=True),
        auto_calibration_bias_session_id=pw.TextField(null=True),
        master_dark_created=pw.BooleanField(null=True, default=False),
        master_flat_created=pw.BooleanField(null=True, default=False),
        master_bias_created=pw.BooleanField(null=True, default=False)
    )

def rollback(migrator, database, fake=False, **kwargs):
    """
    Remove auto-calibration tracking fields from fitsSession table
    """
    # Remove the auto-calibration tracking fields
    migrator.drop_columns('fitssession', 
        'is_auto_calibration',
        'auto_calibration_dark_session_id',
        'auto_calibration_flat_session_id',
        'auto_calibration_bias_session_id',
        'master_dark_created',
        'master_flat_created',
        'master_bias_created'
    )