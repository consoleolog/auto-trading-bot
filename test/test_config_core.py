from datetime import datetime, timezone

from src.config.config_core import ConfigSchema, ConfigSource, ConfigValidationError, ConfigValue


class TestConfigSource:
    def test_file_value(self):
        """FILE 소스의 값은 'file' 이다."""
        assert ConfigSource.FILE.value == "file"

    def test_environment_value(self):
        """ENVIRONMENT 소스의 값은 'environment' 이다."""
        assert ConfigSource.ENVIRONMENT.value == "environment"

    def test_remote_value(self):
        """REMOTE 소스의 값은 'remote' 이다."""
        assert ConfigSource.REMOTE.value == "remote"

    def test_default_value(self):
        """DEFAULT 소스의 값은 'default' 이다."""
        assert ConfigSource.DEFAULT.value == "default"


class TestConfigValue:
    def test_stores_value_and_source(self):
        """value 와 source 가 올바르게 저장된다."""
        cv = ConfigValue(value="localhost", source=ConfigSource.FILE)

        assert cv.value == "localhost"
        assert cv.source == ConfigSource.FILE

    def test_updated_at_defaults_to_utc_now(self):
        """updated_at 기본값은 현재 UTC 시간이다."""
        cv = ConfigValue(value=1, source=ConfigSource.DEFAULT)

        assert cv.updated_at.tzinfo == timezone.utc

    def test_custom_updated_at(self):
        """사용자 지정 updated_at 이 올바르게 설정된다."""
        custom_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        cv = ConfigValue(value="v", source=ConfigSource.REMOTE, updated_at=custom_time)

        assert cv.updated_at == custom_time

    def test_generic_type_with_int(self):
        """int 타입 value 를 저장할 수 있다."""
        cv = ConfigValue(value=8080, source=ConfigSource.ENVIRONMENT)

        assert cv.value == 8080

    def test_generic_type_with_dict(self):
        """dict 타입 value 를 저장할 수 있다."""
        cv = ConfigValue(value={"key": "val"}, source=ConfigSource.FILE)

        assert cv.value == {"key": "val"}

    def test_repr(self):
        """__repr__ 이 value, source, updated_at 을 포함한다."""
        cv = ConfigValue(value="test", source=ConfigSource.DEFAULT)
        result = repr(cv)

        assert "test" in result
        assert "ConfigSource.DEFAULT" in result


class TestConfigValidationError:
    def test_stores_errors_list(self):
        """errors 리스트가 올바르게 저장된다."""
        errors = ["error1", "error2"]
        exc = ConfigValidationError(errors)

        assert exc.errors == errors

    def test_message_contains_all_errors(self):
        """에러 메시지에 모든 에러가 포함된다."""
        errors = ["missing host", "invalid port"]
        exc = ConfigValidationError(errors)

        assert "missing host" in str(exc)
        assert "invalid port" in str(exc)

    def test_is_exception(self):
        """ConfigValidationError 는 Exception 의 하위 클래스이다."""
        exc = ConfigValidationError(["err"])

        assert isinstance(exc, Exception)


class TestConfigSchemaRequire:
    def test_require_registers_key(self):
        """require 로 등록한 키가 _required 에 저장된다."""
        schema = ConfigSchema()
        schema.require("host", str)

        assert "host" in schema._required

    def test_require_stores_type(self):
        """require 로 등록한 타입이 올바르게 저장된다."""
        schema = ConfigSchema()
        schema.require("port", int)

        assert schema._required["port"]["type"] is int

    def test_require_stores_min_max(self):
        """require 로 등록한 min, max 값이 올바르게 저장된다."""
        schema = ConfigSchema()
        schema.require("port", int, min_value=1, max_value=65535)

        assert schema._required["port"]["min"] == 1
        assert schema._required["port"]["max"] == 65535

    def test_require_stores_choices(self):
        """require 로 등록한 choices 가 올바르게 저장된다."""
        schema = ConfigSchema()
        schema.require("env", str, choices=["dev", "prod"])

        assert schema._required["env"]["choices"] == ["dev", "prod"]


class TestConfigSchemaOptional:
    def test_optional_registers_key(self):
        """optional 로 등록한 키가 _optional 에 저장된다."""
        schema = ConfigSchema()
        schema.optional("debug", bool, default=False)

        assert "debug" in schema._optional

    def test_optional_stores_default(self):
        """optional 로 등록한 default 값이 올바르게 저장된다."""
        schema = ConfigSchema()
        schema.optional("timeout", int, default=30)

        assert schema._optional["timeout"]["default"] == 30


class TestConfigSchemaValidate:
    def test_valid_config_returns_empty_errors(self):
        """유효한 config 는 빈 에러 리스트를 반환한다."""
        schema = ConfigSchema()
        schema.require("host", str)
        schema.require("port", int)

        errors = schema.validate({"host": "localhost", "port": 8080})

        assert errors == []

    def test_missing_required_key_returns_error(self):
        """필수 키가 없으면 에러를 반환한다."""
        schema = ConfigSchema()
        schema.require("host", str)

        errors = schema.validate({})

        assert len(errors) == 1
        assert "Missing required config: host" in errors[0]

    def test_wrong_type_returns_error(self):
        """타입이 맞지 않으면 에러를 반환한다."""
        schema = ConfigSchema()
        schema.require("port", int)

        errors = schema.validate({"port": "not_a_number"})

        assert len(errors) == 1
        assert "expected int" in errors[0]
        assert "got str" in errors[0]

    def test_value_below_min_returns_error(self):
        """값이 min 보다 작으면 에러를 반환한다."""
        schema = ConfigSchema()
        schema.require("port", int, min_value=1)

        errors = schema.validate({"port": 0})

        assert len(errors) == 1
        assert "below minimum" in errors[0]

    def test_value_above_max_returns_error(self):
        """값이 max 보다 크면 에러를 반환한다."""
        schema = ConfigSchema()
        schema.require("port", int, max_value=65535)

        errors = schema.validate({"port": 70000})

        assert len(errors) == 1
        assert "above maximum" in errors[0]

    def test_value_not_in_choices_returns_error(self):
        """값이 choices 에 포함되지 않으면 에러를 반환한다."""
        schema = ConfigSchema()
        schema.require("env", str, choices=["dev", "prod"])

        errors = schema.validate({"env": "staging"})

        assert len(errors) == 1
        assert "not in" in errors[0]

    def test_value_in_choices_passes(self):
        """값이 choices 에 포함되면 에러가 없다."""
        schema = ConfigSchema()
        schema.require("env", str, choices=["dev", "prod"])

        errors = schema.validate({"env": "prod"})

        assert errors == []

    def test_optional_key_missing_no_error(self):
        """optional 키가 없어도 에러가 발생하지 않는다."""
        schema = ConfigSchema()
        schema.optional("debug", bool, default=False)

        errors = schema.validate({})

        assert errors == []

    def test_optional_key_present_with_wrong_type_returns_error(self):
        """optional 키가 있지만 타입이 다르면 에러를 반환한다."""
        schema = ConfigSchema()
        schema.optional("debug", bool)

        errors = schema.validate({"debug": "yes"})

        assert len(errors) == 1
        assert "expected bool" in errors[0]

    def test_multiple_errors_collected(self):
        """여러 에러가 동시에 수집된다."""
        schema = ConfigSchema()
        schema.require("host", str)
        schema.require("port", int)

        errors = schema.validate({})

        assert len(errors) == 2


class TestConfigSchemaNestedKeys:
    def test_nested_key_validation(self):
        """dot notation 으로 중첩 키를 검증할 수 있다."""
        schema = ConfigSchema()
        schema.require("database.host", str)

        errors = schema.validate({"database": {"host": "localhost"}})

        assert errors == []

    def test_missing_nested_key_returns_error(self):
        """중첩 키가 없으면 에러를 반환한다."""
        schema = ConfigSchema()
        schema.require("database.host", str)

        errors = schema.validate({"database": {}})

        assert len(errors) == 1
        assert "database.host" in errors[0]

    def test_missing_parent_key_returns_error(self):
        """부모 키가 없어도 에러를 반환한다."""
        schema = ConfigSchema()
        schema.require("database.host", str)

        errors = schema.validate({})

        assert len(errors) == 1

    def test_deeply_nested_key(self):
        """3단계 이상 중첩된 키도 검증할 수 있다."""
        schema = ConfigSchema()
        schema.require("a.b.c", int)

        errors = schema.validate({"a": {"b": {"c": 42}}})

        assert errors == []


class TestConfigSchemaApplyDefaults:
    def test_applies_default_for_missing_key(self):
        """누락된 optional 키에 기본값을 적용한다."""
        schema = ConfigSchema()
        schema.optional("debug", bool, default=False)

        result = schema.apply_defaults({})

        assert result["debug"] is False

    def test_does_not_overwrite_existing_value(self):
        """이미 존재하는 값은 덮어쓰지 않는다."""
        schema = ConfigSchema()
        schema.optional("debug", bool, default=False)

        result = schema.apply_defaults({"debug": True})

        assert result["debug"] is True

    def test_applies_nested_default(self):
        """중첩 키에도 기본값을 적용한다."""
        schema = ConfigSchema()
        schema.optional("server.timeout", int, default=30)

        result = schema.apply_defaults({})

        assert result["server"]["timeout"] == 30

    def test_does_not_modify_original_config(self):
        """원본 config dict 를 변경하지 않는다."""
        schema = ConfigSchema()
        schema.optional("debug", bool, default=False)
        original = {}

        schema.apply_defaults(original)

        assert "debug" not in original

    def test_skips_none_default(self):
        """default 가 None 인 경우 적용하지 않는다."""
        schema = ConfigSchema()
        schema.optional("debug", bool, default=None)

        result = schema.apply_defaults({})

        assert "debug" not in result
