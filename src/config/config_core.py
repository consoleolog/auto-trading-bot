from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class ConfigSource(Enum):
    """
    Config 소스의 출처

    Attributes:
        FILE: 파일
        ENVIRONMENT: 환경 변수
        REMOTE: 원격 (DB, etc..)
        DEFAULT: 기본값
    """

    FILE = "file"
    ENVIRONMENT = "environment"
    REMOTE = "remote"
    DEFAULT = "default"


@dataclass
class ConfigValue(Generic[T]):
    value: T
    source: ConfigSource
    updated_at: datetime = field(default=datetime.now(tz=timezone.utc))

    def __repr__(self):
        return f"ConfigValue({self.value!r}, {self.source!r}, {self.updated_at!r})"


class ConfigValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Config validation failed: {', '.join(errors)}")


class ConfigSchema:
    """
    Define expected configuration structure and validation rules.

    Example:
        schema = ConfigSchema()
        schema.require("database.host", str)
        schema.require("database.port", int, min_value=1, max_value=65535)
        schema.optional("debug", bool, default=False)
    """

    def __init__(self):
        self._required: dict[str, dict] = {}
        self._optional: dict[str, dict] = {}

    def require(
        self,
        key: str,
        value_type: type,
        min_value: Any | None = None,
        max_value: Any | None = None,
        choices: list | None = None,
    ):
        """Define a required configuration key"""
        self._required[key] = {"type": value_type, "min": min_value, "max": max_value, "choices": choices}

    def optional(
        self,
        key: str,
        value_type: type,
        default: Any = None,
        min_value: Any | None = None,
        max_value: Any | None = None,
    ):
        """Define an optional configuration key with default"""
        self._optional[key] = {"type": value_type, "default": default, "min": min_value, "max": max_value}

    def validate(self, config: dict[str, Any]) -> list[str]:
        """
        Validate configuration against schema.

        Returns list of validation errors (empty if valid).
        """
        errors = []

        # Check required keys
        for key, rules in self._required.items():
            value = self._get_nested(config, key)

            if value is None:
                errors.append(f"Missing required config: {key}")
                continue

            errors.extend(self._validate_value(key, value, rules))

        # Check optional keys (if present)
        for key, rules in self._optional.items():
            value = self._get_nested(config, key)

            if value is not None:
                errors.extend(self._validate_value(key, value, rules))

        return errors

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
    def _validate_value(key: str, value: Any, rules: dict) -> list[str]:
        """Validate a single value against its rules"""
        errors = []

        # Type check
        if not isinstance(value, rules["type"]):
            errors.append(f"{key}: expected {rules['type'].__name__}, got {type(value).__name__}")
            return errors

        # Range checks for numbers
        if rules.get("min") is not None and value < rules["min"]:
            errors.append(f"{key}: value {value} below minimum {rules['min']}")

        if rules.get("max") is not None and value > rules["max"]:
            errors.append(f"{key}: value {value} above maximum {rules['max']}")

        # Choice validation
        if rules.get("choices") and value not in rules["choices"]:
            errors.append(f"{key}: value {value} not in {rules['choices']}")

        return errors

    def apply_defaults(self, config: dict[str, Any]) -> dict[str, Any]:
        """Apply default values for missing optional keys"""
        result = config.copy()

        for key, rules in self._optional.items():
            if self._get_nested(result, key) is None and rules["default"] is not None:
                self._set_nested(result, key, rules["default"])

        return result

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
