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
    parser.add_argument('--install-xvfb', action='store_true', help='Install Xvfb for headless GUI testing (requires sudo)')
    args = parser.parse_args()
    
    # Determine the path to the virtual environment's Python depending on the OS
    if sys.platform.startswith('win'):
        venv_python = os.path.join('.venv', 'Scripts', 'python.exe')
    else:   # Assume Unix-like OS
        venv_python = os.path.join('.venv', 'bin', 'python')
        
    # Check if the virtual environment's Python exists
    if not os.path.exists(venv_python):
        print(f"Error: Virtual environment Python not found at {venv_python}")
        print("Make sure you have activated your virtual environment.")
        return 1
    
    # Check if user wants to install Xvfb
    if args.install_xvfb:
        print("Installing Xvfb...")
        try:
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'xvfb'], check=True)
            print("Xvfb installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Xvfb: {e}")
            return 1
        except Exception as e:
            print(f"Error installing Xvfb: {e}")
            return 1
    
    # Check if required packages are installed
    try:
        import pytest
        import pytest_cov
        import pytest_timeout
    except ImportError:
        print("Installing required packages...")
        subprocess.run([venv_python, '-m', 'pip', 'install', 'pytest', 'pytest-cov', 'pytest-timeout'])
    
    # Check if we're in a headless environment and set up virtual display
    display_env = os.environ.copy()
    xvfb_process = None
    
    # Set Qt environment variables for headless testing
    display_env['QT_QPA_PLATFORM'] = 'offscreen'
    display_env['QT_LOGGING_RULES'] = 'qt.qpa.plugin=false'
    
    if not args.no_gui and 'DISPLAY' not in os.environ:
        # Try to start Xvfb for headless GUI testing
        try:
            print("No DISPLAY found, attempting to start virtual display (Xvfb)...")
            xvfb_process = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1024x768x24'], 
                                          stdout=subprocess.DEVNULL, 
                                          stderr=subprocess.DEVNULL)
            display_env['DISPLAY'] = ':99'
            # Override QT_QPA_PLATFORM when Xvfb is available
            display_env['QT_QPA_PLATFORM'] = 'xcb'
            time.sleep(2)  # Give Xvfb time to start
            print("Virtual display started successfully")
        except FileNotFoundError:
            print("Xvfb not found. Using offscreen platform for GUI tests.")
            print("Install Xvfb with: sudo apt-get install xvfb for better GUI testing")
        except Exception as e:
            print(f"Failed to start virtual display: {e}")
            print("Using offscreen platform for GUI tests")
    
    # Construct the command to run the tests
    cmd = [venv_python, '-m', 'pytest']
    
    # Add timeout for all tests
    cmd.extend(['--timeout=10'])  # Reduced global timeout to 10 seconds
    
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
        result = subprocess.run(cmd, env=display_env)
        elapsed_time = time.time() - start_time
        print(f"End time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Elapsed time: {elapsed_time:.2f} seconds")
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1
    finally:
        # Clean up Xvfb process if it was started
        if xvfb_process:
            xvfb_process.terminate()
            xvfb_process.wait()

if __name__ == '__main__':
    sys.exit(main())
