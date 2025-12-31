# Enhanced Quality Analysis Integration

## Overview

The enhanced quality analysis has been integrated into the AstroFiler AutoCalibration workflow, replacing the basic placeholder implementation with a sophisticated SEP-based star detection and measurement system.

## What's New

### 🌟 **SEP-Based Star Detection**
- Uses Source Extractor Python (SEP) for robust star detection
- Automatic background subtraction and source extraction
- Handles edge cases with proper parameter validation
- Falls back to photutils DAOStarFinder if SEP unavailable

### 📊 **Enhanced Measurements**
- **FWHM (arcseconds)**: Full Width Half Maximum for seeing quality assessment
- **HFR (arcseconds)**: Half Flux Radius for alternative star quality metric  
- **Eccentricity**: Star shape analysis (0=circular, 1=highly elongated)
- **Star Count**: Number of detected sources
- **Image SNR**: Signal-to-noise ratio
- **Image Scale**: Arcsec/pixel calculated from FITS headers or telescope data

### 🗄️ **Database Integration**
Quality metrics are automatically stored in the database:
- `fitsFileAvgFWHMArcsec`: Average FWHM in arcseconds
- `fitsFileAvgEccentricity`: Average star eccentricity (0-1)  
- `fitsFileAvgHFRArcsec`: Average HFR in arcseconds
- `fitsFileImageSNR`: Image signal-to-noise ratio
- `fitsFileStarCount`: Number of detected stars
- `fitsFileImageScale`: Image scale in arcsec/pixel

## How to Use

### 1. **AutoCalibration Workflow**
The quality analysis is now part of the standard AutoCalibration workflow:

```bash
# Run complete workflow including quality analysis
python AutoCalibration.py

# Run only quality analysis
python AutoCalibration.py -o quality

# Run with verbose output
python AutoCalibration.py -o quality -v
```

### 2. **GUI Integration**
In the AstroFiler GUI:
1. Go to **Tools** → **Auto Calibration**
2. Check the **Quality Assessment** checkbox
3. Click **Run Workflow**

### 3. **Programmatic Usage**
```python
from astrofiler.core.enhanced_quality import EnhancedQualityAnalyzer
from astrofiler.core.auto_calibration import perform_quality_assessment

# Direct analyzer usage
analyzer = EnhancedQualityAnalyzer()
results = analyzer.analyze_and_update_file(fits_path, fits_file_id)

# Through AutoCalibration workflow
success = perform_quality_assessment(config, session_id=None)
```

### 4. **Testing**
Use the provided test script:

```bash
python test_enhanced_quality.py
```

## Migration

### Database Schema
A new migration has been created (`010_add_quality_metrics_fields.py`) that adds the quality fields to existing databases. Run migrations to add these fields:

```bash
python -m peewee_migrate migrate --database astrofiler.db migrations/
```

### SEP Dependency
Install the SEP package for optimal performance:

```bash
pip install sep
```

If SEP is not available, the system will fall back to photutils DAOStarFinder.

## Implementation Details

### Quality Analysis Process
1. **Load FITS file** and validate data
2. **Calculate image scale** from FITS headers or telescope database
3. **Detect stars** using SEP or photutils
4. **Measure properties**:
   - FWHM from elliptical Gaussian fitting
   - HFR from flux distribution analysis  
   - Eccentricity from image moments
   - Kron aperture photometry for accurate flux
5. **Update database** with calculated metrics

### Error Handling
- Robust parameter validation prevents crashes
- Graceful degradation when calculations fail
- Detailed logging for troubleshooting
- Progress callbacks for user feedback

### Performance Optimizations
- C-contiguous data handling for SEP
- Limited to 200 brightest stars for performance
- Efficient background estimation
- Vectorized calculations where possible

## Jupyter Notebook Integration

The development work was done in the `simple_image_viewer_sep.ipynb` notebook, which serves as:
- **Testing ground** for quality analysis methods
- **Visualization tool** for seeing detection results
- **Development environment** for parameter tuning
- **Reference implementation** for the core methods

The notebook demonstrates the same quality analysis that's now integrated into the AutoCalibration workflow.

## Future Enhancements

### Potential Improvements
- **Quality reports**: HTML/PDF reports with visualizations
- **Trending analysis**: Quality metrics over time
- **Alert system**: Notifications for poor quality sessions
- **Batch processing**: Parallel analysis of multiple files
- **Advanced metrics**: Sky background, gradient analysis, astrometric accuracy

### Integration Opportunities
- **Session quality scoring**: Overall session assessment
- **Automatic frame rejection**: Skip poor quality frames
- **Adaptive calibration**: Quality-based master selection  
- **Cloud integration**: Quality metrics in cloud storage metadata

## Troubleshooting

### Common Issues

**SEP not available**: 
```
pip install sep
```

**No stars detected**:
- Check image data quality
- Verify FITS file format
- Adjust detection threshold in enhanced_quality.py

**Database errors**:
- Ensure migrations have been run
- Check database permissions
- Verify file paths are accessible

**Performance issues**:
- Limit file count for batch processing
- Check available memory for large images
- Consider parallel processing for multiple files

For detailed debugging, enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```