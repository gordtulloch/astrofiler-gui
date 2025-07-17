#!/usr/bin/env python3
"""
Run tests for the AstroFiler application using the virtual environment's Python.
"""

import os
import sys
import subprocess
import argparse
import time

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run tests for AstroFiler')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-k', '--keyword', type=str, help='Only run tests which match the given keyword expression')
    parser.add_argument('-x', '--exitfirst', action='store_true', help='Exit instantly on first error or failed test')
    parser.add_argument('--coverage', action='store_true', help='Run with coverage report')
    parser.add_argument('--no-gui', action='store_true', help='Skip tests that require a GUI environment')
    parser.add_argument('--gui-only', action='store_true', help='Only run tests that require a GUI environment')
    parser.add_argument('--no-db', action='store_true', help='Skip tests that require database operations')
    parser.add_argument('--output', type=str, help='Save test results to file')
    parser.add_argument('--junit-xml', type=str, help='Save test results in JUnit XML format')
    args = parser.parse_args()
    
    # Determine the path to the virtual environment's Python
    venv_python = os.path.join('.venv', 'bin', 'python')
    
    if not os.path.exists(venv_python):
        print(f"Error: Virtual environment Python not found at {venv_python}")
        print("Make sure you have activated your virtual environment.")
        return 1
    
    # Check if required packages are installed
    try:
        import pytest
        import pytest_cov
    except ImportError:
        print("Installing required packages...")
        subprocess.run([venv_python, '-m', 'pip', 'install', 'pytest', 'pytest-cov'])
    
    # Construct the command to run the tests
    cmd = [venv_python, '-m', 'pytest']
    
    # Add arguments
    if args.verbose:
        cmd.append('-v')
    
    if args.keyword:
        cmd.extend(['-k', args.keyword])
        
    if args.exitfirst:
        cmd.append('-x')
        
    if args.coverage:
        cmd.extend(['--cov=.', '--cov-report', 'term-missing'])
    
    # Handle GUI tests
    if args.no_gui:
        cmd.extend(['-m', 'not gui'])
    elif args.gui_only:
        cmd.extend(['-m', 'gui'])
    
    # Handle database tests
    if args.no_db:
        cmd.extend(['-k', 'not db'])
    
    # Handle output options
    if args.output:
        cmd.extend(['--resultlog', args.output])
    
    if args.junit_xml:
        cmd.extend(['--junitxml', args.junit_xml])
    
    # Add the test directory
    cmd.append('test')
    
    print(f"Running: {' '.join(cmd)}")
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run the tests
    start_time = time.time()
    try:
        result = subprocess.run(cmd)
        elapsed_time = time.time() - start_time
        print(f"End time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Elapsed time: {elapsed_time:.2f} seconds")
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
