import logging
import sys
from app.core.config import settings

def get_logger(module_name: str = settings.APP_NAME) -> logging.Logger:
    """Creates a unified, formatted logger for the entire application."""
    logger = logging.getLogger(module_name)
    
    # Prevent duplicate handlers if instantiated multiple times
    if not logger.handlers:
        logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
        
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

# Global logger instance
logger = get_logger()