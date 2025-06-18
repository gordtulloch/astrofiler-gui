#############################################################################################################
## C O N F I G                                                                                       ##
#############################################################################################################
# Object to retrieve configuration
import configparser
import os

import logging
logger = logging.getLogger('Config')

class Config():
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'astrofiler.ini')
        # Check if the file exists
        if not os.path.exists(self.file_path):
            logger.info("Config file not found, creating with defaults.")
            self.config['DEFAULT'] = {
                'SOURCE'    : '/home/gtulloch/REPOSITORY.source/',     # Where the source files are stored
                'REPO'      : '/home/gtulloch/REPOSITORY.target/', # Where the repository is stored
            }
            with open(self.file_path, 'w') as configfile:
                self.config.write(configfile)
                return      
    def get(self,keyword):
                self.config = configparser.ConfigParser()
                self.config.read(self.file_path)
                return self.config['DEFAULT'][keyword]
