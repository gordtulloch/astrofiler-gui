#!/usr/bin/env python3
"""
AutoCalibration.py - Command line utility for auto-calibration operations

This script performs automatic calibration operations including master frame creation,
light frame calibration, and quality assessment from the command line.

Logging:
    - All output is logged to astrofiler.log by default (suitable for nightly tasks)
    - Use --log-file to specify an alternative log file
    - Use --quiet to suppress console output (logs only to file)
    - Use --verbose for detailed debug logging

Usage:
    python AutoCalibration.py [options]

Options:
    -h, --help          Show this help message and exit
    -v, --verbose       Enable verbose logging
    -q, --quiet         Suppress console output (logs only to file)
    -c, --config        Path to configuration file (default: astrofiler.ini)
    -o, --operation     Operation to perform (analyze|masters|calibrate-lights|quality|all|clear-masters)
    -s, --session       Specific session ID to process (optional)
    -f, --force         Force operation even if masters exist or frames already calibrated
    --quality-only      Only perform quality assessment without calibration
    -r, --report        Generate detailed quality report
    --min-files         Override minimum files per master (default: from config)
    --no-cleanup        Skip cleanup operations after processing
    --dry-run           Show what would be done without making changes
    --log-file          Write logs to specified file (default: astrofiler.log)

Operations:
    analyze             Analyze sessions for calibration opportunities
    masters             Create master calibration frames only
    calibrate-lights    Calibrate light frames using existing masters (PySiril/numpy)
    quality             Assess frame and master quality only
    clear-masters       Clear all existing master frames from database and files
    all                 Complete auto-calibration workflow (default)

Quality Assessment:
    - FWHM analysis for light frames (seeing quality)
    - Uniformity analysis for calibration frames
    - Noise metrics and signal-to-noise ratios
    - Overall quality scoring (0-100)
    - Intelligent recommendations

Examples:
    # Complete auto-calibration workflow
    python AutoCalibration.py
    
    # Analyze calibration opportunities with verbose output
    python AutoCalibration.py -o analyze -v
    
    # Create masters for specific session
    python AutoCalibration.py -o masters -s 123 -v
    
    # Calibrate light frames (uses PySiril if available, numpy fallback)
    python AutoCalibration.py -o calibrate-lights -v
    
    # Force recalibrate already-calibrated frames
    python AutoCalibration.py -o calibrate-lights --force -v
    
    # Quality assessment with detailed report
    python AutoCalibration.py -o quality -r -v
    
    # Clear all existing master frames
    python AutoCalibration.py -o clear-masters -v
    
    # Dry run to see what would be processed
    python AutoCalibration.py --dry-run -v
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

import time

def ensure_astrofiler_imports():
    """Ensure astrofiler package can be imported correctly from src directory"""
    global src_path
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

def setup_logging(verbose=False, quiet=False, log_file=None):
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create formatters
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Setup handlers - always include file logging
    handlers = []
    
    # Add console handler unless quiet mode is enabled
    if not quiet:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        handlers.append(console_handler)
    
    # Default to astrofiler.log if no specific log file provided
    if log_file is None:
        log_file = 'astrofiler.log'
    
    # Add file handler
    try:
        file_handler = logging.FileHandler(log_file, mode='a')  # Append mode for nightly tasks
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
    except Exception as e:
        # If we can't write to the log file, fall back to console only
        if quiet:
            # In quiet mode, if file logging fails, use console to show error
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(console_formatter)
            handlers.append(console_handler)
        print(f"Warning: Could not setup file logging to {log_file}: {e}")
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # Force reconfiguration if already configured
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

def get_auto_calibration_config(config):
    """Extract auto-calibration configuration from config file"""
    try:
        auto_cal_config = {
            'min_files_per_master': config.getint('DEFAULT', 'min_files_per_master', fallback=3),
            'auto_calibration_progress': config.getboolean('DEFAULT', 'auto_calibration_progress', fallback=True),
            'siril_path': config.get('DEFAULT', 'siril_cli_path', fallback=''),
        }
        
        # Validate Siril path if specified
        if auto_cal_config['siril_path'] and not os.path.exists(auto_cal_config['siril_path']):
            logging.warning(f"Siril path not found: {auto_cal_config['siril_path']}")
            logging.warning("Master frame creation will use fallback methods")
        
        return auto_cal_config
        
    except Exception as e:
        raise ValueError(f"Invalid auto-calibration configuration: {e}")

def validate_database_access():
    """Validate database connectivity"""
    try:
        ensure_astrofiler_imports()
        
        from astrofiler.database import setup_database
        from astrofiler.models import fitsFile, fitsSession
        
        # Setup database connection
        setup_database()
        
        # Test basic queries
        file_count = fitsFile.select().count()
        session_count = fitsSession.select().count()
        
        logging.info(f"Database validation successful: {file_count} files, {session_count} sessions")
        return True
        
    except Exception as e:
        raise Exception(f"Database validation failed: {e}")

def analyze_calibration_opportunities(config, session_id=None, min_files=None):
    """Analyze sessions for calibration opportunities with detailed diagnostic information"""
    ensure_astrofiler_imports()
    
    from astrofiler.core.master_manager import get_master_manager
    from astrofiler.models import fitsSession as FitsSessionModel
    
    logging.info("Starting calibration opportunity analysis...")
    
    try:
        master_manager = get_master_manager()
        
        # Get min files configuration
        configured_min_files = config.getint('DEFAULT', 'min_files_per_master', fallback=3)
        actual_min_files = min_files if min_files else configured_min_files
        
        logging.info(f"Using minimum files per master: {actual_min_files} (config default: {configured_min_files})")
        
        # Get master statistics to show current state
        stats = master_manager.get_master_statistics()
        
        logging.info(f"Current master frame status:")
        logging.info(f"  - Total masters: {stats.get('total_masters', 0)}")
        logging.info(f"  - Bias masters: {stats.get('by_type', {}).get('bias', 0)}")
        logging.info(f"  - Dark masters: {stats.get('by_type', {}).get('dark', 0)}")
        logging.info(f"  - Flat masters: {stats.get('by_type', {}).get('flat', 0)}")
        logging.info(f"  - Total file size: {stats.get('total_size', 0) / (1024**3):.1f} GB")
        
        # Analyze calibration sessions for opportunities
        logging.info("Scanning for calibration sessions...")
        
        # Query calibration sessions
        calibration_types = ['bias', 'Bias', 'BIAS', 'dark', 'Dark', 'DARK', 'flat', 'Flat', 'FLAT']
        all_cal_sessions = FitsSessionModel.select().where(
            FitsSessionModel.fitsSessionObjectName.in_(calibration_types)
        )
        
        sessions_by_type = {'bias': [], 'dark': [], 'flat': []}
        total_sessions = 0
        
        for session in all_cal_sessions:
            total_sessions += 1
            obj_name = session.fitsSessionObjectName.lower()
            cal_type = None
            
            if 'bias' in obj_name:
                cal_type = 'bias'
            elif 'dark' in obj_name:
                cal_type = 'dark'
            elif 'flat' in obj_name:
                cal_type = 'flat'
            
            if cal_type:
                # Check if session has enough files
                file_count = session.get_session_file_count()
                can_create_master = file_count >= actual_min_files
                
                session_info = {
                    'session_id': session.fitsSessionId,
                    'session_type': obj_name,
                    'file_count': file_count,
                    'can_create_master': can_create_master,
                    'telescope': session.fitsSessionTelescope or 'Unknown',
                    'instrument': session.fitsSessionImager or 'Unknown',
                    'date': str(session.fitsSessionDate) if session.fitsSessionDate else 'Unknown'
                }
                
                if can_create_master:
                    sessions_by_type[cal_type].append(session_info)
        
        logging.info(f"Found {total_sessions} total calibration sessions")
        
        # Report analysis results
        logging.info(f"\n=== MASTER CREATION OPPORTUNITIES ===")
        
        total_opportunities = 0
        for cal_type in ['bias', 'dark', 'flat']:
            viable_sessions = sessions_by_type[cal_type]
            total_opportunities += len(viable_sessions)
            
            logging.info(f"\n{cal_type.upper()} Sessions:")
            logging.info(f"  Sessions with {actual_min_files}+ files: {len(viable_sessions)}")
            
            if viable_sessions:
                for i, session in enumerate(viable_sessions[:5], 1):  # Show first 5
                    logging.info(f"    {i}. Session {session['session_id']}: {session['file_count']} files")
                    logging.info(f"       {session['telescope']}, {session['instrument']}, {session['date']}")
                
                if len(viable_sessions) > 5:
                    logging.info(f"    ... and {len(viable_sessions) - 5} more sessions")
        
        if total_opportunities > 0:
            logging.info(f"\nTotal opportunities: {total_opportunities} sessions ready for master creation")
            logging.info(f"To create these masters, run:")
            logging.info(f"  python AutoCalibration.py -o masters -v")
        else:
            logging.info(f"\nNo calibration sessions found with sufficient files ({actual_min_files}+ each)")
        
        # Analyze light frames calibration status
        logging.info(f"\n=== LIGHT FRAME CALIBRATION STATUS ===")
        
        from astrofiler.models import fitsFile as FitsFileModel
        
        # Query all light frames
        light_frames_query = FitsFileModel.select().where(
            FitsFileModel.fitsFileType.contains('Light')
        )
        
        total_light_frames = light_frames_query.count()
        
        # Count calibrated light frames
        calibrated_light_frames = FitsFileModel.select().where(
            (FitsFileModel.fitsFileType.contains('Light')) &
            (FitsFileModel.fitsFileCalibrated == 1)
        ).count()
        
        uncalibrated_light_frames = total_light_frames - calibrated_light_frames
        
        logging.info(f"Total light frames: {total_light_frames}")
        logging.info(f"  - Calibrated: {calibrated_light_frames}")
        logging.info(f"  - Uncalibrated: {uncalibrated_light_frames}")
        
        if uncalibrated_light_frames > 0:
            calibration_percentage = (calibrated_light_frames / total_light_frames * 100) if total_light_frames > 0 else 0
            logging.info(f"  - Calibration progress: {calibration_percentage:.1f}%")
        
        # Analyze soft-deleted frames
        logging.info(f"\n=== SOFT-DELETED FRAMES ===")
        
        # Count soft-deleted light frames
        soft_deleted_lights = FitsFileModel.select().where(
            (FitsFileModel.fitsFileType.contains('Light')) &
            (FitsFileModel.fitsFileSoftDelete == True)
        ).count()
        
        # Count soft-deleted calibration frames by type
        soft_deleted_bias = FitsFileModel.select().where(
            (FitsFileModel.fitsFileType.contains('Bias')) &
            (FitsFileModel.fitsFileSoftDelete == True)
        ).count()
        
        soft_deleted_dark = FitsFileModel.select().where(
            (FitsFileModel.fitsFileType.contains('Dark')) &
            (FitsFileModel.fitsFileSoftDelete == True)
        ).count()
        
        soft_deleted_flat = FitsFileModel.select().where(
            (FitsFileModel.fitsFileType.contains('Flat')) &
            (FitsFileModel.fitsFileSoftDelete == True)
        ).count()
        
        soft_deleted_calibration = soft_deleted_bias + soft_deleted_dark + soft_deleted_flat
        total_soft_deleted = soft_deleted_lights + soft_deleted_calibration
        
        logging.info(f"Total soft-deleted frames: {total_soft_deleted}")
        logging.info(f"  - Light frames: {soft_deleted_lights}")
        logging.info(f"  - Calibration frames: {soft_deleted_calibration}")
        logging.info(f"    • Bias frames: {soft_deleted_bias}")
        logging.info(f"    • Dark frames: {soft_deleted_dark}")
        logging.info(f"    • Flat frames: {soft_deleted_flat}")
        
        if total_soft_deleted > 0:
            logging.info(f"\nTo permanently remove soft-deleted frames:")
            logging.info(f"  Use the AstroFiler GUI Duplicates widget to manage deleted files")
        
        return {
            'total_opportunities': total_opportunities,
            'bias_sessions': sessions_by_type['bias'],
            'dark_sessions': sessions_by_type['dark'],
            'flat_sessions': sessions_by_type['flat'],
            'light_frame_stats': {
                'total': total_light_frames,
                'calibrated': calibrated_light_frames,
                'uncalibrated': uncalibrated_light_frames
            },
            'soft_deleted_stats': {
                'total': total_soft_deleted,
                'light_frames': soft_deleted_lights,
                'calibration_frames': soft_deleted_calibration,
                'bias_frames': soft_deleted_bias,
                'dark_frames': soft_deleted_dark,
                'flat_frames': soft_deleted_flat
            }
        }
        
    except Exception as e:
        logging.error(f"Error analyzing calibration opportunities: {e}")
        return {'error': str(e)}

def create_master_frames(config, session_id=None, force=False, dry_run=False, verbose=False):
    """Create master calibration frames - wrapper for core library function"""
    ensure_astrofiler_imports()
    
    from astrofiler.core.auto_calibration import create_master_frames as core_create_master_frames
    
    logging.info("Starting master frame creation...")
    
    try:
        # Call the core library function with CLI progress callback
        success = core_create_master_frames(
            config=config,
            session_id=session_id,
            force=force,
            dry_run=dry_run,
            verbose=verbose,
            progress_callback=create_cli_progress_callback("Creating masters")
        )
        
        return success
            
    except Exception as e:
        logging.error(f"Error in master frame creation: {e}")
        return False

def clear_all_masters(config, dry_run=False):
    """
    Clear all existing master frames from database and files.
    
    Args:
        config: Configuration object
        dry_run: If True, show what would be done without making changes
        
    Returns:
        bool: True if successful, False otherwise
    """
    from astrofiler.core.master_manager import get_master_manager
    from astrofiler.models import Masters
    import os
    
    logging.info("Starting master frames cleanup...")
    
    try:
        if dry_run:
            logging.info("DRY RUN: Showing what would be cleared")
        
        # Get all masters from database
        all_masters = list(Masters.select())
        
        if not all_masters:
            logging.info("No master frames found in database")
            return True
        
        logging.info(f"Found {len(all_masters)} master frame(s) in database")
        
        # Get statistics before deletion
        master_stats = {}
        total_size = 0
        files_to_delete = []
        
        for master in all_masters:
            master_type = master.master_type or 'unknown'
            master_stats[master_type] = master_stats.get(master_type, 0) + 1
            
            # Check if file exists and get size
            if master.master_path and os.path.exists(master.master_path):
                file_size = os.path.getsize(master.master_path)
                total_size += file_size
                files_to_delete.append((master.master_path, file_size))
                
                if dry_run:
                    logging.info(f"  Would delete: {master.master_path} ({file_size:,} bytes)")
            elif master.master_path:
                logging.warning(f"  File not found: {master.master_path}")
        
        # Report what will be cleared
        logging.info("Master frame summary:")
        for cal_type, count in master_stats.items():
            logging.info(f"  - {cal_type.title()} masters: {count}")
        logging.info(f"  - Total file size: {total_size / (1024*1024):.1f} MB")
        logging.info(f"  - Files to delete: {len(files_to_delete)}")
        
        if dry_run:
            logging.info("DRY RUN: No changes made")
            return True
        
        # Confirm deletion
        logging.warning("This will permanently delete ALL master frames and their database records!")
        logging.info("Database records to delete:")
        for master in all_masters:
            logging.info(f"  - {master.master_id} ({master.master_type}, {master.creation_date})")
        
        # Delete files first
        deleted_files = 0
        deleted_size = 0
        
        for file_path, file_size in files_to_delete:
            try:
                os.remove(file_path)
                deleted_files += 1
                deleted_size += file_size
                logging.info(f"Deleted file: {file_path}")
            except Exception as e:
                logging.warning(f"Failed to delete file {file_path}: {e}")
        
        # Delete database records
        deleted_records = 0
        for master in all_masters:
            try:
                master.delete_instance()
                deleted_records += 1
                logging.info(f"Deleted database record: {master.master_id}")
            except Exception as e:
                logging.warning(f"Failed to delete database record {master.master_id}: {e}")
        
        # Clean up ALL files and directories in Masters folder
        masters_dir = os.path.join(config.get('DEFAULT', 'repo', fallback='./'), 'Masters')
        if os.path.exists(masters_dir):
            try:
                import shutil
                # Get list of all items in Masters directory
                all_items = []
                for item in os.listdir(masters_dir):
                    item_path = os.path.join(masters_dir, item)
                    all_items.append(item_path)
                    if dry_run:
                        if os.path.isdir(item_path):
                            # Count files in subdirectory
                            file_count = sum(len(files) for _, _, files in os.walk(item_path))
                            logging.info(f"  Would remove directory: {item_path} ({file_count} files)")
                        else:
                            file_size = os.path.getsize(item_path)
                            logging.info(f"  Would remove file: {item_path} ({file_size:,} bytes)")
                
                if not dry_run:
                    # Remove all items in Masters directory
                    for item_path in all_items:
                        try:
                            if os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                                logging.info(f"Removed directory: {item_path}")
                            else:
                                os.remove(item_path)
                                logging.info(f"Removed file: {item_path}")
                        except Exception as e:
                            logging.warning(f"Failed to remove {item_path}: {e}")
                            
            except Exception as e:
                logging.warning(f"Error cleaning up master directories: {e}")
        else:
            logging.warning(f"Masters directory not found: {masters_dir}")
        
        # Report results
        logging.info("Master frames cleanup completed:")
        logging.info(f"  - Files deleted: {deleted_files}")
        logging.info(f"  - Space freed: {deleted_size / (1024*1024):.1f} MB")
        logging.info(f"  - Database records deleted: {deleted_records}")
        
        if deleted_records == len(all_masters) and deleted_files == len(files_to_delete):
            logging.info("All master frames successfully cleared!")
            return True
        else:
            logging.warning("Some master frames could not be cleared. Check logs for details.")
            return False
            
    except Exception as e:
        logging.error(f"Error clearing master frames: {e}")
        return False

def perform_quality_assessment(config, session_id=None, generate_report=False):
    """Perform quality assessment on frames"""
    from astrofiler.core import fitsProcessing
    from astrofiler.models import fitsFile, fitsSession
    
    logging.info("Starting quality assessment...")
    
    try:
        processor = fitsProcessing()
        
        # Get files to assess
        query = fitsFile.select()
        if session_id:
            query = query.where(fitsFile.fitsFileSessionId == session_id)
        
        files_to_assess = list(query)
        
        if not files_to_assess:
            logging.info("No files found for quality assessment")
            return True
        
        # Convert to file paths
        file_paths = [f.fitsFileId for f in files_to_assess]
        
        logging.info(f"Assessing quality of {len(file_paths)} files...")
        
        # Batch quality assessment
        results = processor.batchAssessQuality(
            file_paths=file_paths,
            progress_callback=create_cli_progress_callback("Quality assessment")
        )
        
        # Analyze results
        if results:
            scores = [r.get('overall_score', 0) for r in results if 'overall_score' in r]
            if scores:
                avg_score = sum(scores) / len(scores)
                logging.info(f"Quality assessment complete: Average score {avg_score:.1f}/100")
                
                # Quality distribution
                excellent = len([s for s in scores if s >= 90])
                good = len([s for s in scores if 75 <= s < 90])
                acceptable = len([s for s in scores if 60 <= s < 75])
                poor = len([s for s in scores if 40 <= s < 60])
                unusable = len([s for s in scores if s < 40])
                
                logging.info(f"Quality distribution: Excellent: {excellent}, Good: {good}, "
                           f"Acceptable: {acceptable}, Poor: {poor}, Unusable: {unusable}")
                
                if generate_report:
                    generate_quality_report(results, config)
            
        return True
        
    except Exception as e:
        logging.error(f"Error in quality assessment: {e}")
        return False

def calibrate_light_frames(config, session_id=None, force=False, dry_run=False):
    """
    Calibrate light frames using available master frames - wrapper for core library function.
    
    Uses PySiril for professional-grade calibration when available, falls back to numpy.
    
    Light frames are calibrated by:
    1. Subtracting master bias
    2. Subtracting master dark
    3. Dividing by master flat (normalized)
    
    The calibrated frames are saved with 'cal_' prefix in the same directory.
    """
    ensure_astrofiler_imports()
    
    from astrofiler.core.auto_calibration import calibrate_light_frames as core_calibrate_light_frames
    
    logging.info("Starting light frame calibration...")
    if force:
        logging.info("Force recalibration enabled - will recalibrate already-calibrated frames")
    
    try:
        # Call the core library function with CLI progress callback
        success = core_calibrate_light_frames(
            config=config,
            session_id=session_id,
            force_recalibrate=force,
            dry_run=dry_run,
            progress_callback=create_cli_progress_callback("Calibrating lights")
        )
        
        return success
    except Exception as e:
        logging.error(f"Error in light frame calibration: {e}")
        return False

def run_complete_workflow(config, session_id=None, force=False, dry_run=False):
    """Run the complete auto-calibration workflow"""
    from astrofiler.core import fitsProcessing
    
    logging.info("Starting complete auto-calibration workflow...")
    
    try:
        processor = fitsProcessing()
        
        # Run the complete workflow
        result = processor.runAutoCalibrationWorkflow(
            progress_callback=create_cli_progress_callback("Auto-calibration workflow")
        )
        
        if result.get('success', False):
            logging.info("Auto-calibration workflow completed successfully")
            
            # Report results
            masters_created = result.get('masters_created', 0)
            opportunities_found = result.get('opportunities_detected', 0)
            errors = result.get('errors', [])
            
            logging.info(f"Results: {masters_created} masters created, {opportunities_found} opportunities found")
            
            if errors:
                logging.warning(f"Workflow completed with {len(errors)} errors:")
                for error in errors:
                    logging.warning(f"  - {error}")
            
            return True
        else:
            errors = result.get('errors', [])
            logging.error(f"Auto-calibration workflow failed: {'; '.join(errors)}")
            return False
        
    except Exception as e:
        logging.error(f"Error in complete workflow: {e}")
        return False

def create_cli_progress_callback(operation_name):
    """Create a progress callback suitable for CLI output"""
    last_percent = -1
    
    def progress_callback(current, total=None, message=""):
        nonlocal last_percent
        
        # Handle two call signatures:
        # 1. (current, total, message) - standard 3-arg format
        # 2. (percentage, message) - 2-arg format where current is already a percentage
        
        if total is None:
            # 2-arg format: current is percentage, total is message
            percent = int(current)
            message = total if isinstance(total, str) else ""
        elif isinstance(total, int) and total > 0:
            # 3-arg format: calculate percentage
            percent = int((current / total) * 100)
        else:
            # Just log the message
            logging.info(f"{operation_name}: {message if message else total}")
            return True
        
        # Only log every 10% to avoid spam
        if percent != last_percent and percent % 10 == 0:
            logging.info(f"{operation_name}: {percent}% - {message}")
            last_percent = percent
        
        return True  # Continue processing
    
    return progress_callback

def generate_quality_report(quality_results, config):
    """Generate detailed quality assessment report"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"quality_report_{timestamp}.txt"
        
        with open(report_filename, 'w') as f:
            f.write("AstroFiler Quality Assessment Report\n")
            f.write("=" * 40 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total files assessed: {len(quality_results)}\n\n")
            
            # Summary statistics
            scores = [r.get('overall_score', 0) for r in quality_results if 'overall_score' in r]
            if scores:
                f.write(f"Average quality score: {sum(scores)/len(scores):.1f}/100\n")
                f.write(f"Best quality score: {max(scores):.1f}/100\n")
                f.write(f"Worst quality score: {min(scores):.1f}/100\n\n")
            
            # Detailed results
            f.write("Individual File Results:\n")
            f.write("-" * 40 + "\n")
            
            for i, result in enumerate(quality_results, 1):
                file_path = result.get('file_path', f'File {i}')
                score = result.get('overall_score', 0)
                category = result.get('quality_category', 'Unknown')
                
                f.write(f"{i}. {os.path.basename(file_path)}\n")
                f.write(f"   Score: {score:.1f}/100 ({category})\n")
                
                # Add specific metrics if available
                frame_type = result.get('frame_type', 'Unknown')
                f.write(f"   Type: {frame_type}\n")
                
                if 'fwhm_metrics' in result:
                    fwhm = result['fwhm_metrics'].get('fwhm_average', 0)
                    if fwhm > 0:
                        f.write(f"   FWHM: {fwhm:.2f} pixels\n")
                
                if 'noise_metrics' in result:
                    snr = result['noise_metrics'].get('signal_to_noise', 0)
                    if snr > 0:
                        f.write(f"   SNR: {snr:.2f}\n")
                
                f.write("\n")
        
        logging.info(f"Quality report saved to: {report_filename}")
        
    except Exception as e:
        logging.error(f"Error generating quality report: {e}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='AstroFiler Auto-Calibration CLI Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Suppress console output (logs only to file)')
    parser.add_argument('-c', '--config', default='astrofiler.ini',
                       help='Path to configuration file (default: astrofiler.ini)')
    parser.add_argument('-o', '--operation', choices=['analyze', 'masters', 'calibrate-lights', 'quality', 'all', 'clear-masters'],
                       default='all', help='Operation to perform (default: all)')
    parser.add_argument('-s', '--session', type=str,
                       help='Specific session ID to process')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Force operation even if masters exist')
    parser.add_argument('--quality-only', action='store_true',
                       help='Only perform quality assessment without calibration')
    parser.add_argument('-r', '--report', action='store_true',
                       help='Generate detailed quality report')
    parser.add_argument('--min-files', type=int,
                       help='Override minimum files per master')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Skip cleanup operations after processing')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--log-file',
                       help='Write logs to specified file (default: astrofiler.log)')
    
    args = parser.parse_args()
    
    # Setup logging with astrofiler.log as default
    setup_logging(args.verbose, args.quiet, args.log_file)
    
    logging.info("AstroFiler Auto-Calibration CLI Tool Starting...")
    logging.info(f"Operation: {args.operation}")
    if args.dry_run:
        logging.info("DRY RUN MODE - No changes will be made")
    
    try:
        # Load configuration
        config = load_config(args.config)
        auto_cal_config = get_auto_calibration_config(config)
        
        # Validate database access
        validate_database_access()
        
        # Execute requested operation
        success = True
        
        if args.operation == 'analyze':
            opportunities = analyze_calibration_opportunities(config, args.session, args.min_files)
            success = opportunities is not None
            
        elif args.operation == 'masters':
            success = create_master_frames(config, args.session, args.force, args.dry_run, args.verbose)
            
        elif args.operation == 'calibrate-lights':
            success = calibrate_light_frames(config, args.session, args.force, args.dry_run)
            
        elif args.operation == 'quality':
            success = perform_quality_assessment(config, args.session, args.report)
            
        elif args.operation == 'clear-masters':
            success = clear_all_masters(config, args.dry_run)
            
        elif args.operation == 'all':
            if args.quality_only:
                success = perform_quality_assessment(config, args.session, args.report)
            else:
                success = run_complete_workflow(config, args.session, args.force, args.dry_run)
        
        if success:
            logging.info("Auto-calibration operation completed successfully")
            return 0
        else:
            logging.error("Auto-calibration operation failed")
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
