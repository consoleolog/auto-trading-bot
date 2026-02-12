from ..config import ConfigManager


class StructuredLogger:
    def __init__(self, name: str = "TradingBot", config: ConfigManager | None = None):
        self.name = name

        default_config = self._default_config()

        if config:
            default_config.update(config.get("logging"))
        self.config = default_config

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
