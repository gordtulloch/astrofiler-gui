#!/usr/bin/env python3
"""
Test runner script for AstroFiler
"""
import sys
import subprocess
import os
from pathlib import Path

def run_tests():
    """Run the test suite with appropriate options."""
    
    # Change to the project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Basic test command
    cmd = [
        sys.executable, '-m', 'pytest',
        'tests/',
        '-v',
        '--tb=short',
        '--color=yes'
    ]
    
    # Add coverage if requested
    if '--coverage' in sys.argv:
        cmd.extend([
            '--cov=astrofiler_db',
            '--cov=astrofiler_file', 
            '--cov=astrofiler_gui',
            '--cov-report=html',
            '--cov-report=term-missing'
        ])
        sys.argv.remove('--coverage')
    
    # Add specific test markers if requested
    if '--unit' in sys.argv:
        cmd.extend(['-m', 'unit'])
        sys.argv.remove('--unit')
    elif '--integration' in sys.argv:
        cmd.extend(['-m', 'integration'])
        sys.argv.remove('--integration')
    elif '--gui' in sys.argv:
        cmd.extend(['-m', 'gui'])
        sys.argv.remove('--gui')
    
    # Pass through any additional arguments
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nTest run interrupted by user")
        return 1
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

def install_test_requirements():
    """Install test requirements if needed."""
    try:
        import pytest
        print("Pytest already installed")
    except ImportError:
        print("Installing test requirements...")
        cmd = [sys.executable, '-m', 'pip', 'install', '-r', 'requirements-test.txt']
        subprocess.run(cmd, check=True)

if __name__ == '__main__':
    if '--install-deps' in sys.argv:
        install_test_requirements()
        sys.argv.remove('--install-deps')
    
    if '--help' in sys.argv or '-h' in sys.argv:
        print("""
AstroFiler Test Runner

Usage: python run_tests.py [options]

Options:
    --install-deps    Install test dependencies first
    --coverage        Run with coverage reporting
    --unit            Run only unit tests
    --integration     Run only integration tests
    --gui             Run only GUI tests
    --help, -h        Show this help message
    
Examples:
    python run_tests.py                    # Run all tests
    python run_tests.py --coverage         # Run with coverage
    python run_tests.py --unit             # Run only unit tests
    python run_tests.py tests/test_gui.py  # Run specific test file
    
Any additional arguments are passed directly to pytest.
        """)
        sys.exit(0)
    
    exit_code = run_tests()
    sys.exit(exit_code)
