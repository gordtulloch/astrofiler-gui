# AstroFiler Test Suite

This document describes the test suite for the AstroFiler application and provides instructions for running tests.

## Overview

The AstroFiler test suite consists of four main test categories:

1. **Basic Functionality Tests** (`test_basic.py`) - Database operations and core functionality
2. **File Processing Tests** (`test_file_processing.py`) - FITS file processing and registration
3. **GUI Component Tests** (`test_gui.py`) - User interface components and interactions
4. **Mapping Functionality Tests** (`test_mapping.py`) - Header mapping features and database operations

## Test Structure

```
test/
├── TESTING.md              # This documentation file
├── test_basic.py           # Database and core functionality tests
├── test_file_processing.py # FITS file processing tests
├── test_gui.py             # GUI component tests
└── test_mapping.py         # Header mapping functionality tests
```

## Running Tests

### Quick Start

To run all tests with the default configuration:

```bash
python run_tests.py
```

### Verbose Output

For detailed test output:

```bash
python run_tests.py -v
```

### Test Categories

#### Run Only Database Tests
```bash
python run_tests.py -k "test_basic"
```

#### Run Only File Processing Tests
```bash
python run_tests.py -k "test_file_processing"
```

#### Run Only GUI Tests
```bash
python run_tests.py -k "test_gui"
```

#### Skip GUI Tests (for headless environments)
```bash
python run_tests.py --no-gui
```

#### Run Only GUI Tests
```bash
python run_tests.py --gui-only
```

### Advanced Options

#### Coverage Report
```bash
python run_tests.py --coverage
```

#### Stop on First Failure
```bash
python run_tests.py -x
```

#### Run Specific Test
```bash
python run_tests.py -k "test_session_creation"
```

#### Install Xvfb for Better GUI Testing (Linux)
```bash
python run_tests.py --install-xvfb
```

#### Export Results
```bash
# Save results to file
python run_tests.py --output results.txt

# Export JUnit XML format
python run_tests.py --junit-xml results.xml
```

## Test Categories in Detail

### 1. Basic Functionality Tests (`test_basic.py`)

Tests core database operations and basic functionality:

- **`test_database_creation`** - Verifies database initialization
- **`test_session_creation`** - Tests creating and retrieving sessions
- **`test_file_creation_and_linking`** - Tests creating files and linking to sessions

**Dependencies**: Peewee ORM, SQLite database

**Features**:
- Uses temporary databases for isolation
- Proper setup/teardown for each test
- Tests both creation and retrieval operations

### 2. File Processing Tests (`test_file_processing.py`)

Tests FITS file processing and registration:

- **`test_register_fits_image`** - Tests single FITS file registration
- **`test_register_fits_images`** - Tests batch FITS file processing

**Dependencies**: 
- Mocked FITS file operations
- Mocked file system operations
- Database models

**Features**:
- Comprehensive mocking of external dependencies
- Tests both single file and batch processing
- Validates proper parameter passing

### 3. GUI Component Tests (`test_gui.py`)

Tests user interface components:

- **`test_session_tab_creation`** - Tests Sessions tab creation
- **`test_images_tab_creation`** - Tests Images tab creation  
- **`test_context_menu_creation`** - Tests context menu functionality
- **`test_checkout_session`** - Tests session checkout functionality

**Dependencies**:
- PySide6 Qt framework
- Qt offscreen platform for headless testing
- Comprehensive mocking of database operations

**Features**:
- Automatic headless environment detection
- Proper Qt application lifecycle management
- Resource cleanup to prevent memory leaks
- Timeout protection to prevent hanging tests

### 4. Mapping Functionality Tests (`test_mapping.py`)

Tests the header mapping functionality:

- **`test_mapping_model_creation`** - Tests creating new mapping records
- **`test_mapping_model_retrieval`** - Tests retrieving mapping records from database
- **`test_mapping_model_update`** - Tests updating existing mapping records
- **`test_mapping_model_deletion`** - Tests deleting mapping records
- **`test_mapping_null_values`** - Tests handling of null/empty values in mappings
- **`test_mapping_query_by_card`** - Tests querying mappings by header card type
- **`test_mapping_bulk_operations`** - Tests bulk operations on mapping records
- **`test_mapping_with_fits_files`** - Tests mapping application to FITS file records
- **`test_mappings_dialog_import`** - Tests importing the MappingsDialog class
- **`test_qt_dependencies_available`** - Tests availability of required Qt components
- **`test_mappings_dialog_creation`** - Tests creating MappingsDialog instances

**Dependencies**:
- Peewee ORM for database operations
- PySide6 Qt framework for dialog testing
- Temporary database isolation for each test

**Features**:
- Complete database isolation using temporary SQLite databases
- Comprehensive CRUD operations testing
- Integration testing with FITS file records
- GUI component import and creation testing
- Automatic CI environment detection for GUI tests

## Environment Setup

### Requirements

The test suite automatically installs required packages:
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `pytest-timeout` - Timeout management

### GUI Testing Environment

#### Automatic Configuration
The test suite automatically configures itself for different environments:

- **With Display**: Uses normal Qt platform
- **Headless**: Uses Qt offscreen platform
- **With Xvfb**: Uses virtual display for better compatibility

#### Manual Configuration

For headless environments, you can manually set:
```bash
export QT_QPA_PLATFORM=offscreen
export QT_LOGGING_RULES=qt.qpa.plugin=false
```

#### Installing Xvfb (Linux)
For better GUI testing compatibility:
```bash
sudo apt-get install xvfb
# OR
python run_tests.py --install-xvfb
```

## Test Configuration

### Timeouts

Tests have built-in timeout protection:
- **Global timeout**: 10 seconds (configurable)
- **Individual test timeouts**: 3-10 seconds per test
- **GUI tests**: Shorter timeouts to prevent hanging

### Database Isolation

Each test uses a temporary database:
- Created fresh for each test class
- Automatically cleaned up after tests
- No shared state between tests

### Mocking Strategy

Tests use comprehensive mocking:
- **Database operations**: Mocked to prevent external dependencies
- **File system operations**: Mocked for consistency
- **GUI data loading**: Mocked to prevent database calls during widget creation
- **External dialogs**: Mocked to prevent user interaction requirements

## Troubleshooting

### Common Issues

#### GUI Tests Skipped
```
Reason: GUI environment not available
```
**Solution**: Install Xvfb or run with `--no-gui`

#### Tests Hanging
**Solution**: Tests have automatic timeout protection. If hanging persists:
1. Check for infinite loops in application code
2. Verify all external calls are properly mocked
3. Use shorter timeout with `--timeout=5`

#### Import Errors
**Solution**: Ensure you're running from the project root directory and the virtual environment is activated

#### Database Errors
**Solution**: Tests use temporary databases. If errors persist:
1. Check database schema matches model definitions
2. Verify all database operations are properly mocked in tests

### Debug Mode

For debugging failing tests:
```bash
# Run with maximum verbosity
python run_tests.py -v -s

# Run single test with debugging
python run_tests.py -k "test_name" -v -s --tb=long
```

### Performance

Normal test execution should complete in under 1 second:
- **Database tests**: ~0.1-0.2 seconds
- **File processing tests**: ~0.1-0.2 seconds  
- **GUI tests**: ~0.2-0.4 seconds

If tests are significantly slower, check for:
- Unmocked database operations
- Unmocked file system operations
- Missing timeout decorators

## Continuous Integration

The test suite is designed for CI/CD environments:

```bash
# CI-friendly command
python run_tests.py --no-gui --junit-xml=test-results.xml --coverage
```

This configuration:
- Skips GUI tests that require display
- Exports results in JUnit format
- Generates coverage reports
- Runs reliably in headless environments

## Contributing

When adding new tests:

1. **Follow naming convention**: `test_feature_description`
2. **Use appropriate timeouts**: Add `@pytest.mark.timeout(seconds)` for long-running tests
3. **Mock external dependencies**: Database, file system, network operations
4. **Clean up resources**: Call `close()` and `deleteLater()` for Qt widgets
5. **Use temporary databases**: Follow the pattern in `test_basic.py`
6. **Document complex tests**: Add clear docstrings explaining test purpose

### Test Checklist

- [ ] Test has descriptive name and docstring
- [ ] External dependencies are mocked
- [ ] Resources are properly cleaned up
- [ ] Test runs in under 10 seconds
- [ ] Test is deterministic (same result every run)
- [ ] Test is isolated (doesn't depend on other tests)
