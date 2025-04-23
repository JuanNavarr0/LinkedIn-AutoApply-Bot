"""
Logging configuration utility for the application.

Provides a function to set up and configure a standardized logger.
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = __name__,
    level: str = "INFO",
    log_to_file: bool = False,
    log_file: str = "app.log"
) -> logging.Logger:
    """
    Configure and return a logger instance.

    Args:
        name: The name for the logger, typically the module name (__name__).
        level: The logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR").
        log_to_file: Whether to log to a file in addition to the console.
        log_file: The name of the file to log to if log_to_file is True.

    Returns:
        A configured logging.Logger instance.
    """
    # Ensure level name is uppercase
    level_upper = level.upper()
    log_level = getattr(logging, level_upper, logging.INFO)  # Default to INFO if invalid level string

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Prevent adding multiple handlers if logger already exists
    if logger.hasHandlers():
        logger.handlers.clear()

    # Define log format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Console Handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # File Handler (Optional)
    if log_to_file:
        try:
            file_handler = logging.FileHandler(log_file, mode='a')  # Append mode
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info(f"Logging configured to write to file: {log_file}")
        except Exception as e:
            logger.error(f"Failed to configure file logging to {log_file}: {e}", exc_info=True)

    logger.info(f"Logger '{name}' configured with level {level_upper}.")
    return logger