# Light Frame Calibration Implementation Checklist

## ✅ **Already Completed Components**

### Core Infrastructure
- [x] **Light calibration functions in `astrofiler_smart.py`**
  - `calibrate_light_frame()` - Single frame processing with bias/dark/flat corrections
  - `calibrate_session_lights()` - Batch session processing with progress tracking
  - `get_session_master_frames()` - Master frame discovery and validation
  - `_update_calibrated_frame_header()` - Comprehensive FITS header updates

- [x] **CLI Implementation in `commands/AutoCalibration.py`**
  - `calibrate_light_frames()` function with session filtering and dry-run support
  - Integration with complete workflow (`-o calibrate` and `-o all` options)
  - Progress tracking and detailed result reporting

- [x] **GUI Integration in `ui/sessions_widget.py`**
  - `calibrate_light_sessions()` method with progress dialog
  - Context menu integration for selected sessions
  - User confirmation and cancellation support

- [x] **Database Integration**
  - Master frame reference fields in sessions table
  - Calibration status tracking in files table
  - Automatic database updates after calibration

- [x] **FITS Header Standards**
  - Industry-standard calibration headers (CALIBRAT, CALDATE, CALSOFT)
  - Master frame references with checksums (BIASMAST, DARKMAST, FLATMAST)
  - Processing history and quality metrics
  - Astronomy software compatibility

---

## 🔄 **Implementation Tasks**

### 1. **Master Frame Association System**
- [ ] **Review and enhance `findMatchingMasterFrame()` in `astrofiler_file.py`**
  - Verify telescope/instrument matching logic
  - Ensure proper binning, gain, offset matching
  - Add temperature tolerance for dark frames (±5°C)
  - Implement filter matching for flat frames
  - Add date-based master frame selection (closest but not future)

- [ ] **Create master frame validation system**
  - Check master frame file existence before calibration
  - Verify master frame integrity (file size, header validity)
  - Implement fallback logic for missing masters
  - Add master frame compatibility warnings

### 2. **Batch Processing Enhancement**
- [ ] **Implement session-level calibration workflow**
  - Detect uncalibrated light sessions automatically
  - Priority queue based on session date/importance
  - Skip sessions without suitable master frames
  - Handle mixed session types (some calibrated, some not)

- [ ] **Add progress tracking improvements**
  - Multi-level progress (session → file → processing step)
  - Estimated time remaining calculations
  - Detailed progress logging with timestamps
  - Cancellation handling at multiple levels

### 3. **Configuration Integration**
- [ ] **Add light calibration settings to `astrofiler.ini`**
  ```ini
  [AUTO_CALIBRATION]
  enable_light_calibration = True
  calibration_output_suffix = _calibrated
  preserve_original_files = True
  auto_calibrate_on_master_creation = False
  calibration_quality_check = True
  max_temperature_difference = 5.0
  ```

- [ ] **Create GUI configuration interface**
  - Add light calibration section to Configuration dialog
  - Enable/disable toggle for automatic calibration
  - Output naming convention settings
  - Quality check and validation options

### 4. **Quality Assurance System**
- [ ] **Pre-calibration validation**
  - Verify light frame headers and data integrity
  - Check exposure time compatibility with dark masters
  - Validate filter compatibility with flat masters
  - Ensure proper image dimensions match masters

- [ ] **Post-calibration quality checks**
  - Statistical analysis of calibrated frames (noise, dynamic range)
  - Negative pixel detection and reporting
  - Quality score calculation and thresholds
  - Automatic rejection of poor calibrations

### 5. **Integration with Existing Systems**
- [ ] **Auto-calibration workflow integration**
  - Trigger light calibration after master creation
  - Add to complete auto-calibration workflow in `runAutoCalibrationWorkflow()`
  - Integrate with existing progress tracking system
  - Update UI status indicators after calibration

- [ ] **Cloud sync integration**
  - Include calibrated frames in cloud backup operations
  - Mark original light frames for soft deletion after calibration
  - Ensure calibrated frames have cloud URLs updated
  - Handle calibrated frame download from cloud

### 6. **Database Enhancements**
- [ ] **Calibration tracking improvements**
  - Add calibration timestamp fields
  - Store calibration parameters (masters used, steps applied)
  - Track calibration quality scores
  - Link calibrated frames to their masters

- [ ] **Session-level calibration status**
  - Add session calibration completion percentage
  - Track which sessions have been fully calibrated
  - Store calibration statistics per session
  - Enable session-based calibration queries

### 7. **Error Handling and Recovery**
- [ ] **Robust error management**
  - Handle corrupted or missing master frames gracefully
  - Provide detailed error messages for calibration failures
  - Implement retry logic for temporary failures
  - Log all calibration attempts and outcomes

- [ ] **Recovery mechanisms**
  - Detect and resume interrupted calibration batches
  - Handle disk space issues during calibration
  - Provide manual intervention options for failed calibrations
  - Backup and restore functionality for critical failures

### 8. **Performance Optimization**
- [ ] **Memory management**
  - Implement efficient data loading for large files
  - Use memory mapping for very large FITS files
  - Add memory usage monitoring and limits
  - Optimize data type usage (float32 vs float64)

- [ ] **Parallel processing**
  - Enable multi-threading for independent calibrations
  - Implement queue-based processing system
  - Add CPU usage monitoring and throttling
  - Optimize I/O operations for batch processing

### 9. **User Interface Enhancements**
- [ ] **Calibration status visualization**
  - Add calibration status columns to sessions view
  - Show calibration progress indicators
  - Display master frame associations visually
  - Add calibration quality indicators

- [ ] **Interactive calibration management**
  - Calibration planning and preview functionality
  - Manual master frame selection interface
  - Calibration parameter adjustment UI
  - Results viewing and comparison tools

### 10. **Documentation and Testing**
- [ ] **User documentation**
  - Create light calibration user guide
  - Document calibration settings and options
  - Provide troubleshooting guide
  - Add FAQ for common calibration issues

- [ ] **Testing framework**
  - Create unit tests for calibration functions
  - Integration tests for complete workflows
  - Performance benchmarks for large datasets
  - Regression tests for edge cases

---

## 🚀 **Immediate Priority Tasks (Next Sprint)**

### **Phase 1: Core Functionality (Week 1)**
1. **Review and test existing calibration functions**
   - Verify `calibrate_light_frame()` works with current data
   - Test `calibrate_session_lights()` with real sessions
   - Validate master frame discovery logic

2. **Enhance master frame matching**
   - Improve `findMatchingMasterFrame()` algorithm
   - Add comprehensive validation checks
   - Implement proper error handling

3. **Add configuration settings**
   - Extend `astrofiler.ini` with calibration options
   - Create GUI configuration interface
   - Implement settings validation

### **Phase 2: Integration (Week 2)**
1. **Auto-calibration workflow integration**
   - Add light calibration to main workflow
   - Update progress tracking system
   - Test complete end-to-end process

2. **UI enhancements**
   - Add calibration status indicators
   - Improve progress reporting
   - Create calibration management interface

### **Phase 3: Quality and Performance (Week 3)**
1. **Quality assurance implementation**
   - Add pre/post calibration validation
   - Implement quality scoring system
   - Create error recovery mechanisms

2. **Performance optimization**
   - Memory usage optimization
   - Batch processing improvements
   - Progress tracking enhancements

---

## 📊 **Success Metrics**

- [ ] **Functionality**: Successfully calibrate light frames using available masters
- [ ] **Performance**: Process 100+ light frames in reasonable time (<30 min)
- [ ] **Quality**: Achieve >95% success rate for calibration operations  
- [ ] **Usability**: Complete calibration workflow accessible through GUI
- [ ] **Integration**: Seamless integration with existing auto-calibration system
- [ ] **Reliability**: Robust error handling with graceful failure recovery

---

## 🔧 **Technical Notes**

### **Current Implementation Status**
- Core calibration algorithms: ✅ Complete
- CLI interface: ✅ Complete  
- Basic GUI integration: ✅ Complete
- Master frame discovery: ⚠️ Needs enhancement
- Configuration system: ❌ Missing
- Quality assurance: ❌ Missing
- Performance optimization: ❌ Missing

### **Key Dependencies**
- Siril CLI path configuration
- Master frame availability 
- Database migration 008 (session calibration tracking)
- FITS file integrity and proper headers
- Sufficient disk space for calibrated outputs

### **Risk Factors**
- Large file processing memory requirements
- Master frame compatibility issues
- Long processing times for large datasets
- Disk space consumption from calibrated files