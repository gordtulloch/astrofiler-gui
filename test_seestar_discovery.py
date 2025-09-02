#!/usr/bin/env python3
"""
Test script for diagnosing SeeStar discovery issues
"""

import sys
import socket
import logging

# Setup logging to see detailed output
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.insert(0, '.')

def test_mdns_resolution():
    """Test mDNS resolution for seestar.local"""
    print("=== Testing mDNS Resolution ===")
    
    hostnames_to_test = [
        'seestar.local',
        'SEESTAR.local', 
        'SeeStar.local'
    ]
    
    for hostname in hostnames_to_test:
        try:
            print(f"Testing hostname: {hostname}")
            ip = socket.gethostbyname(hostname)
            print(f"✓ {hostname} resolved to: {ip}")
            
            # Test SMB port
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((ip, 445))
                sock.close()
                
                if result == 0:
                    print(f"✓ SMB port 445 is open on {ip}")
                else:
                    print(f"✗ SMB port 445 is closed on {ip} (error: {result})")
                    
            except Exception as e:
                print(f"✗ Error testing SMB port on {ip}: {e}")
                
        except Exception as e:
            print(f"✗ Failed to resolve {hostname}: {e}")
        print()

def test_smart_telescope_manager():
    """Test the SmartTelescopeManager discovery"""
    print("=== Testing SmartTelescopeManager ===")
    
    try:
        from astrofiler_smart import SmartTelescopeManager
        manager = SmartTelescopeManager()
        
        print(f"Default SeeStar hostname: {manager.supported_telescopes['SeeStar']['default_hostname']}")
        
        # Test with explicit hostname
        print("\n--- Testing with explicit hostname ---")
        ip, error = manager.find_telescope('SeeStar', hostname='seestar.local')
        if ip:
            print(f"✓ Found SeeStar at {ip}")
        else:
            print(f"✗ SeeStar not found via hostname: {error}")
        
        # Test with default discovery
        print("\n--- Testing default discovery ---")
        ip, error = manager.find_telescope('SeeStar')
        if ip:
            print(f"✓ Found SeeStar at {ip}")
        else:
            print(f"✗ SeeStar not found via discovery: {error}")
            
    except Exception as e:
        print(f"✗ Error with SmartTelescopeManager: {e}")
        import traceback
        traceback.print_exc()

def test_network_info():
    """Test network information"""
    print("=== Network Information ===")
    
    try:
        from astrofiler_smart import SmartTelescopeManager
        manager = SmartTelescopeManager()
        
        network = manager.get_local_network()
        print(f"Detected local network: {network}")
        
        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"Local IP address: {local_ip}")
        
    except Exception as e:
        print(f"Error getting network info: {e}")

if __name__ == "__main__":
    print("SeeStar Discovery Diagnostic Tool")
    print("=" * 40)
    
    test_network_info()
    print()
    test_mdns_resolution()
    print()
    test_smart_telescope_manager()
    
    print("\n=== Summary ===")
    print("If mDNS resolution works but SmartTelescopeManager fails,")
    print("there may be an issue with SMB connectivity or firewall settings.")
    print("Make sure:")
    print("1. SeeStar is powered on and connected to same network")
    print("2. Your firewall allows SMB traffic (port 445)")
    print("3. SeeStar SMB sharing is enabled")
