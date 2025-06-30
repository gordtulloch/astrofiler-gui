import peewee as pw
import logging

# Add a logger
logger = logging.getLogger(__name__)

# Create a database proxy
db = pw.SqliteDatabase('astrofiler.db')

class BaseModel(pw.Model):
    class Meta:
        database = db

class fitsFile(BaseModel):
    fitsFileId = pw.TextField(primary_key=True)
    fitsFileName = pw.TextField(null=True)
    fitsFileDate = pw.DateField(null=True)
    fitsFileCalibrated = pw.IntegerField(null=True)
    fitsFileType = pw.TextField(null=True)
    fitsFileStacked = pw.IntegerField(null=True)
    fitsFileObject = pw.TextField(null=True)
    fitsFileExpTime = pw.TextField(null=True)
    fitsFileXBinning = pw.TextField(null=True)
    fitsFileYBinning = pw.TextField(null=True)
    fitsFileCCDTemp = pw.TextField(null=True)
    fitsFileTelescop = pw.TextField(null=True)
    fitsFileInstrument = pw.TextField(null=True)
    fitsFileGain = pw.TextField(null=True)
    fitsFileOffset = pw.TextField(null=True)
    fitsFileFilter = pw.TextField(null=True)
    fitsFileHash = pw.TextField(null=True)
    fitsFileSession = pw.TextField(null=True)

class fitsSession(BaseModel):
    fitsSessionId = pw.TextField(primary_key=True)
    fitsSessionObjectName = pw.TextField(null=True)
    fitsSessionDate = pw.DateField(null=True)
    fitsSessionTelescope = pw.TextField(null=True)
    fitsSessionImager = pw.TextField(null=True)
    fitsBiasSession = pw.TextField(null=True)
    fitsDarkSession = pw.TextField(null=True)
    fitsFlatSession = pw.TextField(null=True)

def setup_database():
    """Connect to the SQLite database and create the fitsFile and fitsSession tables if they don't exist."""
    try:
        db.connect()
        db.create_tables([fitsFile, fitsSession])
        db.close()
        logger.info("Database setup complete. fitsFile and fitsSession tables created.")
        
    except pw.OperationalError as e:
        logger.error(f"Database error: {e}")
