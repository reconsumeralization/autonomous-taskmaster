import os
import logging
from logging.handlers import RotatingFileHandler
import sys

# ================== Logging Setup ==================
def setup_logging(config: dict):
    """Initialize logging to file, stderr (for MCP), and console with rotation."""
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = config.get('LOG_FILE', 'mcp_server.log')
    log_level_str = config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    log_path = os.path.join(log_dir, log_file)
    
    # File Handler (Rotating)
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # STDERR Handler (for MCP compatibility)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s') # Simpler format for console
    stderr_handler.setFormatter(stderr_formatter)

    # Get the root logger and configure it
    logger = logging.getLogger() 
    logger.setLevel(log_level)
    
    # Clear existing handlers (important if this function is called multiple times)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)

    logging.info(f"Logging initialized. Level: {log_level_str}. File: {log_path}. Outputting to STDERR.")

# Example Usage (can be removed later)
# if __name__ == '__main__':
#     example_config = {
#         "LOG_FILE": "test_log.log",
#         "LOG_LEVEL": "DEBUG"
#     }
#     setup_logging(example_config)
#     logging.debug("This is a debug message.")
#     logging.info("This is an info message.")
#     logging.warning("This is a warning message.")
#     logging.error("This is an error message.") 

def run_pytest(cwd, result, stdout, stderr):
    if result.returncode == 0:
        logging.info(f"Pytest PASSED (Exit Code: {result.returncode}) in {cwd}")
        logging.debug(f"Pytest STDOUT:\n{stdout}")
        if stderr: 
            logging.debug(f"Pytest STDERR:\n{stderr}")
    else:
        logging.warning(f"Pytest FAILED (Exit Code: {result.returncode}) in {cwd}")
        if stdout: 
            logging.info(f"Pytest STDOUT:\n{stdout}")
        if stderr: 
            logging.error(f"Pytest STDERR:\n{stderr}")
    return success, stdout, stderr 