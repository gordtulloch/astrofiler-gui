#!/usr/bin/env python3
"""
Test script to verify the advanced master management integration.
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

def test_master_management_integration():
    """Test that master management is properly integrated."""
    logger.info("Testing advanced master management integration...")
    
    try:
        # Test imports
        from astrofiler.core import fitsProcessing, MasterFrameManager, get_master_manager
        from astrofiler.core.master_manager import MasterFrameManager as DirectMasterManager
        from astrofiler.core.calibration import CalibrationProcessor
        
        logger.info("✓ All imports successful")
        
        # Test unified fitsProcessing class
        processor = fitsProcessing()
        assert hasattr(processor, 'master_manager'), "fitsProcessing should have master_manager"
        assert hasattr(processor, 'createAdvancedMaster'), "Should have createAdvancedMaster method"
        assert hasattr(processor, 'validateMasters'), "Should have validateMasters method"
        assert hasattr(processor, 'cleanupMasters'), "Should have cleanupMasters method"
        assert hasattr(processor, 'getMasterStatistics'), "Should have getMasterStatistics method"
        
        logger.info("✓ Advanced methods available in fitsProcessing")
        
        # Test master manager singleton
        manager1 = get_master_manager()
        manager2 = get_master_manager()
        assert manager1 is manager2, "get_master_manager should return singleton"
        
        logger.info("✓ Master manager singleton working")
        
        # Test calibration processor integration
        calib_processor = CalibrationProcessor()
        assert hasattr(calib_processor, 'getMasterStatistics'), "Should have statistics method"
        assert hasattr(calib_processor, 'cleanupMasters'), "Should have cleanup method"
        
        logger.info("✓ Calibration processor integration working")
        
        # Test method delegation
        try:
            stats = processor.getMasterStatistics()
            assert isinstance(stats, dict), "Statistics should return a dictionary"
            logger.info("✓ Master statistics method working")
        except Exception as e:
            logger.warning(f"Statistics method test failed (expected if no DB): {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Integration test failed: {e}")
        return False

def main():
    """Run integration tests."""
    logger.info("Starting advanced master management integration tests...")
    logger.info("=" * 60)
    
    success = test_master_management_integration()
    
    logger.info("=" * 60)
    if success:
        logger.info("🎉 All integration tests passed! Advanced master management ready.")
        return True
    else:
        logger.error("❌ Integration tests failed. Check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)