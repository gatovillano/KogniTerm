import logging
import os
from logging.handlers import RotatingFileHandler


def _build_file_handler(log_dir: str | None = None) -> RotatingFileHandler:
    """Creates a shared RotatingFileHandler pointing to .kogniterm/logs/kogniterm.log."""
    if log_dir is None:
        log_dir = os.path.join(os.getcwd(), ".kogniterm", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "kogniterm.log")

    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    return file_handler


def setup_logger(
    name: str = "kogniterm",
    level: int = logging.DEBUG,
    console_output: bool = False,
) -> logging.Logger:
    """Configures and returns a logger with file handler and optional console handler.

    Args:
        name: Logger name (default: "kogniterm")
        level: Logging level (default: INFO)
        console_output: If False, disables StreamHandler to prevent TUI interference
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid multiple handlers if already configured
    if logger.handlers:
        return logger

    logger.addHandler(_build_file_handler())

    # Console Handler - only add if console_output is True
    # This prevents logs from appearing in the TUI
    if console_output:
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.WARNING)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Returns a logger for the given name, ensuring it's a child of kogniterm."""
    if not name.startswith("kogniterm.") and name != "kogniterm":
        name = f"kogniterm.{name}"
    return logging.getLogger(name)


def disable_console_handler(
    logger: logging.Logger = None, name: str = "kogniterm"
) -> None:
    """Disables console (StreamHandler) output for a logger to prevent TUI interference.

    Args:
        logger: Logger instance (if None, gets logger by name)
        name: Logger name if logger is None (default: "kogniterm")
    """
    if logger is None:
        logger = logging.getLogger(name)

    # Remove all StreamHandler instances
    handlers_to_remove = [
        h for h in logger.handlers if isinstance(h, logging.StreamHandler)
    ]
    for handler in handlers_to_remove:
        logger.removeHandler(handler)
        handler.close()


def enable_file_logging_only(
    name: str = "kogniterm", level: int = logging.INFO
) -> logging.Logger:
    """Sets up logging to file only (no console output) for TUI mode.

    This is the recommended way to initialize logging when using the TUI.
    It configures both the named logger AND the Python root logger so that
    logs from third-party libraries (uvicorn, fastapi, litellm, asyncio, etc.)
    are also routed to the log file instead of polluting stdout/stderr.

    Args:
        name: Logger name (default: "kogniterm")
        level: Logging level (default: INFO)
    """
    # --- 1. Build a shared file handler for reuse ---
    file_handler = _build_file_handler()

    # --- 2. Silence the Python root logger completely ---
    # Remove any existing handlers (including the default lastResort StreamHandler
    # and any handler added by a previous logging.basicConfig call).
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    # Route root-level records to the file so third-party libs are captured there.
    root.addHandler(file_handler)
    root.setLevel(level)

    # Also neutralise the logging.lastResort fallback handler that Python uses
    # when no handlers are configured. Setting it to a NullHandler prevents any
    # "No handlers could be found" warnings from leaking to the terminal.
    logging.lastResort = logging.NullHandler()

    # --- 3. Configure the named kogniterm logger ---
    kogniterm_logger = logging.getLogger(name)
    kogniterm_logger.setLevel(level)
    # Propagate=True means records flow up to root (and its FileHandler).
    # No need to add a second FileHandler here.
    kogniterm_logger.propagate = True

    return kogniterm_logger