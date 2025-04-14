import logging
import sys

def setup_logging():
    """Configures logging to file (DEBUG) and console (INFO)."""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # File Handler (DEBUG level)
    file_handler = logging.FileHandler('app.log', mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_formatter)

    # Console Handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_formatter)

    # Get the root logger and add handlers (only if they haven't been added)
    logger = logging.getLogger()
    # Check if handlers already exist to prevent duplicates during hot reload
    if not logger.handlers:
        logger.setLevel(logging.DEBUG) # Set root logger level
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.info("--- Logging Initialized ---")
    # else: # No need for else, just don't add handlers if they exist
        # logger.info("Logging already initialized.")

# Call setup function immediately when module is imported
setup_logging()
