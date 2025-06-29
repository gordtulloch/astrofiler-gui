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
from math import cos,sin 
from astropy.io import fits
import shutil
import pytz
from peewee import IntegrityError
import configparser

from astrofiler_db import fitsFile as FitsFileModel, fitsSequence as fitsSequenceModel

import logging
logging=logging.getLogger(__name__)

class fitsProcessing:
    """
    A class for processing FITS files, including registration, calibration, and database operations.
    
    This class handles:
    - Importing FITS file data into the database
    - Renaming and moving files to repository structure
    - Creating sequences from FITS files
    - Creating thumbnails
    - Calibrating images
    """
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        self.sourceFolder = config.get('DEFAULT', 'source', fallback='.')
        self.repoFolder = config.get('DEFAULT', 'repo', fallback='.')

    ################################################################################################################
    ## - this function submits a fits file to the database                                          ##
    #################################################################################################################
    def submitFileToDB(self,fileName,hdr):
        if "DATE-OBS" in hdr:
            # Create new fitsFile record
            if "OBJECT" in hdr:
                newfile=FitsFileModel.create(fitsFileId=uuid.uuid4(),fitsFileName=fileName,fitsFileDate=hdr["DATE-OBS"],fitsFileType=hdr["IMAGETYP"],
                            fitsFileObject=hdr["OBJECT"],fitsFileExpTime=hdr["EXPTIME"],fitsFileXBinning=hdr["XBINNING"],
                            fitsFileYBinning=hdr["YBINNING"],fitsFileCCDTemp=hdr["CCD-TEMP"],fitsFileTelescop=hdr["TELESCOP"],
                            fitsFileInstrument=hdr["INSTRUME"],
                            fitsFileSequence=None)
            else:
                newfile=FitsFileModel.create(fitsFileId=uuid.uuid4(),fitsFileName=fileName,fitsFileDate=hdr["DATE-OBS"],fitsFileType=hdr["IMAGETYP"],
                            fitsFileExpTime=hdr["EXPTIME"],fitsFileXBinning=hdr["XBINNING"],
                            fitsFileYBinning=hdr["YBINNING"],fitsFileCCDTemp=hdr["CCD-TEMP"],fitsFileTelescop=hdr["TELESCOP"],
                            fitsFileInstrument=hdr["INSTRUME"],
                            fitsFileSequence=None)
            return newfile.fitsFileId
        else:
            logging.error("Error: File not added to repo due to missing date is "+fileName)
            return None
        return True

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
                    hdr.append(('OBJECT', objectName, 'Adjusted via MCP'), end=True)
                    hdul.flush()  # changes are written back to original.fits
                    
                    if ("FILTER" in hdr):
                        newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(hdr["OBJECT"].replace(" ", "_"),hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                    else:
                        newName=newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(hdr["OBJECT"].replace(" ", "_"),hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
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
                    newName=newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format("Flat",hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
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
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["EXPTIME"],fitsDate)
            elif "Flat" in hdr["IMAGETYP"]:
                if ("FILTER" in hdr):
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate)
                else:
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),"OSC",fitsDate)
            elif hdr["IMAGETYP"]=="Bias":
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate)
            else:
                logging.warning("File not processed as IMAGETYP not recognized: "+str(os.path.join(root, file)))
                return None

            if not os.path.isdir(newPath) and moveFiles:
                os.makedirs (newPath)

            # If we can add the file to the database move it to the repo
            newFitsFileId=self.submitFileToDB(newPath+newName.replace(" ", "_"),hdr)
            if (newFitsFileId != None) and moveFiles:
                if not os.path.exists(newPath+newName):
                    logging.info("Moving file "+os.path.join(root, file)+" to "+newPath+newName)
                else:
                    logging.warning("File already exists in repo - "+newPath+newName)
                    newName=newName.replace(".fits","_dup.fits")
                    logging.info("Renaming file to "+newName)              
            else:
                logging.warning("Warning: File not moved to repo is "+str(os.path.join(root, file)))
        else:
            logging.warning("File not added to repo - no IMAGETYP card - "+str(os.path.join(root, file)))

        return newFitsFileId

    #################################################################################################################
    ## registerFitsImages - this function scans the images folder and registers all fits files in the database     ##
    #################################################################################################################
    def registerFitsImages(self,moveFiles=True):
        registeredFiles=[]
        newFitsFileId=None
        currCount=0

        # Scan the pictures folder
        if moveFiles:
            logging.info("Processing images in "+self.sourceFolder)
            workFolder=self.sourceFolder
        else:
            logging.info("Syncronizing images in "+os.path.abspath(self.repoFolder))
            workFolder=self.repoFolder

        for root, dirs, files in os.walk(os.path.abspath(workFolder)):
            for file in files:
                logging.info("Processing file "+os.path.join(root, file))
                if (newFitsFileId := self.registerFitsImage(root,file,moveFiles)) != None:
                    # Add the file to the list of registered files
                    currCount += 1
                    if currCount % 10 == 0:
                        logging.info(f"Processed {currCount} files so far...")
                    registeredFiles.append(newFitsFileId)
                    self.createThumbnail(newFitsFileId)
                else:
                    logging.warning("File not added to repo - no IMAGETYP card - "+str(os.path.join(root, file)))
        return registeredFiles

    #################################################################################################################
    ## createThumbnail - this function creates a thumbnail image for a fits file and saves it to the repository    ##
    #################################################################################################################
    def createThumbnail(self,fitsFileId):
        # Load the fits file
        fits_file = FitsFileModel.get_or_none(FitsFileModel.fitsFileId == fitsFileId)
        if not fits_file:
            logging.info(f"Failed to load fits file: {fitsFileId}")
            return
        
        # Read the data from the fits file
        try:
            with fits.open(fits_file.fitsFileName) as hdul:
                data = hdul[0].data
        except Exception as e:
            logging.info(f"Failed to read fits file: {e}")
            return
        
        # Create a thumbnail image
        thumbnail_data = data[::10, ::10]

        # Stretch the image to 0-100
        thumbnail_data = (thumbnail_data - np.min(thumbnail_data)) / (np.max(thumbnail_data) - np.min(thumbnail_data)) * 100
        
        # Save the thumbnail image as a JPG file
        thumbnail_path = os.path.join(self.repoFolder+'Thumbnails/', f'thumbnail_{fits_file.fitsFileId}.jpg')

        try:
            plt.imsave(thumbnail_path, thumbnail_data, cmap='gray')
            logging.info(f"Thumbnail image saved to: {thumbnail_path}")
        except Exception as e:
            logging.info(f"Failed to save thumbnail image: {e}")
        
        return

    #################################################################################################################
    ## createLightSequences - this function creates sequences for all Light files not currently assigned to one    ##
    #################################################################################################################
    def createLightSequences(self):
        sequencesCreated=[]
        
        # Query for all fits files that are not assigned to a sequence
        unassigned_files = FitsFileModel.select().where(FitsFileModel.fitsFileSequence.is_null(True), FitsFileModel.fitsFileType.contains("Light"))
        
        # How many unassigned_files are there?
        logging.info("createSequences found "+str(len(unassigned_files))+" unassigned files to sequence")

        # Loop through each unassigned file and create a sequence each time the object changes
        currentObject= ""
    
        for currentFitsFile in unassigned_files:
            logging.info("Current Object is "+currentFitsFile.fitsFileObject)
            logging.info("Processing "+str(currentFitsFile.fitsFileName))

            # If the object name has changed, create a new sequence
            if str(currentFitsFile.fitsFileObject) != currentObject:
                # Create a new fitsSequence record
                currentSequenceId = uuid.uuid4()
                try:
                    newFitsSequence=fitsSequenceModel.create(fitsSequenceId=currentSequenceId,
                                                    fitsSequenceObjectName=currentFitsFile.fitsFileObject,
                                                    fitsSequenceTelescope=currentFitsFile.fitsFileTelescop,
                                                    fitsSequenceImager=currentFitsFile.fitsFileInstrument,
                                                    fitsSequenceDate=currentFitsFile.fitsFileDate,
                                                    fitsMasterBias=None,fitsMasterDark=None,fitsMasterFlat=None)
                    sequencesCreated.append(currentSequenceId)
                    logging.info("New sequence created for "+str(newFitsSequence.fitsSequenceId))
                except IntegrityError as e:
                    # Handle the integrity error
                    logging.error("IntegrityError: "+str(e))
                    continue     
                currentObject = str(currentFitsFile.fitsFileObject)
            # Assign the current sequence to the fits file
            currentFitsFile.fitsFileSequence=currentSequenceId
            currentFitsFile.save()
            logging.info("Assigned "+str(currentFitsFile.fitsFileName)+" to sequence "+str(currentSequenceId))
            sequencesCreated.append(currentSequenceId)
            
        return sequencesCreated
        
    #################################################################################################################
    ## sameDay - this function returns True if two dates are within 12 hours of each other, False otherwise        ##
    #################################################################################################################
    def sameDay(self,Date1,Date2): # If Date1 is within 12 hours of Date2
        current_date = datetime.strptime(Date1, '%Y-%m-%d')
        target_date = datetime.strptime(Date2, '%Y-%m-%d')
        time_difference = abs(current_date - target_date)
        return time_difference <= timedelta(hours=12)
        
    #################################################################################################################
    ## createCalibrationSequences - this function creates sequences for all calibration files not currently        ##
    ##                              assigned to one                                                                ##
    #################################################################################################################
    def createCalibrationSequences(self):
        createdCalibrationSequences=[]
        
        # Query for all calibration files that are not assigned to a sequence
        unassignedBiases = FitsFileModel.select().where(FitsFileModel.fitsFileSequence.is_null(True), FitsFileModel.fitsFileType.contains("Bias"))
        unassignedDarks  = FitsFileModel.select().where(FitsFileModel.fitsFileSequence.is_null(True), FitsFileModel.fitsFileType.contains("Dark"))
        unassignedFlats  = FitsFileModel.select().where(FitsFileModel.fitsFileSequence.is_null(True), FitsFileModel.fitsFileType.contains("Flat"))
        
        # How many unassigned_files are there?
        logging.info("createCalibrationSequences found "+str(len(unassignedBiases))+" unassigned Bias calibration files to sequence")
        logging.info("createCalibrationSequences found "+str(len(unassignedDarks))+" unassigned Dark calibration files to sequence")
        logging.info("createCalibrationSequences found "+str(len(unassignedFlats))+" unassigned Flat calibration files to sequence")

        # Bias calibration files
        currDate="0001-01-01"
        uuidStr=uuid.uuid4()
                        
        for biasFitsFile in unassignedBiases:
            if not self.sameDay(biasFitsFile.fitsFileDate.strftime('%Y-%m-%d'),currDate):
                currDate=datetime.strptime(biasFitsFile.fitsFileDate,'%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d')
                uuidStr=uuid.uuid4() # New sequence
                newFitsSequence=fitsSequenceModel.create(fitsSequenceId=uuidStr,
                                                fitsSequenceDate=biasFitsFile.fitsFileDate,
                                                fitsSequenceObjectName='Flat',
                                                fitsMasterBias=None,
                                                fitsMasterDark=None,
                                                fitsMasterFlat=None)
                logging.info("New date for bias "+currDate) 
            biasFitsFile.fitsFileSequence=uuidStr
            biasFitsFile.save()   
            logging.info("Set sequence for bias "+biasFitsFile.fitsFileName+" to "+str(uuidStr))
            createdCalibrationSequences.append(uuidStr)
        
        # Dark calibration files
        currDate="0001-01-01"
        uuidStr=uuid.uuid4()
        for darkFitsFile in unassignedDarks:
            if not self.sameDay(darkFitsFile.fitsFileDate.strftime('%Y-%m-%d'),currDate):
                currDate=datetime.strptime(darkFitsFile.fitsFileDate,'%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d')
                uuidStr=uuid.uuid4() # New sequence
                newFitsSequence=fitsSequenceModel.create(fitsSequenceId=uuidStr,
                                                fitsSequenceDate=darkFitsFile.fitsFileDate,
                                                fitsSequenceObjectName='Dark',
                                                fitsMasterBias=None,
                                                fitsMasterDark=None,
                                                fitsMasterFlat=None)
                logging.info("New date "+currDate) 
            darkFitsFile.fitsFileSequence=uuidStr
            darkFitsFile.save()   
            logging.info("Set sequence for dark "+darkFitsFile.fitsFileName+" to "+str(uuidStr))
            createdCalibrationSequences.append(uuidStr)
            
        # Flat calibration files
        currDate="0001-01-01"
        uuidStr=uuid.uuid4()
        for flatFitsFile in unassignedFlats:
            if not self.sameDay(flatFitsFile.fitsFileDate.strftime('%Y-%m-%d'),currDate):
                currDate=datetime.strptime(flatFitsFile.fitsFileDate,'%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d')
                uuidStr=uuid.uuid4() # New sequence
                newFitsSequence=fitsSequenceModel.create(fitsSequenceId=uuidStr,
                                fitsSequenceDate=flatFitsFile.fitsFileDate,
                                fitsSequenceObjectName='Flat',
                                fitsMasterBias=None,
                                fitsMasterDark=None,
                                fitsMasterFlat=None)
                logging.info("New date "+currDate) 
            flatFitsFile.fitsFileSequence=uuidStr
            flatFitsFile.save()   
            logging.info("Set sequence for flat "+flatFitsFile.fitsFileName+" to "+str(uuidStr))
            createdCalibrationSequences.append(uuidStr)
        
        return createdCalibrationSequences

    #################################################################################################################
    ## calibrateFitsFile - this function calibrates a light IMAGETYP using master bias, dark, and flat IMAGETYPs. If     ##
    ##                     the master IMAGETYPs do not exist, they are created for the sequence.                      ##
    #################################################################################################################
    def calibrateFitsImage(self,targetFitsFile):
        pass
    