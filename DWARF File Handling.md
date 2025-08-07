# DWARF Telescope FITS File Handling

AstroFiler includes specialized support for DWARF telescope FITS files, which often have incomplete or non-standard headers. This document explains how the automatic header correction works and what folder structure is required. It is assumed that all Dwarf products have the same file structure - file a support ticket if this changes.

## Overview

DWARF telescopes (identified by `TELESCOP = "DWARF"` in the FITS header) require special processing because their FITS files often have:
- Missing or incomplete header fields (DATE-OBS, EXPTIME, XBINNING, YBINNING, CCD-TEMP)
- Non-standard naming conventions
- Data embedded in folder names rather than headers

The `dwarfFixHeader()` function automatically detects and corrects these issues during file processing.

## ⚠️ **CRITICAL REQUIREMENT: Folder Structure**

**WARNING:** For DWARF files to be processed successfully, you **MUST** provide a complete DWARF folder structure in your incoming directory. The system will **REJECT** any DWARF files that don't follow this exact structure.

### Required Folder Structure

Your incoming directory must contain these specific folders:

```
/your-incoming-directory/
├── CALI_FRAME/
│   ├── bias/
│   │   ├── cam_0/          # WIDE instrument bias files
│   │   └── cam_1/          # TELE instrument bias files
│   ├── dark/
│   │   ├── cam_0/          # WIDE instrument dark files
│   │   └── cam_1/          # TELE instrument dark files
│   └── flat/
│       ├── cam_0/          # WIDE instrument flat files
│       └── cam_1/          # TELE instrument flat files
├── DWARF_DARK/             # TELE dark library files
└── DWARF_RAW_[DATA]/       # Light frame folders (one or more)
etc.
```

**If any of these required folders are missing, the DWARF file processing will fail with:**
> `"Dwarf folder structure not recognized"`

## Light Files (DWARF_RAW folders)

Light frames are stored in folders with names that encode all the metadata:

### Folder Naming Convention
```
DWARF_RAW_(INSTRUMEN)_(OBJECT)_EXP_(EXPTIME)_GAIN_(GAIN)_(DATE-OBS)
```

### Example
```
DWARF_RAW_WIDE_M31_EXP_300_GAIN_100_2023-07-15T03:26:15
```

### What Gets Extracted
- **INSTRUMEN**: `WIDE` → Sets `INSTRUME` header
- **OBJECT**: `M31` → Sets `OBJECT` header
- **EXPTIME**: `300` → Sets `EXPTIME` header (seconds)
- **GAIN**: `100` → Sets `GAIN` header
- **DATE-OBS**: `2023-07-15T03:26:15` → Sets `DATE-OBS` header

### Added Defaults
- `IMAGETYP` = `'LIGHT'`
- `XBINNING` = `1` (if missing)
- `YBINNING` = `1` (if missing)
- `CCD-TEMP` = `-10.0` (if missing)

## Master Calibration Files (CALI_FRAME)

Master calibration frames are organized by type and camera:

### Folder Structure
```
CALI_FRAME/
├── bias/cam_0/    # WIDE camera bias masters
├── bias/cam_1/    # TELE camera bias masters
├── dark/cam_0/    # WIDE camera dark masters
├── dark/cam_1/    # TELE camera dark masters
├── flat/cam_0/    # WIDE camera flat masters
└── flat/cam_1/    # TELE camera flat masters
```

### Camera Mapping
- **cam_0** → `INSTRUME = 'WIDE'`
- **cam_1** → `INSTRUME = 'TELE'`

### File Naming Conventions

#### Bias Masters
```
bias_gain_(GAIN)_bin_(BINNING)_*.fits
```
Example: `bias_gain_100_bin_1_master.fits`

#### Flat Masters
```
flat_gain_(GAIN)_bin_(BINNING)_*.fits
```
Example: `flat_gain_100_bin_1_L_master.fits`

#### Dark Masters
```
dark_exp_(EXPTIME)_gain_(GAIN)_bin_(BINNING)_(CCD-TEMP)_*.fits
```
Example: `dark_exp_300_gain_100_bin_1_-10_master.fits`

### What Gets Set
- `IMAGETYP` = `'BIAS'`, `'FLAT'`, or `'DARK'`
- `OBJECT` = `'MASTERBIAS'`, `'MASTERFLAT'`, or `'MASTERDARK'`
- `INSTRUME` = `'WIDE'` or `'TELE'` (based on cam_0/cam_1)
- `GAIN`, `XBINNING`, `YBINNING` extracted from filename
- `EXPTIME`, `CCD-TEMP` extracted from filename (darks only)
- `DATE-OBS` added if missing (current timestamp)

## Dark Library Files (DWARF_DARK)

TELE instrument dark library files with specific naming:

### File Naming Convention
```
tele_exp_(EXPTIME)_gain_(GAIN)_bin_(BINNING)_(OBS-DATE).fits
```

### Example
```
tele_exp_300_gain_100_bin_1_2023-07-15.fits
```

### What Gets Set
- `INSTRUME` = `'TELE'`
- `IMAGETYP` = `'DARKMASTER'`
- `OBJECT` = `'DARKMASTER'`
- `EXPTIME`, `GAIN`, `XBINNING`, `YBINNING` extracted from filename
- `DATE-OBS` from filename or current timestamp

## Configuration

It is desireable for headers to be set properly to facilitate use of other processing software. The header correction behavior is controlled by the configuration setting:

```ini
[DEFAULT]
save_modified_headers = True/False
```

When `save_modified_headers = True`:
- Modified headers are automatically saved back to the FITS files
- Original files are updated with corrected metadata

When `save_modified_headers = False`:
- Headers are corrected in memory for database storage
- Original files remain unchanged

## Failed Images

Files with the prefix `failed_` are automatically ignored and not processed.

## Error Handling

Common error scenarios:

### Missing Required Folders
```
ERROR: Dwarf folder structure not recognized for file: example.fits
```
**Solution:** Ensure all required folders (CALI_FRAME, DWARF_DARK, DWARF_RAW_*) exist

### Invalid Folder Names
```
WARNING: Error parsing DWARF_RAW folder name
```
**Solution:** Verify folder names follow the exact naming convention

### Missing Header Fields
```
WARNING: Error fixing DWARF header
```
**Solution:** Check that all required data is present in folder/file names

## Integration with AstroFiler

The DWARF header correction is automatically applied during:
- **Load Repo** operations (when moving files from incoming to repository)
- **Sync Repo** operations (when updating database from existing repository)

No manual intervention is required - the system automatically detects DWARF telescopes and applies the appropriate corrections.

## Logging

All DWARF file processing is logged with detailed information:
- Header corrections applied
- Files processed successfully
- Errors encountered
- Configuration settings used

Check the `astrofiler.log` file for detailed processing information.

## Best Practices

1. **Verify Folder Structure:** Always ensure the complete DWARF folder structure exists before processing
2. **Test with Small Batches:** Process a few files first to verify the structure is correct
3. **Check Logs:** Monitor the log file for any processing errors or warnings
4. **Backup Originals:** If using `save_modified_headers = True`, keep backups of original files
5. **Consistent Naming:** Ensure all folder and file names follow the exact conventions documented here

---

*This feature was added to handle the unique requirements of DWARF telescope data formats. For questions or issues, refer to the AstroFiler documentation or check the log files for detailed error information.*
