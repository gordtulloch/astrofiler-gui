############################################################################################################
## A S T R O F I L E R                                                                                    ##
############################################################################################################

from datetime import datetime,timedelta
import os
from math import cos,sin 
from astropy.io import fits
from config import Config
import warnings
warnings.filterwarnings("ignore")

VERSION="0.0.1"

class astrofiler(object):
    def __init__(self):
        self.config=Config()
        self.sourceFolder=self.config.get('SOURCE')
        self.repoFolder=self.config.get('REPO')
        logging.info("Post Processing object initialized")

    #################################################################################################################
    ## registerFitsImage - this functioncalls a function to registers each fits files in the database              ##
    ## and also corrects any issues with the Fits header info (e.g. WCS)                                           ##
    #################################################################################################################
    # Note: Movefiles means we are moving from a source folder to the repo
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
            if (hdr["IMAGETYP"].upper()=="LIGHT"):
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
                    objectName=hdr["OBJECT"].replace(' ', '').replace('_', '').upper()
                    hdr.append(('OBJECT', objectName, 'Adjusted via Astrofiler'), end=True)
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
            ############## F L A T S #############################################################################            
            elif hdr["IMAGETYP"].upper()=="FLAT":
                if ("FILTER" in hdr):
                    newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
                else:
                    newName=newName="{0}-{1}-{2}-{3}-{4}-{5}s-{6}x{7}-t{8}.fits".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),"OSC",fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
            
            ############## D A R K S / B I A S E S ################################################################   
            elif hdr["IMAGETYP"].upper()=="DARK" or hdr["IMAGETYP"].upper()=="BIAS":
                newName="{0}-{1}-{1}-{2}-{3}-{4}s-{5}x{6}-t{7}.fits".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate,hdr["EXPTIME"],hdr["XBINNING"],hdr["YBINNING"],hdr["CCD-TEMP"])
            else:
                logging.warning("File not processed as IMAGETYP="+hdr["IMAGETYP"]+" not recognized: "+str(os.path.join(root, file)))
            hdul.close()
            newPath=""

            ######################################################################################################
            # Create the folder structure (if needed)
            fitsDate=dateobj.strftime("%Y%m%d")
            if (hdr["IMAGETYP"].upper()=="LIGHT"):
                newPath=self.repoFolder+"Light/{0}/{1}/{2}/{3}/".format(hdr["OBJECT"].replace(" ", ""),hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate)
            elif hdr["IMAGETYP"].upper()=="DARK ":
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["EXPTIME"],fitsDate)
            elif hdr["IMAGETYP"].upper()=="FLAT":
                if ("FILTER" in hdr):
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),hdr["FILTER"],fitsDate)
                else:
                    newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/{4}/".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),"OSC",fitsDate)
            elif hdr["IMAGETYP"].upper()=="BIAS":
                newPath=self.repoFolder+"Calibrate/{0}/{1}/{2}/{3}/".format(hdr["IMAGETYP"],hdr["TELESCOP"].replace(" ", "_").replace("\\", "_"),
                                    hdr["INSTRUME"].replace(" ", "_"),fitsDate)
            else:
                logging.warning("File not processed as IMAGETYP not recognized: "+str(os.path.join(root, file)))
                return None

            if not os.path.isdir(newPath) and moveFiles:
                os.makedirs (newPath)

            # If we can add the file to the database move it to the repo
            if moveFiles:
                if not os.path.exists(newPath+newName):
                    logging.info("Moving file "+os.path.join(root, file)+" to "+newPath+newName)
                else:
                    logging.warning("File already exists in repo - "+newPath+newName)
                    newName=newName.replace(".fits","_dup.fits")
                    logging.info("Renaming file to "+newName)              
        else:
            logging.warning("File not added to repo - no IMAGETYP card - "+str(os.path.join(root, file)))

        return

    #################################################################################################################
    ## registerFitsImages - this function scans the images folder and registers all fits files in the database     ##
    #################################################################################################################
    def registerFitsImages(self,moveFiles=True):
        registeredFiles=[]
        newFitsFileId=None
        
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
                if (self.registerFitsImage(root,file,moveFiles)):
                    logging.warning("File added to repo - "+str(os.path.join(root, file)))
                else:
                    logging.warning("File not added to repo - "+str(os.path.join(root, file)))
        return True

if __name__ == "__main__":
    print("Astrofiler "+VERSION+" by Gord Tulloch gord.tulloch@gmail.com")
    
    # Set up python logging to astrofile.log
    import logging
    from logging.handlers import RotatingFileHandler

    log_formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
    log_handler = RotatingFileHandler(
        'astrofiler.log',
        mode='a',
        maxBytes=1024*1024*5, # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    log_handler.setFormatter(log_formatter)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)

    logging.info("Starting astrofiler")
    
    # Initialize the astrofiler object
    astrofiler = astrofiler()
    # Register the fits images
    astrofiler.registerFitsImages(moveFiles=True)
    logging.info("Astrofiler finished processing")
    print("Astrofiler finished processing")
    logging.shutdown()
