## Database Schema

### Core Tables

```sql
-- FITS File Catalog
fitsFile:
- fitsFileId (Primary Key)
- fitsFileName (Text)
- fitsFileObject (Text) 
- fitsFileFilter (Text)
- fitsFileExpTime (Text)
- fitsFileDate (Date)
- fitsFileType (Text)
- fitsFileHash (Text) -- SHA-256 hash for duplicate detection
- fitsFileTelescop (Text)
- fitsFileInstrument (Text)
- fitsFileCCDTemp (Text)
- fitsFileXBinning (Text)
- fitsFileYBinning (Text)
- fitsFileGain (Text)
- fitsFileOffset (Text)
- fitsFileSession (Text) -- Foreign key to fitsSession

-- Session Management (Enhanced)
fitsSession:
- fitsSessionId (Primary Key)
- fitsSessionObjectName (Text)
- fitsSessionDate (Date)
- fitsSessionTelescope (Text)
- fitsSessionImager (Text)
- fitsSessionExposure (Text) -- Exposure time for session-level matching
- fitsSessionBinningX (Text) -- X binning for session-level matching
- fitsSessionBinningY (Text) -- Y binning for session-level matching
- fitsSessionCCDTemp (Text) -- CCD temperature for session-level matching
- fitsSessionGain (Text) -- Gain setting for session-level matching
- fitsSessionOffset (Text) -- Offset setting for session-level matching
- fitsSessionFilter (Text) -- Filter for session-level matching
- fitsBiasSession (Text) -- Biases matched to this light session
- fitsDarkSession (Text) -- Darks matched to this light session
- fitsFlatSession (Text) -- Flats matched to this light session
```

### Calibration Matching Logic

The enhanced session schema enables sophisticated calibration matching:

#### Bias Frame Matching
- Telescope and Imager
- Binning settings (X and Y)
- Gain and Offset settings
- Observation date (same day or earlier)

#### Dark Frame Matching
- All bias criteria plus:
- Exposure time (exact match)
- CCD Temperature (within ±5°C tolerance)

#### Flat Frame Matching
- All bias criteria plus:
- Filter (exact match for color-specific calibration)