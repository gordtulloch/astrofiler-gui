"""
FITS session model for AstroFiler.

This model represents imaging sessions grouped by common characteristics.
"""

import peewee as pw
from .base import BaseModel

class fitsSession(BaseModel):
    """Model representing an imaging session with common characteristics."""
    
    fitsSessionId = pw.TextField(primary_key=True)
    fitsSessionObjectName = pw.TextField(null=True)
    fitsSessionDate = pw.DateField(null=True)
    fitsSessionTelescope = pw.TextField(null=True)
    fitsSessionImager = pw.TextField(null=True)
    fitsSessionExposure = pw.TextField(null=True)
    fitsSessionBinningX = pw.TextField(null=True)
    fitsSessionBinningY = pw.TextField(null=True)
    fitsSessionCCDTemp = pw.TextField(null=True)
    fitsSessionGain = pw.TextField(null=True)
    fitsSessionOffset = pw.TextField(null=True)
    fitsSessionFilter = pw.TextField(null=True)
    fitsBiasSession = pw.TextField(null=True)
    fitsDarkSession = pw.TextField(null=True)
    fitsFlatSession = pw.TextField(null=True)
    
    # Auto-calibration tracking fields
    is_auto_calibration = pw.BooleanField(null=True, default=False)
    auto_calibration_dark_session_id = pw.TextField(null=True)
    auto_calibration_flat_session_id = pw.TextField(null=True)
    auto_calibration_bias_session_id = pw.TextField(null=True)
    
    # Session-level quality metrics (averaged from files)
    fitsSessionAvgFWHMArcsec = pw.FloatField(null=True)  # Average FWHM in arcseconds
    fitsSessionAvgEccentricity = pw.FloatField(null=True)  # Average star eccentricity (0-1)
    fitsSessionAvgHFRArcsec = pw.FloatField(null=True)  # Average HFR in arcseconds
    fitsSessionImageSNR = pw.FloatField(null=True)  # Average signal-to-noise ratio
    fitsSessionStarCount = pw.IntegerField(null=True)  # Average detected stars
    fitsSessionImageScale = pw.FloatField(null=True)  # Image scale in arcsec/pixel

    class Meta:
        table_name = 'fitsSession'
    
    def is_calibration_session(self):
        """
        Check if this session contains calibration frames.
        
        Returns:
            bool: True if this is a calibration session
        """
        return self.is_auto_calibration or False
    
    def is_light_session(self):
        """
        Check if this session contains light frames.
        
        Returns:
            bool: True if this is a light frame session
        """
        return not self.is_calibration_session()
    
    def get_calibration_criteria(self):
        """
        Get the calibration matching criteria for this session.
        
        Returns:
            dict: Dictionary with calibration matching criteria
        """
        return {
            'telescope': self.fitsSessionTelescope,
            'instrument': self.fitsSessionImager,
            'binning_x': self.fitsSessionBinningX,
            'binning_y': self.fitsSessionBinningY,
            'ccd_temp': self.fitsSessionCCDTemp,
            'gain': self.fitsSessionGain,
            'offset': self.fitsSessionOffset,
            'exposure_time': self.fitsSessionExposure,
            'filter_name': self.fitsSessionFilter
        }
    
    def link_calibration_sessions(self, bias_session=None, dark_session=None, flat_session=None):
        """
        Link this session to calibration sessions.
        
        Args:
            bias_session (str): Bias session ID
            dark_session (str): Dark session ID  
            flat_session (str): Flat session ID
        """
        if bias_session:
            self.fitsBiasSession = bias_session
        if dark_session:
            self.fitsDarkSession = dark_session
        if flat_session:
            self.fitsFlatSession = flat_session
        self.save()
    
    def has_linked_calibrations(self):
        """
        Check if this session has linked calibration sessions.
        
        Returns:
            bool: True if calibration sessions are linked
        """
        return bool(self.fitsBiasSession or self.fitsDarkSession or self.fitsFlatSession)
    
    def get_linked_calibration_sessions(self):
        """
        Get the linked calibration session IDs.
        
        Returns:
            dict: Dictionary with linked session IDs
        """
        return {
            'bias': self.fitsBiasSession,
            'dark': self.fitsDarkSession,
            'flat': self.fitsFlatSession
        }
    
    def mark_as_auto_calibration(self, cal_type, source_session_ids=None):
        """
        Mark this session as an auto-calibration session.
        
        Args:
            cal_type (str): Type of calibration ('bias', 'dark', 'flat')
            source_session_ids (dict): Source session IDs for auto-calibration
        """
        self.is_auto_calibration = True
        
        if source_session_ids:
            if 'dark' in source_session_ids:
                self.auto_calibration_dark_session_id = source_session_ids['dark']
            if 'flat' in source_session_ids:
                self.auto_calibration_flat_session_id = source_session_ids['flat']
            if 'bias' in source_session_ids:
                self.auto_calibration_bias_session_id = source_session_ids['bias']
                
        self.save()
    
    def get_session_files(self):
        """
        Get all FITS files associated with this session.
        
        Returns:
            list: List of fitsFile objects
        """
        from .fits_file import fitsFile
        return list(fitsFile.select().where(fitsFile.fitsFileSession == self.fitsSessionId))
    
    def get_session_file_count(self):
        """
        Get the count of files in this session.
        
        Returns:
            int: Number of files in session
        """
        from .fits_file import fitsFile
        return fitsFile.select().where(fitsFile.fitsFileSession == self.fitsSessionId).count()