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
logging=logging.getLogger(__name__)

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
            logging.error(f"Error calculating hash for {filePath}: {str(e)}")
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
            logging.info("Ignoring file "+os.path.join(root, file)+" with extension -"+file_extension+"-")
            return False

        try:
            hdul = fits.open(os.path.join(root, file), mode='update')
        except ValueError as e:
            logging.warning("Invalid FITS file. File not processed is "+str(os.path.join(root, file)))
            return False

        hdr = hdul[0].header
        if "IMAGETYP" in hdr:
            # Create an os-friendly date
            try:
                if "DATE-OBS" not in hdr:
                    logging.warning("No DATE-OBS card in header. File not processed is "+str(os.path.join(root, file)))
                    return False
                datestr=hdr["DATE-OBS"].replace("T", " ")
                datestr=datestr[0:datestr.find('.')]
                dateobj=datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
                fitsDate=dateobj.strftime("%Y%m%d%H%M%S")
            except ValueError as e:
                logging.warning("Invalid date format in header. File not processed is "+str(os.path.join(root, file)))
                return False

            ############## L I G H T S ################################################################
            if "Light" in hdr["IMAGETYP"]:
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
                        hdr.append(('CD1_1', str(fitsCD1_1), 'Adjusted via Obsy'), end=True)
                        hdr.append(('CD1_2', str(fitsCD1_2), 'Adjusted via Obsy'), end=True)
                        hdr.append(('CD2_1', str(fitsCD2_1), 'Adjusted via Obsy'), end=True)
                        hdr.append(('CD2_2', str(fitsCD2_2), 'Adjusted via Obsy'), end=True)
                        hdul.flush()  # changes are written back to original.fits
                    else:
                        logging.warning("No WCS information in header, file not updated is "+str(os.path.join(root, file)))

                # Standardize the object name and create a new file name
                if ("OBJECT" in hdr):
                    # Standardize object name, remove spaces and underscores
                    objectName=hdr["OBJECT"].replace(' ', '').replace('_', '')
                    hdr.append(('OBJECT', objectName, 'Adjusted via Astrofiler'), end=True)
                    hdul.flush()  # changes are written back to original.fits
                    
                    if ("FILTER" in hdr):
                        newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(hdr["OBJECT"].replace(" ", "_"),hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                    else:
                        newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(hdr["OBJECT"].replace(" ", "_"),hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),"OSC",fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                else:
                    logging.warning("Invalid object name in header. File not processed is "+str(os.path.join(root, file)))
                    return False
            ############## F L A T S ##################################################################            
            elif "Flat" in hdr["IMAGETYP"]:
                if ("FILTER" in hdr):
                    newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format("Flat",hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                else:
                    newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format("Flat",hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),"OSC",fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
            
            ############## D A R K S ##################################################################   
            elif "Dark" in hdr["IMAGETYP"]:
                newName="{0}-{1}-{2}-{3}-{4}s-{5}x{6}-t{7}.fits".format("Dark",hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
            ############## B I A S E S ################################################################   
            elif "Bias" in hdr["IMAGETYP"]:
                newName="{0}-{1}-{2}-{3}-{4}s-{5}x{6}-t{7}.fits".format("Bias",hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])

            else:
                logging.warning("File not processed as IMAGETYP -"+hdr["IMAGETYP"]+"- not recognized: "+str(os.path.join(root, file)))
            hdul.close()
            newPath=""

            ######################################################################################################
            # Create the folder structure (if needed)
            fitsDate=dateobj.strftime("%Y%m%d")
            if "Light" in hdr["IMAGETYP"]:
                newPath=self.repoFolder+"Light/{0}/{1}/{2}/{3}/".format(hdr["OBJECT"].replace(" ", ""),hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate)
            elif "Dark" in hdr["IMAGETYP"]:
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format("Dark",hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["EXPTIME"],fitsDate)
            elif "Flat" in hdr["IMAGETYP"]:
                if ("FILTER" in hdr):
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format("Flat",hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate)
                else:
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format("Flat",hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),"OSC",fitsDate)
            elif hdr["IMAGETYP"]=="Bias":
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/".format("Bias",hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate)
            else:
                logging.warning("File not processed as IMAGETYP not recognized: "+str(os.path.join(root, file)))
                return None

            if not os.path.isdir(newPath) and moveFiles:
                os.makedirs (newPath)

            # Calculate file hash for duplicate detection
            currentFilePath = os.path.join(root, file)
            fileHash = self.calculateFileHash(currentFilePath)
            logging.info("Registering file "+os.path.join(root, file)+" to "+newPath+newName.replace(" ", "_"))
            newFitsFileId=self.submitFileToDB(newPath+newName.replace(" ", "_"),hdr,fileHash)
            if (newFitsFileId != None) and moveFiles:
                if not os.path.exists(newPath+newName):
                    logging.debug("Moving file "+os.path.join(root, file)+" to "+newPath+newName)
                    # Move the file to the new location
                    try:
                        shutil.move(os.path.join(root, file), newPath+newName)
                    except shutil.Error as e:
                        logging.error("Shutil error moving file "+os.path.join(root, file)+" to "+newPath+newName+": "+str(e))
                        return None
                    except OSError as e:
                        logging.error("OS error moving file "+os.path.join(root, file)+" to "+newPath+newName+": "+str(e))
                        return None
                    logging.debug("File successfully moved to repo - "+newPath+newName)
                else:
                    logging.warning("File already exists in repo, no changes - "+newPath+newName)
            else:
                logging.warning("Warning: File not moved to repo is "+str(os.path.join(root, file)))
        else:
            logging.warning("File not added to repo - no IMAGETYP card - "+str(os.path.join(root, file)))

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
            logging.info("Processing images in "+self.sourceFolder)
            workFolder=self.sourceFolder
        else:
            logging.info("Syncronizing images in "+os.path.abspath(self.repoFolder))
            workFolder=self.repoFolder

        # First pass: count total files to process
        total_files = 0
        for root, dirs, files in os.walk(os.path.abspath(workFolder)):
            for file in files:
                file_name, file_extension = os.path.splitext(file)
                if "fit" in file_extension:
                    total_files += 1
        
        logging.info(f"Found {total_files} FITS files to process")
        
        # If no files found, return early
        if total_files == 0:
            logging.info("No FITS files found to process")
            if progress_callback:
                progress_callback(0, 0, "No FITS files found")
            return registeredFiles
        
        # Second pass: process files with progress tracking
        successful_files = 0
        failed_files = 0
        cancelled_by_user = False
        
        logging.info(f"Starting second pass to process {total_files} FITS files")
        
        for root, dirs, files in os.walk(os.path.abspath(workFolder)):
            logging.debug(f"Processing directory: {root} with {len(files)} files")
            for file in files:
                file_name, file_extension = os.path.splitext(file)
                if "fit" in file_extension:
                    currCount += 1
                    logging.info(f"Found FITS file #{currCount}: {file}")
                    
                    # Call progress callback if provided
                    if progress_callback:
                        logging.info(f"Calling progress callback for file {currCount}/{total_files}: {file}")
                        should_continue = progress_callback(currCount, total_files, file)
                        logging.info(f"Progress callback returned: {should_continue}")
                        if not should_continue:
                            logging.info("Processing cancelled by user")
                            cancelled_by_user = True
                            break
                    else:
                        logging.debug("No progress callback provided")
                    
                    # Calculate and display progress
                    progress_percent = (currCount / total_files) * 100 if total_files > 0 else 0
                    elapsed_time = datetime.now() - start_time
                    if currCount > 0:
                        avg_time_per_file = elapsed_time / currCount
                        estimated_remaining = avg_time_per_file * (total_files - currCount)
                        eta_str = f", ETA: {estimated_remaining}"
                    else:
                        eta_str = ""
                    
                    logging.info(f"Processing file {currCount}/{total_files} ({progress_percent:.1f}%): {file}{eta_str}")
                    
                    # Try to register the file
                    newFitsFileId = self.registerFitsImage(root, file, moveFiles)
                    if newFitsFileId is not None:
                        # Add the file to the list of registered files
                        registeredFiles.append(newFitsFileId)
                        successful_files += 1
                        logging.info(f"Successfully registered file: {file}")
                    else:
                        failed_files += 1
                        logging.warning(f"Failed to register file: {file}")
                else:
                    logging.debug("Ignoring non-FITS file: "+file)
            
            # Check if processing was cancelled
            if cancelled_by_user:
                break
        
        total_time = datetime.now() - start_time
        logging.info(f"Processing complete! Found {total_files} files, successfully registered {successful_files} files, failed {failed_files} files in {total_time}")
        
        if cancelled_by_user:
            logging.info("Processing was cancelled by user")
        
        return registeredFiles

    #################################################################################################################
    ## createLightSessions - this function creates sessions for all Light files not currently assigned to one    ##
    #################################################################################################################
    def createLightSessions(self, progress_callback=None):
        sessionsCreated=[]
        
        # Query for all fits files that are not assigned to a session
        unassigned_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("Light"))
        
        # How many unassigned_files are there?
        logging.info("createSessions found "+str(len(unassigned_files))+" unassigned files to session")

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
                    logging.info("Session creation cancelled by user")
                    break
            
            logging.info("Current Object is "+currentFitsFile.fitsFileObject)
            logging.info("Processing "+str(currentFitsFile.fitsFileName))

            # If the object name has changed, create a new session
            if str(currentFitsFile.fitsFileObject) != currentObject:
                # Create a new fitsSession record
                currentSessionId = uuid.uuid4()
                try:
                    newFitsSession=fitsSessionModel.create(fitsSessionId=currentSessionId,
                                                    fitsSessionObjectName=currentFitsFile.fitsFileObject,
                                                    fitsSessionTelescope=currentFitsFile.fitsFileTelescop,
                                                    fitsSessionImager=currentFitsFile.fitsFileInstrument,
                                                    fitsSessionDate=currentFitsFile.fitsFileDate,
                                                    fitsMasterBias=None,fitsMasterDark=None,fitsMasterFlat=None)
                    sessionsCreated.append(currentSessionId)
                    logging.info("New session created for "+str(newFitsSession.fitsSessionId))
                except IntegrityError as e:
                    # Handle the integrity error
                    logging.error("IntegrityError: "+str(e))
                    continue     
                currentObject = str(currentFitsFile.fitsFileObject)
            # Assign the current session to the fits file
            currentFitsFile.fitsFileSession=currentSessionId
            currentFitsFile.save()
            logging.info("Assigned "+str(currentFitsFile.fitsFileName)+" to session "+str(currentSessionId))
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
        unassignedBiases = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("Bias"))
        unassignedDarks  = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("Dark"))
        unassignedFlats  = FitsFileModel.select().where(FitsFileModel.fitsFileSession.is_null(True), FitsFileModel.fitsFileType.contains("Flat"))
        
        # Calculate total files for progress tracking
        total_biases = len(unassignedBiases)
        total_darks = len(unassignedDarks)
        total_flats = len(unassignedFlats)
        total_files = total_biases + total_darks + total_flats
        current_count = 0
        
        # How many unassigned_files are there?
        logging.info("createCalibrationSessions found "+str(total_biases)+" unassigned Bias calibration files to Session")
        logging.info("createCalibrationSessions found "+str(total_darks)+" unassigned Dark calibration files to Session")
        logging.info("createCalibrationSessions found "+str(total_flats)+" unassigned Flat calibration files to Session")

        # Bias calibration files
        currDate="0001-01-01"
        uuidStr=uuid.uuid4()
                        
        for biasFitsFile in unassignedBiases:
            current_count += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = progress_callback(current_count, total_files, f"Bias: {biasFitsFile.fitsFileName}")
                if not should_continue:
                    logging.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            if not self.sameDay(biasFitsFile.fitsFileDate.strftime('%Y-%m-%d'),currDate):
                currDate=datetime.strptime(biasFitsFile.fitsFileDate,'%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d')
                uuidStr=uuid.uuid4() # New Session
                newFitsSession=fitsSessionModel.create(fitsSessionId=uuidStr,
                                                fitsSessionDate=biasFitsFile.fitsFileDate,
                                                fitsSessionObjectName='Bias',
                                                fitsMasterBias=None,
                                                fitsMasterDark=None,
                                                fitsMasterFlat=None)
                logging.info("New date for bias "+currDate) 
            biasFitsFile.fitsFileSession=uuidStr
            biasFitsFile.save()   
            logging.info("Set Session for bias "+biasFitsFile.fitsFileName+" to "+str(uuidStr))
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
                    logging.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            if not self.sameDay(darkFitsFile.fitsFileDate.strftime('%Y-%m-%d'),currDate):
                currDate=datetime.strptime(darkFitsFile.fitsFileDate,'%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d')
                uuidStr=uuid.uuid4() # New Session
                newFitsSession=fitsSessionModel.create(fitsSessionId=uuidStr,
                                                fitsSessionDate=darkFitsFile.fitsFileDate,
                                                fitsSessionObjectName='Dark',
                                                fitsMasterBias=None,
                                                fitsMasterDark=None,
                                                fitsMasterFlat=None)
                logging.info("New date "+currDate) 
            darkFitsFile.fitsFileSession=uuidStr
            darkFitsFile.save()   
            logging.info("Set Session for dark "+darkFitsFile.fitsFileName+" to "+str(uuidStr))
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
                    logging.info("Calibration Session creation cancelled by user")
                    return createdCalibrationSessions
            
            if not self.sameDay(flatFitsFile.fitsFileDate.strftime('%Y-%m-%d'),currDate):
                currDate=datetime.strptime(flatFitsFile.fitsFileDate,'%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d')
                uuidStr=uuid.uuid4() # New Session
                newFitsSession=fitsSessionModel.create(fitsSessionId=uuidStr,
                                fitsSessionDate=flatFitsFile.fitsFileDate,
                                fitsSessionObjectName='Flat',
                                fitsMasterBias=None,
                                fitsMasterDark=None,
                                fitsMasterFlat=None)
                logging.info("New date "+currDate) 
            flatFitsFile.fitsFileSession=uuidStr
            flatFitsFile.save()   
            logging.info("Set Session for flat "+flatFitsFile.fitsFileName+" to "+str(uuidStr))
            createdCalibrationSessions.append(uuidStr)
        
        return createdCalibrationSessions

    #################################################################################################################
    ## calibrateFitsFile - this function calibrates a light IMAGETYP using master bias, dark, and flat IMAGETYPs. If     ##
    ##                     the master IMAGETYPs do not exist, they are created for the Session.                      ##
    #################################################################################################################
    def calibrateFitsImage(self,targetFitsFile):
        pass

    #################################################################################################################
    ## - this function submits a fits file to the database                                          ##
    #################################################################################################################
    def submitFileToDB(self,fileName,hdr,fileHash=None):
        if "DATE-OBS" in hdr:
            # Create new fitsFile record
            logging.info("Adding file "+fileName+" to repo with date "+hdr["DATE-OBS"])
            if "OBJECT" in hdr:
                newfile=FitsFileModel.create(fitsFileId=uuid.uuid4(),fitsFileName=fileName,fitsFileDate=hdr["DATE-OBS"],fitsFileType=hdr["IMAGETYP"],
                            fitsFileObject=hdr["OBJECT"],fitsFileExpTime=hdr["EXPTIME"],fitsFileXBinning=hdr["XBINNING"],
                            fitsFileYBinning=hdr["YBINNING"],fitsFileCCDTemp=hdr["CCD-TEMP"],fitsFileTelescop=hdr["TELESCOP"],
                            fitsFileInstrument=hdr["INSTRUME"],fitsFileFilter=hdr.get("FILTER", None),
                            fitsFileHash=fileHash,fitsFileSession=None)
            else:
                newfile=FitsFileModel.create(fitsFileId=uuid.uuid4(),fitsFileName=fileName,fitsFileDate=hdr["DATE-OBS"],fitsFileType=hdr["IMAGETYP"],
                            fitsFileExpTime=hdr["EXPTIME"],fitsFileXBinning=hdr["XBINNING"],
                            fitsFileYBinning=hdr["YBINNING"],fitsFileCCDTemp=hdr["CCD-TEMP"],fitsFileTelescop=hdr["TELESCOP"],
                            fitsFileInstrument=hdr["INSTRUME"],fitsFileFilter=hdr.get("FILTER", "OSC"),
                            fitsFileHash=fileHash,fitsFileSession=None)
            return newfile.fitsFileId
        else:
            logging.error("Error: File not added to repo due to missing date is "+fileName)
            return None
        return True
