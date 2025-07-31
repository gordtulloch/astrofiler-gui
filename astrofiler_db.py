import peewee as pw
import logging
import os
from peewee_migrate import Router

# Add a logger
logger = logging.getLogger(__name__)

# Create a database proxy
db = pw.SqliteDatabase('astrofiler.db')

# Initialize migration router
router = Router(db, migrate_dir='migrations')

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
    fitsSessionExposure = pw.TextField(null=True)
    fitsSessionBinningX = pw.TextField(null=True)
    fitsSessionBinningY = pw.TextField(null=True)
    fitsSessionCCDTemp = pw.TextField(null=True)
    fitsSessionGain = pw.TextField(null=True)
    fitsSessionOffset = pw.TextField(null=True)
    fitsSessionFilter = pw.TextField(null=True)
    fitsBiasSession = pw.TextField(null=True)
    fitsDarkSession = pw.TextField(null=True)
    fitsFlatSession = pw.TextField(null=True)
    fitsBiasMaster = pw.TextField(null=True)
    fitsDarkMaster = pw.TextField(null=True)
    fitsFlatMaster = pw.TextField(null=True)

def setup_database():
    """Initialize database with peewee-migrate for version control and migrations."""
    try:
        # Connect to database
        db.connect()
        
        # Ensure migrations directory exists
        os.makedirs('migrations', exist_ok=True)
        
        # Run any pending migrations
        router.run()
        
        # Create tables if they don't exist (initial setup)
        db.create_tables([fitsFile, fitsSession], safe=True)
        
        db.close()
        logger.info("Database setup complete with peewee-migrate. Tables created/updated.")
        return True
        
    except Exception as e:
        logger.error(f"Database setup error: {e}")
        if db.is_connection_usable():
            db.close()
        return False

def create_migration(name):
    """Create a new migration file with the given name."""
    try:
        # Connect to database
        db.connect()
        
        # Create migration
        router.create(name)
        
        db.close()
        logger.info(f"Migration '{name}' created successfully.")
        return True
        
    except Exception as e:
        logger.error(f"Error creating migration '{name}': {e}")
        if db.is_connection_usable():
            db.close()
        return False

def run_migrations():
    """Run all pending migrations."""
    try:
        # Connect to database
        db.connect()
        
        # Run migrations
        router.run()
        
        db.close()
        logger.info("All migrations completed successfully.")
        return True
        
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        if db.is_connection_usable():
            db.close()
        return False

def get_migration_status():
    """Get the current migration status."""
    try:
        # Connect to database
        db.connect()
        
        # Get migration history
        done_migrations = []
        pending_migrations = []
        
        try:
            # Check if migration history table exists
            tables = db.get_tables()
            if 'migratehistory' in tables:
                # Query migration history directly
                cursor = db.execute_sql("SELECT name FROM migratehistory ORDER BY id")
                done_migrations = [row[0] for row in cursor.fetchall()]
            
            # Get available migration files
            import os
            import glob
            if os.path.exists('migrations'):
                migration_files = glob.glob('migrations/[0-9]*.py')
                migration_names = []
                for f in migration_files:
                    # Extract migration name from filename (e.g., "001_initial_schema.py" -> "001_initial_schema")
                    basename = os.path.basename(f)
                    name = basename.replace('.py', '')
                    migration_names.append(name)
                migration_names.sort()
                
                # Find pending migrations
                pending_migrations = [m for m in migration_names if m not in done_migrations]
            
        except Exception as e:
            logger.debug(f"Could not get detailed migration info: {e}")
            # Fallback to basic info
            done_migrations = []
            pending_migrations = []
        
        db.close()
        
        return {
            'done': done_migrations,
            'undone': pending_migrations,
            'current': done_migrations[-1] if done_migrations else 'none'
        }
        
    except Exception as e:
        logger.error(f"Error getting migration status: {e}")
        if db.is_connection_usable():
            db.close()
        return None
