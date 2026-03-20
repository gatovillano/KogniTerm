import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = "kogniterm", level: int = logging.INFO) -> logging.Logger:
    """Configures and returns a logger with both file and (optional) console handlers."""
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

    # Console Handler (only for WARNING and above, to avoid UI corruption in TUI)
    # Note: In TUI mode, we might want to disable this OR use a special handler.
    # For now, we'll keep it at WARNING level.
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
