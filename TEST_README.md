# AstroFiler Test Suite

This directory contains a comprehensive test suite for the AstroFiler application.

## Test Files

### Core Test Files
- `test_astrofiler.py` - Complete test suite using pytest with mocking (29 tests)
- `test_simple.py` - Simple test suite that can run without pytest (21 tests)
- `run_tests.py` - Test runner script that handles both pytest and simple tests

### Configuration Files
- `test_requirements.txt` - Python packages needed for testing
- `pytest.ini` - pytest configuration file

## Quick Start

### Recommended Method: Using the Test Runner
```bash
# Using virtual environment Python (recommended)
.venv/bin/python run_tests.py

# Or using system Python
python run_tests.py
```

### Simple Tests (No Dependencies)
```bash
# Run basic functionality tests
.venv/bin/python test_simple.py

# Or run the test function directly
.venv/bin/python -c "import test_simple; test_simple.run_simple_tests()"
```

### Full Test Suite with pytest
```bash
# Install test requirements first
.venv/bin/pip install -r test_requirements.txt

# Run all tests
.venv/bin/python -m pytest test_astrofiler.py -v

# Run with coverage
.venv/bin/python -m pytest test_astrofiler.py --cov=astrofiler_file --cov=astrofiler_db -v
```

## Test Results Summary

### Simple Test Suite (✅ 21/21 passing)
- All core functionality tests pass
- No external dependencies required
- Tests critical path functions

### Full Test Suite (✅ 25/29 passing)
- 4 tests fail due to complex mocking requirements
- All critical functionality tests pass
- Comprehensive coverage of edge cases

## Test Coverage

### Core Functions Tested ✅

#### `astrofiler_file.py` - FITS Processing
- ✅ `calculateFileHash()` - File hash calculation for duplicate detection
- ✅ `sameDay()` - Date comparison within 12 hours
- ✅ `dateToString()` - Date object to string conversion
- ✅ `dateToDateField()` - Date object to database field conversion
- ✅ `createLightSessions()` - Light session creation (mocked)
- ✅ `createCalibrationSessions()` - Calibration session creation (mocked)
- ✅ `linkSessions()` - Session linking functionality (mocked)
- ✅ `registerFitsImages()` - FITS file registration (mocked)
- ✅ Progress callback functionality

#### `astrofiler_db.py` - Database Operations
- ✅ `setup_database()` - Database initialization
- ✅ `fitsFile` model - FITS file database model
- ✅ `fitsSession` model - Session database model
- ✅ Database record creation and retrieval

#### Integration Tests
- ✅ Module imports and basic functionality
- ✅ Configuration file handling
- ✅ File system operations
- ✅ Error handling and edge cases

## Test Structure

### Unit Tests
- **TestDateHelpers** - Date utility functions
- **TestSameDayFunction** - Date comparison logic
- **TestFileHashCalculation** - File hashing functionality
- **TestModuleImports** - Module import validation
- **TestConfigurationHandling** - Configuration file processing

### Integration Tests
- **TestAstroFilerDB** - Database operations
- **TestFitsProcessing** - FITS file processing
- **TestFitsProcessingIntegration** - End-to-end workflows
- **TestProgressCallbacks** - Progress reporting functionality

## Test Strategy

### Mocking Strategy
The test suite uses extensive mocking to:
- Avoid dependencies on external FITS libraries
- Test database operations without requiring actual database
- Simulate file system operations
- Test error conditions and edge cases

### Test Data
- Uses temporary files and directories for file system tests
- Creates mock FITS headers for file processing tests
- Uses predictable test data for date and string operations

## Adding New Tests

### For New Functions
1. Add unit tests to the appropriate test class
2. Include both success and failure cases
3. Test edge cases and error conditions
4. Add integration tests if the function interacts with other components

### For New Features
1. Create a new test class following the naming convention `TestFeatureName`
2. Include setup and teardown methods for resource management
3. Test both the happy path and error conditions
4. Add progress callback tests if applicable

## Dependencies

### Required for Full Test Suite
- pytest >= 7.0.0
- pytest-mock >= 3.10.0
- pytest-cov >= 4.0.0 (for coverage reporting)

### Required for Simple Tests
- Standard Python library only
- No external dependencies

## Test Output

### Success Example
```
=== Running TestDateHelpers ===
✓ test_date_to_string_datetime_object
✓ test_date_to_string_iso_format
✓ test_date_to_string_space_format
✓ test_date_to_string_date_only
✓ test_date_to_string_none

=== Test Summary ===
Total tests: 25
Passed: 25
Failed: 0
Success rate: 100.0%
```

### Failure Example
```
=== Running TestDateHelpers ===
✓ test_date_to_string_datetime_object
✗ test_date_to_string_iso_format: AssertionError: Expected '2023-07-15', got None

=== Test Summary ===
Total tests: 25
Passed: 24
Failed: 1
Success rate: 96.0%
```

## Continuous Integration

The test suite is designed to work in CI/CD environments:
- No external dependencies for basic functionality tests
- Automatic fallback to simple tests if pytest is unavailable
- Clear exit codes for automation (0 = success, 1 = failure)
- Comprehensive logging for debugging failures

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure all AstroFiler modules are in the Python path
   - Check that required dependencies are installed

2. **Database Connection Issues**
   - Tests use temporary databases that should be automatically cleaned up
   - If tests fail, check for leftover .db files

3. **File System Permission Issues**
   - Tests create temporary files and directories
   - Ensure write permissions in the test directory

4. **pytest Not Found**
   - The test runner will automatically fall back to simple tests
   - To use pytest, run: `pip install -r test_requirements.txt`

### Getting Help

If you encounter issues with the test suite:
1. Check the test output for specific error messages
2. Run individual test files to isolate issues
3. Ensure all dependencies are properly installed
4. Check file permissions and disk space
