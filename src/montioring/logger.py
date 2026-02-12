import logging
import sys
from pathlib import Path

from ..config import ConfigManager
from .formatters import ColoredFormatter, JsonFormatter, StandardFormatter
from .ignore_filter import IgnorePortScannersFilter


class StructuredLogger:
    def __init__(self, name: str = "TradingBot", config: ConfigManager | None = None):
        self.name = name

        default_config = self._default_config()

        if config:
            default_config.update(config.get("logging"))
        self.config = default_config
        self.setup_logging()

    @staticmethod
    def _default_config() -> dict:
        return {
            "log_level": "INFO",
            "log_dir": "logs",
            "max_file_size": 10 * 1024 * 1024,  # 10MB
            "backup_count": 10,
            "format": "json",  # json or text
            "outputs": ["console", "file", "database"],
            "performance_tracking": True,
            "error_tracking": True,
        }

    def _get_formatter(self, output_type: str):
        if self.config.get("format") == "json" and output_type != "console":
            return JsonFormatter()
        else:
            return ColoredFormatter() if output_type == "console" else StandardFormatter()

    def setup_logging(self):
        log_dir = Path(self.config.get("log_dir", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger()
        logger.setLevel(getattr(logging, self.config.get("log_level", "INFO")))

        # 기존에 있던 handlers 삭제
        logger.handlers = []

        # 라이브러리 관련 로그는 심각한 오류만 표시
        logging.getLogger("aiohttp.server").setLevel(logging.CRITICAL)

        # Console handler
        if "console" in self.config.get("outputs"):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(self._get_formatter(output_type="console"))
            console_handler.addFilter(IgnorePortScannersFilter())
            logger.addHandler(console_handler)
