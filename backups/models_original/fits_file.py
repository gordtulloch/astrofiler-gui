"""
FITS file model for AstroFiler.

This model represents individual FITS files in the system.
"""

import peewee as pw
from .base import BaseModel

class fitsFile(BaseModel):
    """Model representing a FITS file in the system."""
    
    fitsFileId = pw.TextField(primary_key=True)
    fitsFileName = pw.TextField(null=True)
    fitsFileDate = pw.DateField(null=True)
    fitsFileCalibrated = pw.IntegerField(null=True)
    fitsFileType = pw.TextField(null=True)
    fitsFileStacked = pw.IntegerField(null=True)
    fitsFileObject = pw.TextField(null=True)
    fitsFileExpTime = pw.TextField(null=True)
    fitsFileXBinning = pw.TextField(null=True)
    fitsFileYBinning = pw.TextField(null=True)
    fitsFileCCDTemp = pw.TextField(null=True)
    fitsFileTelescop = pw.TextField(null=True)
    fitsFileInstrument = pw.TextField(null=True)
    fitsFileGain = pw.TextField(null=True)
    fitsFileOffset = pw.TextField(null=True)
    fitsFileFilter = pw.TextField(null=True)
    fitsFileHash = pw.TextField(null=True)
    fitsFileSession = pw.TextField(null=True)
    fitsFileCloudURL = pw.TextField(null=True)
    fitsFileSoftDelete = pw.BooleanField(null=True, default=False)
    fitsFileCalibrationDate = pw.DateTimeField(null=True)
    fitsFileOriginalFile = pw.TextField(null=True)
    fitsFileOriginalCloudURL = pw.TextField(null=True)

    class Meta:
        table_name = 'fitsFile'
    
    def is_calibration_frame(self):
        """
        Check if this file is a calibration frame (bias, dark, flat).
        
        Returns:
            bool: True if this is a calibration frame
        """
        return self.fitsFileType in ['Bias Frame', 'Dark Frame', 'Flat Field']
    
    def is_light_frame(self):
        """
        Check if this file is a light frame.
        
        Returns:
            bool: True if this is a light frame
        """
        return self.fitsFileType == 'Light Frame'
    
    def get_calibration_criteria(self):
        """
        Get the calibration matching criteria for this file.
        
        Returns:
            dict: Dictionary with calibration matching criteria
        """
        return {
            'telescope': self.fitsFileTelescop,
            'instrument': self.fitsFileInstrument,
            'binning_x': self.fitsFileXBinning,
            'binning_y': self.fitsFileYBinning,
            'ccd_temp': self.fitsFileCCDTemp,
            'gain': self.fitsFileGain,
            'offset': self.fitsFileOffset,
            'exposure_time': self.fitsFileExpTime if self.fitsFileType == 'Dark Frame' else None,
            'filter_name': self.fitsFileFilter if self.fitsFileType == 'Flat Field' else None
        }
    
    def mark_as_calibrated(self, calibration_date=None):
        """
        Mark this file as calibrated.
        
        Args:
            calibration_date: Date of calibration (defaults to now)
        """
        import datetime
        self.fitsFileCalibrated = 1
        if calibration_date:
            self.fitsFileCalibrationDate = calibration_date
        else:
            self.fitsFileCalibrationDate = datetime.datetime.now()
        self.save()
    
    def is_precalibrated(self):
        """
        Check if this file is from a telescope that provides pre-calibrated images.
        
        Returns:
            bool: True if from Seestar or iTelescope
        """
        if self.fitsFileTelescop:
            telescope = self.fitsFileTelescop.lower()
            return 'seestar' in telescope or 'itelescope' in telescope
        return False