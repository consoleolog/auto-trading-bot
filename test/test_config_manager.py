import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.config.config_core import ConfigSchema, ConfigSource, ConfigValidationError, ConfigValue
from src.config.config_manager import ConfigManager


@pytest.fixture
def manager():
    """기본 ConfigManager 인스턴스를 생성하고, 테스트 후 정리한다."""
    cm = ConfigManager()
    yield cm
    cm.close()


@pytest.fixture
def schema():
    """테스트용 ConfigSchema 를 생성한다."""
    s = ConfigSchema()
    s.require("host", str)
    s.require("port", int, min_value=1, max_value=65535)
    s.optional("debug", bool, default=False)
    return s


@pytest.fixture
def manager_with_schema(schema):
    """스키마가 설정된 ConfigManager 인스턴스를 생성한다."""
    cm = ConfigManager(schema=schema)
    yield cm
    cm.close()


@pytest.fixture
def json_file(tmp_path: Path) -> Path:
    """테스트용 JSON 설정 파일을 생성한다."""
    f = tmp_path / "config.json"
    f.write_text(json.dumps({"host": "localhost", "port": 8080}), encoding="utf-8")
    return f


@pytest.fixture
def yaml_file(tmp_path: Path) -> Path:
    """테스트용 YAML 설정 파일을 생성한다."""
    f = tmp_path / "config.yaml"
    f.write_text(yaml.dump({"host": "localhost", "port": 8080}), encoding="utf-8")
    return f


class TestInit:
    def test_default_schema_is_none(self, manager: ConfigManager):
        """기본 schema 는 None 이다."""
        assert manager.schema is None

    def test_custom_schema(self, manager_with_schema: ConfigManager, schema: ConfigSchema):
        """사용자 지정 schema 가 올바르게 설정된다."""
        assert manager_with_schema.schema is schema

    def test_initial_config_is_empty(self, manager: ConfigManager):
        """초기 설정은 빈 dict 이다."""
        assert manager._config == {}

    def test_initial_change_callbacks_empty(self, manager: ConfigManager):
        """초기 change_callbacks 는 비어 있다."""
        assert manager._change_callbacks == []

    def test_initial_config_files_empty(self, manager: ConfigManager):
        """초기 config_files 는 비어 있다."""
        assert manager._config_files == []


class TestLoadFile:
    def test_load_json_file(self, manager: ConfigManager, json_file: Path):
        """JSON 파일을 로드할 수 있다."""
        manager.load_file(str(json_file), watch=False)

        assert manager.get("host") == "localhost"
        assert manager.get("port") == 8080

    def test_load_yaml_file(self, manager: ConfigManager, yaml_file: Path):
        """YAML 파일을 로드할 수 있다."""
        manager.load_file(str(yaml_file), watch=False)

        assert manager.get("host") == "localhost"
        assert manager.get("port") == 8080

    def test_missing_required_file_raises_error(self, manager: ConfigManager, tmp_path: Path):
        """required=True 일 때 파일이 없으면 FileNotFoundError 가 발생한다."""
        with pytest.raises(FileNotFoundError):
            manager.load_file(str(tmp_path / "missing.json"), required=True)

    def test_missing_optional_file_no_error(self, manager: ConfigManager, tmp_path: Path):
        """required=False 일 때 파일이 없어도 에러가 발생하지 않는다."""
        manager.load_file(str(tmp_path / "missing.json"), required=False)

    def test_unsupported_format_raises_error(self, manager: ConfigManager, tmp_path: Path):
        """지원하지 않는 파일 형식은 ValueError 가 발생한다."""
        f = tmp_path / "config.txt"
        f.write_text("key=value")

        with pytest.raises(ValueError, match="Unsupported"):
            manager.load_file(str(f), watch=False)

    def test_file_added_to_config_files(self, manager: ConfigManager, json_file: Path):
        """로드한 파일 경로가 _config_files 에 추가된다."""
        manager.load_file(str(json_file), watch=False)

        assert json_file.resolve() in manager._config_files

    def test_merge_multiple_files(self, manager: ConfigManager, tmp_path: Path):
        """여러 파일을 로드하면 설정이 병합된다."""
        f1 = tmp_path / "base.json"
        f1.write_text(json.dumps({"host": "base", "port": 80}), encoding="utf-8")

        f2 = tmp_path / "override.json"
        f2.write_text(json.dumps({"host": "override"}), encoding="utf-8")

        manager.load_file(str(f1), watch=False)
        manager.load_file(str(f2), watch=False)

        assert manager.get("host") == "override"
        assert manager.get("port") == 80

    def test_values_wrapped_with_file_source(self, manager: ConfigManager, json_file: Path):
        """파일에서 로드한 값은 FILE 소스로 래핑된다."""
        manager.load_file(str(json_file), watch=False)

        cv = manager.get_with_source("host")

        assert isinstance(cv, ConfigValue)
        assert cv.source == ConfigSource.FILE


class TestLoadEnv:
    def test_load_with_mapping(self, manager: ConfigManager):
        """매핑을 사용하여 환경변수를 로드할 수 있다."""
        with patch.dict(os.environ, {"MY_HOST": "envhost"}):
            manager.load_env(mapping={"MY_HOST": "host"})

        assert manager.get("host") == "envhost"

    def test_load_with_prefix(self, manager: ConfigManager):
        """접두사를 사용하여 환경변수를 로드할 수 있다."""
        with patch.dict(os.environ, {"APP_HOST": "envhost"}, clear=False):
            manager.load_env(prefix="APP_")

        assert manager.get("host") == "envhost"

    def test_env_json_value_parsed(self, manager: ConfigManager):
        """JSON 형식의 환경변수 값이 파싱된다."""
        with patch.dict(os.environ, {"PORT": "8080"}):
            manager.load_env(mapping={"PORT": "port"})

        assert manager.get("port") == 8080

    def test_env_string_value_kept(self, manager: ConfigManager):
        """JSON 이 아닌 문자열 값은 그대로 유지된다."""
        with patch.dict(os.environ, {"HOST": "localhost"}):
            manager.load_env(mapping={"HOST": "host"})

        assert manager.get("host") == "localhost"

    def test_env_values_have_environment_source(self, manager: ConfigManager):
        """환경변수에서 로드한 값은 ENVIRONMENT 소스로 래핑된다."""
        with patch.dict(os.environ, {"HOST": "envhost"}):
            manager.load_env(mapping={"HOST": "host"})

        cv = manager.get_with_source("host")

        assert isinstance(cv, ConfigValue)
        assert cv.source == ConfigSource.ENVIRONMENT

    def test_missing_env_var_skipped(self, manager: ConfigManager):
        """존재하지 않는 환경변수는 무시된다."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NONEXISTENT", None)
            manager.load_env(mapping={"NONEXISTENT": "key"})

        assert manager.get("key") is None

    def test_prefix_converts_to_dot_notation(self, manager: ConfigManager):
        """접두사 방식에서 밑줄이 dot notation 으로 변환된다."""
        with patch.dict(os.environ, {"APP_DATABASE_HOST": "dbhost"}, clear=False):
            manager.load_env(prefix="APP_")

        assert manager.get("database.host") == "dbhost"


class TestGet:
    def test_get_existing_key(self, manager: ConfigManager):
        """존재하는 키의 값을 반환한다."""
        manager.set("host", "localhost")

        assert manager.get("host") == "localhost"

    def test_get_missing_key_returns_default(self, manager: ConfigManager):
        """존재하지 않는 키는 default 를 반환한다."""
        assert manager.get("missing", "fallback") == "fallback"

    def test_get_missing_key_returns_none_by_default(self, manager: ConfigManager):
        """default 미지정 시 None 을 반환한다."""
        assert manager.get("missing") is None

    def test_get_nested_key(self, manager: ConfigManager):
        """중첩된 키를 dot notation 으로 접근할 수 있다."""
        manager.set("database.host", "localhost")

        assert manager.get("database.host") == "localhost"

    def test_get_dict_unwraps_all_values(self, manager: ConfigManager, json_file: Path):
        """dict 를 반환할 때 모든 ConfigValue 가 언래핑된다."""
        manager.load_file(str(json_file), watch=False)

        result = manager.get_all()

        assert isinstance(result["host"], str)
        assert isinstance(result["port"], int)


class TestGetWithSource:
    def test_returns_config_value(self, manager: ConfigManager):
        """ConfigValue 객체를 반환한다."""
        manager.set("host", "localhost", source=ConfigSource.FILE)

        result = manager.get_with_source("host")

        assert isinstance(result, ConfigValue)
        assert result.value == "localhost"
        assert result.source == ConfigSource.FILE

    def test_missing_key_returns_none(self, manager: ConfigManager):
        """존재하지 않는 키는 None 을 반환한다."""
        assert manager.get_with_source("missing") is None


class TestSet:
    def test_set_value(self, manager: ConfigManager):
        """값을 설정할 수 있다."""
        manager.set("key", "value")

        assert manager.get("key") == "value"

    def test_set_with_default_source(self, manager: ConfigManager):
        """기본 소스는 DEFAULT 이다."""
        manager.set("key", "value")

        cv = manager.get_with_source("key")

        assert cv.source == ConfigSource.DEFAULT

    def test_set_with_custom_source(self, manager: ConfigManager):
        """사용자 지정 소스를 설정할 수 있다."""
        manager.set("key", "value", source=ConfigSource.REMOTE)

        cv = manager.get_with_source("key")

        assert cv.source == ConfigSource.REMOTE

    def test_set_nested_key(self, manager: ConfigManager):
        """중첩 키를 설정할 수 있다."""
        manager.set("a.b.c", 42)

        assert manager.get("a.b.c") == 42

    def test_set_triggers_change_callbacks(self, manager: ConfigManager):
        """값 설정 시 change 콜백이 호출된다."""
        callback = MagicMock()
        manager.on_change(callback)

        manager.set("key", "value")

        callback.assert_called_once()

    def test_set_overwrites_existing(self, manager: ConfigManager):
        """기존 값을 덮어쓸 수 있다."""
        manager.set("key", "old")
        manager.set("key", "new")

        assert manager.get("key") == "new"


class TestOnChange:
    def test_registers_callback(self, manager: ConfigManager):
        """콜백이 등록된다."""
        callback = MagicMock()
        manager.on_change(callback)

        assert callback in manager._change_callbacks

    def test_callback_receives_config_copy(self, manager: ConfigManager):
        """콜백이 전체 설정의 복사본을 받는다."""
        received = {}

        def capture(config):
            received.update(config)

        manager.on_change(capture)
        manager.set("host", "localhost")

        assert received["host"] == "localhost"

    def test_callback_error_does_not_crash(self, manager: ConfigManager):
        """콜백 에러가 발생해도 매니저가 중단되지 않는다."""
        bad_callback = MagicMock(side_effect=RuntimeError("boom"))
        manager.on_change(bad_callback)

        manager.set("key", "value")

        assert manager.get("key") == "value"


class TestValidate:
    def test_no_schema_returns_true(self, manager: ConfigManager):
        """스키마가 없으면 True 를 반환한다."""
        assert manager.validate() is True

    def test_valid_config_returns_true(self, manager_with_schema: ConfigManager):
        """유효한 설정은 True 를 반환한다."""
        manager_with_schema.set("host", "localhost")
        manager_with_schema.set("port", 8080)

        assert manager_with_schema.validate() is True

    def test_invalid_config_raises_error(self, manager_with_schema: ConfigManager):
        """유효하지 않은 설정은 ConfigValidationError 가 발생한다."""
        with pytest.raises(ConfigValidationError):
            manager_with_schema.validate()


class TestReload:
    def test_reload_rereads_files(self, manager: ConfigManager, tmp_path: Path):
        """reload 시 파일을 다시 읽는다."""
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"host": "old"}), encoding="utf-8")
        manager.load_file(str(f), watch=False)

        f.write_text(json.dumps({"host": "new"}), encoding="utf-8")
        manager.reload()

        assert manager.get("host") == "new"

    def test_reload_clears_config_before_rereading(self, manager: ConfigManager, tmp_path: Path):
        """reload 시 기존 설정을 초기화한 후 다시 읽는다."""
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"host": "orig", "extra": "val"}), encoding="utf-8")
        manager.load_file(str(f), watch=False)

        f.write_text(json.dumps({"host": "new"}), encoding="utf-8")
        manager.reload()

        assert manager.get("host") == "new"
        assert manager.get("extra") is None

    def test_reload_triggers_change_callbacks(self, manager: ConfigManager, json_file: Path):
        """reload 시 change 콜백이 호출된다."""
        manager.load_file(str(json_file), watch=False)
        callback = MagicMock()
        manager.on_change(callback)

        manager.reload()

        callback.assert_called_once()

    def test_reload_applies_schema_defaults(self, tmp_path: Path, schema: ConfigSchema):
        """reload 시 스키마 기본값이 적용된다."""
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"host": "localhost", "port": 8080}), encoding="utf-8")

        cm = ConfigManager(schema=schema)
        cm.load_file(str(f), watch=False)
        cm.reload()

        assert cm.get("debug") is False
        cm.close()

    def test_reload_skips_deleted_files(self, manager: ConfigManager, tmp_path: Path):
        """삭제된 파일은 reload 시 무시된다."""
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"host": "val"}), encoding="utf-8")
        manager.load_file(str(f), watch=False)

        f.unlink()
        manager.reload()

        assert manager.get("host") is None


class TestDeepMerge:
    def test_nested_dicts_merged(self, manager: ConfigManager):
        """중첩 dict 가 재귀적으로 병합된다."""
        base = {"db": {"host": "a", "port": 1}}
        override = {"db": {"host": "b"}}

        manager._deep_merge(base, override)

        assert base["db"]["host"] == "b"
        assert base["db"]["port"] == 1

    def test_non_dict_overrides(self, manager: ConfigManager):
        """dict 가 아닌 값은 덮어쓴다."""
        base = {"key": "old"}
        override = {"key": "new"}

        manager._deep_merge(base, override)

        assert base["key"] == "new"


class TestWrapUnwrap:
    def test_wrap_leaf_values(self, manager: ConfigManager):
        """leaf 값을 ConfigValue 로 래핑한다."""
        result = manager._wrap_values({"k": "v"}, ConfigSource.FILE)

        assert isinstance(result["k"], ConfigValue)
        assert result["k"].value == "v"
        assert result["k"].source == ConfigSource.FILE

    def test_wrap_nested_dict(self, manager: ConfigManager):
        """중첩 dict 의 leaf 값만 래핑한다."""
        result = manager._wrap_values({"a": {"b": 1}}, ConfigSource.FILE)

        assert isinstance(result["a"]["b"], ConfigValue)

    def test_wrap_list(self, manager: ConfigManager):
        """리스트 내 값도 래핑한다."""
        result = manager._wrap_values({"items": [1, 2]}, ConfigSource.DEFAULT)

        assert isinstance(result["items"][0], ConfigValue)
        assert result["items"][0].value == 1

    def test_unwrap_config_value(self, manager: ConfigManager):
        """ConfigValue 를 언래핑한다."""
        data = {"k": ConfigValue(value="v", source=ConfigSource.FILE)}

        result = manager._unwrap_values(data)

        assert result["k"] == "v"

    def test_unwrap_nested(self, manager: ConfigManager):
        """중첩 구조의 ConfigValue 를 모두 언래핑한다."""
        data = {
            "a": {
                "b": ConfigValue(value=42, source=ConfigSource.FILE),
            },
        }

        result = manager._unwrap_values(data)

        assert result["a"]["b"] == 42


class TestClose:
    def test_close_stops_watcher(self, manager: ConfigManager):
        """close 호출 시 watcher 가 중지된다."""
        manager._watcher = MagicMock()

        manager.close()

        manager._watcher.stop.assert_called_once()
