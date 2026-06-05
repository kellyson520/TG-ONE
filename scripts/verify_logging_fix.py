from core.logging import setup_logging
import structlog
import logging

try:
    print("Calling setup_logging()...")
    setup_logging()
    print("setup_logging() completed successfully.")
    
    logger = structlog.get_logger("test_logger")
    logger.info("This is an info message from structlog")
    logger.warning("This is a warning message from structlog")
    
    print("Verification successful.")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Verification failed: {e}")
