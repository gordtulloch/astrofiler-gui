"""
Mapping model for AstroFiler.

This model handles field mappings for standardizing FITS header values.
"""

import peewee as pw
from .base import BaseModel

class Mapping(BaseModel):
    """Model for mapping FITS header values to standardized values."""
    
    id = pw.AutoField()
    card = pw.CharField(max_length=20)  # TELESCOP, INSTRUME, OBSERVER, NOTES
    current = pw.CharField(max_length=255, null=True)  # Current value (can be blank)
    replace = pw.CharField(max_length=255, null=True)  # Replacement value (can be blank)

    class Meta:
        table_name = 'Mapping'
    
    @classmethod
    def get_mapped_value(cls, card_name, current_value):
        """
        Get the mapped value for a given card and current value.
        
        Args:
            card_name (str): The FITS header card name (e.g., 'TELESCOP', 'INSTRUME')
            current_value (str): The current value to map
            
        Returns:
            str: The mapped value, or the original value if no mapping exists
        """
        if not current_value:
            return current_value
            
        try:
            mapping = cls.get(
                (cls.card == card_name) & 
                (cls.current == current_value)
            )
            return mapping.replace if mapping.replace else current_value
        except cls.DoesNotExist:
            return current_value
    
    @classmethod
    def add_mapping(cls, card_name, current_value, replace_value):
        """
        Add or update a mapping.
        
        Args:
            card_name (str): The FITS header card name
            current_value (str): The current value
            replace_value (str): The replacement value
            
        Returns:
            Mapping: The created or updated mapping
        """
        mapping, created = cls.get_or_create(
            card=card_name,
            current=current_value,
            defaults={'replace': replace_value}
        )
        
        if not created and mapping.replace != replace_value:
            mapping.replace = replace_value
            mapping.save()
            
        return mapping
    
    @classmethod
    def remove_mapping(cls, card_name, current_value):
        """
        Remove a mapping.
        
        Args:
            card_name (str): The FITS header card name
            current_value (str): The current value
            
        Returns:
            bool: True if mapping was removed, False if it didn't exist
        """
        try:
            mapping = cls.get(
                (cls.card == card_name) & 
                (cls.current == current_value)
            )
            mapping.delete_instance()
            return True
        except cls.DoesNotExist:
            return False
    
    @classmethod
    def get_mappings_for_card(cls, card_name):
        """
        Get all mappings for a specific card.
        
        Args:
            card_name (str): The FITS header card name
            
        Returns:
            list: List of Mapping objects
        """
        return list(cls.select().where(cls.card == card_name).order_by(cls.current))
    
    @classmethod
    def get_all_cards(cls):
        """
        Get all unique card names that have mappings.
        
        Returns:
            list: List of unique card names
        """
        return [row.card for row in cls.select(cls.card).distinct().order_by(cls.card)]
    
    def __str__(self):
        return f"{self.card}: '{self.current}' -> '{self.replace}'"