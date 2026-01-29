"""
Logging Configuration
Structured logging for production debugging
"""
import logging
import sys
import os
from datetime import datetime

_logging_configured = False

def setup_logging(app_name='tesserae'):
    """Configure structured logging for the application
    
    Sets up console logging with timestamps and levels.
    Suppresses noisy third-party loggers.
    """
    global _logging_configured
    
    if _logging_configured:
        return logging.getLogger(app_name)
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    debug_mode = os.environ.get('DEBUG', '').lower() in ('true', '1', 'yes')
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
    
    logger = logging.getLogger(app_name)
    logger.setLevel(log_level)
    
    _logging_configured = True
    return logger

def get_logger(name):
    """Get a logger for a specific module
    
    Args:
        name: Module name (e.g., 'app', 'scorer', 'matcher')
    
    Returns:
        Logger instance with tesserae namespace
    """
    return logging.getLogger(f'tesserae.{name}')
