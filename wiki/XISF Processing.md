# XISF Processing in AstroFiler

This document describes the XISF (Extensible Image Serialization Format) to FITS conversion functionality integrated into AstroFiler. XISF is a file format used by PixInsight and other astronomical image processing software.

The XISF processing implementation is based on the XISF 1.0 specification and provides features equivalent to the reference Rust implementation at https://github.com/vrruiz/xisfits.

## Overview

AstroFiler now supports automatic detection and conversion of XISF files during the import process. When XISF files are encountered through either the UI "Load New" button or the LoadRepo command-line utility, they are automatically converted to FITS format and processed through the normal AstroFiler workflow.

### Key Features

- **Automatic Detection**: XISF files (.xisf, .XISF) are automatically detected during file import
- **Seamless Conversion**: XISF files are converted to FITS format transparently
- **File Preservation**: Original XISF files are preserved in their original location
- **Incoming Folder Placement**: Converted FITS files are placed in the incoming folder for processing
- **Complete Integration**: Converted files flow through the normal AstroFiler processing pipeline

## File Processing Workflow

1. **File Discovery**: During file import, AstroFiler scans for supported file extensions including .xisf
2. **XISF Detection**: When a XISF file is found, the converter is automatically invoked
3. **Conversion**: The XISF file is converted to FITS format with full metadata preservation
4. **File Placement**: The resulting FITS file is placed in the AstroFiler incoming folder
5. **Normal Processing**: The FITS file is processed through the standard AstroFiler workflow
6. **Original Preservation**: The original XISF file remains in its original location

## XISF Format Support

### Complete XISF Implementation
- **Binary header parsing**: Proper reading of 8-byte signature, 4-byte XML length, and 4-byte reserved fields
- **XML metadata extraction**: Full parsing of Image elements and FITS keywords
- **Attachment locations**: Support for embedded binary data with offset and length specifications
- **Multi-dimensional images**: Support for images with arbitrary dimensions beyond simple width/height

### Data Types
All XISF sample formats are supported with automatic conversion to FITS-compatible types:

| XISF Format | Size | FITS BITPIX | Conversion Notes |
|-------------|------|-------------|------------------|
| UInt8 | 1 byte | 8 | Direct conversion |
| UInt16 | 2 bytes | 16 | Direct conversion |
| UInt32 | 4 bytes | 32 or -32 | Converted to int32 if possible, otherwise float32 |
| UInt64 | 8 bytes | -64 | Converted to float64 for range preservation |
| Int16 | 2 bytes | 16 | Direct conversion |
| Int32 | 4 bytes | 32 | Direct conversion |
| Float32 | 4 bytes | -32 | IEEE 754 single precision |
| Float64 | 8 bytes | -64 | IEEE 754 double precision |
| Complex32 | 8 bytes | -32 | Converted to magnitude (float32) |
| Complex64 | 16 bytes | -64 | Converted to magnitude (float64) |

### Compression Support
- **zlib**: Standard zlib compression
- **zlib+sh**: zlib with byte shuffling for improved compression
- **lz4**: LZ4 fast compression
- **lz4+sh**: LZ4 with byte shuffling
- **gzip**: Standard gzip compression

### Advanced Features
- **Data validation**: Comprehensive validation of pixel counts, data ranges, and format consistency
- **Statistics logging**: Detailed data statistics including min/max/mean values and saturation detection
- **Metadata preservation**: Complete preservation of XISF metadata as FITS keywords
- **Multi-channel images**: Proper handling of RGB and other multi-channel image formats
- **Byte shuffling**: Implementation of XISF byte shuffling/unshuffling for compressed data

## FITS Output Format

### Standard FITS Keywords
The converter creates proper FITS files with all required keywords:
- `SIMPLE`: Always True
- `BITPIX`: Converted from XISF sample format
- `NAXIS`: Number of dimensions
- `NAXIS1`, `NAXIS2`, etc.: Image dimensions
- `BZERO`, `BSCALE`: Data scaling (set to 0 and 1)

### XISF-Specific Keywords
Additional keywords preserve XISF-specific information:
- `ORIGIN`: Identifies AstroFiler XISF converter
- `XISFFILE`: Original XISF filename
- `XISFSAMP`: Original sample format
- `XISFGEOM`: Original geometry string
- `XISFCMPR`: Compression codec used
- `XISFCLRS`: Color space
- `XISFDIMS`: Number of dimensions
- `XISFDIM1`, `XISFDIM2`, etc.: Individual dimension sizes

### Preserved Metadata
All original metadata is preserved including:
- FITS keywords from the XISF file
- Software information (name and version)
- Creation timestamp
- Observer and object information
- Custom properties and comments

## Using XISF Files in AstroFiler

### Through the User Interface

1. **Launch AstroFiler**: Start the GUI application
2. **Navigate to Images Tab**: Select the Images tab in the interface
3. **Click "Load New"**: Use the Load New button to import files
4. **Select XISF Files**: Choose .xisf files from your file browser
5. **Automatic Processing**: XISF files are automatically detected and converted

The UI will show progress messages indicating XISF conversion is taking place.

### Through LoadRepo Command

The LoadRepo command-line utility automatically handles XISF files:

```bash
# Load files from a directory containing XISF files
python commands/LoadRepo.py /path/to/images/

# The command will automatically:
# 1. Detect XISF files in the directory
# 2. Convert them to FITS format
# 3. Place FITS files in the incoming folder
# 4. Process them through the normal workflow
# 5. Leave original XISF files in place
```

### File Organization

After processing XISF files:

- **Original XISF files**: Remain in their original location unchanged
- **Converted FITS files**: Placed in the AstroFiler incoming folder
- **Processed data**: Moves through normal AstroFiler repository structure
- **Database entries**: Created for the FITS files in the AstroFiler database

## Configuration

### Requirements

The XISF converter requires the following Python packages:
- `numpy`: For array operations
- `astropy`: For FITS file creation
- `lz4`: For LZ4 compression support

These dependencies are included in the AstroFiler environment.

### Logging

XISF conversion activities are logged with detailed information:
- Conversion start and completion
- File placement locations
- Data statistics (min/max/mean values)
- Error conditions and warnings

Check the AstroFiler log files for detailed conversion information.

## Error Handling

The XISF converter provides comprehensive error handling:

### File Format Issues
- **Invalid XISF format**: Non-XISF files are skipped with appropriate warnings
- **Corrupted headers**: Malformed XISF files are detected and reported
- **Missing data**: Files with incomplete or missing image data are handled gracefully

### Conversion Issues
- **Unsupported compression**: Rare or unsupported compression formats are reported
- **Memory constraints**: Large files that exceed available memory are handled
- **Data validation**: Inconsistent data sizes or formats are detected

### Integration Issues
- **Folder permissions**: Issues writing to the incoming folder are reported
- **Disk space**: Insufficient disk space for converted files is detected
- **Database errors**: Problems registering converted files are logged

## Performance Considerations

### Memory Usage
- The converter loads entire images into memory for processing
- Large XISF files may require significant RAM
- Consider available memory when processing multiple large files

### Processing Speed
- LZ4 compression typically processes faster than zlib
- Byte shuffling adds processing overhead but improves compression ratios
- Very large files may take several minutes to convert

### Storage Requirements
- Converted FITS files are typically similar in size to the original XISF files
- Uncompressed FITS files may be larger than compressed XISF files
- Plan adequate storage in the incoming folder for converted files

## Troubleshooting

### Common Issues

**XISF files not being detected:**
- Verify file extensions are .xisf or .XISF
- Check that files are valid XISF format
- Review AstroFiler logs for error messages

**Conversion failures:**
- Check available memory for large files
- Verify the xisfFile package is properly installed
- Review compression codec support

**File placement issues:**
- Confirm incoming folder exists and is writable
- Check disk space in the incoming folder
- Verify AstroFiler configuration settings

### Log Messages

Key log messages to watch for:
- `Converting XISF file: <path>` - Conversion starting
- `Output FITS file will be placed in: <path>` - File placement
- `Successfully converted XISF to FITS: <path>` - Successful conversion
- `Original XISF file remains at: <path>` - Original file preservation

## Technical Implementation

### File Structure Handling
The converter properly handles the complete XISF file structure:
1. **8-byte signature**: "XISF0100" identification
2. **4-byte XML length**: Size of XML header in little-endian format
3. **4-byte reserved**: Reserved field for future use
4. **XML header**: Complete metadata in XML format
5. **Binary data**: Image data (may be compressed and/or shuffled)

### Data Conversion Process
1. **Header parsing**: Extract XML metadata and convert to FITS keywords
2. **Data location**: Determine binary data location (embedded or referenced)
3. **Decompression**: Handle compressed data with appropriate codecs
4. **Byte shuffling**: Reverse XISF byte shuffling if present
5. **Type conversion**: Convert to FITS-compatible data types
6. **FITS creation**: Create properly formatted FITS file

### Integration Points
The XISF converter integrates with AstroFiler at several points:
- **File extension detection**: In the `registerFitsImages` method
- **Conversion invocation**: Through the `convertXisfToFits` method
- **Normal processing**: Converted files flow through standard FITS processing
- **Database registration**: Converted files are registered like any FITS file

## Future Enhancements

Potential future improvements to XISF processing:
- **Streaming conversion**: For very large files that exceed available memory
- **Batch processing**: Optimized processing of multiple XISF files
- **Compression preservation**: Optional preservation of XISF compression in FITS files
- **Multi-HDU support**: Support for XISF files with multiple images

## References

- [XISF 1.0 Specification](https://pixinsight.com/doc/docs/XISF-1.0-spec/XISF-1.0-spec.html)
- [Reference Rust Implementation](https://github.com/vrruiz/xisfits)
- [FITS Standard](https://fits.gsfc.nasa.gov/fits_standard.html)
- [AstroFiler Documentation](../README.md)