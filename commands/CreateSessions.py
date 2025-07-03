#!/usr/bin/env python3
"""
CreateSessions.py - Command line utility to create sessions for unassigned FITS files

This script creates both light sessions and calibration sessions for files that haven't been
assigned to sessions yet. It processes unassigned light frames and groups them by object,
then creates calibration sessions for bias, dark, and flat files.

Usage:
    python CreateSessions.py [options]

Options:
    -h, --help       Show this help message and exit
    -v, --verbose    Enable verbose logging
    -c, --config     Path to configuration file (default: astrofiler.ini)
    -l, --lights     Only create light sessions
    -C, --calibs     Only create calibration sessions

Requirements:
    - astrofiler.ini configuration file
    - Existing database with FITS files
    - Write permissions to database

Example:
    # Create both light and calibration sessions
    python CreateSessions.py
    
    # Create sessions with verbose output
    python CreateSessions.py -v
    
    # Only create light sessions
    python CreateSessions.py -l
    
    # Only create calibration sessions
    python CreateSessions.py -C
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
            logging.FileHandler('createsessions.log'),
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

def create_light_sessions(processor, logger):
    """Create light sessions for unassigned files."""
    logger.info("Creating light sessions...")
    try:
        created_sessions = processor.createLightSessions(progress_callback=None)
        logger.info(f"Light sessions created: {len(created_sessions)}")
        return len(created_sessions)
    except Exception as e:
        logger.error(f"Error creating light sessions: {e}")
        raise

def create_calibration_sessions(processor, logger):
    """Create calibration sessions for unassigned files."""
    logger.info("Creating calibration sessions...")
    try:
        created_sessions = processor.createCalibrationSessions(progress_callback=None)
        logger.info(f"Calibration sessions created: {len(created_sessions)}")
        return len(created_sessions)
    except Exception as e:
        logger.error(f"Error creating calibration sessions: {e}")
        raise

def main():
    """Main function to create sessions from command line."""
    parser = argparse.ArgumentParser(
        description="Create sessions for unassigned FITS files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python CreateSessions.py                # Create both types of sessions
    python CreateSessions.py -v            # Verbose output
    python CreateSessions.py -l            # Only light sessions
    python CreateSessions.py -C            # Only calibration sessions
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('-c', '--config', default='astrofiler.ini',
                        help='Path to configuration file (default: astrofiler.ini)')
    parser.add_argument('-l', '--lights', action='store_true',
                        help='Only create light sessions')
    parser.add_argument('-C', '--calibs', action='store_true',
                        help='Only create calibration sessions')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    try:
        logger.info("=== AstroFiler Session Creator Starting ===")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Load configuration
        logger.info(f"Loading configuration from: {args.config}")
        config = load_config(args.config)
        
        # Setup database
        logger.info("Setting up database...")
        setup_database()
        
        # Create processor instance
        processor = fitsProcessing()
        
        # Determine what to process
        create_lights = not args.calibs  # Create lights unless only calibs requested
        create_calibs = not args.lights  # Create calibs unless only lights requested
        
        logger.info(f"Will create light sessions: {create_lights}")
        logger.info(f"Will create calibration sessions: {create_calibs}")
        
        total_light_sessions = 0
        total_calib_sessions = 0
        
        # Create light sessions
        if create_lights:
            total_light_sessions = create_light_sessions(processor, logger)
        
        # Create calibration sessions
        if create_calibs:
            total_calib_sessions = create_calibration_sessions(processor, logger)
        
        # Report results
        logger.info(f"=== Session Creation Complete ===")
        if create_lights:
            logger.info(f"Light sessions created: {total_light_sessions}")
        if create_calibs:
            logger.info(f"Calibration sessions created: {total_calib_sessions}")
        
        total_sessions = total_light_sessions + total_calib_sessions
        
        if total_sessions == 0:
            logger.warning("No sessions were created - all files may already be assigned!")
            return 1
        else:
            logger.info(f"Total sessions created: {total_sessions}")
            logger.info("Session creation completed successfully!")
            return 0
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user (Ctrl+C)")
        return 1
    except Exception as e:
        logger.error(f"Error during session creation: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
