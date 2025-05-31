import logging
import sys
import os
from logging.handlers import RotatingFileHandler # Import RotatingFileHandler

def setup_logging():
    """Configures logging to file (DEBUG, rotating) and console (configurable level)."""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s') # Added filename/lineno

    # Rotating File Handler (DEBUG level)
    # Max 5MB per file, keep 3 backup files
    log_filename = 'app.log'
    max_bytes = 5 * 1024 * 1024 # 5 MB
    backup_count = 3
    file_handler = RotatingFileHandler(log_filename, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_formatter)

    # Console Handler - レベルを環境変数で制御可能
    console_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    console_level = getattr(logging, console_level_str, logging.INFO)
    
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)

    # Get the root logger and add handlers (only if they haven't been added)
    logger = logging.getLogger()
    # Prevent adding handlers multiple times during hot reloads
    if not any(isinstance(h, (RotatingFileHandler, logging.StreamHandler)) for h in logger.handlers):
        logger.setLevel(logging.DEBUG) # Set root logger level to capture DEBUG for file handler
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.info(f"--- Logging Initialized (File: {log_filename}, Console Level: {console_level_str}, MaxSize: {max_bytes/1024/1024:.1f}MB, Backups: {backup_count}) ---")
    else:
        # Update formatter/level if already initialized (useful for some hot reload scenarios)
        for handler in logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                handler.setFormatter(log_formatter)
                handler.setLevel(logging.DEBUG)
            elif isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                handler.setFormatter(console_formatter)
                handler.setLevel(console_level)
        logger.info("--- Logging Already Initialized (Handlers potentially updated) ---")


# Call setup function immediately when module is imported
setup_logging()
