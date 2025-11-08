#!/usr/bin/env python3
"""
Download.py - Command line utility to download files from smart telescopes

This script connects to smart telescopes and downloads FITS files to the incoming folder.
Supports SeeStar, StellarMate, and iTelescope with their respective protocols (SMB/FTPS).

Usage:
    python Download.py [options]

Options:
    -h, --help              Show this help message and exit
    -v, --verbose           Enable verbose logging
    -c, --config            Path to configuration file (default: astrofiler.ini)
    -t, --telescope TYPE    Telescope type: SeeStar, StellarMate, iTelescope
    -H, --hostname HOST     Hostname or IP address of telescope
    -n, --network RANGE     Network range to scan (e.g., 192.168.1.0/24)
    -d, --destination DIR   Download destination folder
    -u, --username USER     Username for telescope connection (iTelescope)
    -p, --password PASS     Password for telescope connection (iTelescope)
    --delete                Delete files from telescope after download
    --dry-run               Show what would be downloaded without downloading

Telescope Types:
    SeeStar     - SeeStar S50 smart telescope (SMB protocol)
    StellarMate - StellarMate device (SMB protocol)  
    DWARF 3     - DWARF 3 smart telescope (FTP protocol)
    iTelescope  - iTelescope network (FTPS protocol)

Examples:
    # Download from SeeStar with auto-discovery
    python Download.py -t SeeStar -v
    
    # Download from DWARF 3 at default IP
    python Download.py -t "DWARF 3" -v
    
    # Download from specific iTelescope with credentials
    python Download.py -t iTelescope -u username -p password
    
    # Download from StellarMate at specific IP
    python Download.py -t StellarMate -H 192.168.1.100
    
    # Dry run to see what files are available
    python Download.py -t SeeStar --dry-run -v
"""

import sys
import os
import argparse
import logging
import configparser
from pathlib import Path

# Add parent directory to path to import astrofiler modules
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
import setup_path  # Configure Python path for new package structure

from astrofiler.services.telescope import SmartTelescopeManager
from astrofiler.core import fitsProcessing

def setup_logging(verbose=False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from some libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('SMB').setLevel(logging.WARNING)

def load_config(config_path):
    """Load configuration file."""
    config = configparser.ConfigParser()
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    config.read(config_path)
    return config

def get_destination_folder(config, override_path=None):
    """Get destination folder from config or override."""
    if override_path:
        return override_path
    
    try:
        source_folder = config.get('DEFAULT', 'source')
        if not source_folder:
            raise ValueError("source folder not configured")
        return source_folder
    except (configparser.NoOptionError, configparser.NoSectionError):
        raise ValueError("source folder not found in configuration")

def download_files(telescope_type, hostname, network, destination, username=None, password=None, delete_files=False, dry_run=False):
    """Download files from smart telescope."""
    logger = logging.getLogger(__name__)
    
    # Initialize smart telescope manager
    manager = SmartTelescopeManager()
    
    logger.info(f"Starting download from {telescope_type} telescope")
    
    # Find telescope
    if hostname:
        logger.info(f"Using provided hostname: {hostname}")
        ip, error = manager.find_telescope(telescope_type, hostname=hostname)
    else:
        logger.info(f"Scanning network for {telescope_type} telescope...")
        ip, error = manager.find_telescope(telescope_type, network_range=network)
    
    if error:
        logger.error(f"Failed to find telescope: {error}")
        return False
    
    if not ip:
        logger.error(f"No {telescope_type} telescope found")
        return False
    
    logger.info(f"Found {telescope_type} telescope at {ip}")
    
    # Get credentials for iTelescope if not provided
    if telescope_type == "iTelescope":
        if not username or not password:
            logger.info("Getting iTelescope credentials from configuration...")
            cred_username, cred_password = manager.get_itelescope_credentials()
            username = username or cred_username
            password = password or cred_password
            
            if not username or not password:
                logger.error("iTelescope credentials required. Use -u and -p options or configure in astrofiler.ini")
                return False
    
    # Get file list
    logger.info("Scanning for FITS files...")
    fits_files, error = manager.get_fits_files(telescope_type, ip, username, password)
    
    if error:
        logger.error(f"Failed to get file list: {error}")
        return False
    
    if not fits_files:
        logger.info("No FITS files found on telescope")
        return True
    
    logger.info(f"Found {len(fits_files)} FITS files")
    
    if dry_run:
        logger.info("DRY RUN - Files that would be downloaded:")
        for i, file_info in enumerate(fits_files, 1):
            size_mb = file_info.get('size', 0) / (1024 * 1024)
            logger.info(f"  {i:3d}. {file_info['name']} ({size_mb:.1f} MB)")
        return True
    
    # Create destination directory if it doesn't exist
    os.makedirs(destination, exist_ok=True)
    
    # Download files
    downloaded_count = 0
    failed_count = 0
    registered_count = 0
    
    for i, file_info in enumerate(fits_files, 1):
        file_name = file_info['name']
        logger.info(f"Downloading {i}/{len(fits_files)}: {file_name}")
        
        # Create local file path (directly in destination for iTelescope, preserve structure for others)
        if telescope_type == 'iTelescope':
            local_path = os.path.join(destination, file_name)
        else:
            folder_name = file_info.get('folder_name', 'unknown')
            local_dir = os.path.join(destination, folder_name)
            os.makedirs(local_dir, exist_ok=True)
            local_path = os.path.join(local_dir, file_name)
        
        # Download file
        success, error = manager.download_file(telescope_type, ip, file_info, local_path, username, password)
        
        if success:
            downloaded_count += 1
            logger.info(f"Downloaded: {file_name}")
            
            # Unzip if necessary
            if file_name.lower().endswith('.zip'):
                try:
                    import zipfile
                    zip_dir = os.path.dirname(local_path)
                    
                    with zipfile.ZipFile(local_path, 'r') as zip_ref:
                        file_list = zip_ref.namelist()
                        zip_ref.extractall(zip_dir)
                        
                        # Find extracted FITS files
                        for extracted_file in file_list:
                            if extracted_file.lower().endswith(('.fit', '.fits')):
                                extracted_path = os.path.join(zip_dir, extracted_file)
                                if os.path.exists(extracted_path):
                                    logger.info(f"Extracted: {extracted_file}")
                                    local_path = extracted_path
                                    break
                        
                        # Remove zip file
                        os.remove(local_path if local_path.endswith('.zip') else os.path.join(zip_dir, file_name))
                        
                except Exception as e:
                    logger.warning(f"Error extracting {file_name}: {e}")
            
            # Register in database
            try:
                processor = fitsProcessing()
                root_dir = os.path.dirname(local_path)
                file_name_only = os.path.basename(local_path)
                
                registered_id = processor.registerFitsImage(root_dir, file_name_only, moveFiles=True)
                if registered_id:
                    registered_count += 1
                    logger.info(f"Registered in database: {file_name_only}")
                
            except Exception as e:
                logger.warning(f"Failed to register {file_name_only}: {e}")
            
            # Delete from telescope if requested
            if delete_files:
                delete_success, delete_error = manager.delete_file(telescope_type, ip, file_info)
                if delete_success:
                    logger.info(f"Deleted from telescope: {file_name}")
                else:
                    logger.warning(f"Failed to delete {file_name}: {delete_error}")
        
        else:
            failed_count += 1
            logger.error(f"Failed to download {file_name}: {error}")
    
    logger.info(f"Download completed: {downloaded_count} downloaded, {registered_count} registered, {failed_count} failed")
    return failed_count == 0

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download files from smart telescopes",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('-c', '--config', default='astrofiler.ini',
                        help='Path to configuration file (default: astrofiler.ini)')
    parser.add_argument('-t', '--telescope', required=True,
                        choices=['SeeStar', 'StellarMate', 'DWARF 3', 'iTelescope'],
                        help='Telescope type')
    parser.add_argument('-H', '--hostname',
                        help='Hostname or IP address of telescope')
    parser.add_argument('-n', '--network',
                        help='Network range to scan (e.g., 192.168.1.0/24)')
    parser.add_argument('-d', '--destination',
                        help='Download destination folder')
    parser.add_argument('-u', '--username',
                        help='Username for telescope connection (iTelescope)')
    parser.add_argument('-p', '--password',
                        help='Password for telescope connection (iTelescope)')
    parser.add_argument('--delete', action='store_true',
                        help='Delete files from telescope after download')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be downloaded without downloading')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config(args.config)
        logger.info(f"Loaded configuration from {args.config}")
        
        # Get destination folder
        destination = get_destination_folder(config, args.destination)
        logger.info(f"Destination folder: {destination}")
        
        # Validate iTelescope requirements
        if args.telescope == 'iTelescope' and not args.dry_run:
            if not args.username and not args.password:
                # Check if credentials are in config
                try:
                    config_username = config.get('DEFAULT', 'itelescope_username', fallback='')
                    config_password = config.get('DEFAULT', 'itelescope_password', fallback='')
                    if not config_username or not config_password:
                        logger.error("iTelescope requires credentials. Use -u/-p options or configure in astrofiler.ini")
                        return 1
                except Exception:
                    logger.error("iTelescope requires credentials. Use -u/-p options or configure in astrofiler.ini")
                    return 1
        
        # Download files
        success = download_files(
            telescope_type=args.telescope,
            hostname=args.hostname,
            network=args.network,
            destination=destination,
            username=args.username,
            password=args.password,
            delete_files=args.delete,
            dry_run=args.dry_run
        )
        
        if success:
            logger.info("Download operation completed successfully")
            return 0
        else:
            logger.error("Download operation failed")
            return 1
            
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())