#!/usr/bin/env python3
"""
Astrofiler Smart Telescope Integration
Handles communication with smart telescopes like SEESTAR for automated file retrieval.
"""

import socket
import ipaddress
import os
import logging
import configparser
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import ftplib
import numpy as np
import hashlib
from datetime import datetime
from astropy.io import fits
from ..models import fitsSession, fitsFile
from ..core import get_master_calibration_path

# Configure logging
logger = logging.getLogger(__name__)

# Reduce SMB library verbosity
logging.getLogger('SMB').setLevel(logging.WARNING)
logging.getLogger('SMB.SMBConnection').setLevel(logging.WARNING)
logging.getLogger('SMB.SMBProtocol').setLevel(logging.WARNING)

try:
    from smb.SMBConnection import SMBConnection
    from smb.base import NotReadyError, NotConnectedError
    SMB_AVAILABLE = True
except ImportError:
    SMB_AVAILABLE = False

class SmartTelescopeManager:
    """Manages connections to smart telescopes."""
    
    def __init__(self):
        self.supported_telescopes = {
            'SeeStar': {
                'default_hostname': 'seestar.local',
                'default_username': 'guest',
                'default_password': 'guest',
                'share_name': 'EMMC Images',
                'fits_path': 'MyWorks'
            },
            'StellarMate': {
                'default_hostname': 'stellarmate.local',
                'default_username': 'stellarmate',
                'default_password': 'smate',
                'share_name': 'Pictures',
                'fits_path': ''  # Start scanning from root
            },
            'DWARF 3': {
                'default_hostname': '192.168.88.1',
                'default_username': None,  # No authentication for FTP
                'default_password': None,  # No authentication for FTP
                'protocol': 'ftp',
                'fits_path': 'Astronomy'  # DWARF stores FITS files in /Astronomy
            },
            'iTelescope': {
                'default_hostname': 'data.itelescope.net',
                'default_username': '',  # To be configured by user
                'default_password': '',  # To be configured by user
                'protocol': 'ftps',  # FTP with TLS
                'fits_path': '',  # Start scanning from root
                'port': 21
            },
            'Celestron Origin': {
                'default_hostname': '',  # To be configured by user (telescope IP)
                'default_username': 'celestron',  # Default FTP credentials per Celestron documentation
                'default_password': 'celestron',  # Note: These are standard defaults, telescope may not support changing them
                'protocol': 'ftp',  # Plain FTP (not FTPS)
                'fits_path': 'RawData',  # Celestron Origin stores raw FITS in /RawData
                'port': 21
            }
        }
    
    def get_itelescope_credentials(self):
        """Get iTelescope credentials from configuration file."""
        try:
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            
            username = config.get('DEFAULT', 'itelescope_username', fallback='')
            password = config.get('DEFAULT', 'itelescope_password', fallback='')
            
            return username.strip(), password.strip()
        except Exception as e:
            logger.error(f"Error reading iTelescope credentials: {e}")
            return '', ''
    
    def get_celestron_hostname(self):
        """Get Celestron Origin hostname from configuration file."""
        try:
            config = configparser.ConfigParser()
            config.read('astrofiler.ini')
            
            hostname = config.get('DEFAULT', 'celestron_hostname', fallback='')
            
            return hostname.strip()
        except Exception as e:
            logger.error(f"Error reading Celestron Origin hostname: {e}")
            return ''
    
    def get_local_network(self):
        """Get the local network range based on the local IP address."""
        try:
            # Connect to a remote address to determine the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Determine likely network based on IP
            if local_ip.startswith('192.168.'):
                # Extract the third octet and assume /24
                parts = local_ip.split('.')
                return f"192.168.{parts[2]}.0/24"
            elif local_ip.startswith('10.'):
                # For 10.x networks, assume /24 on the same subnet
                parts = local_ip.split('.')
                return f"10.{parts[1]}.{parts[2]}.0/24"
            elif local_ip.startswith('172.'):
                # 172.16.0.0 to 172.31.255.255 - assume /24
                parts = local_ip.split('.')
                return f"172.{parts[1]}.{parts[2]}.0/24"
            else:
                return "192.168.1.0/24"
                
        except Exception as e:
            logger.debug(f"Error getting network info: {e}")
            return "10.0.0.0/24"
    
    def check_smb_port(self, ip, timeout=2):
        """Check if SMB port (445) is open on the given IP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((str(ip), 445))
                return result == 0
        except:
            return False
    
    def check_ftp_port(self, ip, timeout=2):
        """Check if FTP port (21) is open on the given IP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((str(ip), 21))
                return result == 0
        except:
            return False
    
    def get_hostname(self, ip):
        """Try to get the hostname for the given IP address."""
        try:
            hostname = socket.gethostbyaddr(str(ip))[0]
            return hostname
        except:
            return None
    
    def is_target_device(self, hostname, telescope_type):
        """Check if the device matches the target telescope type."""
        if not hostname:
            return False
        
        if telescope_type == 'SeeStar':
            return 'seestar' in hostname.lower()
        elif telescope_type == 'StellarMate':
            return 'stellarmate' in hostname.lower()
        
        return False
    
    def find_telescope(self, telescope_type, network_range=None, hostname=None):
        """Find a specific telescope on the network."""
        logger.info(f"Starting search for {telescope_type} telescope (hostname={hostname}, network={network_range})")
        
        # For iTelescope, bypass all network scanning and SMB checks
        if telescope_type == 'iTelescope':
            if hostname:
                logger.info(f"Using provided iTelescope hostname: {hostname}")
                return hostname, None
            else:
                default_hostname = self.supported_telescopes['iTelescope']['default_hostname']
                logger.info(f"Using default iTelescope hostname: {default_hostname}")
                return default_hostname, None
        
        if not SMB_AVAILABLE:
            logger.error("SMB protocol not available. Install pysmb package.")
            return None, "SMB protocol not available. Install pysmb package."
        
        if hostname:
            # For SeeStar, only use mDNS resolution for seestar.local hostnames
            # No reverse DNS lookups as SeeStar patched their firmware to disable them
            try:
                logger.debug(f"Resolving hostname {hostname}")
                ip = socket.gethostbyname(hostname)
                logger.debug(f"Hostname {hostname} resolved to {ip}")
                
                if self.check_smb_port(ip):
                    # For SeeStar, trust the mDNS hostname and skip reverse DNS
                    if telescope_type == 'SeeStar':
                        if 'seestar' in hostname.lower() or hostname.upper().startswith('SEESTAR'):
                            logger.info(f"Found {telescope_type} telescope at {ip} (mDNS hostname: {hostname})")
                            return ip, None
                        else:
                            logger.warning(f"Hostname {hostname} doesn't match expected SeeStar pattern")
                            return None, f"Hostname {hostname} doesn't match expected SeeStar pattern"
                    
                    # For StellarMate, trust the mDNS hostname and skip reverse DNS
                    elif telescope_type == 'StellarMate':
                        if 'stellarmate' in hostname.lower() or hostname.upper().startswith('STELLARMATE'):
                            logger.info(f"Found {telescope_type} telescope at {ip} (mDNS hostname: {hostname})")
                            return ip, None
                        else:
                            logger.warning(f"Hostname {hostname} doesn't match expected StellarMate pattern")
                            return None, f"Hostname {hostname} doesn't match expected StellarMate pattern"
                    
                    # For other telescope types, check if the provided hostname matches
                    elif self.is_target_device(hostname, telescope_type):
                        logger.info(f"Found {telescope_type} telescope at {ip} (user provided hostname: {hostname})")
                        return ip, None
                
                logger.warning(f"Device {hostname} ({ip}) not found or not accessible")
                return None, f"Device {hostname} not found or not accessible"
            except Exception as e:
                logger.error(f"Unable to resolve hostname {hostname}: {e}")
                return None, f"Unable to resolve hostname {hostname}"
        
        # For SeeStar, try the default mDNS hostname first before network scanning
        if telescope_type == 'SeeStar':
            default_hostname = self.supported_telescopes['SeeStar']['default_hostname']
            logger.info(f"Trying default mDNS hostname: {default_hostname}")
            try:
                ip = socket.gethostbyname(default_hostname)
                if self.check_smb_port(ip):
                    logger.info(f"Found {telescope_type} telescope at {ip} via mDNS ({default_hostname})")
                    return ip, None
            except Exception as e:
                logger.debug(f"Default mDNS hostname {default_hostname} not reachable: {e}")
        
        # For StellarMate, try the default mDNS hostname first before network scanning
        elif telescope_type == 'StellarMate':
            default_hostname = self.supported_telescopes['StellarMate']['default_hostname']
            logger.info(f"Trying default mDNS hostname: {default_hostname}")
            try:
                ip = socket.gethostbyname(default_hostname)
                if self.check_smb_port(ip):
                    logger.info(f"Found {telescope_type} telescope at {ip} via mDNS ({default_hostname})")
                    return ip, None
            except Exception as e:
                logger.debug(f"Default mDNS hostname {default_hostname} not reachable: {e}")
        
        # Scan network for device (no reverse DNS lookups for SeeStar, skip entirely for iTelescope)
        if telescope_type == 'iTelescope':
            logger.error("iTelescope should have been handled above - network scanning not applicable")
            return None, "iTelescope configuration error"
            
        if not network_range:
            network_range = self.get_local_network()
            logger.debug(f"Using auto-detected network range: {network_range}")
        
        try:
            network = ipaddress.IPv4Network(network_range, strict=False)
            logger.info(f"Scanning network {network} for {telescope_type} devices...")
        except ValueError as e:
            logger.error(f"Invalid network range {network_range}: {e}")
            return None, f"Invalid network range: {e}"
        
        # Use ThreadPoolExecutor for parallel scanning
        with ThreadPoolExecutor(max_workers=50) as executor:
            # Submit scan jobs for all IPs in the network
            future_to_ip = {executor.submit(self._scan_ip_for_telescope, ip, telescope_type): ip for ip in network.hosts()}
            logger.debug(f"Submitted {len(future_to_ip)} scan tasks")
            
            # Process completed scans
            completed = 0
            for future in as_completed(future_to_ip):
                completed += 1
                if completed % 50 == 0:  # Log progress every 50 IPs
                    logger.debug(f"Scanned {completed}/{len(future_to_ip)} IPs...")
                
                result = future.result()
                if result:
                    logger.info(f"Found {telescope_type} telescope at {result}")
                    return result, None
        
        logger.warning(f"No {telescope_type} device found on network {network_range}")
        return None, f"No {telescope_type} device found on network {network_range}"
    
    def _scan_ip_for_telescope(self, ip, telescope_type):
        """Scan a single IP for the target telescope type."""
        config = self.supported_telescopes.get(telescope_type, {})
        
        if config.get('protocol') == 'ftp':
            # For DWARF telescopes using FTP
            if self.check_ftp_port(ip):
                logger.debug(f"Found FTP service at {ip} - potential {telescope_type} device")
                return str(ip)
        else:
            # For SMB-based telescopes (SeeStar, StellarMate)
            if self.check_smb_port(ip):
                if telescope_type in ['SeeStar', 'StellarMate']:
                    logger.debug(f"Found SMB service at {ip} - potential {telescope_type} device")
                    return str(ip)
                else:
                    # For other telescope types, still use reverse DNS if needed
                    hostname = self.get_hostname(ip)
                    if self.is_target_device(hostname, telescope_type):
                        return str(ip)
        return None
    
    def get_fits_files(self, telescope_type, ip, username=None, password=None):
        """Get all FITS files from the telescope."""
        logger.info(f"Starting FITS file discovery on {telescope_type} at {ip}")
        
        config = self.supported_telescopes.get(telescope_type)
        if not config:
            logger.error(f"Unsupported telescope type: {telescope_type}")
            return [], f"Unsupported telescope type: {telescope_type}"
        
        # Check protocol type
        if config.get('protocol') == 'ftp':
            return self._get_fits_files_ftp(telescope_type, ip, username, password)
        elif config.get('protocol') == 'ftps':
            return self._get_fits_files_ftps(telescope_type, ip, username, password)
        else:
            return self._get_fits_files_smb(telescope_type, ip, username, password)
    
    def _get_fits_files_smb(self, telescope_type, ip, username=None, password=None):
        """Get FITS files via SMB protocol (SeeStar)."""
        if not SMB_AVAILABLE:
            logger.error("SMB protocol not available")
            return [], "SMB protocol not available"
        
        config = self.supported_telescopes.get(telescope_type)
        username = username or config['default_username']
        password = password or config['default_password']
        share_name = config['share_name']
        fits_path = config['fits_path']
        
        logger.debug(f"Using SMB share: {share_name}, path: {fits_path}, username: {username}")
        
        try:
            # Create SMB connection
            conn = SMBConnection(username, password, "client", "server", use_ntlm_v2=True)
            
            # Try to connect
            logger.debug(f"Attempting SMB connection to {ip}:445...")
            connected = conn.connect(str(ip), 445, timeout=10)
            
            if not connected:
                logger.error(f"Failed to connect to SMB service at {ip}")
                return [], "Failed to connect to SMB service"
            
            logger.info(f"Successfully connected to SMB service at {ip}")
            
            try:
                # Get FITS files from the specified path
                logger.debug(f"Scanning for FITS files in {share_name}/{fits_path}")
                start_time = time.time()
                fits_files = self._get_fits_files_from_path_smb(conn, share_name, fits_path, telescope_type)
                scan_time = time.time() - start_time
                
                conn.close()
                logger.info(f"Found {len(fits_files)} FITS files in {scan_time:.2f} seconds")
                return fits_files, None
                
            except Exception as e:
                conn.close()
                logger.error(f"Error accessing files on {ip}: {e}")
                return [], f"Error accessing files: {e}"
                
        except Exception as e:
            logger.error(f"Connection error to {ip}: {e}")
            return [], f"Connection error: {e}"
    
    def _get_fits_files_ftp(self, telescope_type, ip, username=None, password=None):
        """Get FITS files via FTP protocol (DWARF, Celestron Origin)."""
        logger.info(f"Using FTP connection for {telescope_type}")
        
        config = self.supported_telescopes.get(telescope_type)
        
        # Use provided credentials, or fall back to defaults from config
        username = username or config.get('default_username')
        password = password or config.get('default_password')
        
        logger.debug(f"FTP credentials: username={'<set>' if username else '<none>'}, password={'<set>' if password else '<none>'}")
        
        try:
            # Create FTP connection
            ftp = ftplib.FTP()
            logger.debug(f"Attempting FTP connection to {ip}:21...")
            ftp.connect(ip, 21, timeout=10)
            
            # Set passive mode (required by many FTP servers behind firewalls/NAT)
            ftp.set_pasv(True)
            logger.debug("Enabled passive FTP mode")
            
            # Login with credentials (or anonymous if no credentials available)
            if username and password:
                logger.debug(f"Logging in as user '{username}'")
                ftp.login(username, password)
                logger.info(f"Successfully connected to FTP service at {ip} (authenticated as {username})")
            else:
                logger.debug(f"Using anonymous login")
                ftp.login()  # Anonymous login
                logger.info(f"Successfully connected to FTP service at {ip} (anonymous)")
            
            try:
                # Check telescope type and scan appropriately
                if telescope_type == 'DWARF 3':
                    # Check for DWARF folder structure
                    if not self._validate_dwarf_structure(ftp):
                        ftp.quit()
                        return [], "DWARF folder structure not recognized"
                    
                    # Get FITS files from DWARF structure
                    start_time = time.time()
                    fits_files = self._get_fits_files_from_dwarf_ftp(ftp)
                    scan_time = time.time() - start_time
                elif telescope_type == 'Celestron Origin':
                    # Get FITS files from Celestron Origin structure
                    start_time = time.time()
                    fits_files = self._get_fits_files_from_celestron_ftp(ftp, config.get('fits_path', 'RawData'))
                    scan_time = time.time() - start_time
                else:
                    ftp.quit()
                    return [], f"Unsupported FTP telescope type: {telescope_type}"
                
                ftp.quit()
                logger.info(f"Found {len(fits_files)} FITS files in {scan_time:.2f} seconds")
                return fits_files, None
                
            except Exception as e:
                ftp.quit()
                logger.error(f"Error accessing files on {ip}: {e}")
                return [], f"Error accessing files: {e}"
                
        except Exception as e:
            logger.error(f"FTP connection error to {ip}: {e}")
            return [], f"FTP connection error: {e}"
    
    def _get_fits_files_ftps(self, telescope_type, hostname, username=None, password=None):
        """Get FITS files via FTPS protocol (iTelescope)."""
        logger.info(f"Using FTPS connection for {telescope_type}")
        
        if not username or not password:
            logger.error("Username and password required for iTelescope FTPS connection")
            return [], "Username and password required for iTelescope FTPS connection"
        
        try:
            # Create FTPS connection (FTP over TLS)
            from ftplib import FTP_TLS
            ftps = FTP_TLS()
            logger.debug(f"Attempting FTPS connection to {hostname}:21...")
            ftps.connect(hostname, 21, timeout=30)
            
            # Login with user credentials
            ftps.login(username, password)
            
            # Switch to secure data connection
            ftps.prot_p()
            logger.info(f"Successfully connected to FTPS service at {hostname}")
            
            try:
                # Get FITS files from iTelescope structure
                start_time = time.time()
                fits_files = self._get_fits_files_from_itelescope_ftps(ftps, hostname)
                scan_time = time.time() - start_time
                
                ftps.quit()
                logger.info(f"Found {len(fits_files)} FITS files in {scan_time:.2f} seconds")
                return fits_files, None
                
            except Exception as e:
                ftps.quit()
                logger.error(f"Error accessing files on {hostname}: {e}")
                return [], f"Error accessing files: {e}"
                
        except Exception as e:
            logger.error(f"FTPS connection error to {hostname}: {e}")
            return [], f"FTPS connection error: {e}"
    
    def _get_fits_files_from_path_smb(self, conn, share_name, target_path, telescope_type):
        """Get all FITS files from folders ending in '_sub' within the target path."""
        fits_files = []
        visited_paths = set()  # Prevent infinite loops
        max_depth = 10  # Limit recursion depth
        
        def scan_directory(path="", depth=0):
            # Prevent infinite recursion
            if depth > max_depth:
                logger.debug(f"Maximum depth reached at '{path}', stopping recursion")
                return
            
            # Prevent revisiting the same path
            if path in visited_paths:
                return
            visited_paths.add(path)
            
            try:
                # List files in the directory
                logger.debug(f"Scanning directory: '{path}' (depth: {depth})")
                files = conn.listPath(share_name, path if path else "/")
                
                for file_info in files:
                    if file_info.filename in ['.', '..']:
                        continue
                    
                    item_path = os.path.join(path, file_info.filename).replace('\\', '/') if path else file_info.filename
                    
                    if file_info.isDirectory:
                        # If we haven't found the target directory yet, keep looking
                        if not path and file_info.filename == target_path:
                            logger.debug(f"Found target directory: {target_path}")
                            scan_directory(item_path, depth + 1)
                        elif path.startswith(target_path + "/") or path == target_path:
                            # We're inside the target directory
                            # Only scan subdirectories that end with '_sub'
                            if file_info.filename.endswith('_sub'):
                                logger.debug(f"Found _sub directory: {file_info.filename}")
                                scan_directory(item_path, depth + 1)
                            else:
                                logger.debug(f"Skipping non-_sub directory: {file_info.filename}")
                        elif not path:
                            # Still looking for the target directory at root level
                            scan_directory(item_path, depth + 1)
                    else:
                        # Check if it's a FITS file and we're in a _sub folder within the target path
                        current_folder = os.path.basename(path) if path else ""
                        if ((path == target_path or path.startswith(target_path + "/")) and 
                            current_folder.endswith('_sub') and
                            (file_info.filename.lower().endswith('.fits') or 
                             file_info.filename.lower().endswith('.fit'))):
                            
                            logger.debug(f"Found FITS file: {file_info.filename} in {path}")
                            fits_files.append({
                                "name": file_info.filename,
                                "path": item_path,
                                "size": file_info.file_size,
                                "date": str(file_info.last_write_time),
                                "share_name": share_name,
                                "folder_name": current_folder  # Add folder name for header processing
                            })
                
            except Exception as e:
                logger.debug(f"Error scanning directory '{path}': {e}")
        
        # Start scanning from root
        logger.debug(f"Starting scan for target directory: {target_path} (looking for folders ending in '_sub')")
        scan_directory()
        
        logger.debug(f"Scan complete. Found {len(fits_files)} FITS files in _sub folders.")
        return fits_files
    
    def _validate_dwarf_structure(self, ftp):
        """Validate that FTP root contains required DWARF folder structure."""
        try:
            files = ftp.nlst('/')
            required_folders = ['CALI_FRAME', 'DWARF_DARK']
            dwarf_raw_folders = [f for f in files if f.startswith('DWARF_RAW')]
            
            has_required = all(folder in files for folder in required_folders)
            has_dwarf_raw = len(dwarf_raw_folders) > 0
            
            if has_required and has_dwarf_raw:
                logger.info(f"Valid DWARF structure found: {required_folders} + {len(dwarf_raw_folders)} DWARF_RAW folders")
                return True
            else:
                logger.warning(f"DWARF folder structure not recognized. Found: {files}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating DWARF structure: {e}")
            return False
    
    def _get_fits_files_from_dwarf_ftp(self, ftp):
        """Get FITS files from DWARF telescope via FTP."""
        fits_files = []
        
        try:
            # Scan root directory for DWARF_RAW folders (light files)
            files = ftp.nlst('/')
            dwarf_raw_folders = [f for f in files if f.startswith('DWARF_RAW')]
            
            for folder in dwarf_raw_folders:
                logger.debug(f"Scanning DWARF_RAW folder: {folder}")
                self._scan_dwarf_raw_folder(ftp, folder, fits_files)
            
            # Scan calibration folders
            if 'CALI_FRAME' in files:
                logger.debug("Scanning CALI_FRAME folder")
                self._scan_dwarf_cali_folder(ftp, 'CALI_FRAME', fits_files)
            
            if 'DWARF_DARK' in files:
                logger.debug("Scanning DWARF_DARK folder")
                self._scan_dwarf_dark_folder(ftp, 'DWARF_DARK', fits_files)
            
        except Exception as e:
            logger.error(f"Error scanning DWARF FTP structure: {e}")
        
        return fits_files
    
    def _scan_dwarf_raw_folder(self, ftp, folder_name, fits_files):
        """Scan a DWARF_RAW folder for light frame FITS files."""
        try:
            # Parse folder name to extract metadata
            # Expected format: DWARF_RAW_(INSTRUMEN)_(OBJECT)_EXP_(EXPTIME)_GAIN_(GAIN)_(DATE-OBS)
            folder_parts = folder_name.split("_")
            object_name = "Unknown"
            instrument = "Unknown"
            exptime = "Unknown"
            gain = "Unknown"
            
            if len(folder_parts) >= 8:
                try:
                    instrument = folder_parts[2]  # INSTRUMEN
                    object_name = folder_parts[3]  # OBJECT  
                    exptime = folder_parts[5]  # EXPTIME (after EXP)
                    gain = folder_parts[7]  # GAIN (after GAIN)
                except IndexError:
                    logger.warning(f"Could not parse DWARF_RAW folder name: {folder_name}")
            
            ftp.cwd('/')
            ftp.cwd(folder_name)
            files = ftp.nlst('.')
            
            for file in files:
                if file.startswith('failed_'):
                    logger.debug(f"Ignoring failed image: {file}")
                    continue
                    
                if file.lower().endswith('.fits') or file.lower().endswith('.fit'):
                    file_path = f"{folder_name}/{file}"
                    try:
                        size = ftp.size(file)
                    except:
                        size = 0
                    
                    fits_files.append({
                        "name": file,
                        "path": file_path,
                        "size": size,
                        "date": "Unknown",
                        "share_name": "ftp_root",
                        "folder_name": folder_name,
                        "telescope_type": "DWARF 3",
                        "file_type": "light",
                        "object": object_name,
                        "instrument": instrument,
                        "exptime": exptime,
                        "gain": gain
                    })
                    logger.debug(f"Found DWARF light file: {file_path} (Object: {object_name}, Instrument: {instrument})")
                    
        except Exception as e:
            logger.error(f"Error scanning DWARF_RAW folder {folder_name}: {e}")
    
    def _scan_dwarf_cali_folder(self, ftp, folder_name, fits_files):
        """Scan CALI_FRAME folder for calibration master frames."""
        try:
            ftp.cwd('/')
            ftp.cwd(folder_name)
            
            # Look for bias, dark, flat folders
            cali_types = ['bias', 'dark', 'flat']
            folders = ftp.nlst('.')
            
            for cali_type in cali_types:
                if cali_type in folders:
                    self._scan_dwarf_cali_type_folder(ftp, f"{folder_name}/{cali_type}", cali_type, fits_files)
                    
        except Exception as e:
            logger.error(f"Error scanning CALI_FRAME folder: {e}")
    
    def _scan_dwarf_cali_type_folder(self, ftp, folder_path, cali_type, fits_files):
        """Scan a calibration type folder (bias/dark/flat) for cam_0 and cam_1 subfolders."""
        try:
            ftp.cwd('/')
            ftp.cwd(folder_path)
            folders = ftp.nlst('.')
            
            # Look for cam_0 (TELE) and cam_1 (WIDE) folders
            for cam_folder in ['cam_0', 'cam_1']:
                if cam_folder in folders:
                    instrument = 'TELE' if cam_folder == 'cam_0' else 'WIDE'
                    self._scan_dwarf_cam_folder(ftp, f"{folder_path}/{cam_folder}", cali_type, instrument, fits_files)
                    
        except Exception as e:
            logger.error(f"Error scanning calibration type folder {folder_path}: {e}")
    
    def _scan_dwarf_cam_folder(self, ftp, folder_path, cali_type, instrument, fits_files):
        """Scan a camera folder for FITS files."""
        try:
            ftp.cwd('/')
            ftp.cwd(folder_path)
            files = ftp.nlst('.')
            
            for file in files:
                if file.lower().endswith('.fits') or file.lower().endswith('.fit'):
                    try:
                        size = ftp.size(file)
                    except:
                        size = 0
                    
                    fits_files.append({
                        "name": file,
                        "path": f"{folder_path}/{file}",
                        "size": size,
                        "date": "Unknown",
                        "share_name": "ftp_root",
                        "folder_name": os.path.basename(folder_path),
                        "telescope_type": "DWARF 3",
                        "file_type": f"master_{cali_type}",
                        "instrument": instrument,
                        "calibration_type": cali_type
                    })
                    logger.debug(f"Found DWARF {cali_type} master file: {folder_path}/{file}")
                    
        except Exception as e:
            logger.error(f"Error scanning camera folder {folder_path}: {e}")
    
    def _scan_dwarf_dark_folder(self, ftp, folder_name, fits_files):
        """Scan DWARF_DARK folder for dark library files."""
        try:
            ftp.cwd('/')
            ftp.cwd(folder_name)
            files = ftp.nlst('.')
            
            for file in files:
                if file.startswith('tele_') and (file.lower().endswith('.fits') or file.lower().endswith('.fit')):
                    try:
                        size = ftp.size(file)
                    except:
                        size = 0
                    
                    fits_files.append({
                        "name": file,
                        "path": f"{folder_name}/{file}",
                        "size": size,
                        "date": "Unknown",
                        "share_name": "ftp_root",
                        "folder_name": folder_name,
                        "telescope_type": "DWARF 3",
                        "file_type": "dark_library",
                        "instrument": "TELE"
                    })
                    logger.debug(f"Found DWARF dark library file: {folder_name}/{file}")
                    
        except Exception as e:
            logger.error(f"Error scanning DWARF_DARK folder: {e}")
    
    def _get_fits_files_from_celestron_ftp(self, ftp, fits_path='RawData'):
        """Get FITS files from Celestron Origin telescope via FTP."""
        fits_files = []
        
        try:
            # Try to access the specified fits_path directory
            logger.debug(f"Scanning Celestron Origin '{fits_path}' folder")
            
            # Test if the directory exists
            try:
                ftp.cwd('/')
                if fits_path:
                    ftp.cwd(fits_path)
                    logger.debug(f"Successfully accessed /{fits_path} directory")
                    ftp.cwd('/')  # Go back to root
                    self._scan_celestron_folder(ftp, fits_path, fits_files)
                else:
                    # Scan from root
                    logger.debug("Scanning from root directory")
                    self._scan_celestron_folder(ftp, '', fits_files)
                    
            except ftplib.error_perm as e:
                # Directory doesn't exist, scan from root instead
                logger.warning(f"Directory '{fits_path}' not found ({e}), scanning from root directory")
                self._scan_celestron_folder(ftp, '', fits_files)
            
        except Exception as e:
            logger.error(f"Error scanning Celestron Origin FTP structure: {e}")
        
        return fits_files
    
    def _scan_celestron_folder(self, ftp, folder_path, fits_files, depth=0, max_depth=5):
        """Recursively scan Celestron Origin folders for FITS files."""
        if depth > max_depth:
            logger.debug(f"Maximum depth reached at '{folder_path}', stopping recursion")
            return
            
        try:
            # Navigate to the folder
            ftp.cwd('/')
            if folder_path:
                ftp.cwd(folder_path)
            
            # Get list of items in current directory
            items = []
            try:
                ftp.retrlines('LIST', items.append)
            except Exception as e:
                logger.debug(f"Could not list directory {folder_path}: {e}")
                return
            
            for item_line in items:
                # Parse FTP LIST output
                parts = item_line.split()
                if len(parts) < 9:
                    continue
                
                permissions = parts[0]
                filename = ' '.join(parts[8:])  # Handle filenames with spaces
                
                # Skip hidden files and current/parent directory references
                if filename.startswith('.') or filename in ['.', '..']:
                    continue
                
                item_path = f"{folder_path}/{filename}" if folder_path else filename
                
                if permissions.startswith('d'):
                    # It's a directory - recurse into it
                    logger.debug(f"Scanning Celestron subdirectory: {item_path}")
                    self._scan_celestron_folder(ftp, item_path, fits_files, depth + 1, max_depth)
                    
                elif filename.lower().endswith(('.fits', '.fit', '.fts')):
                    # It's a FITS file
                    # Extract file size from LIST output (more efficient than using SIZE command)
                    try:
                        size = int(parts[4])
                    except (ValueError, IndexError):
                        size = 0
                    
                    # Extract date from LIST output if possible
                    try:
                        date_str = f"{parts[5]} {parts[6]} {parts[7]}"
                    except:
                        date_str = "Unknown"
                    
                    # Extract object name from filename if possible
                    object_name = self._extract_object_from_filename(filename)
                    
                    fits_files.append({
                        "name": filename,
                        "path": item_path,
                        "size": size,
                        "date": date_str,
                        "share_name": "ftp_root",
                        "folder_name": os.path.basename(folder_path) if folder_path else "root",
                        "telescope_type": "Celestron Origin",
                        "file_type": "light",
                        "object": object_name,
                        "instrument": "Celestron Origin"
                    })
                    logger.debug(f"Found Celestron Origin FITS file: {item_path}")
                    
        except Exception as e:
            logger.error(f"Error scanning Celestron folder {folder_path}: {e}")

    
    def _get_fits_files_from_itelescope_ftps(self, ftps, hostname):
        """Get all calibrated FITS files from iTelescope FTPS server."""
        fits_files = []
        
        try:
            # Start from root directory
            ftps.cwd('/')
            
            # Recursively scan all directories for files starting with 'calibrated'
            self._scan_itelescope_directory(ftps, '', fits_files, hostname)
            
        except Exception as e:
            logger.error(f"Error scanning iTelescope directories: {e}")
            
        return fits_files
    
    def _scan_itelescope_directory(self, ftps, current_path, fits_files, hostname, max_depth=10, current_depth=0):
        """Recursively scan iTelescope directory structure for calibrated files."""
        if current_depth > max_depth:
            logger.debug(f"Maximum depth reached at '{current_path}', stopping recursion")
            return
            
        try:
            # Change to the current directory
            if current_path:
                ftps.cwd('/')
                ftps.cwd(current_path)
            
            # List files and directories
            items = []
            try:
                ftps.retrlines('LIST', items.append)
            except Exception as e:
                logger.debug(f"Could not list directory {current_path}: {e}")
                return
            
            for item_line in items:
                # Parse FTP LIST output (Unix-style)
                # Example: -rw-r--r--   1 user group      1234 Jan 01 12:00 filename.fits
                parts = item_line.split()
                if len(parts) < 9:
                    continue
                    
                permissions = parts[0]
                filename = ' '.join(parts[8:])  # Handle filenames with spaces
                
                # Skip hidden files and current/parent directory references
                if filename.startswith('.'):
                    continue
                
                item_path = f"{current_path}/{filename}" if current_path else filename
                
                if permissions.startswith('d'):
                    # It's a directory
                    if not current_path:
                        # Root level - only scan directories that start with 'T' or 't'
                        if filename.lower().startswith('t'):
                            logger.debug(f"Scanning root telescope directory: {item_path}")
                            self._scan_itelescope_directory(ftps, item_path, fits_files, hostname, max_depth, current_depth + 1)
                        else:
                            logger.debug(f"Skipping non-telescope root directory: {filename}")
                    else:
                        # Subfolder within telescope directory - scan all subdirectories
                        logger.debug(f"Scanning telescope subdirectory: {item_path}")
                        self._scan_itelescope_directory(ftps, item_path, fits_files, hostname, max_depth, current_depth + 1)
                    
                elif filename.lower().startswith('calibrated') and filename.lower().endswith('.fit.zip'):
                    # It's a calibrated FIT zip file
                    try:
                        # Get file size
                        if current_path:
                            ftps.cwd('/')
                            ftps.cwd(current_path)
                        size = ftps.size(filename)
                    except:
                        size = 0
                    
                    # Extract date from LIST output if possible
                    try:
                        date_str = f"{parts[5]} {parts[6]} {parts[7]}"
                    except:
                        date_str = "Unknown"
                    
                    fits_files.append({
                        "name": filename,
                        "path": item_path,
                        "size": size,
                        "date": date_str,
                        "share_name": "ftps_root",
                        "folder_name": os.path.basename(current_path) if current_path else "root",
                        "telescope_type": "iTelescope",
                        "file_type": "calibrated_light_zip",
                        "object": self._extract_object_from_filename(filename),
                        "instrument": "iTelescope",
                        "hostname": hostname
                    })
                    logger.debug(f"Found iTelescope calibrated file: {item_path}")
                    
        except Exception as e:
            logger.error(f"Error scanning iTelescope directory {current_path}: {e}")
    
    def _extract_object_from_filename(self, filename):
        """Extract object name from telescope filename if possible.
        
        Handles various filename patterns:
        - iTelescope: removes 'calibrated' prefix and extracts first part
        - Celestron Origin: extracts first part of filename before underscore
        - Generic: returns first part of filename as object name
        """
        # This is a basic implementation - may need refinement based on actual filename patterns
        try:
            # Remove 'calibrated' prefix and file extension
            base_name = filename.lower()
            if base_name.startswith('calibrated'):
                base_name = base_name[10:]  # Remove 'calibrated' prefix
            if base_name.startswith('_'):
                base_name = base_name[1:]  # Remove leading underscore
            
            # Remove file extension
            if base_name.endswith('.fit.zip'):
                base_name = base_name[:-8]  # Remove '.fit.zip' extension
            elif base_name.endswith('.fits'):
                base_name = base_name[:-5]
            elif base_name.endswith('.fit'):
                base_name = base_name[:-4]
            elif base_name.endswith('.fts'):
                base_name = base_name[:-4]
            
            # Extract first part which might be object name
            parts = base_name.split('_')
            if parts:
                return parts[0].title()
                
        except Exception:
            pass
            
        return "Unknown"
    
    def download_file(self, telescope_type, ip, file_info, local_path, username=None, password=None, progress_callback=None):
        """Download a specific file from the telescope."""
        file_name = os.path.basename(file_info['path'])
        logger.info(f"Starting download of {file_name} ({self.format_file_size(file_info['size'])}) from {ip}")
        
        config = self.supported_telescopes.get(telescope_type)
        if not config:
            logger.error(f"Unsupported telescope type for download: {telescope_type}")
            return False, f"Unsupported telescope type: {telescope_type}"
        
        # Check protocol type
        if config.get('protocol') == 'ftp':
            return self._download_file_ftp(telescope_type, ip, file_info, local_path, progress_callback)
        elif config.get('protocol') == 'ftps':
            return self._download_file_ftps(telescope_type, ip, file_info, local_path, username, password, progress_callback)
        else:
            return self._download_file_smb(telescope_type, ip, file_info, local_path, username, password, progress_callback)
    
    def _download_file_smb(self, telescope_type, ip, file_info, local_path, username=None, password=None, progress_callback=None):
        """Download file via SMB protocol."""
        file_name = os.path.basename(file_info['path'])
        
        if not SMB_AVAILABLE:
            logger.error("SMB protocol not available for download")
            return False, "SMB protocol not available"
        
        config = self.supported_telescopes.get(telescope_type)
        username = username or config['default_username']
        password = password or config['default_password']
        
        try:
            # Create SMB connection
            conn = SMBConnection(username, password, "client", "server", use_ntlm_v2=True)
            
            # Try to connect
            logger.debug(f"Connecting to {ip} for file download...")
            connected = conn.connect(str(ip), 445, timeout=10)
            
            if not connected:
                logger.error(f"Failed to connect to SMB service at {ip} for download")
                return False, "Failed to connect to SMB service"
            
            try:
                # Create local directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                logger.debug(f"Downloading to local path: {local_path}")
                
                # Download the file
                start_time = time.time()
                with open(local_path, 'wb') as local_file:
                    file_size = file_info['size']
                    
                    # Use a wrapper class to handle progress tracking and cancellation
                    class ProgressFileWrapper:
                        def __init__(self, file_obj, progress_callback, total_size):
                            self.file_obj = file_obj
                            self.progress_callback = progress_callback
                            self.total_size = total_size
                            self.bytes_written = 0
                            self.cancelled = False
                        
                        def write(self, data):
                            if self.cancelled:
                                raise Exception("Download cancelled by user")
                            
                            result = self.file_obj.write(data)
                            self.bytes_written += len(data)
                            if self.progress_callback:
                                progress = (self.bytes_written / self.total_size) * 100 if self.total_size > 0 else 0
                                # Check if callback returns False (cancellation request)
                                if self.progress_callback(progress) is False:
                                    self.cancelled = True
                                    raise Exception("Download cancelled by user")
                            return result
                        
                        def __getattr__(self, name):
                            return getattr(self.file_obj, name)
                    
                    # Wrap the file object for progress tracking
                    wrapped_file = ProgressFileWrapper(local_file, progress_callback, file_size)
                    
                    conn.retrieveFile(file_info['share_name'], file_info['path'], wrapped_file)
                
                download_time = time.time() - start_time
                download_speed = (file_info['size'] / 1024 / 1024) / download_time if download_time > 0 else 0
                logger.info(f"Successfully downloaded {file_name} in {download_time:.2f}s ({download_speed:.2f} MB/s)")
                
                conn.close()
                return True, None
                
            except Exception as e:
                conn.close()
                logger.error(f"Error downloading {file_name}: {e}")
                return False, f"Error downloading file: {e}"
                
        except Exception as e:
            logger.error(f"Connection error during download of {file_name}: {e}")
            return False, f"Connection error: {e}"
    
    def _download_file_ftp(self, telescope_type, ip, file_info, local_path, progress_callback=None):
        """Download file via FTP protocol."""
        file_name = os.path.basename(file_info['path'])
        
        config = self.supported_telescopes.get(telescope_type)
        username = config.get('default_username')
        password = config.get('default_password')
        
        logger.debug(f"FTP download credentials: username={'<set>' if username else '<none>'}, password={'<set>' if password else '<none>'}")
        
        try:
            # Create FTP connection
            ftp = ftplib.FTP()
            logger.debug(f"Connecting to {ip} for FTP file download...")
            ftp.connect(ip, 21, timeout=10)
            
            # Set passive mode (required by many FTP servers behind firewalls/NAT)
            ftp.set_pasv(True)
            logger.debug("Enabled passive FTP mode for download")
            
            # Login with credentials (or anonymous)
            if username and password:
                logger.debug(f"Logging in as user '{username}' for download")
                ftp.login(username, password)
                logger.debug(f"FTP login successful (authenticated as {username})")
            else:
                logger.debug(f"Using anonymous login for download")
                ftp.login()  # Anonymous login
                logger.debug(f"FTP login successful (anonymous)")
            
            try:
                # Create local directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                logger.debug(f"Downloading to local path: {local_path}")
                
                # Download the file
                start_time = time.time()
                
                with open(local_path, 'wb') as local_file:
                    def progress_wrapper(data):
                        if progress_callback:
                            # Simple progress tracking for FTP (not as detailed as SMB)
                            progress_callback(50)  # Basic progress indication
                        local_file.write(data)
                    
                    ftp.retrbinary(f'RETR {file_info["path"]}', progress_wrapper)
                
                download_time = time.time() - start_time
                download_speed = (file_info['size'] / 1024 / 1024) / download_time if download_time > 0 else 0
                logger.info(f"Successfully downloaded {file_name} in {download_time:.2f}s ({download_speed:.2f} MB/s)")
                
                ftp.quit()
                return True, None
                
            except Exception as e:
                ftp.quit()
                logger.error(f"Error downloading {file_name}: {e}")
                return False, f"Error downloading file: {e}"
                
        except Exception as e:
            logger.error(f"FTP connection error during download of {file_name}: {e}")
            return False, f"FTP connection error: {e}"
    
    def _download_file_ftps(self, telescope_type, hostname, file_info, local_path, username=None, password=None, progress_callback=None):
        """Download file via FTPS protocol (iTelescope)."""
        file_name = os.path.basename(file_info['path'])
        
        if not username or not password:
            logger.error("Username and password required for iTelescope FTPS download")
            return False, "Username and password required"
        
        try:
            # Create FTPS connection
            from ftplib import FTP_TLS
            ftps = FTP_TLS()
            ftps.connect(hostname, 21, timeout=30)
            ftps.login(username, password)
            ftps.prot_p()  # Switch to secure data connection
            
            try:
                # Navigate to the directory containing the file
                file_dir = os.path.dirname(file_info['path'])
                if file_dir:
                    ftps.cwd('/')
                    ftps.cwd(file_dir)
                
                # Download the file with progress tracking
                total_size = file_info.get('size', 0)
                downloaded = 0
                
                def progress_handler(data):
                    nonlocal downloaded
                    downloaded += len(data)
                    if progress_callback and total_size > 0:
                        progress = int((downloaded / total_size) * 100)
                        progress_callback(f"Downloading {file_name}: {progress}%")
                    local_file.write(data)
                
                with open(local_path, 'wb') as local_file:
                    ftps.retrbinary(f'RETR {file_name}', progress_handler)
                
                ftps.quit()
                logger.info(f"Successfully downloaded {file_name} to {local_path}")
                return True, None
                
            except Exception as e:
                ftps.quit()
                logger.error(f"Error downloading {file_name}: {e}")
                return False, f"Error downloading file: {e}"
                
        except Exception as e:
            logger.error(f"FTPS connection error during download of {file_name}: {e}")
            return False, f"FTPS connection error: {e}"
    
    def format_file_size(self, size_bytes):
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def delete_file(self, telescope_type, ip, file_info):
        """Delete a file from the telescope."""
        if not SMB_AVAILABLE:
            return False, "SMB library not available"
        
        try:
            config = self.supported_telescopes.get(telescope_type)
            if not config:
                return False, f"Unsupported telescope type: {telescope_type}"
            
            conn = SMBConnection(
                config['default_username'], 
                config['default_password'], 
                "astrofiler", 
                ip,
                use_ntlm_v2=True
            )
            
            if not conn.connect(ip, 445):
                return False, "Failed to connect to telescope"
            
            try:
                # Delete the file
                file_name = file_info['name']
                file_path = file_info['path']
                share_name = file_info['share_name']
                
                logger.debug(f"Deleting file {file_name} from {ip}")
                conn.deleteFiles(share_name, file_path)
                
                logger.info(f"Successfully deleted {file_name} from telescope")
                conn.close()
                return True, None
                
            except Exception as e:
                conn.close()
                logger.error(f"Error deleting {file_name}: {e}")
                return False, f"Error deleting file: {e}"
                
        except Exception as e:
            logger.error(f"Connection error during deletion of {file_info.get('name', 'unknown file')}: {e}")
            return False, f"Connection error: {e}"

# Global instance
smart_telescope_manager = SmartTelescopeManager()


def _update_calibrated_frame_header(header, calibration_steps, bias_master, dark_master, 
                                   flat_master, calibrated_data, light_path):
    """
    Update FITS header of calibrated light frame with comprehensive metadata.
    
    Adds astronomy-standard headers for calibrated light frames including:
    - Calibration identification and status
    - Master frame references with full paths and checksums
    - Processing history and timestamps
    - Quality metrics and statistics
    - Software version and processing parameters
    
    Args:
        header: FITS header object to update
        calibration_steps: List of calibration steps applied
        bias_master: Path to bias master (or None)
        dark_master: Path to dark master (or None)
        flat_master: Path to flat master (or None)
        calibrated_data: Calibrated image data array
        light_path: Original light frame path
    """
    import numpy as np
    import hashlib
    import os
    from datetime import datetime
    
    # =================================================================
    # PRIMARY CALIBRATION IDENTIFICATION
    # =================================================================
    header['CALIBRAT'] = (True, 'Image has been calibrated')
    header['IMAGETYP'] = ('LIGHT_CAL', 'Calibrated light frame')
    header['CALDATE'] = (datetime.now().isoformat(), 'Calibration processing timestamp')
    header['CALSOFT'] = ('AstroFiler v1.2.0', 'Calibration software and version')
    
    # Original file reference
    header['ORIGFILE'] = (os.path.basename(light_path), 'Original uncalibrated filename')
    header['ORIGPATH'] = (light_path, 'Full path to original file')
    
    # =================================================================
    # CALIBRATION PROCESS HISTORY
    # =================================================================
    if calibration_steps:
        # Join steps with proper separator for astronomy software compatibility
        steps_str = ' -> '.join(calibration_steps)
        header['CALSTEPS'] = (steps_str, 'Calibration steps applied in order')
        header['NSTEPS'] = (len(calibration_steps), 'Number of calibration steps')
        
        # Add individual step details for machine readability
        for i, step in enumerate(calibration_steps, 1):
            if i <= 9:  # FITS keyword limit
                header[f'STEP{i:01d}'] = (step, f'Calibration step {i}')
    
    # =================================================================
    # MASTER FRAME REFERENCES AND METADATA
    # =================================================================
    master_count = 0
    
    if bias_master and os.path.exists(bias_master):
        master_count += 1
        header['BIASMAST'] = (os.path.basename(bias_master), 'Master bias frame filename')
        header['BIASREF'] = (bias_master, 'Full path to master bias frame')
        
        # Add master frame checksum for verification
        try:
            with open(bias_master, 'rb') as f:
                bias_hash = hashlib.md5(f.read()).hexdigest()[:16]  # Truncate for FITS
            header['BIASMD5'] = (bias_hash, 'MD5 checksum of bias master (truncated)')
        except:
            pass
            
        # Try to get master frame creation info
        try:
            from astropy.io import fits
            with fits.open(bias_master) as hdul:
                bias_header = hdul[0].header
                if 'CREATED' in bias_header:
                    header['BIASMADE'] = (bias_header['CREATED'], 'Bias master creation date')
                if 'NFRAMES' in bias_header:
                    header['BIASN'] = (bias_header['NFRAMES'], 'Number of frames in bias master')
        except:
            pass
    
    if dark_master and os.path.exists(dark_master):
        master_count += 1
        header['DARKMAST'] = (os.path.basename(dark_master), 'Master dark frame filename')
        header['DARKREF'] = (dark_master, 'Full path to master dark frame')
        
        try:
            with open(dark_master, 'rb') as f:
                dark_hash = hashlib.md5(f.read()).hexdigest()[:16]
            header['DARKMD5'] = (dark_hash, 'MD5 checksum of dark master (truncated)')
        except:
            pass
            
        try:
            from astropy.io import fits
            with fits.open(dark_master) as hdul:
                dark_header = hdul[0].header
                if 'CREATED' in dark_header:
                    header['DARKMADE'] = (dark_header['CREATED'], 'Dark master creation date')
                if 'NFRAMES' in dark_header:
                    header['DARKN'] = (dark_header['NFRAMES'], 'Number of frames in dark master')
                if 'EXPTIME' in dark_header:
                    header['DARKEXP'] = (dark_header['EXPTIME'], 'Dark master exposure time')
        except:
            pass
    
    if flat_master and os.path.exists(flat_master):
        master_count += 1
        header['FLATMAST'] = (os.path.basename(flat_master), 'Master flat frame filename')
        header['FLATREF'] = (flat_master, 'Full path to master flat frame')
        
        try:
            with open(flat_master, 'rb') as f:
                flat_hash = hashlib.md5(f.read()).hexdigest()[:16]
            header['FLATMD5'] = (flat_hash, 'MD5 checksum of flat master (truncated)')
        except:
            pass
            
        try:
            from astropy.io import fits
            with fits.open(flat_master) as hdul:
                flat_header = hdul[0].header
                if 'CREATED' in flat_header:
                    header['FLATMADE'] = (flat_header['CREATED'], 'Flat master creation date')
                if 'NFRAMES' in flat_header:
                    header['FLATN'] = (flat_header['NFRAMES'], 'Number of frames in flat master')
                if 'FILTER' in flat_header:
                    header['FLATFILT'] = (flat_header['FILTER'], 'Flat master filter')
        except:
            pass
    
    header['NMASTERS'] = (master_count, 'Number of master frames applied')
    
    # =================================================================
    # CALIBRATION QUALITY METRICS
    # =================================================================
    # Basic image statistics
    header['CALMEAN'] = (float(np.mean(calibrated_data)), 'Mean pixel value after calibration')
    header['CALMED'] = (float(np.median(calibrated_data)), 'Median pixel value after calibration')
    header['CALSTD'] = (float(np.std(calibrated_data)), 'Standard deviation after calibration')
    header['CALNOISE'] = (float(np.std(calibrated_data)), 'Noise level (RMS) after calibration')
    
    # Dynamic range and signal metrics
    min_val = float(np.min(calibrated_data))
    max_val = float(np.max(calibrated_data))
    header['CALMIN'] = (min_val, 'Minimum pixel value after calibration')
    header['CALMAX'] = (max_val, 'Maximum pixel value after calibration')
    header['CALRANGE'] = (max_val - min_val, 'Dynamic range after calibration')
    
    # Signal-to-noise estimation
    if np.std(calibrated_data) > 0:
        snr_estimate = np.mean(calibrated_data) / np.std(calibrated_data)
        header['CALSNR'] = (float(snr_estimate), 'Estimated signal-to-noise ratio')
    
    # Hot/dead pixel detection
    data_flat = calibrated_data.flatten()
    sorted_data = np.sort(data_flat)
    p99_9 = sorted_data[int(len(sorted_data) * 0.999)]
    p0_1 = sorted_data[int(len(sorted_data) * 0.001)]
    
    hot_pixels = np.sum(calibrated_data > p99_9)
    dead_pixels = np.sum(calibrated_data < p0_1)
    
    header['CALHOT'] = (int(hot_pixels), 'Number of potential hot pixels')
    header['CALDEAD'] = (int(dead_pixels), 'Number of potential dead pixels')
    
    # =================================================================
    # PROCESSING ENVIRONMENT AND PARAMETERS
    # =================================================================
    header['CALHOST'] = (os.environ.get('COMPUTERNAME', 'Unknown'), 'Computer used for calibration')
    header['CALOS'] = (f"{os.name}", 'Operating system used for calibration')
    
    # Processing parameters
    header['CALNEG'] = (bool(np.any(calibrated_data < 0)), 'Negative values present after calibration')
    header['CALCLIP'] = ('Applied' if np.any(calibrated_data < 0) else 'None', 'Negative value clipping applied')
    
    # =================================================================
    # ASTRONOMY SOFTWARE COMPATIBILITY HEADERS
    # =================================================================
    # Common headers expected by popular astronomy software
    header['PROCESSED'] = (True, 'Frame has been processed/calibrated')
    header['REDUCER'] = ('AstroFiler', 'Software used for calibration')
    header['REDDATE'] = (datetime.now().strftime('%Y-%m-%d'), 'Date of calibration processing')
    
    # Compatibility with common pipeline formats
    header['HISTORY'] = f"CALIBRATED by AstroFiler v1.2.0 on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if calibration_steps:
        header['HISTORY'] = f"Applied: {' -> '.join(calibration_steps)}"
    
    # =================================================================
    # DATA INTEGRITY AND VERIFICATION
    # =================================================================
    header['CALSUM'] = (float(np.sum(calibrated_data)), 'Checksum: sum of all pixel values')
    header['CALN'] = (int(calibrated_data.size), 'Total number of pixels')
    
    # Version tracking for future compatibility
    header['CALVER'] = ('1.0', 'Calibration header format version')


def calibrate_light_frame(light_path, dark_master=None, flat_master=None, bias_master=None, 
                         output_path=None, progress_callback=None):
    """
    Calibrate a single light frame using master calibration frames.
    
    Args:
        light_path (str): Path to the light frame FITS file
        dark_master (str): Path to master dark frame (optional)
        flat_master (str): Path to master flat frame (optional)
        bias_master (str): Path to master bias frame (optional)
        output_path (str): Path for calibrated output file (optional, auto-generated if not provided)
        progress_callback (callable): Optional callback for progress updates
        
    Returns:
        dict: Calibration result with output path and metadata
    """
    try:
        if progress_callback:
            progress_callback(f"Starting calibration of {os.path.basename(light_path)}")
            
        # Load light frame
        with fits.open(light_path) as hdul:
            light_data = hdul[0].data.astype(np.float32)
            light_header = hdul[0].header.copy()
            
        if light_data is None or light_data.size == 0:
            return {"error": "No image data found in light frame"}
            
        calibrated_data = light_data.copy()
        calibration_steps = []
        
        # Apply bias correction first
        if bias_master and os.path.exists(bias_master):
            if progress_callback:
                progress_callback("Applying bias correction...")
            try:
                with fits.open(bias_master) as hdul:
                    bias_data = hdul[0].data.astype(np.float32)
                calibrated_data -= bias_data
                calibration_steps.append(f"BIAS: {os.path.basename(bias_master)}")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Warning: Failed to apply bias correction: {e}")
        
        # Apply dark correction
        if dark_master and os.path.exists(dark_master):
            if progress_callback:
                progress_callback("Applying dark correction...")
            try:
                with fits.open(dark_master) as hdul:
                    dark_data = hdul[0].data.astype(np.float32)
                    dark_header = hdul[0].header
                    
                # Scale dark frame by exposure time ratio if needed
                light_exptime = light_header.get('EXPTIME', 1.0)
                dark_exptime = dark_header.get('EXPTIME', 1.0)
                
                if dark_exptime > 0 and light_exptime != dark_exptime:
                    scale_factor = light_exptime / dark_exptime
                    dark_data *= scale_factor
                    calibration_steps.append(f"DARK: {os.path.basename(dark_master)} (scaled {scale_factor:.3f})")
                else:
                    calibration_steps.append(f"DARK: {os.path.basename(dark_master)}")
                
                calibrated_data -= dark_data
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Warning: Failed to apply dark correction: {e}")
        
        # Apply flat correction
        if flat_master and os.path.exists(flat_master):
            if progress_callback:
                progress_callback("Applying flat correction...")
            try:
                with fits.open(flat_master) as hdul:
                    flat_data = hdul[0].data.astype(np.float32)
                    
                # Normalize flat field (avoid division by zero)
                flat_mean = np.mean(flat_data[flat_data > 0])
                flat_normalized = flat_data / flat_mean
                flat_normalized[flat_normalized <= 0] = 1.0  # Avoid division by zero
                
                calibrated_data /= flat_normalized
                calibration_steps.append(f"FLAT: {os.path.basename(flat_master)}")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Warning: Failed to apply flat correction: {e}")
        
        # Generate output path if not provided
        if not output_path:
            base_dir = os.path.dirname(light_path)
            base_name = os.path.splitext(os.path.basename(light_path))[0]
            output_path = os.path.join(base_dir, f"{base_name}_calibrated.fits")
            
        # Update FITS header with comprehensive calibration information
        _update_calibrated_frame_header(light_header, calibration_steps, 
                                      bias_master, dark_master, flat_master, 
                                      calibrated_data, light_path)
        
        if progress_callback:
            progress_callback("Saving calibrated frame...")
            
        # Save calibrated frame
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Ensure data is in appropriate range and type
        calibrated_data = np.clip(calibrated_data, 0, None)  # Remove negative values
        
        hdu = fits.PrimaryHDU(data=calibrated_data.astype(np.float32), header=light_header)
        hdu.writeto(output_path, overwrite=True)
        
        if progress_callback:
            progress_callback(f"Calibration complete: {os.path.basename(output_path)}")
            
        return {
            "success": True,
            "output_path": output_path,
            "calibration_steps": calibration_steps,
            "noise_level": float(np.std(calibrated_data)),
            "mean_level": float(np.mean(calibrated_data)),
            "dynamic_range": float(np.max(calibrated_data) - np.min(calibrated_data))
        }
        
    except Exception as e:
        return {"error": f"Failed to calibrate light frame: {str(e)}"}


def calibrate_session_lights(session_id, progress_callback=None, force_recalibrate=False):
    """
    Calibrate all light frames in a session using available master frames.
    
    Args:
        session_id (int): Database ID of the session to calibrate
        progress_callback (callable): Optional callback for progress updates
        force_recalibrate (bool): If True, recalibrate even if already calibrated
        
    Returns:
        dict: Calibration results with statistics
    """
    try:
        if progress_callback:
            progress_callback(f"Starting calibration for session {session_id}")
            
        # Get session and check if it exists
        session = fitsSession.get_by_id(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}
            
        # Check for master frames
        master_frames = get_session_master_frames(session_id)
        if not any(master_frames.values()):
            return {"error": "No master calibration frames available for this session"}
            
        # Get light frames from session
        light_files = fitsFile.select().where(
            (fitsFile.fitsSession == session) & 
            (fitsFile.imageType.in_(['LIGHT', 'Light', 'light', 'Science', 'science', '']))
        )
        
        if not light_files.exists():
            return {"error": "No light frames found in session"}
            
        total_lights = light_files.count()
        calibrated_count = 0
        skipped_count = 0
        error_count = 0
        results = []
        
        for i, light_file in enumerate(light_files, 1):
            if progress_callback:
                progress_callback(f"Processing light frame {i}/{total_lights}: {light_file.fileName}")
                
            # Check if already calibrated (unless forcing recalibration)
            if not force_recalibrate:
                # Look for existing calibrated version
                calibrated_path = os.path.join(
                    os.path.dirname(light_file.filePath),
                    f"{os.path.splitext(light_file.fileName)[0]}_calibrated.fits"
                )
                if os.path.exists(calibrated_path):
                    if progress_callback:
                        progress_callback(f"Skipping already calibrated: {light_file.fileName}")
                    skipped_count += 1
                    continue
                    
            # Calibrate the light frame
            result = calibrate_light_frame(
                light_path=light_file.filePath,
                dark_master=master_frames['dark'],
                flat_master=master_frames['flat'],
                bias_master=master_frames['bias'],
                progress_callback=progress_callback
            )
            
            if result.get('success'):
                calibrated_count += 1
                results.append({
                    "light_file": light_file.fileName,
                    "output_file": os.path.basename(result['output_path']),
                    "calibration_steps": result['calibration_steps'],
                    "noise_level": result['noise_level']
                })
            else:
                error_count += 1
                if progress_callback:
                    progress_callback(f"Error calibrating {light_file.fileName}: {result.get('error', 'Unknown error')}")
                    
        if progress_callback:
            progress_callback(f"Calibration complete: {calibrated_count} processed, {skipped_count} skipped, {error_count} errors")
            
        return {
            "success": True,
            "session_id": session_id,
            "total_lights": total_lights,
            "calibrated_count": calibrated_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "results": results,
            "master_frames_used": {k: os.path.basename(v) if v else None for k, v in master_frames.items()}
        }
        
    except Exception as e:
        return {"error": f"Failed to calibrate session lights: {str(e)}"}


def get_session_master_frames(session_id):
    """
    Get the paths to master calibration frames for a session.
    
    Args:
        session_id (int): Database ID of the session
        
    Returns:
        dict: Paths to master frames (dark, flat, bias) or None if not available
    """
    try:
        session = fitsSession.get_by_id(session_id)
        if not session:
            return {"dark": None, "flat": None, "bias": None}
            
        # Get the auto-calibration session IDs
        dark_session_id = session.auto_calibration_dark_session_id
        flat_session_id = session.auto_calibration_flat_session_id
        bias_session_id = session.auto_calibration_bias_session_id
        
        masters = {"dark": None, "flat": None, "bias": None}
        
        # Look for master dark
        if dark_session_id and session.master_dark_created:
            dark_session = fitsSession.get_by_id(dark_session_id)
            if dark_session:
                master_path = os.path.join(
                    get_master_calibration_path(),
                    f"master_dark_session_{dark_session_id}.fits"
                )
                if os.path.exists(master_path):
                    masters["dark"] = master_path
                    
        # Look for master flat
        if flat_session_id and session.master_flat_created:
            flat_session = fitsSession.get_by_id(flat_session_id)
            if flat_session:
                master_path = os.path.join(
                    get_master_calibration_path(),
                    f"master_flat_session_{flat_session_id}.fits"
                )
                if os.path.exists(master_path):
                    masters["flat"] = master_path
                    
        # Look for master bias
        if bias_session_id and session.master_bias_created:
            bias_session = fitsSession.get_by_id(bias_session_id)
            if bias_session:
                master_path = os.path.join(
                    get_master_calibration_path(),
                    f"master_bias_session_{bias_session_id}.fits"
                )
                if os.path.exists(master_path):
                    masters["bias"] = master_path
                    
        return masters
        
    except Exception as e:
        logging.error(f"Failed to get master frames for session {session_id}: {e}")
        return {"dark": None, "flat": None, "bias": None}
