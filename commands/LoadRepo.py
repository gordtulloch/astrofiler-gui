#!/usr/bin/env python3
"""
LoadRepo.py - Command line utility to load new images from incoming folder

This script scans the source folder for new FITS and XISF files and processes them into the repository.
It moves files from the source folder to the repository structure and registers them in the database.
XISF files are automatically converted to FITS format during processing.

Usage:
    python LoadRepo.py [options]

Options:
    -h, --help          Show this help message and exit
    -v, --verbose       Enable verbose logging
    -c, --config        Path to configuration file (default: astrofiler.ini)
    --source            Override source folder path
    -r, --repo          Override repository folder path
    -s, --single-mapping CARD/INPUT/OUTPUT
                        Add a temporary one-time mapping (e.g., -s OBJECT/Unknown/M31)
                        Can be used multiple times. Mapping is removed after completion.

Requirements:
    - astrofiler.ini configuration file
    - Valid source and repository paths
    - Write permissions to repository folder

Examples:
    # Load new images with default settings
    python LoadRepo.py
    
    # Load with verbose output
    python LoadRepo.py -v
    
    # Load with custom config file
    python LoadRepo.py -c /path/to/config.ini
    
    # Load from specific source folder
    python LoadRepo.py --source /path/to/source
    
    # Load with temporary one-time mapping (map Unknown objects to M31)
    python LoadRepo.py -s OBJECT/Unknown/M31
    
    # Load with multiple temporary mappings
    python LoadRepo.py -s OBJECT/Unknown/M31 -s FILTER//RGB -s TELESCOP/Unknown/MyScope

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
from astrofiler.models import Mapping as MappingModel
from astropy.io import fits as astropy_fits

def apply_mappings_to_fits(file_path):
    """
    Apply header mappings to a FITS file before registration.
    
    This function reads the FITS header, applies any defined mappings
    from the database, and updates the FITS file with the new values.
    This ensures files are named correctly during registration.
    
    Args:
        file_path: Path to the FITS file
        
    Returns:
        bool: True if any mappings were applied, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Get all mappings from database
        mappings = list(MappingModel.select())
        
        if not mappings:
            logger.debug(f"No mappings defined, skipping header mapping for {os.path.basename(file_path)}")
            return False
        
        # Open FITS file and apply mappings
        changes_made = False
        with astropy_fits.open(file_path, mode='update') as hdul:
            header = hdul[0].header
            
            # Apply each mapping
            for mapping in mappings:
                card = mapping.card
                current = mapping.current
                replace = mapping.replace
                
                # Skip if no replacement value
                if not replace:
                    continue
                
                # Check if this card exists in the header
                if card in header:
                    header_value = str(header[card]).strip()
                    
                    # Check if the current value matches (or if current is None/empty for default mapping)
                    if current:
                        # Specific value mapping (including "Unknown" mappings)
                        if header_value.upper() == current.upper():
                            header[card] = replace
                            logger.info(f"Applied mapping to {os.path.basename(file_path)}: {card} '{current}' -> '{replace}'")
                            changes_made = True
                    else:
                        # Default mapping for null/empty values - replace if current value is empty/none
                        if not header_value or header_value.upper() in ['', 'NONE', 'NULL', 'UNKNOWN']:
                            header[card] = replace
                            logger.info(f"Applied default mapping to {os.path.basename(file_path)}: {card} (empty/unknown) -> '{replace}'")
                            changes_made = True
                else:
                    # Card doesn't exist in header
                    if not current or current == '':
                        # We have a default mapping (empty current) and card is missing - add it
                        header[card] = replace
                        header.comments[card] = 'Added via AstroFiler mapping'
                        logger.info(f"Added missing card to {os.path.basename(file_path)}: {card} -> '{replace}'")
                        changes_made = True
                    elif current.upper() == 'UNKNOWN':
                        # We have an "Unknown" mapping and card is missing - treat missing as Unknown
                        header[card] = replace
                        header.comments[card] = 'Added via AstroFiler mapping'
                        logger.info(f"Added missing card (Unknown mapping) to {os.path.basename(file_path)}: {card} -> '{replace}'")
                        changes_made = True
            
            if changes_made:
                hdul.flush()
        
        return changes_made
        
    except Exception as e:
        logger.error(f"Error applying mappings to {file_path}: {e}")
        return False

def setup_logging(verbose=False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure logging - using central astrofiler.log
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
    python LoadRepo.py                           # Load with default settings
    python LoadRepo.py -v                        # Verbose output
    python LoadRepo.py -c custom.ini             # Custom config file
    python LoadRepo.py --source /path/to/source  # Override source folder
    python LoadRepo.py -s OBJECT/Unknown/M31     # Temporary mapping for this run only
    python LoadRepo.py -s OBJECT/Unknown/M31 -s FILTER//RGB  # Multiple temporary mappings

Note: 
    - For database synchronization with existing files, use SyncRepo.py instead.
    - Temporary mappings (-s) are applied only for this run and removed after completion.
    - Use empty INPUT for default mappings (e.g., -s FILTER//RGB maps empty/missing FILTER to RGB)
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('-c', '--config', default='astrofiler.ini',
                        help='Path to configuration file (default: astrofiler.ini)')
    parser.add_argument('--source', 
                        help='Override source folder path')
    parser.add_argument('-r', '--repo',
                        help='Override repository folder path')
    parser.add_argument('-s', '--single-mapping', action='append', metavar='CARD/INPUT/OUTPUT',
                        help='Add a temporary one-time mapping (e.g., -s OBJECT/Unknown/M31). Can be used multiple times. Mapping is removed after completion.')
    
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
        
        # Process temporary single-use mappings if provided
        temp_mapping_ids = []
        if args.single_mapping:
            logger.info(f"Processing {len(args.single_mapping)} temporary mapping(s)...")
            for mapping_spec in args.single_mapping:
                try:
                    # Parse the mapping specification: CARD/INPUT/OUTPUT
                    parts = mapping_spec.split('/')
                    if len(parts) != 3:
                        logger.error(f"Invalid mapping format: {mapping_spec}. Expected CARD/INPUT/OUTPUT")
                        continue
                    
                    card, current, replace = parts
                    card = card.strip().upper()
                    current = current.strip() if current.strip() else None
                    replace = replace.strip()
                    
                    # Validate card name
                    valid_cards = ['TELESCOP', 'INSTRUME', 'OBSERVER', 'OBJECT', 'FILTER', 'NOTES']
                    if card not in valid_cards:
                        logger.error(f"Invalid card name: {card}. Must be one of: {', '.join(valid_cards)}")
                        continue
                    
                    # Validate that replace is not empty
                    if not replace:
                        logger.error(f"Invalid mapping: OUTPUT value cannot be empty in {mapping_spec}")
                        continue
                    
                    # Create temporary mapping
                    temp_mapping = MappingModel.create(
                        card=card,
                        current=current,
                        replace=replace
                    )
                    temp_mapping_ids.append(temp_mapping.id)
                    
                    logger.info(f"Created temporary mapping: {card} '{current or '(default)'}' -> '{replace}'")
                    
                except Exception as e:
                    logger.error(f"Failed to create temporary mapping from {mapping_spec}: {e}")
                    continue
        
        # Create processor instance
        processor = fitsProcessing()
        
        # Override folder paths if specified
        if args.source:
            processor.sourceFolder = source_folder
        if args.repo:
            processor.repoFolder = repo_folder
        
        # Apply mappings to all FITS files in source folder before registration
        logger.info("Checking for FITS files to apply mappings...")
        files_mapped = 0
        try:
            for root, dirs, files in os.walk(source_folder):
                for file in files:
                    if file.lower().endswith(('.fit', '.fits')):
                        file_path = os.path.join(root, file)
                        try:
                            if apply_mappings_to_fits(file_path):
                                files_mapped += 1
                        except Exception as e:
                            logger.warning(f"Failed to apply mappings to {file}: {e}")
            
            if files_mapped > 0:
                logger.info(f"Applied mappings to {files_mapped} FITS files")
            else:
                logger.info("No mappings applied (no mappings defined or no matching files)")
        except Exception as e:
            logger.warning(f"Error during mapping application: {e}")
        
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
        
        # Clean up temporary mappings
        if temp_mapping_ids:
            logger.info(f"Removing {len(temp_mapping_ids)} temporary mapping(s)...")
            try:
                deleted_count = MappingModel.delete().where(MappingModel.id.in_(temp_mapping_ids)).execute()
                logger.info(f"Removed {deleted_count} temporary mapping(s) from database")
            except Exception as e:
                logger.error(f"Error removing temporary mappings: {e}")
        
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
