############################################################################################################
## F I T S   P R O C E S S I N G                                                                          ##
############################################################################################################
# Functions to import fits file data into the database while renaming files and moving them to a repository, 
# calibrate images, create thumbnails linked to test stacks, and send the user an email with a summary of 
# the work done. This module contains the fitsProcessing class that handles all FITS file operations.
#
from datetime import datetime,timedelta
import numpy as np
import matplotlib.pyplot as plt
import uuid
import os
import hashlib
from math import cos,sin 
from astropy.io import fits
import shutil
import pytz
from peewee import IntegrityError
import configparser

from astrofiler_db import fitsFile as FitsFileModel, fitsSession as fitsSessionModel

import logging
logger = logging.getLogger(__name__)

class fitsProcessing:
    """
    A class for processing FITS files, including registration, calibration, and database operations.
    
    This class handles:
    - Importing FITS file data into the database
    - Renaming and moving files to repository structure
    - Creating sessions from FITS files
    - Creating thumbnails
    - Calibrating images
    """
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        self.sourceFolder = config.get('DEFAULT', 'source', fallback='.')
        self.repoFolder = config.get('DEFAULT', 'repo', fallback='.')

    ################################################################################################################
    ## - this function calculates SHA-256 hash of a file for duplicate detection                    ##
    #################################################################################################################
    def calculateFileHash(self, filePath):
        """Calculate SHA-256 hash of a file for duplicate detection."""
        try:
            hash_sha256 = hashlib.sha256()
            with open(filePath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {filePath}: {str(e)}")
            return None

    #################################################################################################################
    ## registerFitsImage - this functioncalls a function to registers each fits files in the database              ##
    ## and also corrects any issues with the Fits header info (e.g. WCS)                                           ##
    #################################################################################################################
    # Note: Movefiles means we are moving from a source folder to the repo, otherwise we are syncing the repo database
    def registerFitsImage(self,root,file,moveFiles):
        newFitsFileId=None
        file_name, file_extension = os.path.splitext(os.path.join(root,file))

        # Ignore everything not a *fit* file
        if "fit" not in file_extension:
            logger.info("Ignoring file "+os.path.join(root, file)+" with extension -"+file_extension+"-")
            return False

        try:
            hdul = fits.open(os.path.join(root, file), mode='update')
        except ValueError as e:
            logger.warning("Invalid FITS file. File not processed is "+str(os.path.join(root, file)))
            return False

        hdr = hdul[0].header
        if "IMAGETYP" in hdr:
            # Fix variances in header cards
            if ("EXPTIME" in hdr):
                exposure=hdr["EXPTIME"]
            else:
                if ("EXPOSURE" in hdr):
                    exposure=hdr["EXPOSURE"]
                else:
                    logger.warning("No EXPTIME or EXPOSURE card in header. File not processed is "+str(os.path.join(root, file)))
                    return False
                
            if "TELESCOP" in hdr:
                telescope=hdr["TELESCOP"]
            else:
                telescope="Unknown"
                    
            # Create an os-friendly date
            try:
                if "DATE-OBS" not in hdr:
                    logger.warning("No DATE-OBS card in header. File not processed is "+str(os.path.join(root, file)))
                    return False
                datestr=hdr["DATE-OBS"].replace("T", " ")
                datestr=datestr[0:datestr.find('.')]
                dateobj=datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
                fitsDate=dateobj.strftime("%Y%m%d%H%M%S")
            except ValueError as e:
                logger.warning("Invalid date format in header. File not processed is "+str(os.path.join(root, file)))
                return False

            ############## L I G H T S ################################################################
            if "LIGHT" in hdr["IMAGETYP"].upper():
                # Adjust the WCS for the image
                if "CD1_1" not in hdr:
                    if "CDELT1" in hdr:
                        fitsCDELT1=float(hdr["CDELT1"])
                        fitsCDELT2=float(hdr["CDELT2"])
                        fitsCROTA2=float(hdr["CROTA2"])
                        fitsCD1_1 =  fitsCDELT1 * cos(fitsCROTA2)
                        fitsCD1_2 = -fitsCDELT2 * sin(fitsCROTA2)
                        fitsCD2_1 =  fitsCDELT1 * sin (fitsCROTA2)
                        fitsCD2_2 = fitsCDELT2 * cos(fitsCROTA2)
                        hdr.append(('CD1_1', str(fitsCD1_1), 'Adjusted via Astrofiler'), end=True)
                        hdr.append(('CD1_2', str(fitsCD1_2), 'Adjusted via Astrofiler'), end=True)
                        hdr.append(('CD2_1', str(fitsCD2_1), 'Adjusted via Astrofiler'), end=True)
                        hdr.append(('CD2_2', str(fitsCD2_2), 'Adjusted via Astrofiler'), end=True)
                        hdul.flush()  # changes are written back to original.fits
                    else:
                        logger.warning("No WCS information in header, file not updated is "+str(os.path.join(root, file)))
                
                
                # Create a new file name
                if ("OBJECT" in hdr):
                    if ("FILTER" in hdr):
                        newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(hdr["OBJECT"],telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                    else:
                        newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(hdr["OBJECT"],telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),"OSC",fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                else:
                    logger.warning("Invalid object name in header. File not processed is "+str(os.path.join(root, file)))
                    return False
                

            ############## F L A T S ##################################################################            
            elif "FLAT" in hdr["IMAGETYP"].upper():
                if ("FILTER" in hdr):
                    newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format("Flat",telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                else:
                    newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format("Flat",telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),"OSC",fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
            
            ############## D A R K S ##################################################################   
            elif "DARK" in hdr["IMAGETYP"].upper():
                newName="{0}-{1}-{2}-{3}-{4}s-{5}x{6}-t{7}.fits".format("Dark",telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
            ############## B I A S E S ################################################################   
            elif "BIAS" in hdr["IMAGETYP"].upper():
                newName="{0}-{1}-{2}-{3}-{4}s-{5}x{6}-t{7}.fits".format("Bias",telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate,exposure,hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])

            else:
                logger.warning("File not processed as IMAGETYP -"+hdr["IMAGETYP"]+"- not recognized: "+str(os.path.join(root, file)))
            hdul.close()
            newPath=""

            ######################################################################################################
            # Create the folder structure (if needed)
            fitsDate=dateobj.strftime("%Y%m%d")
            if "LIGHT" in hdr["IMAGETYP"].upper():
                newPath=self.repoFolder+"Light/{0}/{1}/{2}/{3}/".format(hdr["OBJECT"],telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate)
            elif "DARK" in hdr["IMAGETYP"].upper():
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format("Dark",telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),exposure,fitsDate)
            elif "FLAT" in hdr["IMAGETYP"].upper():
                if ("FILTER" in hdr):
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format("Flat",telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate)
                else:
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format("Flat",telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),"OSC",fitsDate)
            elif "BIAS" in hdr["IMAGETYP"].upper():
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/".format("Bias",telescope.replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate)
            else:
                logger.warning("File not processed as IMAGETYP not recognized: "+str(os.path.join(root, file)))
                return None

            if not os.path.isdir(newPath) and moveFiles:
                os.makedirs (newPath)

            # Calculate file hash for duplicate detection
            currentFilePath = os.path.join(root, file)
            fileHash = self.calculateFileHash(currentFilePath)
            logger.info("Registering file "+os.path.join(root, file)+" to "+newPath+newName.replace(" ", "_"))
            newFitsFileId=self.submitFileToDB(newPath+newName.replace(" ", "_"),hdr,fileHash)
            if (newFitsFileId != None) and moveFiles:
                if not os.path.exists(newPath+newName):
                    logger.info("Moving file "+os.path.join(root, file)+" to "+newPath+newName)
                    # Move the file to the new location
                    try:
                        shutil.move(os.path.join(root, file), newPath+newName)
                    except shutil.Error as e:
                        logger.error("Shutil error moving file "+os.path.join(root, file)+" to "+newPath+newName+": "+str(e))
                        return None
                    except OSError as e:
                        logger.error("OS error moving file "+os.path.join(root, file)+" to "+newPath+newName+": "+str(e))
                        return None
                    logger.info("File successfully moved to repo - "+newPath+newName)
                else:
                    logger.warning("File already exists in repo, no changes - "+newPath+newName)
            else:
                logger.warning("Warning: File not moved to repo is "+str(os.path.join(root, file)))
        else:
            logger.warning("File not added to repo - no IMAGETYP card - "+str(os.path.join(root, file)))

        return newFitsFileId

    #################################################################################################################
    ## registerFitsImages - this function scans the images folder and registers all fits files in the database     ##
    #################################################################################################################
    def registerFitsImages(self,moveFiles=True, progress_callback=None):
        registeredFiles=[]
        newFitsFileId=None
        currCount=0
        start_time = datetime.now()

        # Scan the pictures folder
        if moveFiles:
            logger.info("Processing images in "+self.sourceFolder)
            workFolder=self.sourceFolder
        else:
            logger.info("Syncronizing images in "+os.path.abspath(self.repoFolder))
            workFolder=self.repoFolder

        # First pass: count total files to process
        total_files = 0
        for root, dirs, files in os.walk(os.path.abspath(workFolder)):
            for file in files:
                file_name, file_extension = os.path.splitext(file)
                if "fit" in file_extension:
                    total_files += 1
        
        logger.info(f"Found {total_files} FITS files to process")
        
        # If no files found, return early
        if total_files == 0:
            logger.info("No FITS files found to process")
            if progress_callback:
                progress_callback(0, 0, "No FITS files found")
            return registeredFiles
        
        # Second pass: process files with progress tracking
        successful_files = 0
        failed_files = 0
        cancelled_by_user = False
        
        logger.info(f"Starting second pass to process {total_files} FITS files")
        
        for root, dirs, files in os.walk(os.path.abspath(workFolder)):
            logger.debug(f"Processing directory: {root} with {len(files)} files")
            for file in files:
                file_name, file_extension = os.path.splitext(file)
                if "fit" in file_extension:
                    currCount += 1
                    logger.info(f"Found FITS file #{currCount}: {file}")
                    
                    # Call progress callback if provided
                    if progress_callback:
                        logger.debug(f"Calling progress callback for file {currCount}/{total_files}: {file}")
                        should_continue = progress_callback(currCount, total_files, file)
                        logger.debug(f"Progress callback returned: {should_continue}")
                        if not should_continue:
                            logger.info("Processing cancelled by user")
                            cancelled_by_user = True
                            break
                    else:
                        logger.debug("No progress callback provided")
                    
                    # Calculate and display progress
                    progress_percent = (currCount / total_files) * 100 if total_files > 0 else 0
                    elapsed_time = datetime.now() - start_time
                    if currCount > 0:
                        avg_time_per_file = elapsed_time / currCount
                        estimated_remaining = avg_time_per_file * (total_files - currCount)
                        eta_str = f", ETA: {estimated_remaining}"
                    else:
                        eta_str = ""
                    
                    logger.debug(f"Processing file {currCount}/{total_files} ({progress_percent:.1f}%): {file}{eta_str}")
                    
                    # Try to register the file
                    newFitsFileId = self.registerFitsImage(root, file, moveFiles)
                    if newFitsFileId is not None:
                        # Add the file to the list of registered files
                        registeredFiles.append(newFitsFileId)
                        successful_files += 1
                        logger.info(f"Successfully registered file: {file}")
                    else:
                        failed_files += 1
                        logger.warning(f"Failed to register file: {file}")
                else:
                    logger.debug("Ignoring non-FITS file: "+file)
            
            # Check if processing was cancelled
            if cancelled_by_user:
                break
        
        total_time = datetime.now() - start_time
        logger.info(f"Processing complete! Found {total_files} files, successfully registered {successful_files} files, failed {failed_files} files in {total_time}")
        
        if cancelled_by_user:
            logger.info("Processing was cancelled by user")
        
        return registeredFiles

    #################################################################################################################
    ## createLightSessions - this function creates sessions for all Light files not currently assigned to one    ##
    #################################################################################################################
    def createLightSessions(self, progress_callback=None):
        sessionsCreated=[]
        
        # Query for all fits files that are not assigned to a session
        unassigned_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("Light"))
        
        # How many unassigned_files are there?
        logger.info("createSessions found "+str(len(unassigned_files))+" unassigned files to session")

        # Loop through each unassigned file and create a session each time the object changes
        currentObject= ""
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
            
            logger.info("Current Object is "+currentFitsFile.fitsFileObject+" with date "+str(currentFitsFile.fitsFileDate))
            logger.info("Processing "+str(currentFitsFile.fitsFileName))

            # If the object name or date has changed, create a new session
            if str(currentFitsFile.fitsFileObject) != currentObject or self.dateToDateField(currentFitsFile.fitsFileDate) != currentDate:
                # Create a new fitsSession record
                currentSessionId = uuid.uuid4()
                currentDate = self.dateToDateField(currentFitsFile.fitsFileDate)

                try:
                    newFitsSession=fitsSessionModel.create(fitsSessionId=currentSessionId,
                                                    fitsSessionObjectName=currentFitsFile.fitsFileObject,
                                                    fitsSessionTelescope=currentFitsFile.fitsFileTelescop,
                                                    fitsSessionImager=currentFitsFile.fitsFileInstrument,
                                                    fitsSessionDate=self.dateToDateField(currentFitsFile.fitsFileDate),
                                                    fitsSessionExposure=currentFitsFile.fitsFileExpTime,
                                                    fitsSessionBinningX=currentFitsFile.fitsFileXBinning,
                                                    fitsSessionBinningY=currentFitsFile.fitsFileYBinning,
                                                    fitsSessionCCDTemp=currentFitsFile.fitsFileCCDTemp,
                                                    fitsSessionGain=currentFitsFile.fitsFileGain,
                                                    fitsSessionOffset=currentFitsFile.fitsFileOffset,
                                                    fitsSessionFilter=currentFitsFile.fitsFileFilter,
                                                    fitsBiasSession=None,fitsDarkSession=None,fitsFlatSession=None)
                    sessionsCreated.append(currentSessionId)
                    logger.info("New session created for "+str(newFitsSession.fitsSessionId))
                except IntegrityError as e:
                    # Handle the integrity error
                    logger.error("IntegrityError: "+str(e))
                    continue     
                currentObject = str(currentFitsFile.fitsFileObject)
            # Assign the current session to the fits file
            currentFitsFile.fitsFileSession=currentSessionId
            currentFitsFile.save()
            logger.info("Assigned "+str(currentFitsFile.fitsFileName)+" to session "+str(currentSessionId))
            sessionsCreated.append(currentSessionId)
            
        return sessionsCreated
        
    #################################################################################################################
    ## sameDay - this function returns True if two dates are within 12 hours of each other, False otherwise        ##
    #################################################################################################################
    def sameDay(self,Date1,Date2): # If Date1 is within 12 hours of Date2
        current_date = datetime.strptime(Date1, '%Y-%m-%d')
        target_date = datetime.strptime(Date2, '%Y-%m-%d')
        time_difference = abs(current_date - target_date)
        return time_difference <= timedelta(hours=12)
        
    #################################################################################################################
    ## createCalibrationSessions - this function creates sessions for all calibration files not currently        ##
    ##                              assigned to one                                                                ##
    #################################################################################################################
    def createCalibrationSessions(self, progress_callback=None):
        createdCalibrationSessions=[]
        
        # Query for all calibration files that are not assigned to a session
        unassignedBiases = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("BIAS"))
        unassignedDarks  = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("DARK"))
        unassignedFlats  = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("FLAT"))
        
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

        # Bias calibration files
        currDate="0001-01-01"
        uuidStr=uuid.uuid4()
                        
        for biasFitsFile in unassignedBiases:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Bias: {biasFitsFile.fitsFileName}")
                if not should_continue:
                    logger.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            if not self.sameDay(self.dateToString(biasFitsFile.fitsFileDate), currDate):
                logger.info("Current date for bias is " + str(biasFitsFile.fitsFileDate))
                currDate = self.dateToString(biasFitsFile.fitsFileDate)
                uuidStr = uuid.uuid4()  # New Session
                newFitsSession=fitsSessionModel.create(fitsSessionId=uuidStr,
                                                fitsSessionDate=self.dateToDateField(biasFitsFile.fitsFileDate),
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
                                                fitsFlatSession=None)
                logger.info("New date for bias "+currDate) 
            biasFitsFile.fitsFileSession=uuidStr
            biasFitsFile.save()   
            logger.info("Set Session for bias "+biasFitsFile.fitsFileName+" to "+str(uuidStr))
            createdCalibrationSessions.append(uuidStr)
        
        # Dark calibration files
        currDate="0001-01-01"
        uuidStr=uuid.uuid4()
        for darkFitsFile in unassignedDarks:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Dark: {darkFitsFile.fitsFileName}")
                if not should_continue:
                    logger.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            if not self.sameDay(self.dateToString(darkFitsFile.fitsFileDate), currDate):
                currDate = self.dateToString(darkFitsFile.fitsFileDate)
                logger.info("Current date for dark is " + str(darkFitsFile.fitsFileDate))
                uuidStr=uuid.uuid4() # New Session
                newFitsSession=fitsSessionModel.create(fitsSessionId=uuidStr,
                                                fitsSessionDate=self.dateToDateField(darkFitsFile.fitsFileDate),
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
                                                fitsFlatSession=None)
                logger.info("New date "+currDate) 
            darkFitsFile.fitsFileSession=uuidStr
            darkFitsFile.save()   
            logger.info("Set Session for dark "+darkFitsFile.fitsFileName+" to "+str(uuidStr))
            createdCalibrationSessions.append(uuidStr)
            
        # Flat calibration files
        currDate="0001-01-01"
        uuidStr=uuid.uuid4()
        for flatFitsFile in unassignedFlats:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Flat: {flatFitsFile.fitsFileName}")
                if not should_continue:
                    logger.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            if not self.sameDay(self.dateToString(flatFitsFile.fitsFileDate), currDate):
                currDate = self.dateToString(flatFitsFile.fitsFileDate)
                logger.info("Current date for flat is " + str(flatFitsFile.fitsFileDate))
                uuidStr=uuid.uuid4() # New Session
                newFitsSession=fitsSessionModel.create(fitsSessionId=uuidStr,
                                fitsSessionDate=self.dateToDateField(flatFitsFile.fitsFileDate),
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
                                fitsFlatSession=None)
                logger.info("New date "+currDate) 
            flatFitsFile.fitsFileSession=uuidStr
            flatFitsFile.save()   
            logger.info("Set Session for flat "+flatFitsFile.fitsFileName+" to "+str(uuidStr))
            createdCalibrationSessions.append(uuidStr)
        
        return createdCalibrationSessions

    #################################################################################################################
    ## submitFileToDB- this function submits a fits file to the database                                          ##
    #################################################################################################################
    def submitFileToDB(self,fileName,hdr,fileHash=None):
        if "DATE-OBS" in hdr:
            # Create new fitsFile record
            logger.info("Adding file "+fileName+" to repo with date "+hdr["DATE-OBS"])
            
            # Adjust for different keywords
            if ("EXPTIME" in hdr):
                exposure=hdr["EXPTIME"]
            else:
                if ("EXPOSURE" in hdr):
                    exposure=hdr["EXPOSURE"]
                else:
                    logger.error("Error: File not added to repo due to missing exposure time in "+fileName)
                    return None
            
            if "TELESCOP" in hdr:
                telescope=hdr["TELESCOP"]
            else:
                telescope="Unknown"

            if "OBJECT" in hdr:
                newfile=FitsFileModel.create(fitsFileId=uuid.uuid4(),fitsFileName=fileName,fitsFileDate=hdr["DATE-OBS"],fitsFileType=hdr["IMAGETYP"].upper(),
                            fitsFileObject=hdr["OBJECT"],fitsFileExpTime=exposure,fitsFileXBinning=hdr["XBINNING"],
                            fitsFileYBinning=hdr["YBINNING"],fitsFileCCDTemp=hdr["CCD-TEMP"],fitsFileTelescop=telescope,
                            fitsFileInstrument=hdr["INSTRUME"],fitsFileFilter=hdr.get("FILTER", None),
                            fitsFileHash=fileHash,fitsFileSession=None)
            else:
                newfile=FitsFileModel.create(fitsFileId=uuid.uuid4(),fitsFileName=fileName,fitsFileDate=hdr["DATE-OBS"],fitsFileType=hdr["IMAGETYP"].upper(),
                            fitsFileExpTime=exposure,fitsFileXBinning=hdr["XBINNING"],
                            fitsFileYBinning=hdr["YBINNING"],fitsFileCCDTemp=hdr["CCD-TEMP"],fitsFileTelescop=telescope,
                            fitsFileInstrument=hdr["INSTRUME"],fitsFileFilter=hdr.get("FILTER", "OSC"),
                            fitsFileHash=fileHash,fitsFileSession=None)
            return newfile.fitsFileId
        else:
            logger.error("Error: File not added to repo due to missing date is "+fileName)
            return None
        return True

    #################################################################################################################
    ## linkSessions - this function links calibration sessions to light sessions based on telescope and imager    ##
    ##                matching. For each light session, it finds the most recent calibration sessions for the     ##
    ##                same telescope and imager combination, with additional matching criteria:                    ##
    ##                - All calibration frames must have the same binning settings as the light frames            ##
    ##                - All calibration frames must have the same gain and offset settings                        ##
    ##                - Darks must have the same exposure time as the light frames                                 ##
    ##                - Darks must have CCD temperature within 5 degrees of the light frames                      ##
    ##                - Flats must match the filter of the light frames                                            ##
    #################################################################################################################
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
                        logger.info(f"Linked bias session {bias_session.fitsSessionId} to light session {light_session.fitsSessionId} (binning: {light_x_binning}x{light_y_binning}, gain: {light_gain}, offset: {light_offset})")
                    else:
                        logger.debug(f"No matching bias session found for light session {light_session.fitsSessionId}")
                
                # Find most recent dark session with matching telescope/imager/binning/exposure/gain/offset/ccd_temp (within 5 degrees)
                if not light_session.fitsDarkSession:
                    # For CCD temperature matching, we need to use a custom query with temperature tolerance
                    dark_sessions = (fitsSessionModel
                                   .select()
                                   .where(fitsSessionModel.fitsSessionObjectName == 'Dark',
                                         fitsSessionModel.fitsSessionTelescope == light_session.fitsSessionTelescope,
                                         fitsSessionModel.fitsSessionImager == light_session.fitsSessionImager,
                                         fitsSessionModel.fitsSessionDate <= light_session.fitsSessionDate,
                                         fitsSessionModel.fitsSessionBinningX == light_x_binning,
                                         fitsSessionModel.fitsSessionBinningY == light_y_binning,
                                         fitsSessionModel.fitsSessionExposure == light_exp_time,
                                         fitsSessionModel.fitsSessionGain == light_gain,
                                         fitsSessionModel.fitsSessionOffset == light_offset)
                                   .order_by(fitsSessionModel.fitsSessionDate.desc()))
                    
                    # Filter by CCD temperature tolerance (within 5 degrees)
                    dark_session = None
                    if light_ccd_temp is not None:
                        try:
                            light_temp_float = float(light_ccd_temp)
                            for candidate in dark_sessions:
                                if candidate.fitsSessionCCDTemp is not None:
                                    try:
                                        dark_temp_float = float(candidate.fitsSessionCCDTemp)
                                        if abs(light_temp_float - dark_temp_float) <= 5.0:
                                            dark_session = candidate
                                            break
                                    except (ValueError, TypeError):
                                        continue
                        except (ValueError, TypeError):
                            # If light temp can't be parsed, fall back to first match without temp check
                            dark_session = dark_sessions.first()
                    else:
                        # If no light temp, get first match
                        dark_session = dark_sessions.first()
                    
                    if dark_session:
                        light_session.fitsDarkSession = str(dark_session.fitsSessionId)
                        session_updated = True
                        temp_info = f", temp: {light_ccd_temp}°C" if light_ccd_temp else ""
                        logger.info(f"Linked dark session {dark_session.fitsSessionId} to light session {light_session.fitsSessionId} (exp: {light_exp_time}s, binning: {light_x_binning}x{light_y_binning}, gain: {light_gain}, offset: {light_offset}{temp_info})")
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
                        logger.info(f"Linked flat session {flat_session.fitsSessionId} to light session {light_session.fitsSessionId} (filter: {light_filter}, binning: {light_x_binning}x{light_y_binning}, gain: {light_gain}, offset: {light_offset})")
                    else:
                        logger.debug(f"No matching flat session found for light session {light_session.fitsSessionId} (filter: {light_filter})")
                
                # Save the session if any links were updated
                if session_updated:
                    light_session.save()
                    updated_sessions.append(str(light_session.fitsSessionId))
                    logger.info(f"Updated light session {light_session.fitsSessionId} with calibration links")
            
            logger.info(f"Session linking complete. Updated {len(updated_sessions)} light sessions with calibration links")
            
        except Exception as e:
            logger.error(f"Error in linkSessions: {str(e)}")
            raise
        
        return updated_sessions

    #################################################################################################################
    ## dateToString - helper function to safely convert date to string format                                    ##
    #################################################################################################################
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

    #################################################################################################################
    ## dateToDateField - helper function to safely convert date for database storage                            ##
    #################################################################################################################
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
