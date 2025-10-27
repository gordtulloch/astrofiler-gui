"""
XISF to FITS Converter

This module provides the XISFConverter class for reading XISF files and converting them to FITS format.

XISF (Extensible Image Serialization Format) is an XML-based file format that can contain:
- XML header with metadata and image properties
- Binary image data (can be embedded or referenced)
- Multiple images and other data structures

The converter extracts the header information as FITS-compatible cards and converts the image data.

Thanks to 
"""

import os
import xml.etree.ElementTree as ET
import numpy as np
from astropy.io import fits
import struct
import gzip
import lz4.frame
import zlib
from typing import Dict, Any, Tuple, Optional, Union
import logging
from .data_conversion import prepare_fits_data, validate_data_integrity, log_data_statistics
from .xisf_types import XISFSampleFormat, XISFGeometry

logger = logging.getLogger(__name__)


class XISFConverter:
    """
    A class to convert XISF files to FITS format.
    
    The XISF format consists of an XML header followed by binary data.
    This class reads the XML header to extract metadata and image properties,
    then reads the binary image data and creates a FITS file.
    """
    
    def __init__(self, file_path: str):
        """
        Initialize the XISF converter with a file path.
        
        Args:
            file_path (str): Path to the XISF file to convert
            
        Raises:
            FileNotFoundError: If the specified file doesn't exist
            ValueError: If the file is not a valid XISF file
        """
        self.file_path = file_path
        self.header_cards = {}
        self.image_data = None
        self.xml_header = None
        self.data_offset = 0
        self.image_geometry = {}
        
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"XISF file not found: {file_path}")
        
        # Validate file extension
        if not file_path.lower().endswith('.xisf'):
            logger.warning(f"File {file_path} does not have .xisf extension")
        
        # Read and parse the file
        self._read_file()
        self._parse_xml_header()
        self._extract_header_cards()
    
    def _read_file(self):
        """Read the XISF file with proper binary header parsing."""
        try:
            with open(self.file_path, 'rb') as f:
                # Read XISF binary header (16 bytes total)
                # 8 bytes: signature (should be "XISF0100")
                signature = f.read(8).decode('ascii').rstrip('\x00')
                if signature != "XISF0100":
                    raise ValueError(f"Invalid XISF signature: {signature}")
                
                # 4 bytes: XML header length (little endian)
                xml_length_bytes = f.read(4)
                xml_length = struct.unpack('<I', xml_length_bytes)[0]
                
                # 4 bytes: reserved (little endian)
                reserved_bytes = f.read(4)
                reserved = struct.unpack('<I', reserved_bytes)[0]
                
                logger.debug(f"XISF signature: {signature}")
                logger.debug(f"XML length: {xml_length}")
                logger.debug(f"Reserved: {reserved}")
                
                # Read XML header
                xml_content = f.read(xml_length).decode('utf-8')
                
                # Parse XML
                try:
                    self.xml_header = ET.fromstring(xml_content)
                except ET.ParseError as e:
                    raise ValueError(f"Invalid XML in XISF file: {e}")
                
                # Calculate data offset (16 bytes binary header + XML length)
                self.data_offset = 16 + xml_length
                
                logger.info(f"Successfully read XISF file: {self.file_path}")
                logger.debug(f"Binary header size: 16 bytes")
                logger.debug(f"XML header size: {xml_length} bytes")
                logger.debug(f"Binary data offset: {self.data_offset}")
                
        except Exception as e:
            raise ValueError(f"Error reading XISF file {self.file_path}: {e}")
    
    def _parse_xml_header(self):
        """Parse the XML header to extract image geometry and properties."""
        if self.xml_header is None:
            raise ValueError("XML header not loaded")
        
        # Define the XISF namespace - PixInsight uses this namespace
        namespace = {'xisf': 'http://www.pixinsight.com/xisf'}
        
        # Find the Image element with namespace
        image_elem = self.xml_header.find('.//xisf:Image', namespace)
        if image_elem is None:
            # Fallback: try without namespace in case it's not namespaced
            image_elem = self.xml_header.find('.//Image')
            if image_elem is None:
                raise ValueError("No Image element found in XISF file")
        
        # Parse geometry
        geometry_str = image_elem.get('geometry', '')
        if not geometry_str:
            raise ValueError("No geometry attribute found in Image element")
        
        try:
            geometry = XISFGeometry(geometry_str)
        except ValueError as e:
            raise ValueError(f"Invalid geometry: {e}")
        
        # Parse sample format
        sample_format_str = image_elem.get('sampleFormat', 'UInt16')
        try:
            sample_format = XISFSampleFormat(sample_format_str)
        except ValueError:
            raise ValueError(f"Unsupported sample format: {sample_format_str}")
        
        # Parse location (format: "attachment:offset:length")
        location_str = image_elem.get('location', '')
        location_method = ""
        location_start = 0
        location_length = 0
        
        if location_str:
            location_parts = location_str.split(':')
            if len(location_parts) >= 1:
                location_method = location_parts[0]
            if len(location_parts) >= 2:
                location_start = int(location_parts[1])
            if len(location_parts) >= 3:
                location_length = int(location_parts[2])
        
        # Parse compression (format: "codec:uncompressed_size" or just "codec")
        compression_str = image_elem.get('compression', '')
        compression_codec = ""
        compression_size = 0
        
        if compression_str:
            compression_parts = compression_str.split(':')
            compression_codec = compression_parts[0]
            if len(compression_parts) >= 2:
                compression_size = int(compression_parts[1])
        
        # Store all parsed information
        self.image_geometry = {
            'geometry': geometry,
            'width': geometry.width,
            'height': geometry.height,
            'channels': geometry.channels,
            'dimensions': geometry.dimensions,
            'sample_format': sample_format,
            'color_space': image_elem.get('colorSpace', 'Gray'),
            'location_method': location_method,
            'location_start': location_start,
            'location_length': location_length,
            'compression': compression_str,
            'compression_codec': compression_codec,
            'compression_size': compression_size,
        }
        
        logger.info(f"Image geometry: {geometry}")
        logger.info(f"Sample format: {sample_format.value}")
        logger.info(f"Color space: {self.image_geometry['color_space']}")
        logger.info(f"Location: {location_str}")
        logger.info(f"Compression: {compression_str}")
        
        # Validate required properties
        if geometry.width <= 0 or geometry.height <= 0:
            raise ValueError("Invalid image dimensions in XISF file")
            
        if location_method == "attachment":
            # Validate attachment location
            if location_start <= 0 or location_length <= 0:
                raise ValueError("Invalid attachment location parameters")
    
    def _extract_header_cards(self):
        """Extract metadata from XML and convert to FITS-compatible header cards."""
        if self.xml_header is None:
            raise ValueError("XML header not loaded")
        
        # Start with basic FITS required keywords
        geometry = self.image_geometry['geometry']
        
        self.header_cards = {
            'SIMPLE': True,
            'BITPIX': self._get_bitpix(),
            'NAXIS': self._get_naxis(),
        }
        
        # Add dimension keywords
        for i, dim in enumerate(geometry.dimensions):
            self.header_cards[f'NAXIS{i+1}'] = dim
        
        # Add NAXIS3 for channels if multi-channel
        if geometry.channels > 1:
            naxis_channels = len(geometry.dimensions) + 1
            self.header_cards[f'NAXIS{naxis_channels}'] = geometry.channels
        
        # Extract FITS keywords from XISF properties
        namespace = {'xisf': 'http://www.pixinsight.com/xisf'}
        
        # Try with namespace first
        fits_keywords = self.xml_header.findall('.//xisf:FITSKeyword', namespace)
        if not fits_keywords:
            # Fallback: try without namespace
            fits_keywords = self.xml_header.findall('.//FITSKeyword')
        
        for fits_keyword in fits_keywords:
            name = fits_keyword.get('name', '')
            value = fits_keyword.get('value', '')
            comment = fits_keyword.get('comment', '')
            
            if name:
                # Convert value to appropriate type
                converted_value = self._convert_fits_value(value)
                self.header_cards[name] = converted_value
                
                # Store comment separately if needed
                if comment:
                    self.header_cards[f'COMMENT_{name}'] = comment
        
        # Extract other metadata as FITS keywords
        self._extract_metadata_as_fits_keywords()
        
        logger.info(f"Extracted {len(self.header_cards)} header cards")
    
    def _get_bitpix(self) -> int:
        """Convert XISF sample format to FITS BITPIX value."""
        return self.image_geometry['sample_format'].to_fits_bitpix()
    
    def _get_naxis(self) -> int:
        """Get number of axes for FITS header."""
        geometry = self.image_geometry['geometry']
        naxis = len(geometry.dimensions)
        if geometry.channels > 1:
            naxis += 1
        return naxis
    
    def _convert_fits_value(self, value_str: str):
        """Convert string value to appropriate Python type for FITS."""
        if not value_str:
            return ''
        
        # Try to convert to number
        try:
            if '.' in value_str or 'e' in value_str.lower():
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass
        
        # Try boolean
        if value_str.lower() in ('true', 't'):
            return True
        elif value_str.lower() in ('false', 'f'):
            return False
        
        # Return as string
        return value_str.strip('\'"')
    
    def _extract_metadata_as_fits_keywords(self):
        """Extract additional metadata and convert to FITS keywords."""
        geometry = self.image_geometry['geometry']
        sample_format = self.image_geometry['sample_format']
        
        # Add XISF-specific information
        self.header_cards['ORIGIN'] = 'XISF to FITS Converter'
        self.header_cards['XISFFILE'] = os.path.basename(self.file_path)
        self.header_cards['XISFSAMP'] = sample_format.value
        self.header_cards['XISFGEOM'] = str(geometry)
        self.header_cards['XISFCMPR'] = self.image_geometry['compression_codec']
        self.header_cards['XISFCLRS'] = self.image_geometry['color_space']
        
        # Add geometry information
        self.header_cards['XISFDIMS'] = len(geometry.dimensions)
        for i, dim in enumerate(geometry.dimensions):
            self.header_cards[f'XISFDIM{i+1}'] = dim
        
        # Extract creation time if available
        creation_elem = self.xml_header.find('.//CreationTime')
        if creation_elem is not None and creation_elem.text:
            self.header_cards['DATE'] = creation_elem.text
        
        # Extract software information
        software_elem = self.xml_header.find('.//Software')
        if software_elem is not None:
            software_name = software_elem.get('name', '')
            software_version = software_elem.get('version', '')
            if software_name:
                self.header_cards['SOFTWARE'] = f"{software_name} {software_version}".strip()
    
    def _unshuffle_bytes(self, data: bytes, byte_size: int) -> bytes:
        """
        Unshuffle byte array as per XISF specification.
        
        Based on: http://pixinsight.com/doc/docs/XISF-1.0-spec/XISF-1.0-spec.html#byte_shuffling
        """
        if byte_size <= 1:
            return data
        
        array_size = len(data)
        n_items = array_size // byte_size
        
        if n_items * byte_size != array_size:
            logger.warning(f"Data size {array_size} not divisible by byte size {byte_size}")
            return data
        
        unshuffled = bytearray(array_size)
        
        for j in range(byte_size):
            array_start = j * n_items
            for i in range(n_items):
                unshuffled[i * byte_size + j] = data[array_start + i]
        
        logger.debug(f"Unshuffled {array_size} bytes with byte_size {byte_size}")
        return bytes(unshuffled)
    
    def _read_image_data(self) -> np.ndarray:
        """Read and decode the binary image data with proper compression handling."""
        if self.image_data is not None:
            return self.image_data
        
        geometry = self.image_geometry['geometry']
        sample_format = self.image_geometry['sample_format']
        location_method = self.image_geometry['location_method']
        
        # Determine data location
        if location_method == "attachment":
            # Data is embedded in the file
            location_start = self.image_geometry['location_start']
            location_length = self.image_geometry['location_length']
            
            # Attachment offset is absolute from start of file, not relative to data_offset
            absolute_offset = location_start
            
            logger.debug(f"Using absolute offset: {absolute_offset} (location_start: {location_start})")
            
            with open(self.file_path, 'rb') as f:
                f.seek(absolute_offset)
                binary_data = f.read(location_length)
        else:
            # Assume data follows immediately after XML header
            with open(self.file_path, 'rb') as f:
                f.seek(self.data_offset)
                binary_data = f.read()
        
        logger.debug(f"Read {len(binary_data)} bytes of binary data")
        
        # Handle compression
        compression_codec = self.image_geometry['compression_codec'].lower()
        compression_size = self.image_geometry['compression_size']
        needs_unshuffle = False
        
        if compression_codec:
            logger.info(f"Decompressing data with codec: {compression_codec}")
            
            if compression_codec in ('zlib', 'zlib+sh'):
                try:
                    decompressed = zlib.decompress(binary_data)
                    needs_unshuffle = compression_codec == 'zlib+sh'
                except Exception as e:
                    logger.warning(f"Zlib decompression failed: {e}")
                    decompressed = binary_data
                    
            elif compression_codec in ('lz4', 'lz4+sh'):
                try:
                    decompressed = lz4.frame.decompress(binary_data)
                    needs_unshuffle = compression_codec == 'lz4+sh'
                except Exception as e:
                    logger.warning(f"LZ4 decompression failed: {e}")
                    decompressed = binary_data
                    
            elif compression_codec == 'gzip':
                try:
                    decompressed = gzip.decompress(binary_data)
                except Exception as e:
                    logger.warning(f"Gzip decompression failed: {e}")
                    decompressed = binary_data
            else:
                logger.warning(f"Unsupported compression codec: {compression_codec}")
                decompressed = binary_data
            
            # Validate decompressed size if specified
            if compression_size > 0 and len(decompressed) != compression_size:
                logger.warning(f"Decompressed size mismatch: got {len(decompressed)}, expected {compression_size}")
            
            binary_data = decompressed
        
        # Apply byte unshuffling if needed
        if needs_unshuffle and sample_format.size() > 1:
            logger.info(f"Applying byte unshuffling for {compression_codec}")
            binary_data = self._unshuffle_bytes(binary_data, sample_format.size())
        
        # Convert binary data to numpy array
        dtype_str = sample_format.to_numpy_dtype()
        dtype = np.dtype(dtype_str)
        
        # Calculate expected size
        expected_pixels = geometry.total_pixels
        expected_bytes = expected_pixels * sample_format.size()
        
        logger.debug(f"Expected {expected_pixels} pixels, {expected_bytes} bytes")
        logger.debug(f"Got {len(binary_data)} bytes")
        
        if len(binary_data) < expected_bytes:
            raise ValueError(f"Insufficient data: got {len(binary_data)} bytes, expected {expected_bytes}")
        
        # Convert to numpy array (XISF data is little-endian)
        try:
            # Read only the expected amount of data
            pixel_data = binary_data[:expected_bytes]
            
            # Debug: check raw data
            if len(pixel_data) >= 40:
                raw_sample = np.frombuffer(pixel_data[:40], dtype='<f4')
                logger.debug(f"Raw data sample: {raw_sample}")
            
            data_array = np.frombuffer(pixel_data, dtype=dtype.newbyteorder('<'))
            logger.debug(f"After frombuffer: min={np.min(data_array)}, max={np.max(data_array)}, sample={data_array.flat[:10]}")
            
            # Convert to native byte order for processing
            if data_array.dtype.byteorder not in ('=', '|'):
                data_array = data_array.astype(dtype.newbyteorder('='))
                logger.debug(f"After native conversion: min={np.min(data_array)}, max={np.max(data_array)}, sample={data_array.flat[:10]}")
            
            # Reshape the array based on geometry
            logger.debug(f"Before reshape: shape={data_array.shape}, sample={data_array.flat[:10]}")
            
            if geometry.channels == 1:
                # Single channel: (height, width)
                self.image_data = data_array.reshape((geometry.height, geometry.width))
                logger.debug(f"After reshape (single): shape={self.image_data.shape}, sample={self.image_data.flat[:10]}")
            else:
                # Multi-channel: (channels, height, width)
                channel_size = geometry.channel_size()
                channels_data = []
                
                for ch in range(geometry.channels):
                    start_idx = ch * channel_size
                    end_idx = start_idx + channel_size
                    channel_data = data_array[start_idx:end_idx].reshape((geometry.height, geometry.width))
                    channels_data.append(channel_data)
                
                self.image_data = np.stack(channels_data, axis=0)
            
            logger.info(f"Successfully read image data: shape {self.image_data.shape}, dtype {self.image_data.dtype}")
            
        except Exception as e:
            raise ValueError(f"Error reading image data: {e}")
        
        return self.image_data
    
    def convert_to_fits(self, output_path: Optional[str] = None) -> str:
        """
        Convert the XISF file to FITS format.
        
        Args:
            output_path (str, optional): Output FITS file path. If None, uses same name as input with .fits extension.
            
        Returns:
            str: Path to the created FITS file
        """
        # Determine output path
        if output_path is None:
            base_name = os.path.splitext(self.file_path)[0]
            output_path = f"{base_name}.fits"
        
        # Read image data
        image_data = self._read_image_data()
        
        # Validate data integrity
        geometry = self.image_geometry['geometry']
        sample_format = self.image_geometry['sample_format']
        expected_pixels = geometry.total_pixels
        
        if not validate_data_integrity(image_data, expected_pixels, sample_format):
            logger.warning("Data validation failed, but continuing with conversion")
        
        # Log data statistics
        log_data_statistics(image_data, sample_format)
        
        # Convert data to FITS-compatible format
        fits_data, actual_bitpix = prepare_fits_data(image_data, sample_format)
        
        # Update BITPIX in header if it changed during conversion
        self.header_cards['BITPIX'] = actual_bitpix
        
        # Create FITS header
        header = fits.Header()
        for key, value in self.header_cards.items():
            if not key.startswith('COMMENT_'):
                try:
                    header[key] = value
                except Exception as e:
                    logger.warning(f"Could not add header card {key}={value}: {e}")
        
        # Create FITS HDU
        primary_hdu = fits.PrimaryHDU(data=fits_data, header=header)
        
        # Create FITS file
        hdu_list = fits.HDUList([primary_hdu])
        
        try:
            hdu_list.writeto(output_path, overwrite=True)
            logger.info(f"Successfully created FITS file: {output_path}")
            return output_path
            
        except Exception as e:
            raise ValueError(f"Error writing FITS file {output_path}: {e}")
        
        finally:
            hdu_list.close()
    
    def get_header_cards(self) -> Dict[str, Any]:
        """
        Get the extracted header cards as a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary of header cards
        """
        return self.header_cards.copy()
    
    def get_image_info(self) -> Dict[str, Any]:
        """
        Get information about the image.
        
        Returns:
            Dict[str, Any]: Image information dictionary
        """
        geometry = self.image_geometry.get('geometry')
        sample_format = self.image_geometry.get('sample_format')
        
        return {
            'geometry': {
                'width': geometry.width if geometry else 0,
                'height': geometry.height if geometry else 0,
                'channels': geometry.channels if geometry else 0,
                'dimensions': geometry.dimensions if geometry else [],
                'sample_format': sample_format.value if sample_format else 'Unknown',
                'color_space': self.image_geometry.get('color_space', 'Unknown'),
                'compression': self.image_geometry.get('compression', ''),
                'compression_codec': self.image_geometry.get('compression_codec', ''),
            },
            'header_cards_count': len(self.header_cards),
            'data_loaded': self.image_data is not None,
            'data_shape': self.image_data.shape if self.image_data is not None else None,
            'data_dtype': str(self.image_data.dtype) if self.image_data is not None else None,
            'location_method': self.image_geometry.get('location_method', ''),
            'location_start': self.image_geometry.get('location_start', 0),
            'location_length': self.image_geometry.get('location_length', 0),
        }