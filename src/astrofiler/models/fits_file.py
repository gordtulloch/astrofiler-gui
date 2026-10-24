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
    fitsFileObserver = pw.TextField(null=True)
    fitsFileNotes = pw.TextField(null=True)
    fitsFileHash = pw.TextField(null=True)
    fitsFileSession = pw.TextField(null=True)
    fitsFileCloudURL = pw.TextField(null=True)
    fitsFileSoftDelete = pw.BooleanField(null=True, default=False)
    fitsFileCalibrationDate = pw.DateTimeField(null=True)
    fitsFileOriginalFile = pw.TextField(null=True)
    fitsFileOriginalCloudURL = pw.TextField(null=True)
    
    # Quality metrics fields
    fitsFileAvgFWHMArcsec = pw.FloatField(null=True)  # Average FWHM in arcseconds
    fitsFileAvgEccentricity = pw.FloatField(null=True)  # Average star eccentricity (0-1)
    fitsFileAvgHFRArcsec = pw.FloatField(null=True)  # Average HFR in arcseconds  
    fitsFileImageSNR = pw.FloatField(null=True)  # Signal-to-noise ratio for image
    fitsFileStarCount = pw.IntegerField(null=True)  # Number of detected stars
    fitsFileImageScale = pw.FloatField(null=True)  # Arcsec/pixel scale

    class Meta:
        table_name = 'fitsFile'

    @staticmethod
    def normalize_seestar_metadata(telescop_raw, instrume_raw, focallen=0):
        """
        Normalize TELESCOP and INSTRUME metadata for Seestar series telescopes (S50, S50 Pro, S30, S30 Pro).
        Strips serial numbers and determines Tele vs Wide camera selection.
        """
        t_str = str(telescop_raw or '').strip()
        i_str = str(instrume_raw or '').strip()

        if not t_str:
            return telescop_raw, instrume_raw

        # Identify telescope model
        if 'S50 Pro' in t_str or 'S50_Pro' in t_str:
            new_telescop = 'Seestar S50 Pro'
        elif 'S50' in t_str:
            new_telescop = 'Seestar S50'
        elif 'S30 Pro' in t_str or 'S30_Pro' in t_str:
            new_telescop = 'Seestar S30 Pro'
        elif 'S30' in t_str:
            new_telescop = 'Seestar S30'
        elif 'seestar' in t_str.lower():
            new_telescop = 'Seestar S50'  # Fallback for legacy generic Seestar headers
        else:
            return telescop_raw, instrume_raw

        # Determine Tele vs Wide instrument selection
        camera_type = "Tele"
        if new_telescop != 'Seestar S50':
            try:
                focallen_val = float(focallen or 0)
            except (ValueError, TypeError):
                focallen_val = 0

            if 'Wide' in i_str or 'WIDE' in i_str.upper() or (0 < focallen_val < 100):
                camera_type = "Wide"

        new_instrume = f"{new_telescop} {camera_type}"
        return new_telescop, new_instrume

    def apply_seestar_normalization(self, focallen=0):
        """Standardizes telescope and instrument fields directly on this instance."""
        norm_t, norm_i = self.normalize_seestar_metadata(
            self.fitsFileTelescop, 
            self.fitsFileInstrument, 
            focallen
        )
        self.fitsFileTelescop = norm_t
        self.fitsFileInstrument = norm_i

    def is_calibration_frame(self):
        """
        Check if this file is a calibration frame (bias, dark, flat).
        
        Returns:
            bool: True if this is a calibration frame
        """
        if not self.fitsFileType:
            return False
        file_type = self.fitsFileType.upper()
        return any(token in file_type for token in ['BIAS', 'DARK', 'FLAT'])
    
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
            'exposure_time': self.fitsFileExpTime if self.fitsFileType and 'DARK' in self.fitsFileType.upper() else None,
            'filter_name': self.fitsFileFilter if self.fitsFileType and 'FLAT' in self.fitsFileType.upper() and 'DARK' not in self.fitsFileType.upper() else None
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