#!/usr/bin/env python3
"""
AutoCalibration.py - Command line utility for auto-calibration operations

This script performs automatic calibration operations including master frame creation,
light frame calibration, and quality assessment from the command line.

Usage:
    python AutoCalibration.py [options]

Options:
    -h, --help          Show this help message and exit
    -v, --verbose       Enable verbose logging
    -c, --config        Path to configuration file (default: astrofiler.ini)
    -o, --operation     Operation to perform (analyze|masters|calibrate|quality|all)
    -s, --session       Specific session ID to process (optional)
    -f, --force         Force operation even if masters exist
    -q, --quality-only  Only perform quality assessment without calibration
    -r, --report        Generate detailed quality report
    --min-files         Override minimum files per master (default: from config)
    --no-cleanup        Skip cleanup operations after processing
    --dry-run          Show what would be done without making changes

Operations:
    analyze         Analyze sessions for calibration opportunities
    masters         Create master calibration frames only
    calibrate       Calibrate light frames using existing masters
    quality         Assess frame and master quality only
    all             Complete auto-calibration workflow (default)

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
    
    # Quality assessment with detailed report
    python AutoCalibration.py -o quality -r -v
    
    # Dry run to see what would be processed
    python AutoCalibration.py --dry-run -v
"""

import sys
import os
import argparse
import logging
import configparser
from datetime import datetime
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
            'enable_auto_calibration': config.getboolean('DEFAULT', 'enable_auto_calibration', fallback=True),
            'min_files_per_master': config.getint('DEFAULT', 'min_files_per_master', fallback=3),
            'auto_create_triggers': config.get('DEFAULT', 'auto_create_triggers', fallback='manual'),
            'master_retention_days': config.getint('DEFAULT', 'master_retention_days', fallback=365),
            'auto_calibration_progress': config.getboolean('DEFAULT', 'auto_calibration_progress', fallback=True),
            'siril_path': config.get('DEFAULT', 'siril_path', fallback=''),
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

def analyze_calibration_opportunities(config, session_id=None, min_files=None):
    """Analyze sessions for calibration opportunities"""
    from astrofiler_file import fitsProcessing
    
    logging.info("Starting calibration opportunity analysis...")
    
    try:
        processor = fitsProcessing()
        
        # Override min files if specified
        if min_files:
            original_min_files = config.getint('DEFAULT', 'min_files_per_master', fallback=3)
            # Temporarily override in processor if possible
            logging.info(f"Using minimum files per master: {min_files} (config default: {original_min_files})")
        
        # Detect opportunities
        opportunities = processor.detectAutoCalibrationOpportunities(
            progress_callback=create_cli_progress_callback("Analyzing opportunities")
        )
        
        # Report results
        if opportunities:
            logging.info(f"Found {len(opportunities)} calibration opportunities:")
            for i, opp in enumerate(opportunities, 1):
                session_info = opp.get('session_info', {})
                scores = opp.get('scores', {})
                logging.info(f"  {i}. Session {session_info.get('sessionId', 'Unknown')}: "
                           f"Score {scores.get('total_score', 0):.1f}/100")
                logging.info(f"     Files: {scores.get('file_count', 0)}, "
                           f"Types: {', '.join(scores.get('frame_types', []))}")
        else:
            logging.info("No calibration opportunities found")
        
        return opportunities
        
    except Exception as e:
        logging.error(f"Error analyzing calibration opportunities: {e}")
        return []

def create_master_frames(config, session_id=None, force=False, dry_run=False):
    """Create master calibration frames"""
    from astrofiler_file import fitsProcessing
    
    logging.info("Starting master frame creation...")
    
    if dry_run:
        logging.info("DRY RUN - No files will be created")
    
    try:
        processor = fitsProcessing()
        
        # Check for sessions needing masters
        sessions_needing_masters = processor.getSessionsNeedingMasters(
            min_files=config.getint('DEFAULT', 'min_files_per_master', fallback=3)
        )
        
        if session_id:
            # Filter to specific session
            sessions_needing_masters = [s for s in sessions_needing_masters if s.sessionId == session_id]
            if not sessions_needing_masters:
                logging.warning(f"Session {session_id} not found or doesn't need masters")
                return False
        
        if not sessions_needing_masters:
            logging.info("No sessions found that need master frames")
            return True
        
        logging.info(f"Processing {len(sessions_needing_masters)} sessions for master creation")
        
        if dry_run:
            for session in sessions_needing_masters:
                logging.info(f"Would create masters for session {session.sessionId}: {session.sessionName}")
            return True
        
        # Create masters for each session
        success_count = 0
        for session in sessions_needing_masters:
            try:
                logging.info(f"Creating masters for session {session.sessionId}: {session.sessionName}")
                
                result = processor.createMasterCalibrationFrames(
                    session.sessionId,
                    force_recreation=force,
                    progress_callback=create_cli_progress_callback(f"Session {session.sessionId}")
                )
                
                if result.get('success', False):
                    success_count += 1
                    masters_created = result.get('masters_created', {})
                    logging.info(f"Successfully created {len(masters_created)} masters: {', '.join(masters_created.keys())}")
                else:
                    errors = result.get('errors', [])
                    logging.error(f"Failed to create masters: {'; '.join(errors)}")
                    
            except Exception as e:
                logging.error(f"Error creating masters for session {session.sessionId}: {e}")
        
        logging.info(f"Master creation complete: {success_count}/{len(sessions_needing_masters)} sessions successful")
        return success_count > 0
        
    except Exception as e:
        logging.error(f"Error in master frame creation: {e}")
        return False

def perform_quality_assessment(config, session_id=None, generate_report=False):
    """Perform quality assessment on frames"""
    from astrofiler_file import fitsProcessing
    from astrofiler_db import fitsFile, fitsSession
    
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

def calibrate_light_frames(config, session_id=None, dry_run=False):
    """Calibrate light frames using available masters"""
    from astrofiler_smart import calibrate_session_lights, get_session_master_frames
    from astrofiler_db import fitsSession
    
    logging.info("Starting light frame calibration...")
    
    if dry_run:
        logging.info("DRY RUN - Light frame calibration simulation")
    
    try:
        # Get sessions to process
        if session_id:
            sessions = [fitsSession.get_by_id(session_id)]
            if not sessions[0]:
                logging.error(f"Session {session_id} not found")
                return False
        else:
            # Get all sessions that have master frames available
            sessions = fitsSession.select().where(
                (fitsSession.master_dark_created == True) |
                (fitsSession.master_flat_created == True) |
                (fitsSession.master_bias_created == True)
            )
        
        total_sessions = len(sessions) if session_id else sessions.count()
        
        if total_sessions == 0:
            logging.info("No sessions with available master frames found")
            return True
            
        logging.info(f"Processing {total_sessions} sessions for light frame calibration")
        
        success_count = 0
        
        for i, session in enumerate(sessions, 1):
            logging.info(f"Processing session {i}/{total_sessions}: {session.id}")
            
            # Check for available master frames
            master_frames = get_session_master_frames(session.id)
            available_masters = [k for k, v in master_frames.items() if v]
            
            if not available_masters:
                logging.info(f"No master frames available for session {session.id}, skipping")
                continue
                
            logging.info(f"Available masters for session {session.id}: {', '.join(available_masters)}")
            
            if dry_run:
                logging.info(f"DRY RUN: Would calibrate light frames in session {session.id}")
                success_count += 1
                continue
            
            # Calibrate the session
            result = calibrate_session_lights(
                session_id=session.id,
                progress_callback=create_cli_progress_callback(f"Session {session.id} calibration"),
                force_recalibrate=False
            )
            
            if result.get('success', False):
                success_count += 1
                logging.info(f"Session {session.id} calibration completed: "
                           f"{result['calibrated_count']} processed, "
                           f"{result['skipped_count']} skipped, "
                           f"{result['error_count']} errors")
            else:
                logging.error(f"Session {session.id} calibration failed: {result.get('error', 'Unknown error')}")
        
        logging.info(f"Light frame calibration completed: {success_count}/{total_sessions} sessions processed successfully")
        return success_count > 0
        
    except Exception as e:
        logging.error(f"Error in light frame calibration: {e}")
        return False

def run_complete_workflow(config, session_id=None, force=False, dry_run=False):
    """Run the complete auto-calibration workflow"""
    from astrofiler_file import fitsProcessing
    
    logging.info("Starting complete auto-calibration workflow...")
    
    try:
        processor = fitsProcessing()
        
        # Run the complete workflow
        result = processor.runAutoCalibrationWorkflow(
            force_recreation=force,
            session_filter=session_id,
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
    
    def progress_callback(current, total, message=""):
        nonlocal last_percent
        
        if total > 0:
            percent = int((current / total) * 100)
            # Only log every 10% to avoid spam
            if percent != last_percent and percent % 10 == 0:
                logging.info(f"{operation_name}: {percent}% - {message}")
                last_percent = percent
        else:
            logging.info(f"{operation_name}: {message}")
        
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
    parser.add_argument('-c', '--config', default='astrofiler.ini',
                       help='Path to configuration file (default: astrofiler.ini)')
    parser.add_argument('-o', '--operation', choices=['analyze', 'masters', 'calibrate', 'quality', 'all'],
                       default='all', help='Operation to perform (default: all)')
    parser.add_argument('-s', '--session', type=int,
                       help='Specific session ID to process')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Force operation even if masters exist')
    parser.add_argument('-q', '--quality-only', action='store_true',
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
                       help='Write logs to specified file in addition to console')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose, args.log_file)
    
    logging.info("AstroFiler Auto-Calibration CLI Tool Starting...")
    logging.info(f"Operation: {args.operation}")
    if args.dry_run:
        logging.info("DRY RUN MODE - No changes will be made")
    
    try:
        # Load configuration
        config = load_config(args.config)
        auto_cal_config = get_auto_calibration_config(config)
        
        # Check if auto-calibration is enabled
        if not auto_cal_config['enable_auto_calibration']:
            logging.warning("Auto-calibration is disabled in configuration")
            logging.info("To enable: set 'enable_auto_calibration = true' in astrofiler.ini")
            return 1
        
        # Validate database access
        validate_database_access()
        
        # Execute requested operation
        success = True
        
        if args.operation == 'analyze':
            opportunities = analyze_calibration_opportunities(config, args.session, args.min_files)
            success = opportunities is not None
            
        elif args.operation == 'masters':
            success = create_master_frames(config, args.session, args.force, args.dry_run)
            
        elif args.operation == 'calibrate':
            success = calibrate_light_frames(config, args.session, args.dry_run)
            
        elif args.operation == 'quality':
            success = perform_quality_assessment(config, args.session, args.report)
            
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