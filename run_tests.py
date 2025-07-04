#!/usr/bin/env python3
"""
Test runner for AstroFiler application.
This script can run tests with or without pytest.

Usage:
    python run_tests.py [--validate|--simple|--full]
    
Options:
    --validate  Run only quick validation tests (fastest)
    --simple    Run simple test suite (no dependencies)
    --full      Run full pytest suite (default)
"""

import os
import sys
import subprocess
import argparse

def get_python_executable():
    """Get the appropriate Python executable (prefer virtual environment)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, ".venv", "bin", "python")
    
    if os.path.exists(venv_python):
        return venv_python
    else:
        return sys.executable

def install_test_requirements():
    """Install test requirements."""
    try:
        python_exe = get_python_executable()
        subprocess.check_call([python_exe, "-m", "pip", "install", "-r", "test/test_requirements.txt"])
        return True
    except subprocess.CalledProcessError:
        print("Failed to install test requirements")
        return False

def run_tests_with_pytest():
    """Run tests using pytest."""
    try:
        import pytest
        return pytest.main(["-v", "test/test_astrofiler.py"])
    except ImportError:
        print("pytest not available")
        return False

def run_simple_tests():
    """Run simple tests without pytest."""
    try:
        python_exe = get_python_executable()
        result = subprocess.run([python_exe, "test/test_simple.py"], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running simple tests: {e}")
        return False

def run_validation():
    """Run quick validation tests."""
    try:
        python_exe = get_python_executable()
        result = subprocess.run([python_exe, "test/validate_astrofiler.py"], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running validation: {e}")
        return False

def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="AstroFiler Test Runner")
    parser.add_argument("--validate", action="store_true", 
                       help="Run only quick validation tests (fastest)")
    parser.add_argument("--simple", action="store_true", 
                       help="Run simple test suite (no dependencies)")
    parser.add_argument("--full", action="store_true", 
                       help="Run full pytest suite")
    
    args = parser.parse_args()
    
    print("AstroFiler Test Runner")
    print("=" * 50)
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Handle command line options
    if args.validate:
        print("Running quick validation tests...")
        success = run_validation()
        if success:
            print("\n✓ All validation tests passed!")
            return 0
        else:
            print("\n✗ Some validation tests failed!")
            return 1
    
    elif args.simple:
        print("Running simple test suite...")
        success = run_simple_tests()
        if success:
            print("\n✓ All simple tests passed!")
            return 0
        else:
            print("\n✗ Some simple tests failed!")
            return 1
    
    elif args.full:
        # Force full pytest execution
        if install_test_requirements():
            try:
                import pytest
                print("Running full test suite with pytest...")
                exit_code = run_tests_with_pytest()
                if exit_code == 0:
                    print("\n✓ All tests passed with pytest!")
                else:
                    print(f"\n✗ Some tests failed (exit code: {exit_code})")
                return exit_code
            except ImportError:
                print("pytest still not available after installation")
                return 1
        else:
            print("Failed to install test requirements")
            return 1
    
    else:
        # Default behavior: try pytest, fall back to simple
        # Try to run tests with pytest first
        try:
            import pytest
            print("Running tests with pytest...")
            exit_code = run_tests_with_pytest()
            if exit_code == 0:
                print("\n✓ All tests passed with pytest!")
            else:
                print(f"\n✗ Some tests failed (exit code: {exit_code})")
            return exit_code
        except ImportError:
            print("pytest not available, trying to install...")
            
            # Try to install test requirements
            if install_test_requirements():
                try:
                    import pytest
                    print("pytest installed successfully, running tests...")
                    exit_code = run_tests_with_pytest()
                    if exit_code == 0:
                        print("\n✓ All tests passed with pytest!")
                    else:
                        print(f"\n✗ Some tests failed (exit code: {exit_code})")
                    return exit_code
                except ImportError:
                    print("pytest still not available after installation")
            
            # Fall back to simple tests
            print("Running simple tests without pytest...")
            success = run_simple_tests()
            if success:
                print("\n✓ All simple tests passed!")
                return 0
            else:
                print("\n✗ Some simple tests failed!")
                return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
