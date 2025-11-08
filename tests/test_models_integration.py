#!/usr/bin/env python3
"""
Test script for models integration with new package structure.
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

def test_models_integration():
    """Test the models integration functionality."""
    logger.info("Starting models integration tests...")
    logger.info("=" * 60)
    
    try:
        # Test direct model imports from astrofiler.models
        logger.info("Testing direct model imports...")
        
        from astrofiler.models import (
            BaseModel, 
            db, 
            fitsFile, 
            fitsSession, 
            Mapping, 
            Masters
        )
        logger.info("✓ Direct model imports successful")
        
        # Test imports from main package
        logger.info("Testing package-level model imports...")
        
        from astrofiler import (
            fitsFile as PackageFitsFile,
            fitsSession as PackageFitsSession,
            BaseModel as PackageBaseModel
        )
        logger.info("✓ Package-level model imports successful")
        
        # Verify they're the same objects
        assert fitsFile is PackageFitsFile, "fitsFile not the same object"
        assert fitsSession is PackageFitsSession, "fitsSession not the same object"
        assert BaseModel is PackageBaseModel, "BaseModel not the same object"
        logger.info("✓ Package and direct imports are consistent")
        
        # Test database integration with models
        from astrofiler.database import get_db_manager
        db_manager = get_db_manager()
        logger.info("✓ Database manager can access models")
        
        # Test core module integration
        from astrofiler.core import fitsProcessing
        processor = fitsProcessing()
        logger.info("✓ Core modules work with moved models")
        
        # Test that old import paths are gone
        try:
            import models
            logger.error("✗ Old models import still works - cleanup incomplete")
            return False
        except ImportError:
            logger.info("✓ Old models directory properly removed")
        
        logger.info("-" * 30)
        logger.info("Testing model functionality...")
        
        # Test model class access
        assert hasattr(fitsFile, '_meta'), "fitsFile model structure intact"
        assert hasattr(fitsSession, '_meta'), "fitsSession model structure intact"
        assert hasattr(Mapping, '_meta'), "Mapping model structure intact"
        assert hasattr(Masters, '_meta'), "Masters model structure intact"
        logger.info("✓ All model classes have proper structure")
        
        logger.info("=" * 60)
        logger.info("🎉 All models integration tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Models integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_models_integration()
    exit(0 if success else 1)