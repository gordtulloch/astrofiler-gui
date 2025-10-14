#!/usr/bin/env python3
"""
LoadRepo.py - Command line utility to load repository from incoming folder

This script scans the source folder for FITS files and processes them into the repository.
It moves files from the source folder to the repository structure and registers them in the database.

Usage:
    python LoadRepo.py [options]

Options:
    -h, --help      Show this help message and exit
    -v, --verbose   Enable verbose logging
    -c, --config    Path to configuration file (default: astrofiler.ini)
    -s, --source    Override source folder path
    -r, --repo      Override repository folder path
    -n, --no-move   Don't move files, just register them (sync mode)

Requirements:
    - astrofiler.ini configuration file
    - Valid source and repository paths
    - Write permissions to repository folder

Example:
    # Load repository with default settings
    python LoadRepo.py
    
    # Load with verbose output
    python LoadRepo.py -v
    
    # Load with custom config file
    python LoadRepo.py -c /path/to/config.ini
    
    # Sync mode (don't move files)
    python LoadRepo.py -n
"""

import sys
import os
import argparse
import logging
import configparser
from datetime import datetime

# Add the parent directory to the path to import astrofiler modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astrofiler_file import fitsProcessing
from astrofiler_db import setup_database

def setup_logging(verbose=False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure logging to both file and console
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.FileHandler('loadrepo.log'),
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
    """Main function to load repository from command line."""
    parser = argparse.ArgumentParser(
        description="Load FITS files from source folder into repository",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python LoadRepo.py                     # Load with default settings
    python LoadRepo.py -v                  # Verbose output
    python LoadRepo.py -c custom.ini       # Custom config file
    python LoadRepo.py -s /path/to/source  # Override source folder
    python LoadRepo.py -n                  # Sync mode (don't move files)
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
    parser.add_argument('-n', '--no-move', action='store_true',
                        help="Don't move files, just register them (sync mode)")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    try:
        logger.info("=== AstroFiler Repository Loader Starting ===")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
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
        logger.info(f"Move files: {not args.no_move}")
        
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
        
        # Process files
        logger.info("Starting file processing...")
        move_files = not args.no_move
        
        result = processor.registerFitsImages(
            moveFiles=move_files,
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
        logger.info(f"Mode: {'Move and register' if move_files else 'Sync only'}")
        
        if len(registered_files) == 0:
            if duplicate_count > 0:
                logger.warning(f"No new FITS files processed! {duplicate_count} duplicate files were skipped.")
            else:
                logger.warning("No FITS files found to process!")
            return 1
        else:
            logger.info("Repository load completed successfully!")
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
