#!/usr/bin/env python3
"""
Test logger functionality to debug the "'bool' object is not callable" issue.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_logger():
    """Test basic logger functionality."""
    print("Testing logger import and creation...")
    
    try:
        from subshift.logging import get_logger
        print("✓ Successfully imported get_logger")
        
        # Test logger creation
        logger = get_logger(debug=True)
        print(f"✓ Logger created: {type(logger)}")
        print(f"✓ Logger debug mode: {logger.debug_mode}")
        
        # Test logger methods
        print("Testing logger methods...")
        print(f"  logger.info type: {type(logger.info)}")
        print(f"  logger.debug type: {type(logger.debug)}")  # This might be the issue!
        print(f"  logger.error type: {type(logger.error)}")
        print(f"  logger.warning type: {type(logger.warning)}")
        
        # Test actual logging calls
        print("Testing actual logging calls...")
        logger.info("Test info message")
        logger.error("Test error message")
        logger.warning("Test warning message")
        
        # Test debug logging call - this might fail
        print("Testing debug logging call...")
        logger.debug("Test debug message")
        
        print("✓ All logger tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Logger test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_multiple_logger_instances():
    """Test creating multiple logger instances."""
    print("\nTesting multiple logger instances...")
    
    try:
        from subshift.logging import get_logger
        
        logger1 = get_logger(debug=False)
        logger2 = get_logger(debug=True)
        
        print(f"Logger 1 debug: {logger1.debug_mode}")
        print(f"Logger 2 debug: {logger2.debug_mode}")
        print(f"Same instance: {logger1 is logger2}")
        
        # Test both loggers
        logger1.info("Logger 1 info message")
        logger2.info("Logger 2 info message")
        
        print("✓ Multiple logger test passed!")
        return True
        
    except Exception as e:
        print(f"✗ Multiple logger test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("SubShift Logger Debugging")
    print("=" * 25)
    
    success1 = test_logger()
    success2 = test_multiple_logger_instances()
    
    if success1 and success2:
        print("\n✅ All logger tests passed!")
    else:
        print("\n❌ Logger tests failed!")
        sys.exit(1)
