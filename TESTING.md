# AstroFiler Testing Guide

This document provides comprehensive information about the test suite for the AstroFiler application, including how to run tests, what's being tested, and how to add new tests.

## Test Suite Overview

The AstroFiler test suite is built using the pytest framework and includes tests for:

1. **Database functionality** - Creating and manipulating database records
2. **File processing** - Reading and extracting metadata from FITS files
3. **GUI components** - Verifying UI functionality

## Directory Structure

```
test/
├── __init__.py
├── pytest.ini              # Pytest configuration
├── test_basic.py           # Basic database tests
├── test_file_processing.py # FITS file processing tests
├── test_gui.py             # GUI component tests
```

## Running Tests

### Using the Test Runner Script

The easiest way to run tests is using the provided `run_tests.py` script, which automatically uses the correct Python interpreter from your virtual environment:

```bash
# Run all tests
./run_tests.py

# Run tests with verbose output
./run_tests.py -v

# Run only tests matching a keyword
./run_tests.py -k "session"

# Stop on first failing test
./run_tests.py -x

# Generate test coverage report
./run_tests.py --coverage

# Skip GUI tests
./run_tests.py --no-gui

# Run only GUI tests
./run_tests.py --gui-only
```

### Using pytest Directly

You can also run pytest directly:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest test/

# Run specific test file
pytest test/test_basic.py

# Run specific test
pytest test/test_basic.py::TestBasicFunctionality::test_session_creation
```

## Test Categories

### Basic Tests (`test_basic.py`)

These tests cover the fundamental database operations:

- **Database creation and initialization**
- **Session creation and retrieval**
- **File creation and session linking**

Each test uses a temporary database to avoid interfering with your production data.

### File Processing Tests (`test_file_processing.py`)

These tests verify the FITS file processing functionality:

- **Extracting metadata from FITS files**
- **Scanning directories for FITS files**
- **Importing files into the database**

These tests use mock FITS files to avoid dependency on actual files.

### GUI Tests (`test_gui.py`)

These tests verify the GUI components:

- **Tab creation and configuration**
- **Context menu functionality**
- **Session checkout workflow**

Note: GUI tests are marked with `@pytest.mark.skip` by default because they require a display environment. Remove the skip decorator or use the `--gui-only` flag when running in an environment that supports GUI.

## Writing New Tests

### Adding a New Test Function

1. Choose the appropriate test file (or create a new one)
2. Add a test method following this pattern:

```python
def test_something_specific(self):
    """Test description."""
    # Arrange - set up test conditions
    ...
    
    # Act - perform the action to test
    result = some_function()
    
    # Assert - check that the result is as expected
    assert result == expected_value
```

### Testing Database Operations

Use the `setup_db` fixture to create a temporary database:

```python
def test_new_database_feature(self):
    """Test a new database feature."""
    # The setup_db fixture is automatically applied
    
    # Create some test data
    session = fitsSession.create(
        fitsSessionObjectName="Test",
        fitsSessionDate="2025-07-17"
    )
    
    # Verify the operation
    assert session.fitsSessionObjectName == "Test"
```

### Testing GUI Components

Use mocks to simulate GUI interactions:

```python
@pytest.mark.skip(reason="This test requires a GUI environment")
def test_new_gui_feature(self, qapp):
    """Test a new GUI feature."""
    # Create the component with mocked dependencies
    with patch('astrofiler_gui.SomeDependency') as mock_dep:
        # Set up the mock
        mock_dep.return_value = ...
        
        # Create the component
        component = SomeComponent()
        
        # Verify it behaves correctly
        assert component.property == expected_value
```

## Test Coverage

To generate a test coverage report:

```bash
./run_tests.py --coverage
```

This will show which parts of the codebase are tested and which need more coverage.

## Continuous Integration

Tests are automatically run in the CI/CD pipeline on each commit. The pipeline:

1. Sets up a Python environment
2. Installs dependencies
3. Runs the test suite
4. Reports test results and coverage

## Best Practices

1. **Keep tests isolated** - Each test should be independent and not rely on other tests
2. **Use descriptive test names** - Names should describe what's being tested
3. **Follow the AAA pattern** - Arrange, Act, Assert
4. **Mock external dependencies** - Don't rely on external systems in tests
5. **Test edge cases** - Don't just test the happy path
6. **Keep tests fast** - Slow tests discourage running them frequently

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure you're running tests with the correct Python environment
2. **Database errors**: Check that temporary database paths are writable
3. **GUI test failures**: GUI tests require a display; use `--no-gui` flag if running in a headless environment

### Getting Help

If you encounter issues with the test suite, please:

1. Check the logs for specific error messages
2. Verify your environment setup
3. Contact the project maintainer for assistance

---

*Last Updated: July 17, 2025*
