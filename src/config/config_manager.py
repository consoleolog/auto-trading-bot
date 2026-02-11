import json
import logging
import os
import threading
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .config_core import ConfigSchema, ConfigSource, ConfigValidationError, ConfigValue
from .file_watcher import FileWatcher

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Thread-safe configuration manager with hot reload support.

    Features:
    - Load from multiple sources (files, env vars)
    - Automatic file watching and reload
    - Schema validation
    - Change callbacks for application updates
    - Thread-safe access
    """

    def __init__(self, schema: ConfigSchema | None = None, watch_interval: float = 1.0):
        """
        Initialize the configuration manager.

        Args:
            schema: Optional schema for validation
            watch_interval: File check interval in seconds
        """
        self.schema = schema
        self._config: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._watcher = FileWatcher(poll_interval=watch_interval)
        self._change_callbacks: list[Callable[[dict], None]] = []
        self._config_files: list[Path] = []

    def load_file(self, file_path: str, watch: bool = True, required: bool = True):
        """
        Load configuration from a file.

        Args:
            file_path: Path to config file (JSON or YAML)
            watch: Whether to watch for changes
            required: Raise error if file doesn't exist
        """
        path = Path(file_path).resolve()

        if not path.exists():
            if required:
                raise FileNotFoundError(f"Config file not found: {path}")
            return

        # Read and parse the file
        config = self._read_file(path)

        # Wrap values with ConfigValue
        wrapped_config = self._wrap_values(config, ConfigSource.FILE)

        # Merge with existing config
        with self._lock:
            self._deep_merge(self._config, wrapped_config)
            self._config_files.append(path)

        logger.info(f"Loaded config from {path}")

        # Set up file watching if requested
        if watch:
            self._watcher.watch(str(path), self._on_file_changed)

    def load_env(self, prefix: str = "", mapping: dict[str, str] | None = None):
        """
        Load configuration from environment variables.

        Args:
            prefix: Only load vars starting with this prefix
            mapping: Map env var names to config keys
        """
        if mapping:
            # Use explicit mapping
            for env_var, config_key in mapping.items():
                value = os.environ.get(env_var)
                if value is not None:
                    self._set_from_env(config_key, value)
        else:
            # Load all vars with prefix
            for key, value in os.environ.items():
                if prefix and not key.startswith(prefix):
                    continue

                # Convert env var name to config key
                # APP_DATABASE_HOST -> database.host
                config_key = key[len(prefix) :].lower().replace("_", ".")
                self._set_from_env(config_key, value)

    def _set_from_env(self, key: str, value: str):
        """Set a config value from an environment variable"""
        # Try to parse as JSON for complex types
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            # Keep as string
            parsed = value

        # Wrap in ConfigValue with ENVIRONMENT source
        config_value = ConfigValue(value=parsed, source=ConfigSource.ENVIRONMENT)

        with self._lock:
            self._set_nested(self._config, key, config_value)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Dot-notation key (e.g., "database.host")
            default: Value to return if key not found

        Returns:
            Configuration value or default
        """
        with self._lock:
            value = self._get_nested(self._config, key)

            if value is None:
                return default

            # Unwrap ConfigValue if it's a leaf value
            if isinstance(value, ConfigValue):
                return value.value

            # If it's a dict, recursively unwrap all ConfigValues
            if isinstance(value, dict):
                return self._unwrap_values(value)

            return value

    def get_all(self) -> dict[str, Any]:
        """Get a copy of the entire configuration with unwrapped values"""
        with self._lock:
            return self._unwrap_values(deepcopy(self._config))

    def get_with_source(self, key: str) -> ConfigValue | dict | None:
        """
        Get a configuration value with its metadata (source, updated_at).

        Args:
            key: Dot-notation key (e.g., "database.host")

        Returns:
            ConfigValue object or dict of ConfigValues, or None if not found
        """
        with self._lock:
            return self._get_nested(self._config, key)

    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.DEFAULT):
        """
        Set a configuration value at runtime.

        Note: This doesn't persist to files.

        Args:
            key: Dot-notation key
            value: Value to set
            source: Source of the configuration value
        """
        # Wrap in ConfigValue
        if not isinstance(value, ConfigValue):
            value = ConfigValue(value=value, source=source)

        with self._lock:
            self._set_nested(self._config, key, value)

        # Notify listeners of the change
        self._notify_change()

    def on_change(self, callback: Callable[[dict], None]):
        """
        Register a callback for configuration changes.

        The callback receives the entire new config dict.
        """
        self._change_callbacks.append(callback)

    def validate(self) -> bool:
        """
        Validate current configuration against schema.

        Returns:
            True if valid

        Raises:
            ConfigValidationError if invalid
        """
        if not self.schema:
            return True

        with self._lock:
            # Unwrap ConfigValues for validation
            unwrapped_config = self._unwrap_values(self._config)
            errors = self.schema.validate(unwrapped_config)

        if errors:
            raise ConfigValidationError(errors)

        return True

    def reload(self):
        """Manually reload all configuration files"""
        with self._lock:
            self._config = {}

            for path in self._config_files:
                if path.exists():
                    config = self._read_file(path)
                    wrapped_config = self._wrap_values(config, ConfigSource.FILE)
                    self._deep_merge(self._config, wrapped_config)

        # Apply defaults from schema
        if self.schema:
            with self._lock:
                unwrapped = self._unwrap_values(self._config)
                defaults_applied = self.schema.apply_defaults(unwrapped)
                # Wrap the defaults back
                self._config = self._wrap_values(defaults_applied, ConfigSource.DEFAULT)

        self.validate()
        self._notify_change()
        logger.info("Configuration reloaded")

    def _on_file_changed(self, path: Path):
        """Callback when a watched file changes"""
        logger.info(f"Config file changed: {path}")

        try:
            self.reload()
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")

    def _notify_change(self):
        """Notify all registered callbacks of config change"""
        config_copy = self.get_all()

        for callback in self._change_callbacks:
            try:
                callback(config_copy)
            except Exception as e:
                logger.error(f"Error in config change callback: {e}")

    @staticmethod
    def _read_file(path: Path) -> dict[str, Any]:
        """Read and parse a config file"""
        with open(path, encoding="utf-8") as f:
            content = f.read()

        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        elif path.suffix == ".json":
            return json.loads(content)
        else:
            raise ValueError(f"Unsupported config file format: {path.suffix}")

    def _deep_merge(self, base: dict, override: dict):
        """Recursively merge override into base, handling ConfigValue objects"""
        for key, value in override.items():
            # If both are dicts and neither is wrapped in ConfigValue, merge recursively
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
                and not isinstance(base[key], ConfigValue)
                and not isinstance(value, ConfigValue)
            ):
                self._deep_merge(base[key], value)
            else:
                # Override: later sources win
                base[key] = value

    def _wrap_values(self, data: Any, source: ConfigSource) -> Any:
        """
        Recursively wrap all leaf values in ConfigValue objects.

        Args:
            data: Data to wrap (dict, list, or primitive)
            source: Source of the configuration

        Returns:
            Data structure with wrapped leaf values
        """
        if isinstance(data, dict):
            return {key: self._wrap_values(value, source) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._wrap_values(item, source) for item in data]
        else:
            # Leaf value - wrap it
            return ConfigValue(value=data, source=source)

    def _unwrap_values(self, data: Any) -> Any:
        """
        Recursively unwrap ConfigValue objects to get plain values.

        Args:
            data: Data to unwrap (dict, list, ConfigValue, or primitive)

        Returns:
            Plain data structure without ConfigValue wrappers
        """
        if isinstance(data, ConfigValue):
            # Unwrap the value and recursively process it
            return self._unwrap_values(data.value)
        elif isinstance(data, dict):
            return {key: self._unwrap_values(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._unwrap_values(item) for item in data]
        else:
            return data

    @staticmethod
    def _get_nested(config: dict, key: str) -> Any:
        """Get a nested value using dot notation"""
        parts = key.split(".")
        value = config

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None

        return value

    @staticmethod
    def _set_nested(config: dict, key: str, value: Any):
        """Set a nested value using dot notation"""
        parts = key.split(".")
        current = config

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def close(self):
        """Stop file watching and cleanup"""
        self._watcher.stop()
