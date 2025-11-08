"""
Masters model for AstroFiler.

This model handles master calibration frames separately from fitsFile and fitsSession models.
"""

import peewee as pw
import datetime
import hashlib
import os
import logging
from .base import BaseModel

logger = logging.getLogger(__name__)

class Masters(BaseModel):
    """Model for storing master calibration frames separately from fitsFile and fitsSession."""
    
    id = pw.AutoField()
    master_id = pw.TextField(unique=True)
    master_type = pw.TextField()  # 'bias', 'dark', 'flat'
    master_path = pw.TextField()  # Full path to master file
    creation_date = pw.DateTimeField()
    telescope = pw.TextField(null=True)
    instrument = pw.TextField(null=True)
    exposure_time = pw.TextField(null=True)  # For darks
    binning_x = pw.TextField(null=True)
    binning_y = pw.TextField(null=True)
    ccd_temp = pw.TextField(null=True)
    gain = pw.TextField(null=True)
    offset = pw.TextField(null=True)
    filter_name = pw.TextField(null=True)  # For flats
    source_session_id = pw.TextField(null=True)  # Original session that created this master
    file_count = pw.IntegerField(default=0)  # Number of files stacked
    quality_score = pw.FloatField(null=True)  # Quality assessment score
    file_size = pw.IntegerField(null=True)  # File size in bytes
    hash_value = pw.TextField(null=True)  # File hash for integrity
    cloud_url = pw.TextField(null=True)  # Cloud storage URL
    is_validated = pw.BooleanField(default=False)  # Validation status
    validation_date = pw.DateTimeField(null=True)
    notes = pw.TextField(null=True)  # Additional notes
    soft_delete = pw.BooleanField(default=False)  # Soft delete flag

    class Meta:
        table_name = 'Masters'

    @classmethod
    def find_matching_master(cls, telescope, instrument, master_type, **criteria):
        """
        Find a matching master frame based on equipment and criteria.
        
        Args:
            telescope (str): Telescope name
            instrument (str): Instrument name  
            master_type (str): Type of master ('bias', 'dark', 'flat')
            **criteria: Additional matching criteria (exposure_time, filter_name, etc.)
            
        Returns:
            Masters: Matching master frame or None
        """
        query = cls.select().where(
            cls.telescope == telescope,
            cls.instrument == instrument,
            cls.master_type == master_type,
            cls.soft_delete == False
        )
        
        # Add type-specific criteria
        if master_type == 'dark' and 'exposure_time' in criteria:
            query = query.where(cls.exposure_time == criteria['exposure_time'])
        elif master_type == 'flat' and 'filter_name' in criteria:
            query = query.where(cls.filter_name == criteria['filter_name'])
            
        # Add common criteria
        for field in ['binning_x', 'binning_y', 'ccd_temp', 'gain', 'offset']:
            if field in criteria and criteria[field] is not None:
                query = query.where(getattr(cls, field) == criteria[field])
                
        return query.first()
    
    @classmethod
    def create_master_record(cls, master_path, session_data, cal_type, file_count=0):
        """
        Create a new master calibration frame record.
        
        Args:
            master_path (str): Path to the master file
            session_data (dict): Session data with equipment and settings
            cal_type (str): Type of calibration ('bias', 'dark', 'flat')
            file_count (int): Number of files used to create master
            
        Returns:
            Masters: Created master record
        """
        # Generate unique master ID
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        telescope_safe = session_data.get('telescope', 'unknown').replace(' ', '_')
        master_id = f"{cal_type}_{telescope_safe}_{timestamp}"
        
        # Calculate file hash if file exists
        file_hash = None
        file_size = None
        if os.path.exists(master_path):
            file_size = os.path.getsize(master_path)
            with open(master_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
        
        return cls.create(
            master_id=master_id,
            master_type=cal_type,
            master_path=master_path,
            creation_date=datetime.datetime.now(),
            telescope=session_data.get('telescope'),
            instrument=session_data.get('instrument'),
            exposure_time=session_data.get('exposure_time') if cal_type == 'dark' else None,
            binning_x=session_data.get('binning_x'),
            binning_y=session_data.get('binning_y'),
            ccd_temp=session_data.get('ccd_temp'),
            gain=session_data.get('gain'),
            offset=session_data.get('offset'),
            filter_name=session_data.get('filter_name') if cal_type == 'flat' else None,
            source_session_id=session_data.get('session_id'),
            file_count=file_count,
            file_size=file_size,
            hash_value=file_hash
        )
    
    def validate_file_integrity(self):
        """
        Validate that the master file exists and matches the stored hash.
        
        Returns:
            bool: True if file is valid, False otherwise
        """
        if not os.path.exists(self.master_path):
            return False
            
        if self.hash_value:
            with open(self.master_path, 'rb') as f:
                current_hash = hashlib.md5(f.read()).hexdigest()
                return current_hash == self.hash_value
                
        return True
    
    def get_matching_criteria(self):
        """
        Get the criteria dictionary for matching this master to sessions.
        
        Returns:
            dict: Matching criteria
        """
        criteria = {
            'telescope': self.telescope,
            'instrument': self.instrument,
            'master_type': self.master_type
        }
        
        if self.master_type == 'dark' and self.exposure_time:
            criteria['exposure_time'] = self.exposure_time
        elif self.master_type == 'flat' and self.filter_name:
            criteria['filter_name'] = self.filter_name
            
        # Add optional matching criteria
        for field in ['binning_x', 'binning_y', 'ccd_temp', 'gain', 'offset']:
            value = getattr(self, field)
            if value is not None:
                criteria[field] = value
                
        return criteria

    def update_quality_score(self, score):
        """
        Update the quality score for this master.
        
        Args:
            score (float): Quality score (0.0 to 1.0)
        """
        self.quality_score = max(0.0, min(1.0, float(score)))
        self.save()

    def validate_and_mark(self):
        """
        Validate the master file and mark as validated if successful.
        
        Returns:
            bool: True if validation successful
        """
        if self.validate_file_integrity():
            self.is_validated = True
            self.validation_date = datetime.datetime.now()
            self.save()
            return True
        return False

    def soft_delete_master(self):
        """
        Mark this master as soft deleted.
        """
        self.soft_delete = True
        self.save()

    @classmethod
    def cleanup_invalid_masters(cls):
        """
        Clean up masters whose files no longer exist.
        
        Returns:
            list: List of master IDs that were cleaned up
        """
        cleaned_up = []
        for master in cls.select().where(cls.soft_delete == False):
            if not os.path.exists(master.master_path):
                logger.warning(f"Master file not found: {master.master_path}")
                master.soft_delete_master()
                cleaned_up.append(master.master_id)
        return cleaned_up

    @classmethod
    def get_masters_by_type(cls, master_type, include_deleted=False):
        """
        Get all masters of a specific type.
        
        Args:
            master_type (str): Type of master ('bias', 'dark', 'flat')
            include_deleted (bool): Whether to include soft-deleted masters
            
        Returns:
            list: List of Masters objects
        """
        query = cls.select().where(cls.master_type == master_type)
        if not include_deleted:
            query = query.where(cls.soft_delete == False)
        return list(query.order_by(cls.creation_date.desc()))

    @classmethod
    def get_masters_for_equipment(cls, telescope, instrument):
        """
        Get all masters for specific equipment.
        
        Args:
            telescope (str): Telescope name
            instrument (str): Instrument name
            
        Returns:
            list: List of Masters objects
        """
        return list(cls.select().where(
            cls.telescope == telescope,
            cls.instrument == instrument,
            cls.soft_delete == False
        ).order_by(cls.creation_date.desc()))

    @classmethod
    def get_storage_usage(cls):
        """
        Get total storage usage of all masters.
        
        Returns:
            dict: Dictionary with storage statistics
        """
        total_size = 0
        total_count = 0
        by_type = {'bias': 0, 'dark': 0, 'flat': 0}
        
        for master in cls.select().where(cls.soft_delete == False):
            if master.file_size:
                total_size += master.file_size
                total_count += 1
                if master.master_type in by_type:
                    by_type[master.master_type] += master.file_size
        
        return {
            'total_size_bytes': total_size,
            'total_count': total_count,
            'by_type_bytes': by_type,
            'total_size_gb': total_size / (1024**3) if total_size > 0 else 0
        }

    def __str__(self):
        return f"{self.master_type} master for {self.telescope}/{self.instrument} ({self.master_id})"