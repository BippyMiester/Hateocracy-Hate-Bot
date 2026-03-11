import os
import sys
import time
import logging
import re

LOGS_DIR = "logs"  # Or your preferred logs directory

# A regular expression that matches ANSI escape sequences
ANSI_ESCAPE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

class NoColorFormatter(logging.Formatter):
    def format(self, record):
        # First get the unmodified formatted message.
        s = super().format(record)
        # Then remove ANSI escape sequences (colors)
        return ANSI_ESCAPE.sub('', s)

class Logger:
    _logger = None
    # ANSI escape codes for colors
    COLORS = {
        'DEBUG': '\033[94m',   # Blue
        'INFO': '\033[92m',    # Green
        'WARNING': '\033[93m', # Yellow
        'ERROR': '\033[91m',   # Red
        'CRITICAL': '\033[41m',# White text on Red background
        'RESET': '\033[0m',    # Reset to default color
    }

    @classmethod
    def _initialize(cls, debug=False):
        if cls._logger is not None:
            return  # Already initialized

        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR, exist_ok=True)

        timestamp = int(time.time())
        date_str = time.strftime("%Y-%m-%d")
        log_filename = f"{date_str}-{timestamp}.log"
        log_path = os.path.join(LOGS_DIR, log_filename)

        logger = logging.getLogger("process_uploads")
        logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        # Clear any previous handlers
        if logger.hasHandlers():
            logger.handlers.clear()

        # Create console handler with color
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)

        # Create file handler without color by using our custom NoColorFormatter
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        file_formatter = NoColorFormatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        logger.info(f"Logger initialized. Log file at: {log_path}")
        cls._logger = logger

    @classmethod
    def _colorize(cls, level, msg):
        """Colorize the log message based on the log level."""
        color = cls.COLORS.get(level, cls.COLORS['RESET'])
        return f"{color}{msg}{cls.COLORS['RESET']}"

    @classmethod
    def debug(cls, msg, *args, **kwargs):
        if cls._logger is None:
            cls._initialize(debug=True)
        cls._logger.debug(cls._colorize('DEBUG', msg), *args, **kwargs)

    @classmethod
    def info(cls, msg, *args, **kwargs):
        if cls._logger is None:
            cls._initialize(debug=False)
        cls._logger.info(cls._colorize('INFO', msg), *args, **kwargs)

    @classmethod
    def warning(cls, msg, *args, **kwargs):
        if cls._logger is None:
            cls._initialize(debug=False)
        cls._logger.warning(cls._colorize('WARNING', msg), *args, **kwargs)

    @classmethod
    def error(cls, msg, *args, **kwargs):
        if cls._logger is None:
            cls._initialize(debug=False)
        cls._logger.error(cls._colorize('ERROR', msg), *args, **kwargs)

    @classmethod
    def critical(cls, msg, *args, **kwargs):
        if cls._logger is None:
            cls._initialize(debug=False)
        cls._logger.critical(cls._colorize('CRITICAL', msg), *args, **kwargs)

    @classmethod
    def set_debug(cls, debug=True):
        cls._initialize(debug=debug)