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
    -r, --regenerate Clear all existing sessions first, then regenerate all session data
    -n, --new-only   Only create sessions for files without existing sessions
    -q, --update-quality Update quality metrics for all existing light sessions

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
    
    # Regenerate all sessions (clear existing first)
    python CreateSessions.py -r
    
    # Only create sessions for unassigned files
    python CreateSessions.py -n
    
    # Update quality metrics for all existing sessions
    python CreateSessions.py -q
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
from astrofiler.models import fitsFile as FitsFileModel, fitsSession as FitsSessionModel

def setup_logging(verbose=False):
    """Setup logging configuration."""
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

def create_light_sessions(processor, logger):
    """Create light sessions for unassigned files."""
    logger.info("Creating light sessions...")
    try:
        created_sessions = processor.createLightSessions(progress_callback=None)
        logger.info(f"Light sessions created: {len(created_sessions)}")
        # Quality metrics are automatically updated by createLightSessions
        return len(created_sessions)
    except Exception as e:
        logger.error(f"Error creating light sessions: {e}")
        raise

def update_session_quality_metrics(processor, logger):
    """Update quality metrics for all existing light sessions."""
    logger.info("Updating quality metrics for all sessions...")
    try:
        # Get all light sessions (non-calibration)
        sessions = FitsSessionModel.select().where(
            (FitsSessionModel.is_auto_calibration == False) | 
            (FitsSessionModel.is_auto_calibration.is_null())
        )
        
        session_ids = [str(s.fitsSessionId) for s in sessions]
        if not session_ids:
            logger.info("No light sessions found to update")
            return 0
        
        logger.info(f"Updating quality metrics for {len(session_ids)} sessions...")
        processor.session_processor.updateSessionQualityMetrics(session_ids)
        logger.info(f"Quality metrics updated for {len(session_ids)} sessions")
        return len(session_ids)
    except Exception as e:
        logger.error(f"Error updating session quality metrics: {e}")
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

def clear_existing_sessions(logger):
    """Clear all existing sessions from the database."""
    logger.info("Clearing all existing sessions...")
    try:
        # Clear session references in files first to avoid foreign key constraints
        files_updated = FitsFileModel.update(fitsFileSession=None).execute()
        logger.info(f"Cleared session references from {files_updated} files")
        
        # Delete all sessions
        sessions_deleted = FitsSessionModel.delete().execute()
        logger.info(f"Deleted {sessions_deleted} existing sessions")
        
        return sessions_deleted
    except Exception as e:
        logger.error(f"Error clearing existing sessions: {e}")
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
    python CreateSessions.py -r            # Clear all sessions and regenerate
    python CreateSessions.py -n            # Only create sessions for unassigned files
    python CreateSessions.py -q            # Update quality metrics for existing sessions
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
    parser.add_argument('-r', '--regenerate', action='store_true',
                        help='Clear all existing sessions first, then regenerate all session data')
    parser.add_argument('-n', '--new-only', action='store_true',
                        help='Only create sessions for files without existing sessions')
    parser.add_argument('-q', '--update-quality', action='store_true',
                        help='Update quality metrics for all existing light sessions')
    
    args = parser.parse_args()
    
    # Validate argument combinations
    if args.regenerate and (args.lights or args.calibs or args.new_only or args.update_quality):
        parser.error("--regenerate cannot be used with other options (regenerate always creates both types for all files)")
    if args.new_only and (args.lights or args.calibs):
        parser.error("--new-only cannot be used with --lights or --calibs (new-only always processes both types)")
    if args.update_quality and (args.lights or args.calibs or args.new_only or args.regenerate):
        parser.error("--update-quality must be used alone (only updates quality metrics for existing sessions)")
    
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
        
        # Handle update-quality flag
        if args.update_quality:
            logger.info("Update-quality mode: Will update quality metrics for all existing sessions")
            sessions_updated = update_session_quality_metrics(processor, logger)
            logger.info(f"=== Quality Metrics Update Complete ===")
            logger.info(f"Updated quality metrics for {sessions_updated} sessions")
            return 0
        
        # Handle regenerate flag - this overrides other options
        if args.regenerate:
            create_lights = True
            create_calibs = True
            new_only_mode = False
            logger.info("Regenerate mode: Will clear all existing sessions and recreate both light and calibration sessions")
        elif args.new_only:
            create_lights = True
            create_calibs = True
            new_only_mode = True
            logger.info("New-only mode: Will create sessions only for files without existing sessions")
        else:
            # Determine what to process
            create_lights = not args.calibs  # Create lights unless only calibs requested
            create_calibs = not args.lights  # Create calibs unless only lights requested
            new_only_mode = False
            logger.info(f"Will create light sessions: {create_lights}")
            logger.info(f"Will create calibration sessions: {create_calibs}")
        
        # Check for unassigned files in new-only mode
        if new_only_mode:
            unassigned_light_count = FitsFileModel.select().where(
                FitsFileModel.fitsFileSession.is_null(), 
                FitsFileModel.fitsFileType == 'LIGHT FRAME',
                FitsFileModel.fitsFileSoftDelete == False
            ).count()
            
            unassigned_cal_count = FitsFileModel.select().where(
                FitsFileModel.fitsFileSession.is_null(),
                FitsFileModel.fitsFileType.in_(['BIAS FRAME', 'DARK FRAME', 'FLAT FIELD']),
                FitsFileModel.fitsFileSoftDelete == False
            ).count()
            
            total_unassigned = unassigned_light_count + unassigned_cal_count
            logger.info(f"Found {unassigned_light_count} unassigned light files and {unassigned_cal_count} unassigned calibration files")
            
            if total_unassigned == 0:
                logger.info("No unassigned files found - all files already have sessions assigned")
                return 0
        
        # Clear existing sessions if regenerate flag is set
        if args.regenerate:
            clear_existing_sessions(logger)
        
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
        
        if args.regenerate:
            logger.info("=== Session Regeneration Complete ===")
            logger.info(f"All existing sessions were cleared and recreated")
        elif args.new_only:
            logger.info("=== New-Only Session Creation Complete ===")
            logger.info(f"Sessions created only for files without existing sessions")
        
        if total_sessions == 0:
            if args.regenerate:
                logger.warning("No sessions were created after regeneration - no unassigned files found!")
            elif args.new_only:
                logger.info("No sessions were created - all files already have sessions assigned!")
            else:
                logger.warning("No sessions were created - all files may already be assigned!")
            return 1
        else:
            logger.info(f"Total sessions created: {total_sessions}")
            if args.regenerate:
                logger.info("Session regeneration completed successfully!")
            else:
                logger.info("Session creation completed successfully!")
            return 0
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user (Ctrl+C)")
        return 1
    except Exception as e:
        # Import DatabaseError for special handling
        from astrofiler.exceptions import DatabaseError
        
        # Handle database errors gracefully without traceback
        if isinstance(e, DatabaseError):
            logger.error(f"Database error: {e}")
            print(f"\n{'='*70}")
            print("DATABASE ERROR")
            print(f"{'='*70}")
            print(f"\n{e}\n")
            print(f"{'='*70}\n")
            return 1
        
        # For other exceptions, show traceback if verbose
        logger.error(f"Error during session creation: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        else:
            print(f"\nError: {e}")
            print("Use -v/--verbose for detailed error information")
        return 1

if __name__ == "__main__":
    sys.exit(main())
