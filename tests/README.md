# AstroFiler Test Suite

This directory contains comprehensive test cases for the AstroFiler application using pytest.

## Test Structure

```
tests/
├── __init__.py                 # Makes tests a Python package
├── conftest.py                 # Pytest configuration and shared fixtures
├── test_database.py            # Tests for astrofiler_db.py
├── test_fits_processing.py     # Tests for astrofiler_file.py
├── test_gui.py                 # Tests for astrofiler_gui.py
├── test_integration.py         # Integration tests
├── test_main.py                # Tests for astrofiler.py
└── README.md                   # This file
```

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install -r requirements-test.txt
```

Or install individual packages:
```bash
pip install pytest pytest-qt pytest-cov pytest-mock
```

### Basic Test Execution

Run all tests:
```bash
pytest
```

Run with verbose output:
```bash
pytest -v
```

Run specific test file:
```bash
pytest tests/test_database.py
```

Run specific test class:
```bash
pytest tests/test_database.py::TestDatabaseModels
```

Run specific test method:
```bash
pytest tests/test_database.py::TestDatabaseModels::test_fits_file_model_fields
```

### Test Categories

Run only unit tests:
```bash
pytest -m unit
```

Run only integration tests:
```bash
pytest -m integration
```

Run only GUI tests:
```bash
pytest -m gui
```

### Coverage Reporting

Run tests with coverage:
```bash
pytest --cov=astrofiler_db --cov=astrofiler_file --cov=astrofiler_gui --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Using the Test Runner

Use the provided test runner script:
```bash
python run_tests.py                    # Run all tests
python run_tests.py --coverage         # Run with coverage
python run_tests.py --unit             # Run only unit tests
python run_tests.py --install-deps     # Install dependencies first
```

## Test Coverage

The test suite covers:

### Database Module (`test_database.py`)
- ✅ Model field definitions
- ✅ Primary key configurations
- ✅ Database setup and error handling
- ✅ CRUD operations with in-memory database
- ✅ Query operations

### FITS Processing Module (`test_fits_processing.py`)
- ✅ Class initialization and configuration
- ✅ File submission to database
- ✅ FITS file registration and validation
- ✅ Sequence creation algorithms
- ✅ Thumbnail generation
- ✅ Error handling for invalid files
- ✅ Batch processing workflows

### GUI Module (`test_gui.py`)
- ✅ Widget initialization
- ✅ Button and control functionality
- ✅ Tab creation and management
- ✅ Configuration management
- ✅ Theme handling
- ✅ Event handling and user interactions
- ✅ Error display and messaging

### Integration Tests (`test_integration.py`)
- ✅ End-to-end workflow simulation
- ✅ Module interaction testing
- ✅ Error propagation across modules
- ✅ Performance considerations
- ✅ Configuration integration

### Main Application (`test_main.py`)
- ✅ Application startup
- ✅ Import validation
- ✅ Command line argument handling

## Test Fixtures and Utilities

### Shared Fixtures (`conftest.py`)
- `temp_dir`: Temporary directory for file operations
- `mock_config_file`: Mock configuration file
- `mock_fits_header`: Sample FITS header data
- `mock_database`: Mock database instance
- `sample_fits_files`: Sample FITS file structure

### Mocking Strategy
Tests use extensive mocking to:
- Isolate units under test
- Avoid file system dependencies
- Simulate error conditions
- Speed up test execution
- Ensure reproducible results

## Writing New Tests

### Test Naming Convention
- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

### Example Test Structure
```python
class TestNewFeature:
    """Test new feature functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        pass
    
    def test_feature_success(self):
        """Test successful feature operation."""
        # Arrange
        # Act
        # Assert
        pass
    
    def test_feature_error_handling(self):
        """Test feature error handling."""
        pass
```

### Best Practices
1. Use descriptive test names
2. Follow Arrange-Act-Assert pattern
3. Mock external dependencies
4. Test both success and failure cases
5. Keep tests independent
6. Use appropriate fixtures
7. Add docstrings for complex tests

## Continuous Integration

The test suite is designed to run in CI/CD environments. Key considerations:

- Tests are isolated and don't require external resources
- GUI tests use pytest-qt for headless operation
- Mocking eliminates file system dependencies
- All tests should pass on clean environment

## Troubleshooting

### Common Issues

**Import Errors**: Ensure you're running from the project root directory.

**GUI Test Failures**: GUI tests require a display. On Linux servers, use:
```bash
pip install pytest-xvfb
pytest
```

**Permission Errors**: Ensure write permissions for temporary directories.

**Missing Dependencies**: Install all requirements:
```bash
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### Debugging Tests

Run with debugging output:
```bash
pytest -s -vv
```

Run with Python debugger:
```bash
pytest --pdb
```

Stop on first failure:
```bash
pytest -x
```

## Test Maintenance

- Update tests when adding new features
- Maintain test coverage above 80%
- Review and update mocks when dependencies change
- Keep test data and fixtures up to date
- Regularly run the full test suite

## Performance

The test suite is optimized for speed:
- Uses in-memory databases
- Mocks file operations
- Parallel test execution supported
- Minimal setup/teardown overhead

Typical run times:
- Unit tests: < 10 seconds
- Integration tests: < 30 seconds
- Full suite: < 1 minute
