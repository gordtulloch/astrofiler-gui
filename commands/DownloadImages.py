#!/usr/bin/env python3
"""
DownloadImages.py - Command line utility to download images from smart telescopes

This script connects to smart telescopes (SeeStar, StellarMate, DWARF 3) and downloads FITS files
directly to the repository structure while registering them in the database.

Usage:
    python DownloadImages.py [options]

Options:
    -h, --help              Show this help message and exit
    -v, --verbose           Enable verbose logging
    -c, --config            Path to configuration file (default: astrofiler.ini)
    -t, --telescope         Telescope type: SeeStar, StellarMate, DWARF (default: SeeStar)
    --hostname              Hostname or IP address of telescope (default: auto-detect)
    --network               Network range to scan (e.g., 192.168.1.0/24)
    --target-dir            Target directory for downloads (default: from config)
    --delete                Delete files from telescope after successful download
    --no-register           Don't register files in database (download only)

Requirements:
    - astrofiler.ini configuration file
    - Network access to telescope
    - Write permissions to target directory
    - Required packages: pysmb (for SMB), ftplib (built-in)

Examples:
    # Download from SeeStar with auto-detection
    python DownloadImages.py
    
    # Download from specific SeeStar hostname
    python DownloadImages.py -t SeeStar --hostname seestar.local
    
    # Download from DWARF 3 telescope
    python DownloadImages.py -t "DWARF 3" --hostname 192.168.88.1
    
    # Download and delete files from telescope
    python DownloadImages.py --delete
    
    # Download with custom target directory
    python DownloadImages.py --target-dir /path/to/downloads
    
    # Download only (don't register in database)
    python DownloadImages.py --no-register
"""

import sys
import os
import argparse
import logging
import configparser
import signal
from datetime import datetime

# Add the parent directory to the path to import astrofiler modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astrofiler_smart import SmartTelescopeManager
from astrofiler_file import fitsProcessing
from astrofiler_db import setup_database

class DownloadImagesCLI:
    """Command line interface for downloading telescope images."""
    
    def __init__(self):
        self.logger = None
        self.smart_telescope_manager = SmartTelescopeManager()
        self.stop_requested = False
        self.downloaded_files = 0
        self.registered_files = 0
        self.failed_files = []
        self.deleted_files = 0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals for graceful shutdown."""
        self.logger.info("Interrupt received, stopping download...")
        self.stop_requested = True
    
    def setup_logging(self, verbose=False):
        """Setup logging configuration."""
        level = logging.DEBUG if verbose else logging.INFO
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Configure logging to both file and console
        logging.basicConfig(
            level=level,
            format=format_str,
            handlers=[
                logging.FileHandler('downloadimages.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        return self.logger
    
    def load_config(self, config_path):
        """Load configuration from file."""
        config = configparser.ConfigParser()
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        config.read(config_path)
        return config
    
    def get_default_target_directory(self, config):
        """Get default target directory from configuration - uses incoming directory."""
        try:
            return config.get('DEFAULT', 'source', fallback=os.getcwd())
        except Exception:
            return os.getcwd()
    
    def validate_telescope_type(self, telescope_type):
        """Validate telescope type."""
        valid_types = ['SeeStar', 'StellarMate', 'DWARF 3']
        if telescope_type not in valid_types:
            raise ValueError(f"Invalid telescope type: {telescope_type}. Must be one of: {', '.join(valid_types)}")
        return telescope_type
    
    def get_default_hostname(self, telescope_type):
        """Get default hostname for telescope type."""
        defaults = {
            'SeeStar': 'seestar.local',
            'StellarMate': 'stellarmate.local',
            'DWARF 3': 'dwarf.local'
        }
        return defaults.get(telescope_type, '')
    
    def modify_fits_headers(self, fits_path, folder_name, telescope_type):
        """Modify FITS headers based on folder name (similar to GUI version)."""
        try:
            from astropy.io import fits
            
            with fits.open(fits_path, mode='update') as hdul:
                header = hdul[0].header
                
                # For SeeStar telescopes, extract object name from folder
                if '_sub' in folder_name:
                    object_name = folder_name.replace('_sub', '')
                    header['OBJECT'] = object_name
                    self.logger.debug(f"Updated OBJECT header to: {object_name}")
                
                # Check for mosaic indicators
                if 'mosaic' in folder_name.lower() or 'pano' in folder_name.lower():
                    header['MOSAIC'] = True
                    self.logger.debug("Added MOSAIC header flag")
                
                # Special handling for SeeStar telescopes - set FILTER to RGB if missing or empty
                if telescope_type == "SeeStar":
                    if "FILTER" not in header or not header["FILTER"]:
                        header["FILTER"] = "RGB"
                        self.logger.info(f"Set FILTER to RGB for SeeStar telescope in {os.path.basename(fits_path)}")
                
                hdul.flush()
                
        except Exception as e:
            self.logger.warning(f"Failed to modify FITS headers for {fits_path}: {e}")
    
    def download_telescope_files(self, telescope_type, hostname=None, network=None, 
                                target_directory=None, delete_files=False, register_files=True):
        """Download files from specified telescope."""
        
        self.logger.info(f"Starting download from {telescope_type} telescope")
        
        # Step 1: Find telescope
        self.logger.info("Searching for telescope...")
        ip, error = self.smart_telescope_manager.find_telescope(
            telescope_type, 
            network_range=network,
            hostname=hostname
        )
        
        if self.stop_requested:
            return False
        
        if not ip:
            self.logger.error(f"Failed to find telescope: {error}")
            return False
        
        protocol_info = "SMB" if telescope_type in ["SeeStar", "StellarMate"] else "FTP"
        self.logger.info(f"Connected to {telescope_type} at {ip} ({protocol_info})")
        
        # Step 2: Get FITS files list
        if self.stop_requested:
            return False
        
        self.logger.info("Scanning for FITS files...")
        fits_files, error = self.smart_telescope_manager.get_fits_files(telescope_type, ip)
        
        if self.stop_requested:
            return False
        
        if error:
            self.logger.error(f"Failed to get file list: {error}")
            return False
        
        if not fits_files:
            self.logger.info("No FITS files found on telescope")
            return True
        
        self.logger.info(f"Found {len(fits_files)} FITS files")
        
        # Step 3: Download and process files
        if self.stop_requested:
            return False
        
        for i, file_info in enumerate(fits_files):
            if self.stop_requested:
                break
            
            file_name = file_info['name']
            folder_name = os.path.dirname(file_info['path']).split('/')[-1]
            
            self.logger.info(f"Processing {file_name} ({i+1}/{len(fits_files)})...")
            
            # Create local path
            local_path = os.path.join(target_directory, file_name)
            
            # Download file
            success, error = self.smart_telescope_manager.download_file(
                telescope_type, ip, file_info, local_path
            )
            
            if success:
                self.downloaded_files += 1
                self.logger.info(f"Downloaded {file_name}")
                
                try:
                    # Modify FITS headers if needed
                    self.modify_fits_headers(local_path, folder_name, telescope_type)
                    
                    # Register file in database if requested
                    if register_files:
                        processor = fitsProcessing()
                        root_dir = os.path.dirname(local_path)
                        file_name_only = os.path.basename(local_path)
                        
                        # Register the file (moveFiles=True to move to repository)
                        registered_id = processor.registerFitsImage(root_dir, file_name_only, moveFiles=True)
                        
                        if registered_id:
                            self.registered_files += 1
                            self.logger.info(f"Successfully registered {file_name} in database")
                        else:
                            self.logger.warning(f"Failed to register {file_name} in database")
                    
                    # Delete file from telescope if requested
                    if delete_files:
                        delete_success, delete_error = self.smart_telescope_manager.delete_file(
                            telescope_type, ip, file_info
                        )
                        if delete_success:
                            self.deleted_files += 1
                            self.logger.info(f"Deleted {file_name} from telescope")
                        else:
                            self.logger.warning(f"Failed to delete {file_name}: {delete_error}")
                
                except Exception as e:
                    self.logger.error(f"Error processing {file_name}: {e}")
                    self.failed_files.append(f"{file_name}: {e}")
            else:
                self.failed_files.append(f"{file_name}: {error}")
                self.logger.error(f"Failed to download {file_name}: {error}")
        
        return True
    
    def print_summary(self, register_files, delete_files):
        """Print download summary."""
        print("\n" + "="*50)
        print("DOWNLOAD SUMMARY")
        print("="*50)
        print(f"Downloaded: {self.downloaded_files} files")
        
        if register_files:
            print(f"Registered in database: {self.registered_files} files")
        
        if self.failed_files:
            print(f"Failed: {len(self.failed_files)} files")
            for failed in self.failed_files[:5]:  # Show first 5 failures
                print(f"  - {failed}")
            if len(self.failed_files) > 5:
                print(f"  ... and {len(self.failed_files) - 5} more")
        
        if delete_files:
            print(f"Deleted from telescope: {self.deleted_files} files")
        
        if register_files:
            print("\nFiles processed and moved to repository structure")
        
        print("="*50)


def main():
    """Main function for command line execution."""
    parser = argparse.ArgumentParser(
        description="Download images from smart telescopes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Download from SeeStar (auto-detect)
  %(prog)s -t SeeStar --hostname seestar.local  # Specific SeeStar
  %(prog)s -t "DWARF 3" --hostname 192.168.88.1 # DWARF 3 telescope
  %(prog)s --delete                           # Delete files after download
  %(prog)s --no-register                      # Download only, don't register
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('-c', '--config', default='astrofiler.ini',
                       help='Configuration file path (default: astrofiler.ini)')
    parser.add_argument('-t', '--telescope', default='SeeStar',
                       choices=['SeeStar', 'StellarMate', 'DWARF 3'],
                       help='Telescope type (default: SeeStar)')
    parser.add_argument('--hostname',
                       help='Hostname or IP address of telescope (auto-detect if not specified)')
    parser.add_argument('--network',
                       help='Network range to scan (e.g., 192.168.1.0/24)')
    parser.add_argument('--target-dir',
                       help='Target directory for downloads (default: from config)')
    parser.add_argument('--delete', action='store_true',
                       help='Delete files from telescope after successful download')
    parser.add_argument('--no-register', action='store_true',
                       help="Don't register files in database (download only)")
    
    args = parser.parse_args()
    
    # Create CLI instance
    cli = DownloadImagesCLI()
    
    try:
        # Setup logging
        logger = cli.setup_logging(args.verbose)
        logger.info("Starting DownloadImages CLI")
        logger.info(f"Telescope: {args.telescope}")
        
        # Load configuration
        logger.info(f"Loading configuration from: {args.config}")
        config = cli.load_config(args.config)
        
        # Setup database if registering files
        if not args.no_register:
            logger.info("Setting up database...")
            setup_database()
        
        # Validate telescope type
        telescope_type = cli.validate_telescope_type(args.telescope)
        
        # Get hostname (use default if not specified)
        hostname = args.hostname
        if not hostname:
            hostname = cli.get_default_hostname(telescope_type)
            logger.info(f"Using default hostname: {hostname}")
        
        # Get target directory
        target_directory = args.target_dir
        if not target_directory:
            target_directory = cli.get_default_target_directory(config)
        
        # Validate target directory
        if not os.path.exists(target_directory):
            try:
                os.makedirs(target_directory, exist_ok=True)
                logger.info(f"Created target directory: {target_directory}")
            except Exception as e:
                logger.error(f"Failed to create target directory {target_directory}: {e}")
                return 1
        
        logger.info(f"Target directory: {target_directory}")
        logger.info(f"Register files: {not args.no_register}")
        logger.info(f"Delete files: {args.delete}")
        
        # Warning for delete option
        if args.delete:
            logger.warning("DELETE MODE ENABLED - Files will be permanently removed from telescope!")
        
        # Perform download
        success = cli.download_telescope_files(
            telescope_type=telescope_type,
            hostname=hostname,
            network=args.network,
            target_directory=target_directory,
            delete_files=args.delete,
            register_files=not args.no_register
        )
        
        # Print summary
        cli.print_summary(not args.no_register, args.delete)
        
        if success and not cli.stop_requested:
            logger.info("Download completed successfully")
            return 0
        elif cli.stop_requested:
            logger.info("Download interrupted by user")
            return 130  # Standard exit code for SIGINT
        else:
            logger.error("Download failed")
            return 1
    
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nDownload interrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())