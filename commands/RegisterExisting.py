#!/usr/bin/env python3
"""
AstroFiler Register Existing Files Command
==========================================

Command-line tool to register existing calibrated files and master frames
to avoid duplicate work in the auto-calibration system.

This script scans the repository for:
- Existing master calibration frames (bias, dark, flat)
- Already calibrated light frames
- Updates database records with calibration status
- Links master frames to appropriate sessions
- Validates file consistency and fixes issues

Usage:
    python RegisterExisting.py [options]

Options:
    --config PATH          Configuration file path (default: astrofiler.ini)
    --no-subdirs          Don't scan subdirectories recursively
    --no-header-verify    Skip FITS header verification (faster but less accurate)
    --verbose, -v         Enable verbose logging
    --quiet, -q           Suppress all output except errors
    --dry-run            Show what would be done without making changes
    --log-file PATH      Write log output to file
    --help, -h           Show this help message

Examples:
    # Basic registration with default settings
    python RegisterExisting.py
    
    # Verbose mode with header verification
    python RegisterExisting.py --verbose
    
    # Fast scan without header verification
    python RegisterExisting.py --no-header-verify --quiet
    
    # Dry run to see what would be done
    python RegisterExisting.py --dry-run --verbose

Author: AstroFiler Development Team
Version: 1.0
Date: October 2025
"""

import sys
import os
import argparse
import logging
import time
from pathlib import Path

# Add the parent directory to the Python path so we can import astrofiler modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_logging(verbose=False, quiet=False, log_file=None):
    """Setup logging configuration"""
    if quiet:
        log_level = logging.ERROR
    elif verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    
    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Setup handlers
    handlers = []
    
    # Console handler
    if not quiet:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always debug level for files
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
        force=True
    )
    
    # Set specific logger levels
    logging.getLogger('astrofiler_file').setLevel(log_level)
    logging.getLogger('astrofiler_db').setLevel(log_level)
    
    return logging.getLogger(__name__)

def load_config(config_path='astrofiler.ini'):
    """Load configuration from file"""
    import configparser
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    return config

def validate_database_access():
    """Validate database connectivity"""
    try:
        from astrofiler_db import setup_database, fitsFile, fitsSession
        
        # Test database connection
        setup_database()
        
        # Test basic queries
        file_count = fitsFile.select().count()
        session_count = fitsSession.select().count()
        
        logging.info(f"Database connection validated: {file_count} files, {session_count} sessions")
        return True
        
    except Exception as e:
        logging.error(f"Database validation failed: {e}")
        return False

def create_cli_progress_callback(description="Processing"):
    """Create a progress callback for CLI operations"""
    last_percentage = -1
    
    def progress_callback(current, total, message=""):
        nonlocal last_percentage
        
        if total > 0:
            percentage = int((current / total) * 100)
            
            # Only update on percentage changes to reduce output
            if percentage != last_percentage:
                progress_bar = "=" * (percentage // 2) + ">" + " " * (50 - percentage // 2)
                print(f"\r{description}: [{progress_bar}] {percentage}% - {message}", end="", flush=True)
                last_percentage = percentage
                
                # New line when complete
                if percentage >= 100:
                    print()
        else:
            print(f"{description}: {message}")
        
        return True  # Continue processing
    
    return progress_callback

def register_existing_files(config, scan_subdirectories=True, verify_headers=True, dry_run=False):
    """Register existing calibrated files and master frames"""
    from astrofiler_file import fitsProcessing
    
    logging.info("Starting existing file registration...")
    
    if dry_run:
        logging.info("DRY RUN - No database changes will be made")
    
    try:
        processor = fitsProcessing()
        
        if dry_run:
            logging.info("Would scan repository for existing calibrated files and master frames")
            logging.info(f"  - Scan subdirectories: {scan_subdirectories}")
            logging.info(f"  - Verify FITS headers: {verify_headers}")
            return True
        
        # Execute registration
        results = processor.registerExistingFiles(
            progress_callback=create_cli_progress_callback("Registering existing files"),
            scan_subdirectories=scan_subdirectories,
            verify_headers=verify_headers
        )
        
        # Display results
        summary = results.get('summary', {})
        master_info = summary.get('master_frames', {})
        calibrated_info = summary.get('calibrated_lights', {})
        errors = results.get('errors', [])
        
        logging.info("Registration completed successfully!")
        logging.info(f"  Total files processed: {summary.get('total_files_processed', 0)}")
        logging.info(f"  Master frames found: {master_info.get('found', 0)}")
        logging.info(f"    - Already linked: {master_info.get('already_linked', 0)}")
        logging.info(f"    - Newly linked: {master_info.get('newly_linked', 0)}")
        logging.info(f"  Calibrated light frames found: {calibrated_info.get('found', 0)}")
        logging.info(f"    - Database updated: {calibrated_info.get('updated', 0)}")
        logging.info(f"    - Verification errors: {calibrated_info.get('verification_errors', 0)}")
        logging.info(f"  Database changes made: {summary.get('database_changes', 0)}")
        
        if errors:
            logging.warning(f"  Errors encountered: {len(errors)}")
            for i, error in enumerate(errors[:10]):  # Show first 10 errors
                logging.warning(f"    {i+1}. {error}")
            if len(errors) > 10:
                logging.warning(f"    ... and {len(errors)-10} more errors")
        
        return len(errors) == 0
        
    except Exception as e:
        logging.error(f"Error in existing file registration: {e}")
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Register existing calibrated files and master frames",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--config', 
                       default='astrofiler.ini',
                       help='Configuration file path (default: astrofiler.ini)')
    
    parser.add_argument('--no-subdirs',
                       action='store_true',
                       help="Don't scan subdirectories recursively")
    
    parser.add_argument('--no-header-verify',
                       action='store_true', 
                       help='Skip FITS header verification (faster but less accurate)')
    
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='Enable verbose logging')
    
    parser.add_argument('--quiet', '-q',
                       action='store_true',
                       help='Suppress all output except errors')
    
    parser.add_argument('--dry-run',
                       action='store_true',
                       help='Show what would be done without making changes')
    
    parser.add_argument('--log-file',
                       help='Write log output to file')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(
        verbose=args.verbose,
        quiet=args.quiet,
        log_file=args.log_file
    )
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config(args.config)
        
        # Validate database access
        logger.info("Validating database access...")
        if not validate_database_access():
            logger.error("Database validation failed")
            return 1
        
        # Determine options
        scan_subdirectories = not args.no_subdirs
        verify_headers = not args.no_header_verify
        
        logger.info(f"Registration options:")
        logger.info(f"  - Scan subdirectories: {scan_subdirectories}")
        logger.info(f"  - Verify FITS headers: {verify_headers}")
        logger.info(f"  - Dry run: {args.dry_run}")
        
        # Execute registration
        start_time = time.time()
        success = register_existing_files(
            config,
            scan_subdirectories=scan_subdirectories,
            verify_headers=verify_headers,
            dry_run=args.dry_run
        )
        end_time = time.time()
        
        # Report completion
        duration = end_time - start_time
        if success:
            logger.info(f"Registration completed successfully in {duration:.1f} seconds")
            return 0
        else:
            logger.error(f"Registration failed after {duration:.1f} seconds")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Registration cancelled by user")
        return 130
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())