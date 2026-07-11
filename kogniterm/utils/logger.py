import logging
import os
import sys
import builtins
from logging.handlers import RotatingFileHandler


class StderrRedirector:
    """Redirects writes to sys.stderr to a logger to prevent output from leaking to TUI."""
    def __init__(self, logger_name="kogniterm.stderr"):
        self.logger = logging.getLogger(logger_name)
        self._buffer = []

    def write(self, buf):
        if not buf:
            return
        self._buffer.append(buf)
        if "\n" in buf:
            full_text = "".join(self._buffer)
            # Log all lines except the last trailing newline if any
            lines = full_text.splitlines()
            for line in lines:
                if line.strip():
                    self.logger.error(line)
            self._buffer = []

    def flush(self):
        if self._buffer:
            full_text = "".join(self._buffer)
            lines = full_text.splitlines()
            for line in lines:
                if line.strip():
                    self.logger.error(line)
            self._buffer = []


def setup_tui_redirects():
    """Redirects stderr and standard print() calls to the logging system.
    This prevents third-party libraries or accidental prints from corrupting
    the Textual TUI display, routing them to the log file instead.
    """
    # 1. Redirect sys.stderr to our StderrRedirector
    sys.stderr = StderrRedirector("kogniterm.stderr")

    # 2. Redirect builtins.print to route stdout-directed prints to logging
    _original_print = builtins.print
    def tui_print(*args, **kwargs):
        # If print is directed to a specific file that is NOT stdout or stderr,
        # let it proceed normally (e.g., writing to a file on disk).
        file = kwargs.get("file", sys.stdout)
        if file is not sys.stdout and file is not sys.stderr:
            _original_print(*args, **kwargs)
            return

        message = " ".join(str(arg) for arg in args)
        logging.getLogger("kogniterm.print").info(message)

    builtins.print = tui_print


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


def configure_server_logging(port: int = 8765, level: int = logging.INFO):
    """Configures the logging system for the backend server.
    Redirects FastAPI/Uvicorn logs to a rotating file handler at .kogniterm/logs/server.log
    to prevent console outputs when running the server.
    """
    log_dir = os.path.join(os.getcwd(), ".kogniterm", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "server.log")

    # Rotating File Handler (10MB, 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # Configure Python's root logger for the server process
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    root.addHandler(file_handler)
    root.setLevel(level)

    # Ensure third-party / webserver loggers propagate to root and don't use stream handlers
    web_loggers = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "kogniterm",
        "litellm",
    ]
    for logger_name in web_loggers:
        l = logging.getLogger(logger_name)
        for handler in list(l.handlers):
            l.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        l.propagate = True
        l.setLevel(level)

    # Disable lastResort StreamHandler
    logging.lastResort = logging.NullHandler()