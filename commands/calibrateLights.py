#!/usr/bin/env python3
"""
calibrateLights.py - Simple command line utility for basic light frame calibration

This script performs basic light frame calibration using bias, dark, and flat master frames.
It integrates with AstroFiler's database to find appropriate master frames and applies
standard calibration: Light - Bias - Dark*scale - Flat_normalized.

Usage:
    python calibrateLights.py [options]

Options:
    -h, --help              Show this help message and exit
    -v, --verbose           Enable verbose logging  
    -c, --config            Path to configuration file (default: astrofiler.ini)
    -s, --session           Specific session ID to calibrate
    -o, --object            Calibrate all sessions for specific object name
    -f, --files             Specific FITS files to calibrate (comma-separated paths)
    -d, --output-dir        Output directory for calibrated files (default: same as input)
    --force                 Force recalibration even if output exists
    --masters-dir           Directory containing master frames (default: Masters/)
    --bias-master           Specific bias master frame path
    --dark-master           Specific dark master frame path  
    --flat-master           Specific flat master frame path
    --dry-run               Show what would be done without processing

Calibration Process:
    1. Load light frame
    2. Subtract bias master (if available)
    3. Subtract dark master scaled by exposure time (if available)
    4. Divide by normalized flat master (if available)
    5. Save calibrated frame with _calibrated suffix

Examples:
    # Calibrate all light frames in session 123
    python calibrateLights.py -s 123 -v
    
    # Calibrate specific object with custom masters
    python calibrateLights.py -o "M31" --bias-master Masters/bias_master.fits
    
    # Calibrate specific files
    python calibrateLights.py -f "light001.fits,light002.fits"
    
    # Dry run to see what would be processed
    python calibrateLights.py -s 123 --dry-run -v
"""

import sys
import os
import argparse
import logging
import configparser
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import time

# Add the parent directory to the path to import astrofiler modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_logging(verbose=False, log_file=None):
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create formatters
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Setup handlers
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Add file handler if log file specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    # Disable Peewee SQL query logging to reduce verbosity
    peewee_logger = logging.getLogger('peewee')
    peewee_logger.setLevel(logging.WARNING)

def load_config(config_path='astrofiler.ini'):
    """Load configuration from file"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

def validate_siril_installation():
    """Validate that Siril and pySiril are available"""
    try:
        from pysiril.siril import Siril
        from pysiril.wrapper import Wrapper
        logging.info("PySiril import successful")
        
        # Test Siril connection
        app = Siril()
        app.Open()
        logging.info("Siril connection successful")
        app.Close()
        return True
        
    except ImportError as e:
        raise Exception(f"PySiril not available: {e}. Install with: pip install pysiril")
    except Exception as e:
        raise Exception(f"Siril connection failed: {e}")

def validate_database_access():
    """Validate database connectivity"""
    try:
        from astrofiler_db import setup_database, fitsFile, fitsSession
        
        # Setup database connection
        setup_database()
        
        # Test basic queries
        file_count = fitsFile.select().count()
        session_count = fitsSession.select().count()
        
        logging.info(f"Database validation successful: {file_count} files, {session_count} sessions")
        return True
        
    except Exception as e:
        raise Exception(f"Database validation failed: {e}")

def get_light_files_for_session(session_id):
    """Get light frame files for a specific session"""
    try:
        from astrofiler_db import fitsFile as FitsFileModel, fitsSession as FitsSessionModel
        
        # Get session
        session = FitsSessionModel.get_by_id(session_id)
        
        # Get light files for session
        light_files = FitsFileModel.select().where(
            (FitsFileModel.fitsFileSession == session) &
            (FitsFileModel.fitsFileType.in_(['LIGHT', 'Light', 'light', 'Science', 'science', 'LIGHT FRAME', 'Light Frame', '']))
        )
        
        file_paths = []
        for light_file in light_files:
            if light_file.fitsFileName and os.path.exists(light_file.fitsFileName):
                file_paths.append(light_file.fitsFileName)
            else:
                logging.warning(f"Light file not found: {light_file.fitsFileName}")
                
        logging.info(f"Found {len(file_paths)} light files for session {session_id}")
        return file_paths, session
        
    except Exception as e:
        raise Exception(f"Failed to get light files for session {session_id}: {e}")

def get_light_files_for_object(object_name):
    """Get all light frame files for a specific object"""
    try:
        from astrofiler_db import fitsFile as FitsFileModel, fitsSession as FitsSessionModel
        
        # Get sessions for object
        sessions = FitsSessionModel.select().where(
            FitsSessionModel.fitsSessionObjectName == object_name
        )
        
        file_paths = []
        session_info = []
        
        for session in sessions:
            # Get light files for this session
            light_files = FitsFileModel.select().where(
                (FitsFileModel.fitsFileSession == session) &
                (FitsFileModel.fitsFileType.in_(['LIGHT', 'Light', 'light', 'Science', 'science', 'LIGHT FRAME', 'Light Frame', '']))
            )
            
            session_files = []
            for light_file in light_files:
                if light_file.fitsFileName and os.path.exists(light_file.fitsFileName):
                    file_paths.append(light_file.fitsFileName)
                    session_files.append(light_file.fitsFileName)
                else:
                    logging.warning(f"Light file not found: {light_file.fitsFileName}")
            
            if session_files:
                session_info.append({
                    'session_id': session.fitsSessionId,
                    'session_date': session.fitsSessionDate,
                    'files': session_files
                })
                
        logging.info(f"Found {len(file_paths)} light files for object '{object_name}' across {len(session_info)} sessions")
        return file_paths, session_info
        
    except Exception as e:
        raise Exception(f"Failed to get light files for object '{object_name}': {e}")

def find_master_frames(masters_dir, light_files, bias_master=None, dark_master=None, flat_master=None):
    """Find appropriate master frames for light files"""
    try:
        from astrofiler_smart import get_session_master_frames
        from astrofiler_db import fitsFile as FitsFileModel
        
        masters = {
            'bias': bias_master,
            'dark': dark_master, 
            'flat': flat_master
        }
        
        # If masters are explicitly provided, use them
        if all([bias_master, dark_master, flat_master]):
            logging.info("Using explicitly provided master frames")
            return masters
            
        # Otherwise, try to find masters automatically
        logging.info("Searching for appropriate master frames...")
        
        # Get first light file to determine session
        if light_files:
            first_light = light_files[0]
            
            # Find the database entry for this file
            light_db_entry = FitsFileModel.select().where(
                FitsFileModel.fitsFileName == first_light
            ).first()
            
            if light_db_entry and light_db_entry.fitsFileSession:
                # Use the smart master frame detection
                session_masters = get_session_master_frames(light_db_entry.fitsFileSession)
                
                if session_masters:
                    masters.update(session_masters)
                    logging.info(f"Found session masters: {session_masters}")
                else:
                    logging.info("No session masters found via smart detection")
        
        # Fallback: look in masters directory
        if masters_dir and os.path.exists(masters_dir):
            masters_path = Path(masters_dir)
            
            if not masters['bias']:
                bias_candidates = list(masters_path.glob("*bias*.fits")) + list(masters_path.glob("*BIAS*.fits"))
                if bias_candidates:
                    masters['bias'] = str(bias_candidates[0])
                    logging.info(f"Found bias master: {masters['bias']}")
                    
            if not masters['dark']:
                dark_candidates = list(masters_path.glob("*dark*.fits")) + list(masters_path.glob("*DARK*.fits"))
                if dark_candidates:
                    masters['dark'] = str(dark_candidates[0])
                    logging.info(f"Found dark master: {masters['dark']}")
                    
            if not masters['flat']:
                flat_candidates = list(masters_path.glob("*flat*.fits")) + list(masters_path.glob("*FLAT*.fits"))
                if flat_candidates:
                    masters['flat'] = str(flat_candidates[0])
                    logging.info(f"Found flat master: {masters['flat']}")
        
        # Validate found masters
        for frame_type, master_path in masters.items():
            if master_path:
                if os.path.exists(master_path):
                    logging.info(f"Using {frame_type} master: {master_path}")
                else:
                    logging.warning(f"{frame_type} master not found: {master_path}")
                    masters[frame_type] = None
            else:
                logging.info(f"No {frame_type} master available")
                
        return masters
        
    except Exception as e:
        logging.error(f"Error finding master frames: {e}")
        return {'bias': bias_master, 'dark': dark_master, 'flat': flat_master}

def detect_cfa_status(light_files):
    """Detect if images are Color Filter Array (CFA/OSC) based on FITS headers"""
    try:
        from astropy.io import fits
        
        for light_file in light_files[:3]:  # Check first few files
            try:
                with fits.open(light_file) as hdul:
                    header = hdul[0].header
                    
                    # Check common CFA indicators
                    bayerpat = header.get('BAYERPAT', '').strip()
                    colortyp = header.get('COLORTYP', '').strip()
                    instrume = header.get('INSTRUME', '').strip().lower()
                    
                    # Check for CFA patterns
                    if bayerpat or colortyp == 'RGGB' or 'dslr' in instrume or 'osc' in instrume:
                        logging.info(f"CFA/OSC camera detected: BAYERPAT={bayerpat}, COLORTYP={colortyp}")
                        return True
                        
            except Exception as e:
                logging.warning(f"Could not check CFA status for {light_file}: {e}")
                continue
                
        logging.info("Monochrome camera assumed (no CFA pattern detected)")
        return False
        
    except Exception as e:
        logging.warning(f"Error detecting CFA status: {e}")
        return False

def calibrate_with_pysiril(light_files, masters, output_dir, options):
    """Calibrate light frames using PySiril - basic calibration only"""
    try:
        from pysiril.siril import Siril
        from pysiril.wrapper import Wrapper
        
        logging.info("Starting PySiril basic calibration process...")
        
        # Create temporary working directory
        temp_dir = Path(options.get('temp_dir', 'temp_calibration'))
        temp_dir.mkdir(parents=True, exist_ok=True)
        work_dir = temp_dir / "siril_work"
        work_dir.mkdir(parents=True, exist_ok=True)
        
        logging.info(f"Using working directory: {work_dir}")
        
        try:
            # Initialize Siril
            app = Siril()
            cmd = Wrapper(app)
            app.Open()
            
            # Configure Siril settings for basic processing
            logging.info("Configuring Siril settings...")
            app.Execute("set16bits")  # Use 16-bit processing
            app.Execute("setext fit")  # Use FITS extension
                
            # Change to working directory
            app.Execute(f'cd "{work_dir}"')
            
            # Copy light files to working directory and create sequence
            logging.info(f"Copying {len(light_files)} light files to working directory...")
            
            for i, light_file in enumerate(light_files):
                src_path = Path(light_file)
                dst_name = f"light_{i+1:05d}.fits"
                dst_path = work_dir / dst_name
                shutil.copy2(src_path, dst_path)
                
            # Convert to Siril sequence
            logging.info("Converting to Siril sequence...")
            cmd.convert('light', out=work_dir.as_posix(), fitseq=True)
            
            # Prepare calibration parameters - only basic calibration
            cal_params = {}
            
            # Add master frames if available
            if masters.get('bias') and os.path.exists(masters['bias']):
                bias_work = work_dir / "bias_master.fit"
                shutil.copy2(masters['bias'], bias_work)
                cal_params['bias'] = 'bias_master'
                logging.info(f"Using bias master: {os.path.basename(masters['bias'])}")
                
            if masters.get('dark') and os.path.exists(masters['dark']):
                dark_work = work_dir / "dark_master.fit"
                shutil.copy2(masters['dark'], dark_work)
                cal_params['dark'] = 'dark_master'
                logging.info(f"Using dark master: {os.path.basename(masters['dark'])}")
                
            if masters.get('flat') and os.path.exists(masters['flat']):
                flat_work = work_dir / "flat_master.fit"
                shutil.copy2(masters['flat'], flat_work)
                cal_params['flat'] = 'flat_master'
                logging.info(f"Using flat master: {os.path.basename(masters['flat'])}")
            
            # Perform basic calibration only
            logging.info("Performing basic light frame calibration (bias, dark, flat)...")
            
            if not cal_params:
                logging.warning("No master frames available - copying uncalibrated frames")
                # Just copy files if no calibration frames available
                sequence_name = 'light'
            else:
                # Execute preprocessing (calibration only)
                cmd.preprocess('light', **cal_params)
                sequence_name = 'pp_light'
            
            # Copy individual calibrated frames to output directory
            logging.info("Copying calibrated frames to output directory...")
            
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            calibrated_files = []
            
            if sequence_name == 'light':
                # No calibration applied, copy original files with _calibrated suffix
                for i, light_file in enumerate(light_files):
                    original_name = Path(light_file).stem
                    output_name = f"{original_name}_calibrated.fits"
                    output_file = output_path / output_name
                    shutil.copy2(light_file, output_file)
                    calibrated_files.append(str(output_file))
                    logging.info(f"Copied (no calibration): {output_name}")
            else:
                # Copy calibrated files
                sequence_pattern = f"{sequence_name}_*.fit*"
                cal_files = list(work_dir.glob(sequence_pattern))
                cal_files.sort()  # Ensure correct order
                
                for i, cal_file in enumerate(cal_files):
                    if i < len(light_files):
                        original_name = Path(light_files[i]).stem
                        output_name = f"{original_name}_calibrated.fits"
                        output_file = output_path / output_name
                        
                        shutil.copy2(cal_file, output_file)
                        calibrated_files.append(str(output_file))
                        logging.info(f"Calibrated: {output_name}")
                        
            logging.info(f"Successfully calibrated {len(calibrated_files)} light frames")
            
            return {
                'success': True,
                'calibrated_files': calibrated_files,
                'processed_files': len(light_files),
                'calibration_masters': masters
            }
                
        finally:
            # Close Siril
            try:
                app.Close()
            except:
                pass
            
            # Cleanup temporary files if requested
            if not options.get('keep_temp', False):
                logging.info("Cleaning up temporary files...")
                shutil.rmtree(work_dir, ignore_errors=True)
                
    except Exception as e:
        raise Exception(f"PySiril calibration failed: {e}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='AstroFiler Simple Light Frame Calibration using PySiril',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Basic options
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('-c', '--config', default='astrofiler.ini',
                       help='Path to configuration file (default: astrofiler.ini)')
    
    # Input selection
    parser.add_argument('-s', '--session', type=str,
                       help='Specific session ID to calibrate')
    parser.add_argument('-o', '--object', type=str,
                       help='Calibrate all sessions for specific object name')
    parser.add_argument('-f', '--files', type=str,
                       help='Specific FITS files to calibrate (comma-separated paths)')
    
    # Output options
    parser.add_argument('-d', '--output-dir', type=str,
                       help='Output directory for calibrated files (default: same as input)')
    parser.add_argument('--force', action='store_true',
                       help='Force recalibration even if output exists')
    
    # Master frame options
    parser.add_argument('--masters-dir', type=str, default='Masters',
                       help='Directory containing master frames (default: Masters/)')
    parser.add_argument('--bias-master', type=str,
                       help='Specific bias master frame path')
    parser.add_argument('--dark-master', type=str,
                       help='Specific dark master frame path')
    parser.add_argument('--flat-master', type=str,
                       help='Specific flat master frame path')
    
    # System options
    parser.add_argument('--temp-dir', type=str, default='temp_calibration',
                       help='Temporary directory for processing')
    parser.add_argument('--keep-temp', action='store_true',
                       help='Keep temporary processing files')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without processing')
    parser.add_argument('--log-file', type=str,
                       help='Write logs to specified file in addition to console')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose, args.log_file)
    
    logging.info("AstroFiler Simple Light Frame Calibration Tool Starting...")
    if args.dry_run:
        logging.info("DRY RUN MODE - No processing will be performed")
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Validate prerequisites
        if not args.dry_run:
            validate_siril_installation()
        validate_database_access()
        
        # Determine input files
        light_files = []
        
        if args.session:
            logging.info(f"Processing session: {args.session}")
            light_files, session_info = get_light_files_for_session(args.session)
            
        elif args.object:
            logging.info(f"Processing object: {args.object}")
            light_files, session_info = get_light_files_for_object(args.object)
            
        elif args.files:
            logging.info("Processing specific files")
            file_paths = [f.strip() for f in args.files.split(',')]
            light_files = [f for f in file_paths if os.path.exists(f)]
            
            if len(light_files) != len(file_paths):
                missing = [f for f in file_paths if not os.path.exists(f)]
                logging.warning(f"Missing files: {missing}")
        else:
            raise ValueError("Must specify --session, --object, or --files")
        
        if not light_files:
            logging.error("No light files found to process")
            return 1
            
        logging.info(f"Found {len(light_files)} light files to process")
        
        # Determine output directory
        if args.output_dir:
            output_dir = args.output_dir
        else:
            # Use same directory as first light file
            output_dir = os.path.dirname(light_files[0])
            
        logging.info(f"Output directory: {output_dir}")
        
        # Find master frames
        logging.info("Searching for master calibration frames...")
        masters = find_master_frames(
            args.masters_dir,
            light_files,
            args.bias_master,
            args.dark_master,
            args.flat_master
        )
        
        # Detect CFA status
        cfa_detected = detect_cfa_status(light_files)
        
        # Prepare processing options (simplified)
        processing_options = {
            'temp_dir': args.temp_dir,
            'keep_temp': args.keep_temp
        }
        
        # Show processing plan
        logging.info("=== PROCESSING PLAN ===")
        logging.info(f"Input files: {len(light_files)}")
        logging.info(f"Output directory: {output_dir}")
        logging.info(f"CFA/OSC camera: {cfa_detected}")
        
        for frame_type, master_path in masters.items():
            if master_path:
                logging.info(f"Master {frame_type}: {os.path.basename(master_path)}")
            else:
                logging.info(f"Master {frame_type}: NOT AVAILABLE")
        
        if args.dry_run:
            logging.info("Dry run completed - no processing performed")
            return 0
        
        # Perform calibration
        logging.info("Starting basic calibration process...")
        start_time = time.time()
        
        result = calibrate_with_pysiril(light_files, masters, output_dir, processing_options)
        
        if result.get('success'):
            elapsed_time = time.time() - start_time
            logging.info(f"Calibration completed successfully in {elapsed_time:.1f} seconds")
            
            # Report results
            logging.info("=== CALIBRATION RESULTS ===")
            logging.info(f"Files processed: {result.get('processed_files', 0)}")
            logging.info(f"Calibrated files: {len(result.get('calibrated_files', []))}")
            
            return 0
        else:
            logging.error("Calibration failed")
            return 1
            
    except KeyboardInterrupt:
        logging.info("Operation cancelled by user")
        return 130
        
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())