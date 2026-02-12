import logging


class ColoredFormatter(logging.Formatter):
    """Colored console formatter"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "TRADE": "\033[35m",  # Magenta
        "PROFIT": "\033[92m",  # Bright Green
        "LOSS": "\033[91m",  # Bright Red
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Red Background
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)
