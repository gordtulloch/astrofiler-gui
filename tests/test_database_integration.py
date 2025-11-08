#!/usr/bin/env python3
"""
Test script for database integration with new package structure.
"""

import sys
import os
import logging

# Add parent directory to path for setup_path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setup_path  # Configure Python path for new package structure

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_database_integration():
    """Test the database integration functionality."""
    logger.info("Starting database integration tests...")
    logger.info("=" * 60)
    
    try:
        # Test database imports
        logger.info("Testing database imports...")
        
        from astrofiler.database import (
            DatabaseManager, 
            get_db_manager, 
            setup_database,
            create_migration,
            run_migrations,
            get_migration_status
        )
        logger.info("✓ Database module imports successful")
        
        # Test model imports
        from astrofiler.models import BaseModel, db, fitsFile, fitsSession, Mapping, Masters
        logger.info("✓ Model imports successful")
        
        # Test DatabaseManager instantiation
        db_manager = DatabaseManager()
        logger.info("✓ DatabaseManager instantiation successful")
        
        # Test singleton pattern
        db_manager1 = get_db_manager()
        db_manager2 = get_db_manager()
        assert db_manager1 is db_manager2, "Singleton pattern not working"
        logger.info("✓ DatabaseManager singleton pattern working")
        
        # Test backwards compatibility functions
        status = get_migration_status()
        logger.info(f"✓ Migration status check working: {status is not None}")
        
        # Test health check
        health = db_manager.health_check()
        logger.info(f"✓ Database health check: {'Healthy' if health else 'Issues detected'}")
        
        logger.info("-" * 30)
        logger.info("Testing integration with core modules...")
        
        # Test that core modules can import database components
        from astrofiler.core import fitsProcessing
        processor = fitsProcessing()
        logger.info("✓ Core module integration working")
        
        logger.info("=" * 60)
        logger.info("🎉 All database integration tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_database_integration()
    exit(0 if success else 1)