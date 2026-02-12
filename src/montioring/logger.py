import logging
import sys
from pathlib import Path

from ..config import ConfigManager
from .formatters import ColoredFormatter, JsonFormatter, StandardFormatter
from .ignore_filter import IgnorePortScannersFilter

# 전역 로거 인스턴스 (싱글톤 패턴)
_logger_instance: "StructuredLogger | None" = None


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

        # File handler
        if "file" in self.config.get("outputs"):
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                log_dir / f"{self.name}.log",
                maxBytes=int(self.config.get("max_file_size")),
                backupCount=self.config.get("backup_count"),
            )
            file_handler.setFormatter(self._get_formatter(output_type="file"))
            logger.addHandler(file_handler)

            # 에러 로그는 따로 관리
            if self.config.get("error_tracking"):
                error_handler = RotatingFileHandler(
                    log_dir / f"{self.name}_errors.log",
                    maxBytes=int(self.config.get("max_file_size")),
                    backupCount=self.config.get("backup_count"),
                )
                error_handler.setLevel(logging.ERROR)
                error_handler.setFormatter(self._get_formatter("file"))
                error_handler.addFilter(IgnorePortScannersFilter())
                logger.addHandler(error_handler)


def setup_logger(name: str = "TradingBot", config: ConfigManager | None = None) -> StructuredLogger:
    """
    전역 로거를 설정합니다. 애플리케이션 시작 시 한 번만 호출해야 합니다.

    Args:
        name: 로거 이름 (로그 파일명으로 사용됨)
        config: ConfigManager 인스턴스

    Returns:
        설정된 StructuredLogger 인스턴스
    """
    global _logger_instance
    _logger_instance = StructuredLogger(name=name, config=config)
    return _logger_instance


def get_logger(name: str | None = None) -> logging.Logger:
    """
    모듈별 로거를 가져옵니다.

    Usage:
        from src.monitoring.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Hello World")

    Args:
        name: 로거 이름 (일반적으로 __name__ 사용)

    Returns:
        logging.Logger 인스턴스
    """
    if name is None:
        return logging.getLogger()
    return logging.getLogger(name)
