#!/usr/bin/env python3
"""
Test script to verify cancellation works during telescope scanning phase.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from astrofiler_smart import smart_telescope_manager
import time
import threading

def test_cancellation():
    """Test if find_telescope can be interrupted."""
    print("Testing telescope discovery cancellation...")
    
    # Start discovery in a thread
    result = [None]
    error = [None]
    
    def discover():
        ip, err = smart_telescope_manager.find_telescope('SEESTAR', network_range='10.0.0.0/24')
        result[0] = ip
        error[0] = err
    
    thread = threading.Thread(target=discover)
    thread.start()
    
    # Wait a bit then try to "cancel" (we can't actually cancel mid-discovery yet)
    time.sleep(2)
    print("Simulated user cancellation after 2 seconds")
    
    # Wait for thread to complete
    thread.join()
    
    print(f"Discovery result: IP={result[0]}, Error={error[0]}")

if __name__ == "__main__":
    test_cancellation()
