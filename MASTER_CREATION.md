# Master Calibration Frame Creation

AstroFiler can automatically create master calibration frames (bias, dark, and flat) using Siril CLI integration.

## Prerequisites

1. **Siril Installation**: Install Siril with command-line interface
   - Download from: https://siril.org/
   - Ensure `siril-cli` executable is available

2. **Configuration**: Set Siril CLI path in AstroFiler Config tab
   - Go to Config tab → External Tools
   - Set "Siril CLI Location" to the path of `siril-cli` executable
   - Example: `C:\Program Files\SiriL\bin\siril-cli.exe` (Windows)

## Usage

### Automatic Master Creation

1. **Navigate to Sessions Tab**: Click the Sessions tab in AstroFiler
2. **Click "Create Masters"**: Button located in the top toolbar
3. **Confirm Operation**: Review the confirmation dialog
4. **Monitor Progress**: Watch the progress bar as masters are created
5. **Review Results**: Check the summary of created master frames

### Master Frame Naming Convention

Master frames are automatically named using FITS header metadata:

- **Bias**: `Master-Bias-<TELESCOP>-<INSTRUME>-<XBINNING>x<YBINNING>-<Date>.fits`
- **Dark**: `Master-Dark-<TELESCOP>-<INSTRUME>-<XBINNING>x<YBINNING>-<EXPTIME>-<CCD-TEMP>-<Date>.fits`
- **Flat**: `Master-Flat-<TELESCOP>-<INSTRUME>-<FILTER>-<XBINNING>x<YBINNING>-<Date>.fits`

### Storage Location

- Master frames are stored in: `<Repository>/Masters/`
- Each master is registered in the AstroFiler database
- Session records are updated with master frame references

## Process Details

### What Happens During Master Creation

1. **Session Discovery**: Finds calibration sessions without existing masters
2. **File Validation**: Ensures sufficient files exist for each session (minimum 2)
3. **Siril Processing**: Uses Siril CLI to stack frames with appropriate rejection
4. **Header Updates**: Adds master frame metadata to FITS headers
5. **Database Registration**: Registers master frames in AstroFiler database
6. **Session Updates**: Links master frames to their source sessions

### Siril Stacking Parameters

- **Bias Frames**: 3-sigma rejection, no normalization
- **Dark Frames**: 3-sigma rejection, no normalization  
- **Flat Frames**: 3-sigma rejection, multiplicative normalization

### FITS Header Metadata

Master frames include enhanced metadata:
- `MASTER`: True (identifies as master frame)
- `CALTYPE`: Frame type (BIAS, DARK, FLAT)
- `NFRAMES`: Number of frames combined
- `CREATED`: Creation timestamp
- `CREATOR`: AstroFiler
- `SESSION`: Source session ID

## Troubleshooting

### Common Issues

**"Siril CLI path not configured"**
- Solution: Set correct Siril CLI path in Config tab

**"Not enough files for session"**
- Solution: Ensure calibration sessions have at least 2 files

**"Siril CLI failed"**
- Check Siril installation and executable permissions
- Verify file paths don't contain special characters
- Ensure sufficient disk space in repository

### Log Information

Master creation activities are logged to `astrofiler.log`:
- Session processing status
- File validation results
- Siril execution details
- Error messages and warnings

## Benefits

- **Consistent Quality**: Automated 3-sigma rejection for optimal results
- **Proper Metadata**: FITS headers include all necessary information
- **Database Integration**: Masters tracked in AstroFiler database
- **Organized Storage**: Systematic naming and folder structure
- **Session Linking**: Automatic association with source calibration sessions
- **Efficient Processing**: Uses symbolic links instead of copying files when possible, significantly reducing processing time and disk space requirements

## Performance Optimization

AstroFiler uses an intelligent file handling approach during master creation:

1. **Symbolic Links**: First attempts to create symbolic links to source files (fastest, no disk space used)
2. **Hard Links**: Falls back to hard links if symbolic links aren't supported (fast, minimal disk overhead)
3. **File Copying**: Only copies files as a last resort if both link methods fail

This approach dramatically reduces processing time for large FITS files and minimizes temporary disk space usage during master creation.

This feature streamlines the calibration workflow by automating master frame creation while maintaining professional standards for metadata and organization.
