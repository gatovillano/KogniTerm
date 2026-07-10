import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = "kogniterm", level: int = logging.DEBUG, console_output: bool = False) -> logging.Logger:
    """Configures and returns a logger with file handler and optional console handler.
    
    Args:
        name: Logger name (default: "kogniterm")
        level: Logging level (default: INFO)
        console_output: If False, disables StreamHandler to prevent TUI interference (default: True)
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid multiple handlers if already configured
    if logger.handlers:
        return logger

    # Define log directory
    log_dir = os.path.join(os.getcwd(), ".kogniterm", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "kogniterm.log")

    # File Handler with rotation (10MB max per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console Handler - only add if console_output is True
    # This prevents logs from appearing in the TUI
    if console_output:
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.WARNING)
        logger.addHandler(console_handler)

    return logger

def get_logger(name: str) -> logging.Logger:
    """Returns a logger for the given name, ensuring it's a child of kogniterm."""
    if not name.startswith("kogniterm.") and name != "kogniterm":
        name = f"kogniterm.{name}"
    return logging.getLogger(name)

def disable_console_handler(logger: logging.Logger = None, name: str = "kogniterm") -> None:
    """Disables console (StreamHandler) output for a logger to prevent TUI interference.
    
    Args:
        logger: Logger instance (if None, gets logger by name)
        name: Logger name if logger is None (default: "kogniterm")
    """
    if logger is None:
        logger = logging.getLogger(name)
    
    # Remove all StreamHandler instances
    handlers_to_remove = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
    for handler in handlers_to_remove:
        logger.removeHandler(handler)
        handler.close()

def enable_file_logging_only(name: str = "kogniterm", level: int = logging.INFO) -> logging.Logger:
    """Sets up logging to file only (no console output) for TUI mode.
    
    This is the recommended way to initialize logging when using the TUI.
    
    Args:
        name: Logger name (default: "kogniterm")
        level: Logging level (default: INFO)
    """
    return setup_logger(name=name, level=level, console_output=False)