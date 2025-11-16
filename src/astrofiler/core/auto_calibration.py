"""
Auto-Calibration Core Functions

This module contains the core auto-calibration functions extracted from AutoCalibration.py
for direct use by the GUI, avoiding subprocess calls.
"""

import logging
import os
import configparser
from typing import Optional, Dict, Any, List
from datetime import datetime

# Import database models and core functionality
from ..models import fitsFile, fitsSession, Masters
from ..database import DatabaseManager
from .master_manager import get_master_manager


def load_config(config_path: str = 'astrofiler.ini') -> configparser.ConfigParser:
    """Load configuration from file."""
    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def get_auto_calibration_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get auto-calibration configuration settings."""
    return {
        'min_files_per_master': config.getint('auto_calibration', 'min_files_per_master', fallback=3),
        'enable_quality_assessment': config.getboolean('auto_calibration', 'enable_quality_assessment', fallback=True),
        'quality_threshold': config.getfloat('auto_calibration', 'quality_threshold', fallback=0.7),
        'create_backup': config.getboolean('auto_calibration', 'create_backup', fallback=True),
    }


def validate_database_access() -> bool:
    """Validate that database is accessible and contains data."""
    try:
        # Ensure database is set up
        from ..database import setup_database
        setup_database()
        
        file_count = fitsFile.select().count()
        session_count = fitsSession.select().count()
        
        logging.info(f"Database validation successful: {file_count} files, {session_count} sessions")
        
        if file_count == 0:
            logging.warning("No FITS files found in database")
            return False
            
        return True
        
    except Exception as e:
        logging.error(f"Database validation failed: {e}")
        return False


def analyze_calibration_opportunities(config: configparser.ConfigParser, session_id: Optional[str] = None, 
                                   min_files: Optional[int] = None, progress_callback=None) -> Optional[Dict[str, Any]]:
    """
    Analyze calibration sessions to identify master frame creation opportunities.
    
    Returns:
        Dict with analysis results or None if failed
    """
    try:
        logging.info("Starting analyze_calibration_opportunities function...")
        
        # Get auto-calibration config
        try:
            auto_cal_config = get_auto_calibration_config(config)
            min_files_per_master = min_files or auto_cal_config['min_files_per_master']
            logging.info(f"Config loaded: min_files_per_master = {min_files_per_master}")
        except Exception as e:
            logging.error(f"Error getting auto-calibration config: {e}")
            raise
        
        logging.info("Starting calibration opportunity analysis...")
        logging.info(f"Using minimum files per master: {min_files_per_master} (config default: {auto_cal_config['min_files_per_master']})")
        
        if progress_callback:
            progress_callback(10, "Analyzing current master frame status...")
        
        # Get current master frame status
        try:
            logging.debug("Querying Masters table...")
            masters = Masters.select()
            master_stats = {
                'total': masters.count(),
                'bias': masters.where(Masters.master_type == 'bias').count(),
                'dark': masters.where(Masters.master_type == 'dark').count(),
                'flat': masters.where(Masters.master_type == 'flat').count(),
            }
            logging.info(f"Master stats retrieved: {master_stats}")
        except Exception as e:
            logging.error(f"Error querying Masters table: {e}")
            # Continue without masters info
            master_stats = {'total': 0, 'bias': 0, 'dark': 0, 'flat': 0}
        
        # Calculate total size
        total_size = 0
        for master in masters:
            if master.master_path and os.path.exists(master.master_path):
                total_size += os.path.getsize(master.master_path)
        
        master_stats['total_size_gb'] = total_size / (1024**3)
        
        logging.info("Current master frame status:")
        logging.info(f"  - Total masters: {master_stats['total']}")
        logging.info(f"  - Bias masters: {master_stats['bias']}")
        logging.info(f"  - Dark masters: {master_stats['dark']}")
        logging.info(f"  - Flat masters: {master_stats['flat']}")
        logging.info(f"  - Total file size: {master_stats['total_size_gb']:.1f} GB")
        
        if progress_callback:
            progress_callback(30, "Scanning for calibration sessions...")
        
        # Find calibration sessions
        calibration_types = ['bias', 'Bias', 'BIAS', 'dark', 'Dark', 'DARK', 'flat', 'Flat', 'FLAT']
        query = fitsSession.select().where(fitsSession.fitsSessionObjectName.in_(calibration_types))
        if session_id:
            query = query.where(fitsSession.fitsSessionId == session_id)
        
        sessions = list(query)
        logging.info(f"Found {len(sessions)} total calibration sessions")
        
        if progress_callback:
            progress_callback(50, "Analyzing master creation opportunities...")
        
        # Group sessions by type and analyze
        opportunities = {
            'BIAS': [],
            'DARK': [],
            'FLAT': []
        }
        
        for session in sessions:
            # Count files in session
            file_count = fitsFile.select().where(fitsFile.fitsFileSession == session.fitsSessionId).count()
            
            if file_count >= min_files_per_master:
                # Determine calibration type from object name
                obj_name = session.fitsSessionObjectName.lower() if session.fitsSessionObjectName else ''
                cal_type = None
                
                if 'bias' in obj_name:
                    cal_type = 'BIAS'
                elif 'dark' in obj_name:
                    cal_type = 'DARK'
                elif 'flat' in obj_name:
                    cal_type = 'FLAT'
                
                if cal_type:
                    opportunities[cal_type].append({
                        'session_id': session.fitsSessionId,
                        'file_count': file_count,
                        'telescope': session.fitsSessionTelescope or 'Unknown',
                        'instrument': session.fitsSessionImager or 'Unknown', 
                        'date': session.fitsSessionDate.strftime('%Y-%m-%d') if session.fitsSessionDate else 'Unknown'
                    })
        
        if progress_callback:
            progress_callback(80, "Generating analysis report...")
        
        # Log opportunities
        logging.info("\n=== MASTER CREATION OPPORTUNITIES ===")
        
        total_opportunities = 0
        for cal_type in ['BIAS', 'DARK', 'FLAT']:
            sessions_list = opportunities[cal_type]
            total_opportunities += len(sessions_list)
            
            logging.info(f"\n{cal_type} Sessions:")
            logging.info(f"  Sessions with {min_files_per_master}+ files: {len(sessions_list)}")
            
            for i, session_info in enumerate(sessions_list[:5]):  # Show first 5
                logging.info(f"    {i+1}. Session {session_info['session_id']}: {session_info['file_count']} files")
                logging.info(f"       {session_info['telescope']}, {session_info['instrument']}, {session_info['date']}")
            
            if len(sessions_list) > 5:
                logging.info(f"    ... and {len(sessions_list)-5} more sessions")
        
        logging.info(f"\nTotal opportunities: {total_opportunities} sessions ready for master creation")
        logging.info("To create these masters, run:")
        logging.info("  python AutoCalibration.py -o masters -v")
        
        if progress_callback:
            progress_callback(100, "Analysis complete")
        
        return {
            'master_stats': master_stats,
            'opportunities': opportunities,
            'total_opportunities': total_opportunities,
            'min_files_used': min_files_per_master
        }
        
    except Exception as e:
        logging.error(f"Error analyzing calibration opportunities: {e}")
        return None


def create_master_frames(config: configparser.ConfigParser, session_id: Optional[str] = None, 
                        force: bool = False, dry_run: bool = False, progress_callback=None) -> bool:
    """
    Create master calibration frames from calibration sessions.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        auto_cal_config = get_auto_calibration_config(config)
        min_files_per_master = auto_cal_config['min_files_per_master']
        
        logging.info("Starting master frame creation...")
        
        if session_id:
            logging.info(f"Processing specific session: {session_id}")
        else:
            logging.info("Creating masters for all viable calibration sessions...")
        
        if dry_run:
            logging.info("DRY RUN MODE - No actual master frames will be created")
        
        # Get master manager
        master_manager = get_master_manager()
        
        if progress_callback:
            progress_callback(10, "Finding calibration sessions...")
        
        # Find calibration sessions that need masters
        calibration_types = ['bias', 'Bias', 'BIAS', 'dark', 'Dark', 'DARK', 'flat', 'Flat', 'FLAT']
        query = fitsSession.select().where(fitsSession.fitsSessionObjectName.in_(calibration_types))
        if session_id:
            query = query.where(fitsSession.fitsSessionId == session_id)
        
        sessions = list(query)
        viable_sessions = []
        
        for session in sessions:
            file_count = fitsFile.select().where(fitsFile.fitsFileSession == session.fitsSessionId).count()
            if file_count >= min_files_per_master:
                # Determine calibration type from object name
                obj_name = session.fitsSessionObjectName.lower() if session.fitsSessionObjectName else ''
                cal_type = None
                
                if 'bias' in obj_name:
                    cal_type = 'bias'
                elif 'dark' in obj_name:
                    cal_type = 'dark'
                elif 'flat' in obj_name:
                    cal_type = 'flat'
                
                if cal_type:
                    session.cal_type = cal_type  # Add cal_type as an attribute for later use
                    viable_sessions.append(session)
        
        if not viable_sessions:
            logging.warning("No viable sessions found for master creation")
            return False
        
        logging.info(f"Found {len(viable_sessions)} sessions ready for master creation")
        
        created_count = 0
        total_sessions = len(viable_sessions)
        
        for i, session in enumerate(viable_sessions):
            if progress_callback:
                base_progress = 20 + (i * 70 // total_sessions)
                progress_callback(base_progress, f"Processing session {i+1}/{total_sessions}...")
            
            session_files = fitsFile.select().where(fitsFile.fitsFileSession == session.fitsSessionId)
            file_count = session_files.count()
            
            # Check if a matching master already exists (unless force flag is set)
            if not force:
                session_data = {
                    'telescope': session.fitsSessionTelescope,
                    'instrument': session.fitsSessionImager,
                    'exposure_time': session.fitsSessionExposure,
                    'filter_name': session.fitsSessionFilter,
                    'binning_x': session.fitsSessionBinningX,
                    'binning_y': session.fitsSessionBinningY,
                    'ccd_temp': session.fitsSessionCCDTemp,
                    'gain': session.fitsSessionGain,
                    'offset': session.fitsSessionOffset
                }
                
                existing_master = master_manager.find_matching_master(session_data, session.cal_type)
                
                if existing_master:
                    logging.info(f"Master {session.cal_type} already exists for session {session.fitsSessionId}, skipping: {os.path.basename(existing_master.master_path)}")
                    continue
            
            logging.info(f"Processing session {session.fitsSessionId} for {session.cal_type} master ({file_count} files)")
            
            if dry_run:
                logging.info(f"DRY RUN: Would create {session.cal_type} master from {file_count} files")
                created_count += 1
                continue
            
            try:
                # Create master frame
                def master_progress(progress, total, message):
                    if progress_callback:
                        # Map master creation progress to overall progress
                        percentage = (progress * 100) // total if total > 0 else 0
                        session_progress = base_progress + (percentage * 70 // total_sessions // 100)
                        progress_callback(session_progress, f"Creating {session.cal_type} masters: {percentage}% - {message}")
                
                master_path = master_manager.create_master_from_session(
                    session.fitsSessionId, 
                    session.cal_type,
                    min_files_per_master,
                    master_progress
                )
                
                if master_path:
                    logging.info(f"Created {session.cal_type} master: {master_path}")
                    created_count += 1
                else:
                    logging.warning(f"Failed to create {session.cal_type} master for session {session.fitsSessionId}")
                    
            except Exception as e:
                logging.error(f"Error creating master for session {session.fitsSessionId}: {e}")
                continue
        
        if progress_callback:
            progress_callback(100, f"Master creation complete - {created_count} masters created")
        
        skipped_count = total_sessions - created_count
        logging.info(f"Master frame creation complete. Created {created_count} masters")
        if skipped_count > 0 and not dry_run:
            logging.info(f"Skipped {skipped_count} sessions (masters already exist). Use --force to recreate.")
        
        return True
        
    except Exception as e:
        logging.error(f"Error creating master frames: {e}")
        return False


def calibrate_light_frames(config: configparser.ConfigParser, session_id: Optional[str] = None, 
                          force_recalibrate: bool = False, dry_run: bool = False, progress_callback=None) -> bool:
    """
    Calibrate light frames using available master frames.
    
    Args:
        config: Configuration object
        session_id: Optional specific session ID to calibrate
        force_recalibrate: If True, recalibrate even if frames are already calibrated
        dry_run: If True, show what would be done without making changes
        progress_callback: Optional callback for progress updates
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from .light_calibration import calibrate_session_lights, find_light_sessions_for_calibration, get_calibration_statistics
        
        logging.info("Starting light frame calibration...")
        if force_recalibrate:
            logging.info("Force recalibration enabled - will recalibrate already-calibrated frames")
        
        if session_id:
            logging.info(f"Processing specific session: {session_id}")
        else:
            logging.info("Calibrating all light sessions with available masters...")
        
        if dry_run:
            logging.info("DRY RUN MODE - No actual calibration will be performed")
            
        # Get initial calibration statistics
        initial_stats = get_calibration_statistics()
        logging.info(f"Initial calibration status: {initial_stats['calibrated_frames']}/{initial_stats['total_light_frames']} frames calibrated ({initial_stats['calibration_percentage']:.1f}%)")
        
        if progress_callback:
            progress_callback(10, "Finding light sessions...")
        
        # Find light frame sessions
        if session_id:
            light_sessions = [session_id]
        else:
            light_sessions = find_light_sessions_for_calibration()
        
        logging.info(f"Found {len(light_sessions)} light frame sessions")
        
        if not light_sessions:
            logging.warning("No light frame sessions found")
            return False
        
        calibrated_count = 0
        error_count = 0
        total_processed = 0
        total_sessions = len(light_sessions)
        
        for i, session_id in enumerate(light_sessions):
            if progress_callback:
                base_progress = 20 + (i * 70 // total_sessions) 
                progress_callback(base_progress, f"Calibrating session {i+1}/{total_sessions}...")
            
            if dry_run:
                logging.info(f"DRY RUN: Would calibrate session {session_id}")
                calibrated_count += 1
                continue
            
            try:
                # Create progress callback for this session
                def session_progress(message):
                    if progress_callback:
                        progress_callback(base_progress, f"Session {i+1}: {message}")
                
                # Calibrate the session using the core light calibration module
                result = calibrate_session_lights(
                    session_id=session_id,
                    progress_callback=session_progress,
                    force_recalibrate=force_recalibrate
                )
                
                if result.get('success'):
                    total_processed += result.get('calibrated_count', 0)
                    calibrated_count += 1
                    
                    logging.info(f"Session {session_id} calibration completed: "
                               f"{result['calibrated_count']} processed, "
                               f"{result['skipped_count']} skipped, "
                               f"{result['error_count']} errors")
                else:
                    error_count += 1
                    error_msg = result.get('error', 'Unknown error')
                    logging.warning(f"Session {session_id} calibration failed: {error_msg}")
                
            except Exception as e:
                error_count += 1
                logging.error(f"Error calibrating session {session_id}: {e}")
                continue
        
        # Get final calibration statistics
        final_stats = get_calibration_statistics()
        frames_calibrated = final_stats['calibrated_frames'] - initial_stats['calibrated_frames']
        
        if progress_callback:
            progress_callback(100, f"Calibration complete - {total_processed} frames processed")
        
        logging.info(f"Light frame calibration complete:")
        logging.info(f"  - Sessions processed: {calibrated_count}/{total_sessions}")
        logging.info(f"  - Frames calibrated: {frames_calibrated}")
        logging.info(f"  - Sessions with errors: {error_count}")
        logging.info(f"  - Final status: {final_stats['calibrated_frames']}/{final_stats['total_light_frames']} frames calibrated ({final_stats['calibration_percentage']:.1f}%)")
        
        return True
        
    except Exception as e:
        logging.error(f"Error calibrating light frames: {e}")
        return False


def perform_quality_assessment(config: configparser.ConfigParser, session_id: Optional[str] = None, 
                              generate_report: bool = False, progress_callback=None) -> bool:
    """
    Perform enhanced quality assessment on frames using SEP-based star detection.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logging.info("Starting enhanced quality assessment with SEP star detection...")
        
        # Import the enhanced quality analyzer
        from .enhanced_quality import EnhancedQualityAnalyzer
        from ..models import fitsFile, db
        
        analyzer = EnhancedQualityAnalyzer()
        
        # Get files to analyze
        if session_id:
            logging.info(f"Assessing specific session: {session_id}")
            files_to_analyze = list(fitsFile.select().where(
                fitsFile.fitsFileSession == session_id,
                fitsFile.fitsFileName.is_null(False),
                fitsFile.fitsFileSoftDelete == False
            ))
        else:
            logging.info("Assessing quality of all light frames...")
            # Focus on light frames for quality assessment
            files_to_analyze = list(fitsFile.select().where(
                fitsFile.fitsFileType == 'LIGHT',
                fitsFile.fitsFileName.is_null(False),
                fitsFile.fitsFileSoftDelete == False
            ).limit(100))  # Limit to prevent overwhelming analysis
        
        if not files_to_analyze:
            logging.warning("No files found for quality assessment")
            return True
        
        logging.info(f"Analyzing quality for {len(files_to_analyze)} files...")
        
        # Analyze each file
        successful_analyses = 0
        failed_analyses = 0
        
        for i, fits_file in enumerate(files_to_analyze):
            try:
                # Create progress callback for individual file
                def file_progress(percentage, message):
                    # Calculate overall progress
                    file_progress_weight = 80.0 / len(files_to_analyze)  # 80% for file analysis
                    overall_progress = 10 + (i * file_progress_weight) + (percentage * file_progress_weight / 100)
                    
                    if progress_callback:
                        progress_callback(int(overall_progress), 
                                        f"Analyzing {fits_file.fitsFileObject} ({i+1}/{len(files_to_analyze)}): {message}")
                
                # Perform quality analysis
                quality_results = analyzer.analyze_and_update_file(
                    fits_file.fitsFileName, 
                    fits_file.fitsFileId,
                    progress_callback=file_progress
                )
                
                if quality_results.get("status") == "success":
                    successful_analyses += 1
                    logging.debug(f"Successfully analyzed {fits_file.fitsFileName}")
                else:
                    failed_analyses += 1
                    logging.warning(f"Failed to analyze {fits_file.fitsFileName}: {quality_results.get('message', 'Unknown error')}")
                
            except Exception as e:
                failed_analyses += 1
                logging.error(f"Error analyzing {fits_file.fitsFileName}: {e}")
                continue
        
        # Update progress
        if progress_callback:
            progress_callback(90, "Finalizing quality assessment...")
        
        # Log results
        logging.info(f"Quality assessment completed: {successful_analyses} successful, {failed_analyses} failed")
        
        if generate_report:
            # TODO: Generate quality report using the database metrics
            logging.info("Quality report generation requested but not yet implemented")
        
        if progress_callback:
            progress_callback(100, "Quality assessment complete")
        
        # Consider it successful if we analyzed at least some files
        return successful_analyses > 0
        
    except Exception as e:
        logging.error(f"Error performing quality assessment: {e}")
        return False


def run_complete_workflow(config: configparser.ConfigParser, session_id: Optional[str] = None, 
                         force: bool = False, dry_run: bool = False, progress_callback=None) -> bool:
    """
    Run the complete auto-calibration workflow.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logging.info("Starting complete auto-calibration workflow...")
        
        steps = [
            ("analyze", "Analyzing calibration opportunities"),
            ("masters", "Creating master frames"),
            ("calibrate", "Calibrating light frames"),
            ("quality", "Performing quality assessment")
        ]
        
        for i, (step, description) in enumerate(steps):
            if progress_callback:
                base_progress = i * 25
                progress_callback(base_progress, description)
            
            def step_progress(percentage, message):
                if progress_callback:
                    step_progress_val = base_progress + (percentage * 25 // 100)
                    progress_callback(step_progress_val, message)
            
            if step == "analyze":
                result = analyze_calibration_opportunities(config, session_id, progress_callback=step_progress)
                if not result:
                    return False
                    
            elif step == "masters":
                success = create_master_frames(config, session_id, force, dry_run, step_progress)
                if not success:
                    return False
                    
            elif step == "calibrate":
                success = calibrate_light_frames(config, session_id, dry_run, step_progress)
                if not success:
                    return False
                    
            elif step == "quality":
                success = perform_quality_assessment(config, session_id, False, step_progress)
                if not success:
                    return False
        
        if progress_callback:
            progress_callback(100, "Complete workflow finished")
        
        logging.info("Complete auto-calibration workflow finished successfully")
        return True
        
    except Exception as e:
        logging.error(f"Error in complete workflow: {e}")
        return False