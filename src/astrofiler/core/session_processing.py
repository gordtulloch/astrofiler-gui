"""
Session processing module for AstroFiler.

This module handles session creation and management operations for FITS files,
including creating light sessions, calibration sessions, and linking them together.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Union
from peewee import IntegrityError

from ..models.fits_file import fitsFile as FitsFileModel
from ..models.fits_session import fitsSession as fitsSessionModel

logger = logging.getLogger(__name__)


class SessionProcessor:
    """
    Handles FITS file session processing operations including session creation and linking.
    """
    
    def __init__(self) -> None:
        """Initialize SessionProcessor."""
        pass
    
    def createLightSessions(self, progress_callback=None):
        """
        Create sessions for all Light files not currently assigned to one.
        
        Follows astronomical workflow: position on object, take images in multiple filters, 
        then move to next object. Sessions are grouped by object, date, and filter only.
        
        Args:
            progress_callback: Optional callback function for progress updates
            
        Returns:
            list: List of session IDs that were created
        """
        sessionsCreated = []
        
        # Query for all fits files that are not assigned to a session, sort by object, date, filter
        unassigned_files = FitsFileModel.select().where(
            FitsFileModel.fitsFileSession.is_null(True), 
            FitsFileModel.fitsFileType.contains("Light")
        ).order_by(
            FitsFileModel.fitsFileObject, 
            FitsFileModel.fitsFileDate, 
            FitsFileModel.fitsFileFilter
        )

        # How many unassigned_files are there?
        logger.info("createSessions found "+str(len(unassigned_files))+" unassigned files to session")

        # Loop through each unassigned file and create a session each time the object, date, or filter changes
        currentObject = ""
        currentDate = None
        currentFilter = None
        currentSessionId = None
        total_files = len(unassigned_files)
        current_count = 0

        for currentFitsFile in unassigned_files:
            current_count += 1

            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, str(currentFitsFile.fitsFileName))
                if not should_continue:
                    logger.info("Session creation cancelled by user")
                    break

            # If the object name, date, or filter has changed, create a new session
            fits_date = self.dateToDateField(currentFitsFile.fitsFileDate)
            fits_filter = currentFitsFile.fitsFileFilter
            if (str(currentFitsFile.fitsFileObject) != currentObject or
                fits_date != currentDate or
                fits_filter != currentFilter):
                # Create a new fitsSession record
                currentSessionId = uuid.uuid4()
                currentDate = fits_date
                currentFilter = fits_filter

                try:
                    newFitsSession = fitsSessionModel.create(
                        fitsSessionId=currentSessionId,
                        fitsSessionObjectName=currentFitsFile.fitsFileObject,
                        fitsSessionTelescope=currentFitsFile.fitsFileTelescop,
                        fitsSessionImager=currentFitsFile.fitsFileInstrument,
                        fitsSessionDate=fits_date,
                        fitsSessionExposure=currentFitsFile.fitsFileExpTime,
                        fitsSessionBinningX=currentFitsFile.fitsFileXBinning,
                        fitsSessionBinningY=currentFitsFile.fitsFileYBinning,
                        fitsSessionCCDTemp=currentFitsFile.fitsFileCCDTemp,
                        fitsSessionGain=currentFitsFile.fitsFileGain,
                        fitsSessionOffset=currentFitsFile.fitsFileOffset,
                        fitsSessionFilter=fits_filter,
                        fitsBiasSession=None,
                        fitsDarkSession=None,
                        fitsFlatSession=None
                    )
                    sessionsCreated.append(currentSessionId)
                    logger.debug("New session created for "+str(newFitsSession.fitsSessionId))
                except IntegrityError as e:
                    # Handle the integrity error
                    logger.error("IntegrityError: "+str(e))
                    continue
                currentObject = str(currentFitsFile.fitsFileObject)

            # Assign the current session to the fits file
            currentFitsFile.fitsFileSession = currentSessionId
            currentFitsFile.save()
            logger.debug("Assigned "+str(currentFitsFile.fitsFileName)+" to session "+str(currentSessionId))
            
        # Get unique sessions count
        unique_sessions = len(set(sessionsCreated))
        logger.info(f"Light session creation complete: {unique_sessions} sessions created for {total_files} files")
        
        # Update quality metrics for all created sessions
        if sessionsCreated:
            logger.info("Calculating quality metric averages for sessions...")
            self.updateSessionQualityMetrics(list(set(sessionsCreated)))
        
        return sessionsCreated
    
    def updateSessionQualityMetrics(self, session_ids):
        """
        Calculate and update average quality metrics for sessions.
        
        Args:
            session_ids: List of session IDs to update
        """
        import numpy as np
        
        for session_id in session_ids:
            try:
                # Get all files in this session with quality metrics
                session_files = FitsFileModel.select().where(
                    FitsFileModel.fitsFileSession == session_id
                )
                
                # Collect quality metrics
                fwhm_values = []
                ecc_values = []
                hfr_values = []
                snr_values = []
                star_counts = []
                scale_values = []
                
                for f in session_files:
                    if f.fitsFileAvgFWHMArcsec is not None:
                        fwhm_values.append(f.fitsFileAvgFWHMArcsec)
                    if f.fitsFileAvgEccentricity is not None:
                        ecc_values.append(f.fitsFileAvgEccentricity)
                    if f.fitsFileAvgHFRArcsec is not None:
                        hfr_values.append(f.fitsFileAvgHFRArcsec)
                    if f.fitsFileImageSNR is not None:
                        snr_values.append(f.fitsFileImageSNR)
                    if f.fitsFileStarCount is not None:
                        star_counts.append(f.fitsFileStarCount)
                    if f.fitsFileImageScale is not None:
                        scale_values.append(f.fitsFileImageScale)
                
                # Calculate averages and update session
                update_data = {}
                if fwhm_values:
                    update_data['fitsSessionAvgFWHMArcsec'] = float(np.mean(fwhm_values))
                if ecc_values:
                    update_data['fitsSessionAvgEccentricity'] = float(np.mean(ecc_values))
                if hfr_values:
                    update_data['fitsSessionAvgHFRArcsec'] = float(np.mean(hfr_values))
                if snr_values:
                    update_data['fitsSessionImageSNR'] = float(np.mean(snr_values))
                if star_counts:
                    update_data['fitsSessionStarCount'] = int(np.mean(star_counts))
                if scale_values:
                    update_data['fitsSessionImageScale'] = float(np.mean(scale_values))
                
                if update_data:
                    query = fitsSessionModel.update(**update_data).where(
                        fitsSessionModel.fitsSessionId == session_id
                    )
                    query.execute()
                    logger.debug(f"Updated quality metrics for session {session_id}")
                    
            except Exception as e:
                logger.error(f"Error updating quality metrics for session {session_id}: {e}")
                continue

    def shouldCreateNewCalibrationSession(self, currentFile, currentSession, calType):
        """
        Determine if a new calibration session should be created based on image parameters.
        
        For calibration frames to be compatible for stacking, they must have identical:
        - Date (same observing session)
        - Telescope and imager
        - Binning settings (X and Y)
        - Gain and offset settings
        - For darks: exposure time and CCD temperature (within 5 degrees)
        - For flats: filter
        
        Args:
            currentFile: Current FITS file being processed
            currentSession: Current session parameters (dict or None for first file)
            calType: Calibration type ('bias', 'dark', 'flat')
            
        Returns:
            bool: True if a new session should be created
        """
        # Always create session for first file
        if currentSession is None:
            return True
            
        # Check date - must be same day
        if not self.sameDay(self.dateToString(currentFile.fitsFileDate), currentSession.get('date')):
            return True
            
        # Check telescope and imager - must be identical
        if (currentFile.fitsFileTelescop != currentSession.get('telescope') or 
            currentFile.fitsFileInstrument != currentSession.get('imager')):
            return True
            
        # Check binning - must be identical
        if (currentFile.fitsFileXBinning != currentSession.get('binningX') or 
            currentFile.fitsFileYBinning != currentSession.get('binningY')):
            return True
            
        # Check gain and offset - must be identical  
        if (currentFile.fitsFileGain != currentSession.get('gain') or 
            currentFile.fitsFileOffset != currentSession.get('offset')):
            return True
            
        # Additional checks based on calibration type
        if calType.lower() == 'dark':
            # Dark frames: exposure time must be identical
            if currentFile.fitsFileExpTime != currentSession.get('exposure'):
                return True
                
            # CCD temperature must be within 5 degrees
            try:
                current_temp = float(currentFile.fitsFileCCDTemp or 0)
                session_temp = float(currentSession.get('ccdTemp', 0))
                if abs(current_temp - session_temp) > 5.0:
                    return True
            except (ValueError, TypeError):
                # If we can't parse temperatures, consider them different
                if currentFile.fitsFileCCDTemp != currentSession.get('ccdTemp'):
                    return True
                    
        elif calType.lower() == 'flat':
            # Flat frames: filter must be identical
            if currentFile.fitsFileFilter != currentSession.get('filter'):
                return True
                
        # All parameters match - use existing session
        return False

    def shouldCreateNewLightSession(self, currentFile, currentSession):
        """
        Determine if a new light session should be created based on image parameters.
        
        For light frames to be compatible for processing together, they must have identical:
        - Target object
        - Date (same observing session using sameDay logic)
        - Telescope and imager
        - Filter
        - Exposure time (for proper stacking)
        - Binning settings (X and Y)
        - Gain and offset settings
        
        Args:
            currentFile: Current FITS file being processed
            currentSession: Current session parameters (dict or None for first file)
            
        Returns:
            bool: True if a new session should be created
        """
        # Always create session for first file
        if currentSession is None:
            return True
            
        # Check object - must be identical
        if currentFile.fitsFileObject != currentSession.get('object'):
            return True
            
        # Check date - must be same observing night
        if not self.sameDay(self.dateToString(currentFile.fitsFileDate), currentSession.get('date')):
            return True
            
        # Check telescope and imager - must be identical
        if (currentFile.fitsFileTelescop != currentSession.get('telescope') or 
            currentFile.fitsFileInstrument != currentSession.get('imager')):
            return True
            
        # Check filter - must be identical
        if currentFile.fitsFileFilter != currentSession.get('filter'):
            return True
            
        # Check exposure time - must be identical for proper stacking
        if currentFile.fitsFileExpTime != currentSession.get('exposure'):
            return True
            
        # Check binning - must be identical
        if (currentFile.fitsFileXBinning != currentSession.get('binningX') or 
            currentFile.fitsFileYBinning != currentSession.get('binningY')):
            return True
            
        # Check gain and offset - must be identical  
        if (currentFile.fitsFileGain != currentSession.get('gain') or 
            currentFile.fitsFileOffset != currentSession.get('offset')):
            return True
                
        # All parameters match - use existing session
        return False

    def createCalibrationSessions(self, progress_callback=None):
        """
        Create sessions for all calibration files not currently assigned to one.
        
        Follows actual calibration workflows:
        - Bias: Group by date, telescope, imager, binning
        - Dark: Group by date, telescope, imager, exposure, binning  
        - Flat: Group by date, telescope, imager, filter, binning
        
        Args:
            progress_callback: Optional callback function for progress updates
            
        Returns:
            list: List of session IDs that were created
        """
        createdCalibrationSessions = []
        createdBiasSessions = []
        createdDarkSessions = []
        createdFlatSessions = []
        
        # Query for all calibration files that are not assigned to a session
        # Order by telescope, instrument, date, then binning so grouping is stable
        unassignedBiases = FitsFileModel.select().where(
            FitsFileModel.fitsFileSession.is_null(True), 
            FitsFileModel.fitsFileType.contains("BIAS")
        ).order_by(
            FitsFileModel.fitsFileTelescop,
            FitsFileModel.fitsFileInstrument,
            FitsFileModel.fitsFileDate,
            FitsFileModel.fitsFileXBinning,
            FitsFileModel.fitsFileYBinning
        )
        
        # Order by telescope, instrument, date, then exposure and binning for darks
        unassignedDarks = FitsFileModel.select().where(
            FitsFileModel.fitsFileSession.is_null(True), 
            FitsFileModel.fitsFileType.contains("DARK")
        ).order_by(
            FitsFileModel.fitsFileTelescop,
            FitsFileModel.fitsFileInstrument,
            FitsFileModel.fitsFileDate,
            FitsFileModel.fitsFileExpTime,
            FitsFileModel.fitsFileXBinning,
            FitsFileModel.fitsFileYBinning
        )
        
        # Order by telescope, instrument, date, then filter and binning for flats
        unassignedFlats = FitsFileModel.select().where(
            FitsFileModel.fitsFileSession.is_null(True), 
            FitsFileModel.fitsFileType.contains("FLAT")
        ).order_by(
            FitsFileModel.fitsFileTelescop,
            FitsFileModel.fitsFileInstrument,
            FitsFileModel.fitsFileDate,
            FitsFileModel.fitsFileFilter,
            FitsFileModel.fitsFileXBinning,
            FitsFileModel.fitsFileYBinning
        )
        
        # Calculate total files for progress tracking
        total_biases = len(unassignedBiases)
        total_darks = len(unassignedDarks)
        total_flats = len(unassignedFlats)
        total_files = total_biases + total_darks + total_flats
        current_count = 0
        
        # How many unassigned_files are there?
        logger.info("createCalibrationSessions found "+str(total_biases)+" unassigned Bias calibration files to Session")
        logger.info("createCalibrationSessions found "+str(total_darks)+" unassigned Dark calibration files to Session")
        logger.info("createCalibrationSessions found "+str(total_flats)+" unassigned Flat calibration files to Session")

        # Bias calibration files - group by date, telescope, imager, binning
        currentDate = None
        currentTelescope = None
        currentImager = None 
        currentBinningX = None
        currentBinningY = None
        uuidStr = None
                        
        for biasFitsFile in unassignedBiases:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Bias: {biasFitsFile.fitsFileName}")
                if not should_continue:
                    logger.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            # Check if we need to create a new session
            fits_date = self.dateToDateField(biasFitsFile.fitsFileDate)
            if (fits_date != currentDate or
                biasFitsFile.fitsFileTelescop != currentTelescope or
                biasFitsFile.fitsFileInstrument != currentImager or
                biasFitsFile.fitsFileXBinning != currentBinningX or
                biasFitsFile.fitsFileYBinning != currentBinningY):
                    
                logger.debug("Creating new bias session for date " + str(biasFitsFile.fitsFileDate))
                uuidStr = uuid.uuid4()  # New Session
                newFitsSession = fitsSessionModel.create(
                    fitsSessionId=uuidStr,
                    fitsSessionDate=fits_date,
                    fitsSessionObjectName='Bias',
                    fitsSessionTelescope=biasFitsFile.fitsFileTelescop,
                    fitsSessionImager=biasFitsFile.fitsFileInstrument,
                    fitsSessionExposure=biasFitsFile.fitsFileExpTime,
                    fitsSessionBinningX=biasFitsFile.fitsFileXBinning,
                    fitsSessionBinningY=biasFitsFile.fitsFileYBinning,
                    fitsSessionCCDTemp=biasFitsFile.fitsFileCCDTemp,
                    fitsSessionGain=biasFitsFile.fitsFileGain,
                    fitsSessionOffset=biasFitsFile.fitsFileOffset,
                    fitsSessionFilter=biasFitsFile.fitsFileFilter,
                    fitsBiasSession=None,
                    fitsDarkSession=None,
                    fitsFlatSession=None
                )
                
                # Update current session tracking
                currentDate = fits_date
                currentTelescope = biasFitsFile.fitsFileTelescop
                currentImager = biasFitsFile.fitsFileInstrument
                currentBinningX = biasFitsFile.fitsFileXBinning
                currentBinningY = biasFitsFile.fitsFileYBinning
                
                # Only add to created sessions list when we actually create a new session
                createdCalibrationSessions.append(uuidStr)
                createdBiasSessions.append(uuidStr)
                logger.debug(f"New bias session {uuidStr} for {biasFitsFile.fitsFileTelescop}/{biasFitsFile.fitsFileInstrument} {biasFitsFile.fitsFileXBinning}x{biasFitsFile.fitsFileYBinning}") 
            
            biasFitsFile.fitsFileSession = uuidStr
            biasFitsFile.save()   
            logger.debug("Set Session for bias "+biasFitsFile.fitsFileName+" to "+str(uuidStr))
        
        # Dark calibration files - group by date, telescope, imager, exposure, binning
        currentDate = None
        currentTelescope = None
        currentImager = None
        currentExpTime = None
        currentBinningX = None
        currentBinningY = None
        uuidStr = None
        
        for darkFitsFile in unassignedDarks:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Dark: {darkFitsFile.fitsFileName}")
                if not should_continue:
                    logger.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            # Check if we need to create a new session
            fits_date = self.dateToDateField(darkFitsFile.fitsFileDate)
            if (fits_date != currentDate or
                darkFitsFile.fitsFileTelescop != currentTelescope or
                darkFitsFile.fitsFileInstrument != currentImager or
                darkFitsFile.fitsFileExpTime != currentExpTime or
                darkFitsFile.fitsFileXBinning != currentBinningX or
                darkFitsFile.fitsFileYBinning != currentBinningY):
                    
                logger.debug("Creating new dark session for date " + str(darkFitsFile.fitsFileDate))
                uuidStr = uuid.uuid4()  # New Session
                newFitsSession = fitsSessionModel.create(
                    fitsSessionId=uuidStr,
                    fitsSessionDate=fits_date,
                    fitsSessionObjectName='Dark',
                    fitsSessionTelescope=darkFitsFile.fitsFileTelescop,
                    fitsSessionImager=darkFitsFile.fitsFileInstrument,
                    fitsSessionExposure=darkFitsFile.fitsFileExpTime,
                    fitsSessionBinningX=darkFitsFile.fitsFileXBinning,
                    fitsSessionBinningY=darkFitsFile.fitsFileYBinning,
                    fitsSessionCCDTemp=darkFitsFile.fitsFileCCDTemp,
                    fitsSessionGain=darkFitsFile.fitsFileGain,
                    fitsSessionOffset=darkFitsFile.fitsFileOffset,
                    fitsSessionFilter=darkFitsFile.fitsFileFilter,
                    fitsBiasSession=None,
                    fitsDarkSession=None,
                    fitsFlatSession=None
                )
                
                # Update current session tracking  
                currentDate = fits_date
                currentTelescope = darkFitsFile.fitsFileTelescop
                currentImager = darkFitsFile.fitsFileInstrument
                currentExpTime = darkFitsFile.fitsFileExpTime
                currentBinningX = darkFitsFile.fitsFileXBinning
                currentBinningY = darkFitsFile.fitsFileYBinning
                
                # Only add to created sessions list when we actually create a new session
                createdCalibrationSessions.append(uuidStr)
                createdDarkSessions.append(uuidStr)
                logger.debug(f"New dark session {uuidStr} for {darkFitsFile.fitsFileTelescop}/{darkFitsFile.fitsFileInstrument} {darkFitsFile.fitsFileXBinning}x{darkFitsFile.fitsFileYBinning} {darkFitsFile.fitsFileExpTime}s") 
            
            darkFitsFile.fitsFileSession = uuidStr
            darkFitsFile.save()   
            logger.debug("Set Session for dark "+darkFitsFile.fitsFileName+" to "+str(uuidStr))
            
        # Flat calibration files - group by date, telescope, imager, filter, binning
        currentDate = None
        currentTelescope = None
        currentImager = None
        currentFilter = None
        currentBinningX = None
        currentBinningY = None
        uuidStr = None
        
        for flatFitsFile in unassignedFlats:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Flat: {flatFitsFile.fitsFileName}")
                if not should_continue:
                    logger.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            # Check if we need to create a new session
            fits_date = self.dateToDateField(flatFitsFile.fitsFileDate)
            if (fits_date != currentDate or
                flatFitsFile.fitsFileTelescop != currentTelescope or
                flatFitsFile.fitsFileInstrument != currentImager or
                flatFitsFile.fitsFileFilter != currentFilter or
                flatFitsFile.fitsFileXBinning != currentBinningX or
                flatFitsFile.fitsFileYBinning != currentBinningY):
                    
                logger.debug("Creating new flat session for date " + str(flatFitsFile.fitsFileDate))
                uuidStr = uuid.uuid4()  # New Session
                newFitsSession = fitsSessionModel.create(
                    fitsSessionId=uuidStr,
                    fitsSessionDate=fits_date,
                    fitsSessionObjectName='Flat',
                    fitsSessionTelescope=flatFitsFile.fitsFileTelescop,
                    fitsSessionImager=flatFitsFile.fitsFileInstrument,
                    fitsSessionExposure=flatFitsFile.fitsFileExpTime,
                    fitsSessionBinningX=flatFitsFile.fitsFileXBinning,
                    fitsSessionBinningY=flatFitsFile.fitsFileYBinning,
                    fitsSessionCCDTemp=flatFitsFile.fitsFileCCDTemp,
                    fitsSessionGain=flatFitsFile.fitsFileGain,
                    fitsSessionOffset=flatFitsFile.fitsFileOffset,
                    fitsSessionFilter=flatFitsFile.fitsFileFilter,
                    fitsBiasSession=None,
                    fitsDarkSession=None,
                    fitsFlatSession=None
                )
                
                # Update current session tracking
                currentDate = fits_date
                currentTelescope = flatFitsFile.fitsFileTelescop
                currentImager = flatFitsFile.fitsFileInstrument
                currentFilter = flatFitsFile.fitsFileFilter
                currentBinningX = flatFitsFile.fitsFileXBinning
                currentBinningY = flatFitsFile.fitsFileYBinning
                
                # Only add to created sessions list when we actually create a new session
                createdCalibrationSessions.append(uuidStr)
                createdFlatSessions.append(uuidStr)
                logger.debug(f"New flat session {uuidStr} for {flatFitsFile.fitsFileTelescop}/{flatFitsFile.fitsFileInstrument} {flatFitsFile.fitsFileXBinning}x{flatFitsFile.fitsFileYBinning} {flatFitsFile.fitsFileFilter}") 
            
            flatFitsFile.fitsFileSession = uuidStr
            flatFitsFile.save()   
            logger.debug("Set Session for flat "+flatFitsFile.fitsFileName+" to "+str(uuidStr))
        
        # Calculate session counts by type
        bias_sessions_created = len(createdBiasSessions)
        dark_sessions_created = len(createdDarkSessions)
        flat_sessions_created = len(createdFlatSessions)
        total_sessions_created = bias_sessions_created + dark_sessions_created + flat_sessions_created
        
        logger.info(f"Calibration session creation complete:")
        logger.info(f"  Bias sessions: {bias_sessions_created} (from {total_biases} files)")
        logger.info(f"  Dark sessions: {dark_sessions_created} (from {total_darks} files)")
        logger.info(f"  Flat sessions: {flat_sessions_created} (from {total_flats} files)")
        logger.info(f"  Total calibration sessions: {total_sessions_created}")
        return createdCalibrationSessions

    def linkSessions(self, progress_callback=None):
        """
        Link calibration sessions to light sessions based on telescope, imager, and specific matching criteria.
        
        This function iterates through all light sessions and finds the most recent 
        calibration sessions (bias, dark, flat) that match:
        - Telescope and imager (all calibration types)
        - Binning settings (all calibration types)
        - Gain and offset settings (all calibration types)
        - Exposure time (darks only)
        - CCD temperature within 5 degrees (darks only)
        - Filter (flats only)
        
        Args:
            progress_callback: Optional callback function for progress updates
            
        Returns:
            list: List of session IDs that were updated
        """
        updated_sessions = []
        
        try:
            # Get all light sessions that need calibration linking
            light_sessions = (fitsSessionModel
                             .select()
                             .where(fitsSessionModel.fitsSessionObjectName != 'Bias',
                                   fitsSessionModel.fitsSessionObjectName != 'Dark',
                                   fitsSessionModel.fitsSessionObjectName != 'Flat'))
            
            total_sessions = len(light_sessions)
            current_count = 0
            
            logger.info(f"Found {total_sessions} light sessions to process for calibration linking")
            
            for light_session in light_sessions:
                current_count += 1
                
                # Call progress callback if provided
                if progress_callback:
                    should_continue = progress_callback(current_count, total_sessions, 
                                                      f"Linking: {light_session.fitsSessionObjectName}")
                    if not should_continue:
                        logger.info("Session linking cancelled by user")
                        break
                
                session_updated = False
                
                # Use session-level fields for matching criteria instead of querying individual files
                light_exp_time = light_session.fitsSessionExposure
                light_x_binning = light_session.fitsSessionBinningX
                light_y_binning = light_session.fitsSessionBinningY
                light_filter = light_session.fitsSessionFilter
                light_gain = light_session.fitsSessionGain
                light_offset = light_session.fitsSessionOffset
                light_ccd_temp = light_session.fitsSessionCCDTemp
                
                logger.debug(f"Light session {light_session.fitsSessionId} criteria: exp={light_exp_time}, binning={light_x_binning}x{light_y_binning}, filter={light_filter}, gain={light_gain}, offset={light_offset}, temp={light_ccd_temp}")
                
                # Find most recent bias session with matching telescope/imager/binning/gain/offset
                if not light_session.fitsBiasSession:
                    bias_session = (fitsSessionModel
                                   .select()
                                   .where(fitsSessionModel.fitsSessionObjectName == 'Bias',
                                         fitsSessionModel.fitsSessionTelescope == light_session.fitsSessionTelescope,
                                         fitsSessionModel.fitsSessionImager == light_session.fitsSessionImager,
                                         fitsSessionModel.fitsSessionDate <= light_session.fitsSessionDate,
                                         fitsSessionModel.fitsSessionBinningX == light_x_binning,
                                         fitsSessionModel.fitsSessionBinningY == light_y_binning,
                                         fitsSessionModel.fitsSessionGain == light_gain,
                                         fitsSessionModel.fitsSessionOffset == light_offset)
                                   .order_by(fitsSessionModel.fitsSessionDate.desc())
                                   .first())
                    
                    if bias_session:
                        light_session.fitsBiasSession = str(bias_session.fitsSessionId)
                        session_updated = True
                        logger.debug(f"Linked bias session {bias_session.fitsSessionId} to light session {light_session.fitsSessionId} (binning: {light_x_binning}x{light_y_binning}, gain: {light_gain}, offset: {light_offset})")
                    else:
                        logger.debug(f"No matching bias session found for light session {light_session.fitsSessionId}")
                
                # Find most recent dark session with matching telescope/imager/binning/exposure/gain/offset/ccd_temp (within 5 degrees)
                if not light_session.fitsDarkSession:
                    # Select most recent dark session matching parameters (excluding CCD temperature)
                    dark_session = (fitsSessionModel
                        .select()
                        .where(
                            fitsSessionModel.fitsSessionObjectName == 'Dark',
                            fitsSessionModel.fitsSessionTelescope == light_session.fitsSessionTelescope,
                            fitsSessionModel.fitsSessionImager == light_session.fitsSessionImager,
                            fitsSessionModel.fitsSessionDate <= light_session.fitsSessionDate,
                            fitsSessionModel.fitsSessionBinningX == light_x_binning,
                            fitsSessionModel.fitsSessionBinningY == light_y_binning,
                            fitsSessionModel.fitsSessionExposure == light_exp_time,
                            fitsSessionModel.fitsSessionGain == light_gain,
                            fitsSessionModel.fitsSessionOffset == light_offset
                        )
                        .order_by(fitsSessionModel.fitsSessionDate.desc())
                        .first()
                    )
                    if dark_session:
                        light_session.fitsDarkSession = str(dark_session.fitsSessionId)
                        session_updated = True
                        logger.debug(f"Linked dark session {dark_session.fitsSessionId} to light session {light_session.fitsSessionId} (exp: {light_exp_time}s, binning: {light_x_binning}x{light_y_binning}, gain: {light_gain}, offset: {light_offset})")
                    else:
                        logger.debug(f"No matching dark session found for light session {light_session.fitsSessionId} (exp: {light_exp_time}s)")
                
                # Find most recent flat session with matching telescope/imager/binning/filter/gain/offset
                if not light_session.fitsFlatSession:
                    flat_session = (fitsSessionModel
                                   .select()
                                   .where(fitsSessionModel.fitsSessionObjectName == 'Flat',
                                         fitsSessionModel.fitsSessionTelescope == light_session.fitsSessionTelescope,
                                         fitsSessionModel.fitsSessionImager == light_session.fitsSessionImager,
                                         fitsSessionModel.fitsSessionDate <= light_session.fitsSessionDate,
                                         fitsSessionModel.fitsSessionBinningX == light_x_binning,
                                         fitsSessionModel.fitsSessionBinningY == light_y_binning,
                                         fitsSessionModel.fitsSessionFilter == light_filter,
                                         fitsSessionModel.fitsSessionGain == light_gain,
                                         fitsSessionModel.fitsSessionOffset == light_offset)
                                   .order_by(fitsSessionModel.fitsSessionDate.desc())
                                   .first())
                    
                    if flat_session:
                        light_session.fitsFlatSession = str(flat_session.fitsSessionId)
                        session_updated = True
                        logger.debug(f"Linked flat session {flat_session.fitsSessionId} to light session {light_session.fitsSessionId} (filter: {light_filter}, binning: {light_x_binning}x{light_y_binning}, gain: {light_gain}, offset: {light_offset})")
                    else:
                        logger.debug(f"No matching flat session found for light session {light_session.fitsSessionId} (filter: {light_filter})")
                
                # Save the session if any links were updated
                if session_updated:
                    light_session.save()
                    updated_sessions.append(str(light_session.fitsSessionId))
                    logger.debug(f"Updated light session {light_session.fitsSessionId} with calibration links")
            
            logger.info(f"Session linking complete. Updated {len(updated_sessions)} light sessions with calibration links")
            
        except Exception as e:
            logger.error(f"Error in linkSessions: {str(e)}")
            raise
        
        return updated_sessions

    def sameDay(self, Date1: str, Date2: str) -> bool:
        """
        Check if two dates are within 12 hours of each other.
        
        Simple logic for same observing session - if Date1 is within 12 hours of Date2.
        
        Args:
            Date1: First date string 
            Date2: Second date string
            
        Returns:
            bool: True if dates are within 12 hours of each other, False otherwise
        """
        try:
            current_date = datetime.strptime(Date1, '%Y-%m-%d')
            target_date = datetime.strptime(Date2, '%Y-%m-%d')
            time_difference = abs(current_date - target_date)
            return time_difference <= timedelta(hours=12)
        except (ValueError, AttributeError) as e:
            # If parsing fails, fall back to string comparison
            logger.warning(f"Date parsing failed in sameDay: {Date1}, {Date2}, error: {e}")
            return Date1 == Date2

    def dateToString(self, date_obj):
        """Convert date object to string format, handling both datetime objects and strings."""
        if date_obj is None:
            return None
        
        # If it's already a string, extract date part if it contains time info
        if isinstance(date_obj, str):
            # If string contains ISO datetime format, extract just the date part
            if 'T' in date_obj:
                return date_obj.split('T')[0]
            # If string contains space-separated datetime format, extract date part
            elif ' ' in date_obj and len(date_obj) > 10:
                # Check if it looks like a datetime (has time part)
                parts = date_obj.split(' ')
                if len(parts) >= 2 and ':' in parts[1]:
                    return parts[0]
            # If it's already just a date string, return as is
            return date_obj
        
        # If it's a datetime object, format it
        try:
            return date_obj.strftime('%Y-%m-%d')
        except AttributeError:
            # If it doesn't have strftime, convert to string
            return str(date_obj)

    def dateToDateField(self, date_obj):
        """Convert date object to proper format for database DateField storage."""
        if date_obj is None:
            return None
        
        # If it's already a string in date format, try to parse it first
        if isinstance(date_obj, str):
            try:
                from datetime import datetime
                
                # List of possible date formats to try
                date_formats = [
                    '%Y-%m-%d',                    # 2023-07-15
                    '%Y-%m-%dT%H:%M:%S',          # 2023-07-15T03:26:15
                    '%Y-%m-%dT%H:%M:%S.%f',       # 2023-07-15T03:26:15.438
                    '%Y-%m-%d %H:%M:%S',          # 2023-07-15 03:26:15
                    '%Y-%m-%d %H:%M:%S.%f',       # 2023-07-15 03:26:15.438
                ]
                
                # Try each format
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_obj, fmt).date()
                        return parsed_date
                    except ValueError:
                        continue
                
                # If none of the formats work, try to extract just the date part
                if 'T' in date_obj:
                    date_part = date_obj.split('T')[0]
                    try:
                        parsed_date = datetime.strptime(date_part, '%Y-%m-%d').date()
                        return parsed_date
                    except ValueError:
                        pass
                
                # If still no luck, try to take first 10 characters
                try:
                    parsed_date = datetime.strptime(date_obj[:10], '%Y-%m-%d').date()
                    return parsed_date
                except ValueError:
                    logger.warning(f"Could not parse date string: {date_obj}")
                    return None
                    
            except Exception as e:
                logger.warning(f"Error parsing date string '{date_obj}': {e}")
                return None
        
        # If it's a datetime object, get the date part
        try:
            if hasattr(date_obj, 'date'):
                return date_obj.date()
            return date_obj
        except Exception as e:
            logger.warning(f"Error converting date object: {e}")
            return None