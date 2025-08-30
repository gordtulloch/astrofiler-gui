#!/usr/bin/env python3
"""
Astrofiler Smart Telescope Integration
Handles communication with smart telescopes like SEESTAR for automated file retrieval.
"""

import socket
import ipaddress
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

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
            }
        }
    
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
        
        return False
    
    def find_telescope(self, telescope_type, network_range=None, hostname=None):
        """Find a specific telescope on the network."""
        logger.info(f"Starting search for {telescope_type} telescope (hostname={hostname}, network={network_range})")
        
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
                    
                    # For other telescope types, check if the provided hostname matches
                    if self.is_target_device(hostname, telescope_type):
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
        
        # Scan network for device (no reverse DNS lookups for SeeStar)
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
        if self.check_smb_port(ip):
            # For SeeStar, skip reverse DNS lookups due to firmware changes
            # Only rely on SMB port availability and network position
            if telescope_type == 'SeeStar':
                # SeeStar devices typically respond on SMB port 445
                # Since reverse DNS is disabled, we'll consider any SMB-enabled device
                # in the expected IP range as a potential SeeStar
                # User will need to verify via the hostname field in the GUI
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
        
        if not SMB_AVAILABLE:
            logger.error("SMB protocol not available")
            return [], "SMB protocol not available"
        
        config = self.supported_telescopes.get(telescope_type)
        if not config:
            logger.error(f"Unsupported telescope type: {telescope_type}")
            return [], f"Unsupported telescope type: {telescope_type}"
        
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
                fits_files = self._get_fits_files_from_path(conn, share_name, fits_path)
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
    
    def _get_fits_files_from_path(self, conn, share_name, target_path):
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
    
    def download_file(self, telescope_type, ip, file_info, local_path, username=None, password=None, progress_callback=None):
        """Download a specific file from the telescope."""
        file_name = os.path.basename(file_info['path'])
        logger.info(f"Starting download of {file_name} ({self.format_file_size(file_info['size'])}) from {ip}")
        
        if not SMB_AVAILABLE:
            logger.error("SMB protocol not available for download")
            return False, "SMB protocol not available"
        
        config = self.supported_telescopes.get(telescope_type)
        if not config:
            logger.error(f"Unsupported telescope type for download: {telescope_type}")
            return False, f"Unsupported telescope type: {telescope_type}"
        
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
