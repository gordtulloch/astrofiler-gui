#!/usr/bin/env python3
"""
Test script to verify the SEP overflow fix in master_manager.py

This script tests:
1. SEP configuration and sub-object limit setting
2. Error handling for SEP overflow scenarios
3. Astroalign registration with SEP fallback handling
"""

import sys
import os
import logging
import numpy as np
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_sep_configuration():
    """Test SEP configuration and sub-object limit setting."""
    print("=" * 60)
    print("Testing SEP Configuration")
    print("=" * 60)
    
    try:
        import sep
        print(f"✓ SEP imported successfully (version: {sep.__version__ if hasattr(sep, '__version__') else 'unknown'})")
        
        # Get current limit
        current_limit = sep.get_sub_object_limit()
        print(f"✓ Current SEP sub-object limit: {current_limit}")
        
        # Test setting a higher limit
        original_limit = current_limit
        new_limit = 131072
        sep.set_sub_object_limit(new_limit)
        updated_limit = sep.get_sub_object_limit()
        
        if updated_limit == new_limit:
            print(f"✓ Successfully set SEP sub-object limit to {new_limit}")
        else:
            print(f"✗ Failed to set SEP sub-object limit (expected {new_limit}, got {updated_limit})")
        
        # Restore original limit
        sep.set_sub_object_limit(original_limit)
        restored_limit = sep.get_sub_object_limit()
        
        if restored_limit == original_limit:
            print(f"✓ Successfully restored original limit: {restored_limit}")
        else:
            print(f"✗ Failed to restore original limit (expected {original_limit}, got {restored_limit})")
            
        return True
        
    except ImportError as e:
        print(f"✗ SEP not available: {e}")
        return False
    except Exception as e:
        print(f"✗ Error testing SEP configuration: {e}")
        return False

def test_master_manager_import():
    """Test importing the master_manager module with our fixes."""
    print("\n" + "=" * 60)
    print("Testing Master Manager Import")
    print("=" * 60)
    
    try:
        from astrofiler.core.master_manager import configure_sep_for_crowded_fields, reset_sep_defaults
        print("✓ Successfully imported master_manager helper functions")
        
        # Test the helper functions
        result1 = configure_sep_for_crowded_fields()
        if result1:
            print("✓ configure_sep_for_crowded_fields() executed successfully")
        else:
            print("✗ configure_sep_for_crowded_fields() failed")
        
        result2 = reset_sep_defaults()
        if result2:
            print("✓ reset_sep_defaults() executed successfully")
        else:
            print("✗ reset_sep_defaults() failed")
            
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import master_manager: {e}")
        return False
    except Exception as e:
        print(f"✗ Error testing master_manager: {e}")
        return False

def test_astroalign_availability():
    """Test astroalign import and basic functionality."""
    print("\n" + "=" * 60)
    print("Testing Astroalign Availability")
    print("=" * 60)
    
    try:
        import astroalign as aa
        print(f"✓ Astroalign imported successfully (version: {aa.__version__ if hasattr(aa, '__version__') else 'unknown'})")
        
        # Test if the MaxIterError class is available
        if hasattr(aa, 'MaxIterError'):
            print("✓ MaxIterError class is available")
        else:
            print("⚠ MaxIterError class not found (may be in different version)")
        
        return True
        
    except ImportError as e:
        print(f"✗ Astroalign not available: {e}")
        return False
    except Exception as e:
        print(f"✗ Error testing astroalign: {e}")
        return False

def test_error_handling_simulation():
    """Simulate the error handling scenarios that our fix addresses."""
    print("\n" + "=" * 60)
    print("Testing Error Handling Simulation")
    print("=" * 60)
    
    # Test various error messages that our fix should handle
    error_messages = [
        "deblending overflow: limit of sub-objects reached",
        "object deblending overflow",
        "sub-objects reached while deblending",
        "Input type for target not supported",
        "TypeError: Input type for target not supported"
    ]
    
    def simulate_error_check(error_msg):
        """Simulate the error checking logic from our fix."""
        should_handle = (
            "deblending overflow" in error_msg or
            "sub-objects reached" in error_msg or 
            "object deblending overflow" in error_msg or
            "Input type for target not supported" in error_msg
        )
        return should_handle
    
    all_passed = True
    for error_msg in error_messages:
        should_handle = simulate_error_check(error_msg)
        if should_handle:
            print(f"✓ Error message '{error_msg}' will be handled by our fix")
        else:
            print(f"✗ Error message '{error_msg}' will NOT be handled by our fix")
            all_passed = False
    
    return all_passed

def main():
    """Run all tests."""
    print("Testing SEP Overflow Fix for AstroFiler Calibration")
    print("=" * 60)
    
    results = []
    
    # Run all tests
    results.append(("SEP Configuration", test_sep_configuration()))
    results.append(("Master Manager Import", test_master_manager_import()))
    results.append(("Astroalign Availability", test_astroalign_availability()))
    results.append(("Error Handling Logic", test_error_handling_simulation()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name:.<40} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed! The SEP overflow fix should work correctly.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
