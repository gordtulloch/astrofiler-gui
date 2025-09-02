#!/usr/bin/env python3
"""
Advanced SeeStar discovery tool - test different approaches
"""

import sys
import socket
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, '.')

def test_direct_ip_connection():
    """Test direct connection to discovered IPs"""
    print("=== Testing Direct IP Connections ===")
    
    discovered_ips = ['10.0.0.74', '10.0.0.94']
    
    for ip in discovered_ips:
        print(f"\nTesting {ip}:")
        
        # Test SMB port
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, 445))
            sock.close()
            
            if result == 0:
                print(f"✓ SMB port 445 is open on {ip}")
                
                # Try to test SMB connection
                try:
                    from astrofiler_smart import SmartTelescopeManager
                    manager = SmartTelescopeManager()
                    
                    # Test getting FITS files to see if it's really a SeeStar
                    print(f"  Testing FITS file access on {ip}...")
                    fits_files, error = manager.get_fits_files('SeeStar', ip)
                    
                    if error:
                        print(f"  ✗ FITS access failed: {error}")
                    else:
                        print(f"  ✓ FITS access successful! Found {len(fits_files)} files")
                        print(f"  This appears to be a SeeStar device!")
                        
                        # Show some file info
                        if fits_files:
                            print(f"  Sample files:")
                            for i, file_info in enumerate(fits_files[:3]):
                                print(f"    - {file_info['name']} ({file_info['size']} bytes)")
                        
                except Exception as e:
                    print(f"  ✗ Error testing FITS access: {e}")
                    
            else:
                print(f"✗ SMB port 445 is closed on {ip}")
                
        except Exception as e:
            print(f"✗ Error testing {ip}: {e}")

def test_alternative_hostnames():
    """Test various possible hostnames"""
    print("=== Testing Alternative Hostnames ===")
    
    possible_hostnames = [
        'seestar.local',
        'SEESTAR.local',
        'SeeStar.local',
        'seestar-s50.local',
        'SEESTAR-S50.local',
        'seestar-plus.local',
        'SEESTAR-PLUS.local',
        'zwo-seestar.local',
        'ZWO-SEESTAR.local'
    ]
    
    for hostname in possible_hostnames:
        try:
            ip = socket.gethostbyname(hostname)
            print(f"✓ {hostname} resolved to: {ip}")
        except:
            continue  # Don't print failures to keep output clean

if __name__ == "__main__":
    print("Advanced SeeStar Discovery Tool")
    print("=" * 40)
    
    test_alternative_hostnames()
    print()
    test_direct_ip_connection()
