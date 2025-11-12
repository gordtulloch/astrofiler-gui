#!/usr/bin/env python3
"""
LoadRepo.py - Command line utility to load new images from incoming folder

This script scans the source folder for new FITS and XISF files and processes them into the repository.
It moves files from the source folder to the repository structure and registers them in the database.
XISF files are automatically converted to FITS format during processing.

Usage:
    python LoadRepo.py [options]

Options:
    -h, --help      Show this help message and exit
    -v, --verbose   Enable verbose logging
    -c, --config    Path to configuration file (default: astrofiler.ini)
    -s, --source    Override source folder path
    -r, --repo      Override repository folder path

Requirements:
    - astrofiler.ini configuration file
    - Valid source and repository paths
    - Write permissions to repository folder

Example:
    # Load new images with default settings
    python LoadRepo.py
    
    # Load with verbose output
    python LoadRepo.py -v
    
    # Load with custom config file
    python LoadRepo.py -c /path/to/config.ini
    
    # Load from specific source folder
    python LoadRepo.py -s /path/to/source

Note: For synchronizing the database with existing repository files, use SyncRepo.py instead.
"""

import sys
import os
import argparse
import logging
import configparser
from datetime import datetime

# Configure Python path for new package structure - must be before any astrofiler imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')

# Ensure src path is first in path to avoid conflicts with root astrofiler.py
if src_path in sys.path:
    sys.path.remove(src_path)
sys.path.insert(0, src_path)

def ensure_astrofiler_imports():
    """Ensure astrofiler package can be imported correctly from src directory"""
    global src_path
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from astrofiler.core import fitsProcessing
from astrofiler.database import setup_database

def setup_logging(verbose=False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure logging to both file and console - using central astrofiler.log
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.FileHandler('astrofiler.log', mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def load_config(config_path):
    """Load configuration from file."""
    config = configparser.ConfigParser()
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    config.read(config_path)
    return config

def validate_paths(source_folder, repo_folder):
    """Validate source and repository folder paths."""
    if not os.path.exists(source_folder):
        raise FileNotFoundError(f"Source folder does not exist: {source_folder}")
    
    if not os.path.exists(repo_folder):
        try:
            os.makedirs(repo_folder, exist_ok=True)
            logging.info(f"Created repository folder: {repo_folder}")
        except Exception as e:
            raise RuntimeError(f"Cannot create repository folder {repo_folder}: {e}")
    
    # Check write permissions
    if not os.access(repo_folder, os.W_OK):
        raise PermissionError(f"No write permission for repository folder: {repo_folder}")

def main():
    """Main function to load new images from command line."""
    parser = argparse.ArgumentParser(
        description="Load new FITS and XISF files from source folder into repository",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python LoadRepo.py                     # Load with default settings
    python LoadRepo.py -v                  # Verbose output
    python LoadRepo.py -c custom.ini       # Custom config file
    python LoadRepo.py -s /path/to/source  # Override source folder

Note: For database synchronization with existing files, use SyncRepo.py instead.
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('-c', '--config', default='astrofiler.ini',
                        help='Path to configuration file (default: astrofiler.ini)')
    parser.add_argument('-s', '--source', 
                        help='Override source folder path')
    parser.add_argument('-r', '--repo',
                        help='Override repository folder path')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    try:
        logger.info("=== AstroFiler New Image Loader Starting ===")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Ensure imports work correctly
        ensure_astrofiler_imports()
        
        # Load configuration
        logger.info(f"Loading configuration from: {args.config}")
        config = load_config(args.config)
        
        # Get folder paths
        source_folder = args.source or config.get('DEFAULT', 'source', fallback='.')
        repo_folder = args.repo or config.get('DEFAULT', 'repo', fallback='.')
        
        # Convert to absolute paths
        source_folder = os.path.abspath(source_folder)
        repo_folder = os.path.abspath(repo_folder)
        
        logger.info(f"Source folder: {source_folder}")
        logger.info(f"Repository folder: {repo_folder}")
        
        # Validate paths
        validate_paths(source_folder, repo_folder)
        
        # Setup database
        logger.info("Setting up database...")
        setup_database()
        
        # Create processor instance
        processor = fitsProcessing()
        
        # Override folder paths if specified
        if args.source:
            processor.sourceFolder = source_folder
        if args.repo:
            processor.repoFolder = repo_folder
        
        # Process files - always move files from source to repository
        logger.info("Starting new image processing...")
        
        result = processor.registerFitsImages(
            moveFiles=True,  # Always move files from source to repository
            progress_callback=None  # Disabled for non-interactive use
        )
        
        # Handle the new tuple return format (registered_files, duplicate_count)
        if isinstance(result, tuple):
            registered_files, duplicate_count = result
        else:
            # Backward compatibility for old return format
            registered_files = result
            duplicate_count = 0
        
        # Report results
        logger.info(f"=== Processing Complete ===")
        logger.info(f"Files processed: {len(registered_files)}")
        if duplicate_count > 0:
            logger.info(f"Duplicate files skipped: {duplicate_count}")
        logger.info(f"Mode: Move and register new images")
        
        if len(registered_files) == 0:
            if duplicate_count > 0:
                logger.warning(f"No new FITS/XISF files processed! {duplicate_count} duplicate files were skipped.")
            else:
                logger.warning("No FITS or XISF files found to process!")
            return 1
        else:
            logger.info("New image loading completed successfully!")
            return 0
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user (Ctrl+C)")
        return 1
    except Exception as e:
        logger.error(f"Error during repository load: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
