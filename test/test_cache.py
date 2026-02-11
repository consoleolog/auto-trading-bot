from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database.cache import RedisCache


class TestRedisCache:
    @pytest.fixture
    def redis_config(self):
        """Redis 연결 설정을 반환하는 fixture"""
        return {
            "host": "localhost",
            "port": 6379,
            "password": "test_password",
            "db": 0,
        }

    @pytest.fixture
    def redis_config_no_password(self):
        """비밀번호가 없는 Redis 연결 설정을 반환하는 fixture"""
        return {
            "host": "localhost",
            "port": 6379,
            "password": "",
            "db": 0,
        }

    @pytest.fixture
    def cache(self, redis_config):
        """RedisCache 인스턴스를 반환하는 fixture"""
        return RedisCache(**redis_config)

    # ============= __init__ =============

    def test_init_sets_config_properties(self, redis_config):
        """초기화 시 설정 값들이 올바르게 저장된다."""
        cache = RedisCache(**redis_config)

        assert cache.host == redis_config["host"]
        assert cache.port == redis_config["port"]
        assert cache.password == redis_config["password"]
        assert cache.db == redis_config["db"]
        assert cache.redis_client is None
        assert cache.is_connected is False

    # ============= connect =============

    @pytest.mark.asyncio
    async def test_connect_creates_redis_client_with_password(self, cache, redis_config, caplog):
        """비밀번호가 있을 때 Redis 클라이언트를 생성하고 연결한다."""
        with (
            patch("src.database.cache.redis.from_url", new_callable=AsyncMock) as mock_from_url,
            caplog.at_level("INFO"),
        ):
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_client.config_set = AsyncMock()
            mock_from_url.return_value = mock_client

            await cache.connect()

            # Redis URL이 비밀번호 포함하여 올바르게 생성되었는지 확인
            expected_url = f"redis://:{redis_config['password']}@{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
            mock_from_url.assert_awaited_once()
            call_args = mock_from_url.call_args
            assert call_args[0][0] == expected_url
            assert call_args[1]["encoding"] == "utf-8"
            assert call_args[1]["decode_responses"] is False
            assert call_args[1]["socket_keepalive"] is True
            assert call_args[1]["max_connections"] == 50
            assert call_args[1]["health_check_interval"] == 30

            # ping 호출 확인
            mock_client.ping.assert_awaited_once()

            # keyspace 알림 설정 확인
            mock_client.config_set.assert_awaited_once_with("notify-keyspace-events", "Ex")

            # 연결 상태 확인
            assert cache.is_connected is True
            assert cache.redis_client == mock_client

            # 로그 확인
            assert "Successfully connected to" in caplog.text

    @pytest.mark.asyncio
    async def test_connect_creates_redis_client_without_password(self, redis_config_no_password, caplog):
        """비밀번호가 없을 때 Redis 클라이언트를 생성하고 연결한다."""
        cache = RedisCache(**redis_config_no_password)

        with (
            patch("src.database.cache.redis.from_url", new_callable=AsyncMock) as mock_from_url,
            caplog.at_level("INFO"),
        ):
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_client.config_set = AsyncMock()
            mock_from_url.return_value = mock_client

            await cache.connect()

            # Redis URL이 비밀번호 없이 올바르게 생성되었는지 확인
            expected_url = f"redis://{redis_config_no_password['host']}:{redis_config_no_password['port']}/{redis_config_no_password['db']}"
            call_args = mock_from_url.call_args
            assert call_args[0][0] == expected_url

            assert cache.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_handles_connection_failure(self, cache, caplog):
        """Redis 연결 실패 시 예외를 발생시키고 로그를 남긴다."""
        with (
            patch("src.database.cache.redis.from_url", new_callable=AsyncMock) as mock_from_url,
            caplog.at_level("ERROR"),
        ):
            mock_from_url.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await cache.connect()

            assert "Failed to connect to Redis" in caplog.text
            assert cache.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_handles_ping_failure(self, cache, caplog):
        """Redis ping 실패 시 예외를 발생시킨다."""
        with (
            patch("src.database.cache.redis.from_url", new_callable=AsyncMock) as mock_from_url,
            caplog.at_level("ERROR"),
        ):
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=Exception("Ping failed"))
            mock_from_url.return_value = mock_client

            with pytest.raises(Exception, match="Ping failed"):
                await cache.connect()

            assert "Failed to connect to Redis" in caplog.text

    @pytest.mark.asyncio
    async def test_setup_keyspace_notifications_handles_failure(self, cache, caplog):
        """keyspace 알림 설정 실패 시 경고 로그를 남기지만 연결은 성공한다."""
        with (
            patch("src.database.cache.redis.from_url", new_callable=AsyncMock) as mock_from_url,
            caplog.at_level("WARNING"),
        ):
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_client.config_set = AsyncMock(side_effect=Exception("Config failed"))
            mock_from_url.return_value = mock_client

            await cache.connect()

            assert "Could not set keyspace notifications" in caplog.text
            # keyspace 알림 설정 실패해도 연결은 성공
            assert cache.is_connected is True

    # ============= disconnect =============

    @pytest.mark.asyncio
    async def test_disconnect_closes_redis_client(self, cache, caplog):
        """Redis 클라이언트를 닫고 연결 상태를 False로 설정한다."""
        mock_client = AsyncMock()
        cache.redis_client = mock_client
        cache.is_connected = True

        with caplog.at_level("INFO"):
            await cache.disconnect()

        mock_client.close.assert_awaited_once()
        assert cache.is_connected is False
        assert "Disconnected from Redis cache" in caplog.text

    @pytest.mark.asyncio
    async def test_disconnect_when_no_client(self, cache):
        """Redis 클라이언트가 없을 때 disconnect를 호출해도 에러가 발생하지 않는다."""
        cache.redis_client = None

        # 예외가 발생하지 않아야 함
        await cache.disconnect()

        assert cache.is_connected is False

    # ============= _setup_keyspace_notifications =============

    @pytest.mark.asyncio
    async def test_setup_keyspace_notifications_success(self, cache):
        """keyspace 알림을 성공적으로 설정한다."""
        mock_client = AsyncMock()
        mock_client.config_set = AsyncMock()
        cache.redis_client = mock_client

        await cache._setup_keyspace_notifications()

        mock_client.config_set.assert_awaited_once_with("notify-keyspace-events", "Ex")

    @pytest.mark.asyncio
    async def test_setup_keyspace_notifications_failure(self, cache, caplog):
        """keyspace 알림 설정 실패 시 경고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.config_set = AsyncMock(side_effect=Exception("Permission denied"))
        cache.redis_client = mock_client

        with caplog.at_level("WARNING"):
            await cache._setup_keyspace_notifications()

        assert "Could not set keyspace notifications" in caplog.text
        assert "Permission denied" in caplog.text

    # ============= get =============

    @pytest.mark.asyncio
    async def test_get_returns_json_value(self, cache):
        """JSON으로 저장된 값을 가져온다."""
        import json

        mock_client = AsyncMock()
        test_data = {"name": "test", "value": 123}
        mock_client.get = AsyncMock(return_value=json.dumps(test_data).encode())
        cache.redis_client = mock_client

        result = await cache.get("test_key")

        mock_client.get.assert_awaited_once_with("test_key")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_returns_pickle_value(self, cache):
        """pickle로 저장된 복잡한 객체를 가져온다."""
        import pickle

        mock_client = AsyncMock()
        test_data = {"complex": object()}
        pickled_data = pickle.dumps(test_data)
        mock_client.get = AsyncMock(return_value=pickled_data)
        cache.redis_client = mock_client

        result = await cache.get("test_key")

        mock_client.get.assert_awaited_once_with("test_key")
        # pickle로 직렬화된 데이터는 동일한 타입이어야 함
        assert isinstance(result, dict)
        assert "complex" in result

    @pytest.mark.asyncio
    async def test_get_returns_string_value(self, cache):
        """문자열로 저장된 값을 가져온다."""
        mock_client = AsyncMock()
        test_data = b"simple string value"
        mock_client.get = AsyncMock(return_value=test_data)
        cache.redis_client = mock_client

        result = await cache.get("test_key")

        mock_client.get.assert_awaited_once_with("test_key")
        assert result == "simple string value"

    @pytest.mark.asyncio
    async def test_get_returns_none_when_key_not_found(self, cache):
        """키가 존재하지 않을 때 None을 반환한다."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        cache.redis_client = mock_client

        result = await cache.get("nonexistent_key")

        mock_client.get.assert_awaited_once_with("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 None을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.get("test_key")

        assert result is None
        assert "Cache get error for key test_key" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_get_handles_json_decode_fallback_to_pickle(self, cache):
        """JSON 디코딩 실패 시 pickle로 폴백한다."""
        import pickle

        mock_client = AsyncMock()
        # JSON이 아닌 pickle 데이터
        test_data = [1, 2, 3]
        pickled_data = pickle.dumps(test_data)
        mock_client.get = AsyncMock(return_value=pickled_data)
        cache.redis_client = mock_client

        result = await cache.get("test_key")

        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_handles_all_decode_failures_fallback_to_string(self, cache):
        """JSON과 pickle 디코딩 모두 실패 시 문자열로 폴백한다."""
        mock_client = AsyncMock()
        # JSON도 아니고 pickle도 아닌 순수 바이트 데이터
        test_data = b"\x00\x01\x02invalid"
        mock_client.get = AsyncMock(return_value=test_data)
        cache.redis_client = mock_client

        result = await cache.get("test_key")

        # 디코딩 실패 시에도 문자열로 변환 시도
        assert isinstance(result, str)

    # ============= get_with_options =============

    @pytest.mark.asyncio
    async def test_get_with_options_returns_json_value(self, cache):
        """JSON으로 저장된 값을 가져온다."""
        import json

        mock_client = AsyncMock()
        test_data = {"name": "test", "value": 123}
        mock_client.get = AsyncMock(return_value=json.dumps(test_data).encode())
        cache.redis_client = mock_client

        result = await cache.get_with_options("test_key")

        mock_client.get.assert_awaited_once_with("test_key")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_with_options_returns_default_when_key_not_found(self, cache):
        """키가 존재하지 않을 때 기본값을 반환한다."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        cache.redis_client = mock_client

        default_value = {"default": "value"}
        result = await cache.get_with_options("nonexistent_key", default=default_value)

        mock_client.get.assert_awaited_once_with("nonexistent_key")
        assert result == default_value

    @pytest.mark.asyncio
    async def test_get_with_options_returns_none_default_when_not_provided(self, cache):
        """기본값을 제공하지 않으면 None을 반환한다."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        cache.redis_client = mock_client

        result = await cache.get_with_options("nonexistent_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_options_with_decode_json_false(self, cache):
        """decode_json=False일 때 JSON 디코딩을 시도하지 않는다."""
        mock_client = AsyncMock()
        test_data = b"raw bytes data"
        mock_client.get = AsyncMock(return_value=test_data)
        cache.redis_client = mock_client

        result = await cache.get_with_options("test_key", decode_json=False)

        mock_client.get.assert_awaited_once_with("test_key")
        assert result == "raw bytes data"

    @pytest.mark.asyncio
    async def test_get_with_options_handles_pickle_value(self, cache):
        """pickle로 저장된 값을 가져온다."""
        import pickle

        mock_client = AsyncMock()
        test_data = [1, 2, 3]
        pickled_data = pickle.dumps(test_data)
        mock_client.get = AsyncMock(return_value=pickled_data)
        cache.redis_client = mock_client

        result = await cache.get_with_options("test_key")

        mock_client.get.assert_awaited_once_with("test_key")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_with_options_handles_string_value(self, cache):
        """문자열로 저장된 값을 가져온다."""
        mock_client = AsyncMock()
        test_data = b"simple string"
        mock_client.get = AsyncMock(return_value=test_data)
        cache.redis_client = mock_client

        result = await cache.get_with_options("test_key")

        assert result == "simple string"

    @pytest.mark.asyncio
    async def test_get_with_options_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 기본값을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        default_value = "error_default"
        with caplog.at_level("ERROR"):
            result = await cache.get_with_options("test_key", default=default_value)

        assert result == default_value
        assert "Cache get error for key test_key" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_get_with_options_decode_json_false_returns_raw_bytes(self, cache):
        """decode_json=False일 때 JSON 데이터도 원본 문자열로 반환한다."""
        import json

        mock_client = AsyncMock()
        test_data = {"name": "test"}
        json_bytes = json.dumps(test_data).encode()
        mock_client.get = AsyncMock(return_value=json_bytes)
        cache.redis_client = mock_client

        result = await cache.get_with_options("test_key", decode_json=False)

        # JSON 디코딩 없이 문자열로만 변환
        assert result == json.dumps(test_data)

    # ============= set =============

    @pytest.mark.asyncio
    async def test_set_dict_value_with_ttl(self, cache):
        """dict 값을 TTL과 함께 설정한다."""
        import json

        mock_client = AsyncMock()
        mock_client.setex = AsyncMock()
        cache.redis_client = mock_client

        test_data = {"name": "test", "value": 123}
        ttl = 300

        result = await cache.set("test_key", test_data, ttl=ttl)

        mock_client.setex.assert_awaited_once_with("test_key", ttl, json.dumps(test_data))
        assert result is True

    @pytest.mark.asyncio
    async def test_set_list_value_with_ttl(self, cache):
        """list 값을 TTL과 함께 설정한다."""
        import json

        mock_client = AsyncMock()
        mock_client.setex = AsyncMock()
        cache.redis_client = mock_client

        test_data = [1, 2, 3]
        ttl = 600

        result = await cache.set("test_key", test_data, ttl=ttl)

        mock_client.setex.assert_awaited_once_with("test_key", ttl, json.dumps(test_data))
        assert result is True

    @pytest.mark.asyncio
    async def test_set_string_value_with_ttl(self, cache):
        """문자열 값을 TTL과 함께 설정한다."""
        mock_client = AsyncMock()
        mock_client.setex = AsyncMock()
        cache.redis_client = mock_client

        test_data = "simple string"
        ttl = 300

        result = await cache.set("test_key", test_data, ttl=ttl)

        mock_client.setex.assert_awaited_once_with("test_key", ttl, test_data.encode("utf-8"))
        assert result is True

    @pytest.mark.asyncio
    async def test_set_int_value_with_ttl(self, cache):
        """정수 값을 TTL과 함께 설정한다."""
        mock_client = AsyncMock()
        mock_client.setex = AsyncMock()
        cache.redis_client = mock_client

        test_data = 12345
        ttl = 300

        result = await cache.set("test_key", test_data, ttl=ttl)

        mock_client.setex.assert_awaited_once_with("test_key", ttl, str(test_data).encode("utf-8"))
        assert result is True

    @pytest.mark.asyncio
    async def test_set_float_value_with_ttl(self, cache):
        """실수 값을 TTL과 함께 설정한다."""
        mock_client = AsyncMock()
        mock_client.setex = AsyncMock()
        cache.redis_client = mock_client

        test_data = 123.45
        ttl = 300

        result = await cache.set("test_key", test_data, ttl=ttl)

        mock_client.setex.assert_awaited_once_with("test_key", ttl, str(test_data).encode("utf-8"))
        assert result is True

    @pytest.mark.asyncio
    async def test_set_complex_object_with_pickle(self, cache):
        """복잡한 객체를 pickle로 직렬화하여 설정한다."""
        import pickle
        from datetime import datetime, timezone

        mock_client = AsyncMock()
        mock_client.setex = AsyncMock()
        cache.redis_client = mock_client

        # pickle 가능한 복잡한 객체 사용 (datetime)
        test_data = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ttl = 300

        result = await cache.set("test_key", test_data, ttl=ttl)

        # pickle로 직렬화되었는지 확인
        call_args = mock_client.setex.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == ttl
        # pickle 데이터인지 확인 (unpickle 가능한지)
        unpickled = pickle.loads(call_args[0][2])
        assert unpickled == test_data
        assert result is True

    @pytest.mark.asyncio
    async def test_set_without_expiration_when_ttl_is_zero(self, cache):
        """TTL이 0인 경우 만료 없이 설정한다."""
        import json

        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        cache.redis_client = mock_client

        test_data = {"name": "test"}
        ttl = 0

        result = await cache.set("test_key", test_data, ttl=ttl)

        mock_client.set.assert_awaited_once_with("test_key", json.dumps(test_data))
        assert result is True

    @pytest.mark.asyncio
    async def test_set_without_expiration_when_ttl_is_negative(self, cache):
        """TTL이 음수인 경우 만료 없이 설정한다."""
        import json

        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        cache.redis_client = mock_client

        test_data = {"name": "test"}
        ttl = -1

        result = await cache.set("test_key", test_data, ttl=ttl)

        mock_client.set.assert_awaited_once_with("test_key", json.dumps(test_data))
        assert result is True

    @pytest.mark.asyncio
    async def test_set_uses_default_ttl(self, cache):
        """TTL을 제공하지 않으면 기본값(300)을 사용한다."""
        import json

        mock_client = AsyncMock()
        mock_client.setex = AsyncMock()
        cache.redis_client = mock_client

        test_data = {"name": "test"}

        result = await cache.set("test_key", test_data)

        mock_client.setex.assert_awaited_once_with("test_key", 300, json.dumps(test_data))
        assert result is True

    @pytest.mark.asyncio
    async def test_set_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 False를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.setex = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        test_data = {"name": "test"}

        with caplog.at_level("ERROR"):
            result = await cache.set("test_key", test_data)

        assert result is False
        assert "Cache set error for key test_key" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= delete =============

    @pytest.mark.asyncio
    async def test_delete_single_key(self, cache):
        """단일 키를 삭제한다."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock()
        cache.redis_client = mock_client

        result = await cache.delete("test_key")

        mock_client.delete.assert_awaited_once_with("test_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_multiple_keys(self, cache):
        """여러 키를 한 번에 삭제한다."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock()
        cache.redis_client = mock_client

        keys = ["key1", "key2", "key3"]
        result = await cache.delete(keys)

        mock_client.delete.assert_awaited_once_with("key1", "key2", "key3")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_empty_list(self, cache):
        """빈 리스트로 삭제를 호출해도 성공한다."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock()
        cache.redis_client = mock_client

        result = await cache.delete([])

        mock_client.delete.assert_awaited_once_with()
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_handles_redis_error_with_single_key(self, cache, caplog):
        """단일 키 삭제 시 Redis 오류가 발생하면 False를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.delete("test_key")

        assert result is False
        assert "Cache delete error" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_delete_handles_redis_error_with_multiple_keys(self, cache, caplog):
        """여러 키 삭제 시 Redis 오류가 발생하면 False를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.delete(["key1", "key2"])

        assert result is False
        assert "Cache delete error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= exists =============

    @pytest.mark.asyncio
    async def test_exists_returns_true_when_key_exists(self, cache):
        """키가 존재할 때 True를 반환한다."""
        mock_client = AsyncMock()
        mock_client.exists = AsyncMock(return_value=1)  # Redis exists는 존재하는 키 개수를 반환
        cache.redis_client = mock_client

        result = await cache.exists("test_key")

        mock_client.exists.assert_awaited_once_with("test_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_key_not_exists(self, cache):
        """키가 존재하지 않을 때 False를 반환한다."""
        mock_client = AsyncMock()
        mock_client.exists = AsyncMock(return_value=0)
        cache.redis_client = mock_client

        result = await cache.exists("nonexistent_key")

        mock_client.exists.assert_awaited_once_with("nonexistent_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 False를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.exists = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.exists("test_key")

        assert result is False
        assert "Cache exists error for key test_key" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_exists_converts_non_zero_to_true(self, cache):
        """Redis exists가 0이 아닌 값을 반환하면 True로 변환한다."""
        mock_client = AsyncMock()
        mock_client.exists = AsyncMock(return_value=5)  # 여러 키가 존재할 경우
        cache.redis_client = mock_client

        result = await cache.exists("test_key")

        assert result is True

    # ============= invalidate =============

    @pytest.mark.asyncio
    async def test_invalidate_deletes_matching_keys(self, cache):
        """패턴과 일치하는 키들을 삭제한다."""
        mock_client = AsyncMock()

        # scan_iter가 비동기 이터레이터를 반환하도록 모킹
        async def mock_scan_iter(match):
            for key in [b"user:1", b"user:2", b"user:3"]:
                yield key

        mock_client.scan_iter = mock_scan_iter
        mock_client.delete = AsyncMock(return_value=3)
        cache.redis_client = mock_client

        result = await cache.invalidate("user:*")

        mock_client.delete.assert_awaited_once_with(b"user:1", b"user:2", b"user:3")
        assert result == 3

    @pytest.mark.asyncio
    async def test_invalidate_returns_zero_when_no_keys_match(self, cache):
        """패턴과 일치하는 키가 없을 때 0을 반환한다."""
        mock_client = AsyncMock()

        # 빈 이터레이터 반환
        async def mock_scan_iter(match):
            return
            yield  # 이 줄은 실행되지 않지만 제너레이터로 만들기 위해 필요

        mock_client.scan_iter = mock_scan_iter
        mock_client.delete = AsyncMock()
        cache.redis_client = mock_client

        result = await cache.invalidate("nonexistent:*")

        # delete가 호출되지 않아야 함
        mock_client.delete.assert_not_awaited()
        assert result == 0

    @pytest.mark.asyncio
    async def test_invalidate_handles_single_matching_key(self, cache):
        """단일 키만 일치할 때 해당 키를 삭제한다."""
        mock_client = AsyncMock()

        async def mock_scan_iter(match):
            yield b"session:abc123"

        mock_client.scan_iter = mock_scan_iter
        mock_client.delete = AsyncMock(return_value=1)
        cache.redis_client = mock_client

        result = await cache.invalidate("session:*")

        mock_client.delete.assert_awaited_once_with(b"session:abc123")
        assert result == 1

    @pytest.mark.asyncio
    async def test_invalidate_handles_redis_error_during_scan(self, cache, caplog):
        """scan_iter 중 Redis 오류 발생 시 0을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()

        async def mock_scan_iter(match):
            raise Exception("Redis connection error")
            yield  # 제너레이터로 만들기 위해 필요

        mock_client.scan_iter = mock_scan_iter
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.invalidate("test:*")

        assert result == 0
        assert "Cache invalidate error for pattern test:*" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_invalidate_handles_redis_error_during_delete(self, cache, caplog):
        """delete 중 Redis 오류 발생 시 0을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()

        async def mock_scan_iter(match):
            yield b"test:1"
            yield b"test:2"

        mock_client.scan_iter = mock_scan_iter
        mock_client.delete = AsyncMock(side_effect=Exception("Redis delete error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.invalidate("test:*")

        assert result == 0
        assert "Cache invalidate error for pattern test:*" in caplog.text
        assert "Redis delete error" in caplog.text

    @pytest.mark.asyncio
    async def test_invalidate_with_complex_pattern(self, cache):
        """복잡한 패턴으로도 올바르게 작동한다."""
        mock_client = AsyncMock()

        async def mock_scan_iter(match):
            # 패턴이 올바르게 전달되었는지 확인
            assert match == "cache:data:*:temp"
            yield b"cache:data:123:temp"
            yield b"cache:data:456:temp"

        mock_client.scan_iter = mock_scan_iter
        mock_client.delete = AsyncMock(return_value=2)
        cache.redis_client = mock_client

        result = await cache.invalidate("cache:data:*:temp")

        assert result == 2

    # ============= get_many =============

    @pytest.mark.asyncio
    async def test_get_many_returns_multiple_values(self, cache):
        """여러 키의 값을 한 번에 가져온다."""
        import json

        mock_client = AsyncMock()
        test_data = {
            "key1": {"name": "test1"},
            "key2": {"name": "test2"},
            "key3": {"name": "test3"},
        }
        mock_values = [
            json.dumps(test_data["key1"]).encode(),
            json.dumps(test_data["key2"]).encode(),
            json.dumps(test_data["key3"]).encode(),
        ]
        mock_client.mget = AsyncMock(return_value=mock_values)
        cache.redis_client = mock_client

        result = await cache.get_many(["key1", "key2", "key3"])

        mock_client.mget.assert_awaited_once_with(["key1", "key2", "key3"])
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_many_excludes_nonexistent_keys(self, cache):
        """존재하지 않는 키는 결과에 포함되지 않는다."""
        import json

        mock_client = AsyncMock()
        # key2는 None (존재하지 않음)
        mock_values = [json.dumps({"name": "test1"}).encode(), None, json.dumps({"name": "test3"}).encode()]
        mock_client.mget = AsyncMock(return_value=mock_values)
        cache.redis_client = mock_client

        result = await cache.get_many(["key1", "key2", "key3"])

        assert "key1" in result
        assert "key2" not in result
        assert "key3" in result
        assert result["key1"] == {"name": "test1"}
        assert result["key3"] == {"name": "test3"}

    @pytest.mark.asyncio
    async def test_get_many_returns_string_values(self, cache):
        """문자열 값도 올바르게 가져온다."""
        mock_client = AsyncMock()
        mock_values = [b"value1", b"value2", b"value3"]
        mock_client.mget = AsyncMock(return_value=mock_values)
        cache.redis_client = mock_client

        result = await cache.get_many(["key1", "key2", "key3"])

        assert result == {"key1": "value1", "key2": "value2", "key3": "value3"}

    @pytest.mark.asyncio
    async def test_get_many_returns_empty_dict_when_all_keys_missing(self, cache):
        """모든 키가 존재하지 않으면 빈 딕셔너리를 반환한다."""
        mock_client = AsyncMock()
        mock_values = [None, None, None]
        mock_client.mget = AsyncMock(return_value=mock_values)
        cache.redis_client = mock_client

        result = await cache.get_many(["key1", "key2", "key3"])

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_many_handles_empty_keys_list(self, cache):
        """빈 키 리스트로 호출해도 빈 딕셔너리를 반환한다."""
        mock_client = AsyncMock()
        mock_client.mget = AsyncMock(return_value=[])
        cache.redis_client = mock_client

        result = await cache.get_many([])

        mock_client.mget.assert_awaited_once_with([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_many_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 빈 딕셔너리를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.mget = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.get_many(["key1", "key2"])

        assert result == {}
        assert "Cache get_many error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= set_many =============

    @pytest.mark.asyncio
    async def test_set_many_sets_multiple_values_without_ttl(self, cache):
        """TTL 없이 여러 값을 설정한다."""

        mock_client = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.set = AsyncMock()
        mock_pipe.execute = AsyncMock()

        # pipeline()이 컨텍스트 매니저를 반환하도록 설정
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_client.pipeline = MagicMock(return_value=mock_pipe)

        cache.redis_client = mock_client

        test_data = {
            "key1": {"name": "test1"},
            "key2": {"name": "test2"},
            "key3": "simple_value",
        }

        result = await cache.set_many(test_data)

        assert mock_pipe.set.await_count == 3
        mock_pipe.execute.assert_awaited_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_set_many_sets_multiple_values_with_ttl(self, cache):
        """TTL과 함께 여러 값을 설정한다."""

        mock_client = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.setex = AsyncMock()
        mock_pipe.execute = AsyncMock()

        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_client.pipeline = MagicMock(return_value=mock_pipe)

        cache.redis_client = mock_client

        test_data = {
            "key1": {"name": "test1"},
            "key2": {"name": "test2"},
        }
        ttl = 300

        result = await cache.set_many(test_data, ttl=ttl)

        assert mock_pipe.setex.await_count == 2
        mock_pipe.execute.assert_awaited_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_set_many_handles_empty_mapping(self, cache):
        """빈 딕셔너리로 호출해도 성공한다."""
        mock_client = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock()

        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_client.pipeline = MagicMock(return_value=mock_pipe)

        cache.redis_client = mock_client

        result = await cache.set_many({})

        mock_pipe.execute.assert_awaited_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_set_many_serializes_dict_as_json(self, cache):
        """딕셔너리 값을 JSON으로 직렬화한다."""
        import json

        mock_client = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.set = AsyncMock()
        mock_pipe.execute = AsyncMock()

        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_client.pipeline = MagicMock(return_value=mock_pipe)

        cache.redis_client = mock_client

        test_data = {"key1": {"name": "test", "value": 123}}

        result = await cache.set_many(test_data)

        # set이 JSON 직렬화된 값으로 호출되었는지 확인
        call_args = mock_pipe.set.call_args_list[0]
        assert call_args[0][0] == "key1"
        assert call_args[0][1] == json.dumps({"name": "test", "value": 123})
        assert result is True

    @pytest.mark.asyncio
    async def test_set_many_serializes_list_as_json(self, cache):
        """리스트 값을 JSON으로 직렬화한다."""
        import json

        mock_client = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.set = AsyncMock()
        mock_pipe.execute = AsyncMock()

        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_client.pipeline = MagicMock(return_value=mock_pipe)

        cache.redis_client = mock_client

        test_data = {"key1": [1, 2, 3]}

        result = await cache.set_many(test_data)

        call_args = mock_pipe.set.call_args_list[0]
        assert call_args[0][0] == "key1"
        assert call_args[0][1] == json.dumps([1, 2, 3])
        assert result is True

    @pytest.mark.asyncio
    async def test_set_many_serializes_string_as_bytes(self, cache):
        """문자열 값을 바이트로 직렬화한다."""
        mock_client = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.set = AsyncMock()
        mock_pipe.execute = AsyncMock()

        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_client.pipeline = MagicMock(return_value=mock_pipe)

        cache.redis_client = mock_client

        test_data = {"key1": "simple_string"}

        result = await cache.set_many(test_data)

        call_args = mock_pipe.set.call_args_list[0]
        assert call_args[0][0] == "key1"
        assert call_args[0][1] == b"simple_string"
        assert result is True

    @pytest.mark.asyncio
    async def test_set_many_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 False를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.set = AsyncMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis connection error"))

        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_client.pipeline = MagicMock(return_value=mock_pipe)

        cache.redis_client = mock_client

        test_data = {"key1": "value1"}

        with caplog.at_level("ERROR"):
            result = await cache.set_many(test_data)

        assert result is False
        assert "Cache set_many error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= hget =============

    @pytest.mark.asyncio
    async def test_hget_returns_json_value(self, cache):
        """해시에서 JSON 값을 가져온다."""
        import json

        mock_client = AsyncMock()
        test_value = {"name": "test", "value": 123}
        mock_client.hget = AsyncMock(return_value=json.dumps(test_value).encode())
        cache.redis_client = mock_client

        result = await cache.hget("hash_name", "field_key")

        mock_client.hget.assert_awaited_once_with("hash_name", "field_key")
        assert result == test_value

    @pytest.mark.asyncio
    async def test_hget_returns_string_value(self, cache):
        """해시에서 문자열 값을 가져온다."""
        mock_client = AsyncMock()
        mock_client.hget = AsyncMock(return_value=b"simple_value")
        cache.redis_client = mock_client

        result = await cache.hget("hash_name", "field_key")

        mock_client.hget.assert_awaited_once_with("hash_name", "field_key")
        assert result == "simple_value"

    @pytest.mark.asyncio
    async def test_hget_returns_none_when_field_not_exists(self, cache):
        """필드가 존재하지 않을 때 None을 반환한다."""
        mock_client = AsyncMock()
        mock_client.hget = AsyncMock(return_value=None)
        cache.redis_client = mock_client

        result = await cache.hget("hash_name", "nonexistent_field")

        mock_client.hget.assert_awaited_once_with("hash_name", "nonexistent_field")
        assert result is None

    @pytest.mark.asyncio
    async def test_hget_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 None을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.hget = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.hget("hash_name", "field_key")

        assert result is None
        assert "Cache hget error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= hset =============

    @pytest.mark.asyncio
    async def test_hset_sets_dict_value(self, cache):
        """딕셔너리 값을 해시에 설정한다."""
        import json

        mock_client = AsyncMock()
        mock_client.hset = AsyncMock()
        cache.redis_client = mock_client

        test_value = {"name": "test", "value": 123}

        result = await cache.hset("hash_name", "field_key", test_value)

        mock_client.hset.assert_awaited_once_with("hash_name", "field_key", json.dumps(test_value))
        assert result is True

    @pytest.mark.asyncio
    async def test_hset_sets_list_value(self, cache):
        """리스트 값을 해시에 설정한다."""
        import json

        mock_client = AsyncMock()
        mock_client.hset = AsyncMock()
        cache.redis_client = mock_client

        test_value = [1, 2, 3]

        result = await cache.hset("hash_name", "field_key", test_value)

        mock_client.hset.assert_awaited_once_with("hash_name", "field_key", json.dumps(test_value))
        assert result is True

    @pytest.mark.asyncio
    async def test_hset_sets_string_value(self, cache):
        """문자열 값을 해시에 설정한다."""
        mock_client = AsyncMock()
        mock_client.hset = AsyncMock()
        cache.redis_client = mock_client

        test_value = "simple_string"

        result = await cache.hset("hash_name", "field_key", test_value)

        mock_client.hset.assert_awaited_once_with("hash_name", "field_key", test_value.encode("utf-8"))
        assert result is True

    @pytest.mark.asyncio
    async def test_hset_sets_int_value(self, cache):
        """정수 값을 해시에 설정한다."""
        mock_client = AsyncMock()
        mock_client.hset = AsyncMock()
        cache.redis_client = mock_client

        test_value = 12345

        result = await cache.hset("hash_name", "field_key", test_value)

        mock_client.hset.assert_awaited_once_with("hash_name", "field_key", str(test_value).encode("utf-8"))
        assert result is True

    @pytest.mark.asyncio
    async def test_hset_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 False를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.hset = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.hset("hash_name", "field_key", "value")

        assert result is False
        assert "Cache hset error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= hgetall =============

    @pytest.mark.asyncio
    async def test_hgetall_returns_all_fields(self, cache):
        """해시의 모든 필드를 가져온다."""
        import json

        mock_client = AsyncMock()
        test_data = {
            b"field1": json.dumps({"name": "test1"}).encode(),
            b"field2": json.dumps({"name": "test2"}).encode(),
            b"field3": b"simple_value",
        }
        mock_client.hgetall = AsyncMock(return_value=test_data)
        cache.redis_client = mock_client

        result = await cache.hgetall("hash_name")

        mock_client.hgetall.assert_awaited_once_with("hash_name")
        assert result == {
            "field1": {"name": "test1"},
            "field2": {"name": "test2"},
            "field3": "simple_value",
        }

    @pytest.mark.asyncio
    async def test_hgetall_returns_empty_dict_when_hash_not_exists(self, cache):
        """해시가 존재하지 않을 때 빈 딕셔너리를 반환한다."""
        mock_client = AsyncMock()
        mock_client.hgetall = AsyncMock(return_value={})
        cache.redis_client = mock_client

        result = await cache.hgetall("nonexistent_hash")

        mock_client.hgetall.assert_awaited_once_with("nonexistent_hash")
        assert result == {}

    @pytest.mark.asyncio
    async def test_hgetall_handles_string_keys(self, cache):
        """문자열 키도 올바르게 처리한다."""
        import json

        mock_client = AsyncMock()
        # 키가 이미 문자열인 경우
        test_data = {
            "field1": json.dumps({"name": "test1"}).encode(),
            "field2": b"simple_value",
        }
        mock_client.hgetall = AsyncMock(return_value=test_data)
        cache.redis_client = mock_client

        result = await cache.hgetall("hash_name")

        assert result == {"field1": {"name": "test1"}, "field2": "simple_value"}

    @pytest.mark.asyncio
    async def test_hgetall_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 빈 딕셔너리를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.hgetall = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.hgetall("hash_name")

        assert result == {}
        assert "Cache hgetall error" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_hgetall_handles_mixed_json_and_string_values(self, cache):
        """JSON과 문자열 값이 혼합된 경우를 올바르게 처리한다."""
        import json

        mock_client = AsyncMock()
        test_data = {
            b"json_field": json.dumps({"data": "value"}).encode(),
            b"string_field": b"plain_text",
            b"number_as_json": json.dumps(12345).encode(),  # JSON으로 인코딩된 숫자
        }
        mock_client.hgetall = AsyncMock(return_value=test_data)
        cache.redis_client = mock_client

        result = await cache.hgetall("hash_name")

        assert result == {
            "json_field": {"data": "value"},
            "string_field": "plain_text",
            "number_as_json": 12345,  # JSON으로 파싱되면 정수로 변환됨
        }

    # ============= lpush =============

    @pytest.mark.asyncio
    async def test_lpush_adds_dict_value(self, cache):
        """딕셔너리 값을 리스트 왼쪽에 추가한다."""
        import json

        mock_client = AsyncMock()
        mock_client.lpush = AsyncMock(return_value=1)
        cache.redis_client = mock_client

        test_value = {"name": "test", "value": 123}

        result = await cache.lpush("list_key", test_value)

        mock_client.lpush.assert_awaited_once_with("list_key", json.dumps(test_value))
        assert result == 1

    @pytest.mark.asyncio
    async def test_lpush_adds_list_value(self, cache):
        """리스트 값을 리스트 왼쪽에 추가한다."""
        import json

        mock_client = AsyncMock()
        mock_client.lpush = AsyncMock(return_value=2)
        cache.redis_client = mock_client

        test_value = [1, 2, 3]

        result = await cache.lpush("list_key", test_value)

        mock_client.lpush.assert_awaited_once_with("list_key", json.dumps(test_value))
        assert result == 2

    @pytest.mark.asyncio
    async def test_lpush_adds_string_value(self, cache):
        """문자열 값을 리스트 왼쪽에 추가한다."""
        mock_client = AsyncMock()
        mock_client.lpush = AsyncMock(return_value=1)
        cache.redis_client = mock_client

        test_value = "simple_string"

        result = await cache.lpush("list_key", test_value)

        mock_client.lpush.assert_awaited_once_with("list_key", test_value)
        assert result == 1

    @pytest.mark.asyncio
    async def test_lpush_returns_new_list_length(self, cache):
        """lpush는 리스트의 새로운 길이를 반환한다."""
        mock_client = AsyncMock()
        mock_client.lpush = AsyncMock(return_value=5)
        cache.redis_client = mock_client

        result = await cache.lpush("list_key", "value")

        assert result == 5

    @pytest.mark.asyncio
    async def test_lpush_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 0을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.lpush = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.lpush("list_key", "value")

        assert result == 0
        assert "Cache lpush error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= rpop =============

    @pytest.mark.asyncio
    async def test_rpop_returns_json_value(self, cache):
        """리스트 오른쪽에서 JSON 값을 제거하고 반환한다."""
        import json

        mock_client = AsyncMock()
        test_value = {"name": "test", "value": 123}
        mock_client.rpop = AsyncMock(return_value=json.dumps(test_value).encode())
        cache.redis_client = mock_client

        result = await cache.rpop("list_key")

        mock_client.rpop.assert_awaited_once_with("list_key")
        assert result == test_value

    @pytest.mark.asyncio
    async def test_rpop_returns_string_value(self, cache):
        """리스트 오른쪽에서 문자열 값을 제거하고 반환한다."""
        mock_client = AsyncMock()
        mock_client.rpop = AsyncMock(return_value=b"simple_string")
        cache.redis_client = mock_client

        result = await cache.rpop("list_key")

        mock_client.rpop.assert_awaited_once_with("list_key")
        assert result == "simple_string"

    @pytest.mark.asyncio
    async def test_rpop_returns_none_when_list_empty(self, cache):
        """리스트가 비어있을 때 None을 반환한다."""
        mock_client = AsyncMock()
        mock_client.rpop = AsyncMock(return_value=None)
        cache.redis_client = mock_client

        result = await cache.rpop("list_key")

        mock_client.rpop.assert_awaited_once_with("list_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_rpop_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 None을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.rpop = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.rpop("list_key")

        assert result is None
        assert "Cache rpop error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= lrange =============

    @pytest.mark.asyncio
    async def test_lrange_returns_multiple_json_values(self, cache):
        """리스트에서 여러 JSON 값을 가져온다."""
        import json

        mock_client = AsyncMock()
        test_values = [
            {"name": "test1"},
            {"name": "test2"},
            {"name": "test3"},
        ]
        mock_client.lrange = AsyncMock(return_value=[json.dumps(v).encode() for v in test_values])
        cache.redis_client = mock_client

        result = await cache.lrange("list_key", 0, -1)

        mock_client.lrange.assert_awaited_once_with("list_key", 0, -1)
        assert result == test_values

    @pytest.mark.asyncio
    async def test_lrange_returns_string_values(self, cache):
        """리스트에서 여러 문자열 값을 가져온다."""
        mock_client = AsyncMock()
        mock_client.lrange = AsyncMock(return_value=[b"value1", b"value2", b"value3"])
        cache.redis_client = mock_client

        result = await cache.lrange("list_key", 0, 2)

        mock_client.lrange.assert_awaited_once_with("list_key", 0, 2)
        assert result == ["value1", "value2", "value3"]

    @pytest.mark.asyncio
    async def test_lrange_returns_empty_list_when_no_values(self, cache):
        """범위에 값이 없을 때 빈 리스트를 반환한다."""
        mock_client = AsyncMock()
        mock_client.lrange = AsyncMock(return_value=[])
        cache.redis_client = mock_client

        result = await cache.lrange("list_key", 0, -1)

        mock_client.lrange.assert_awaited_once_with("list_key", 0, -1)
        assert result == []

    @pytest.mark.asyncio
    async def test_lrange_with_specific_range(self, cache):
        """특정 범위의 값만 가져온다."""
        import json

        mock_client = AsyncMock()
        test_values = [{"id": 1}, {"id": 2}]
        mock_client.lrange = AsyncMock(return_value=[json.dumps(v).encode() for v in test_values])
        cache.redis_client = mock_client

        result = await cache.lrange("list_key", 1, 2)

        mock_client.lrange.assert_awaited_once_with("list_key", 1, 2)
        assert result == test_values

    @pytest.mark.asyncio
    async def test_lrange_handles_mixed_json_and_string_values(self, cache):
        """JSON과 문자열 값이 혼합된 경우를 올바르게 처리한다."""
        import json

        mock_client = AsyncMock()
        mock_values = [
            json.dumps({"data": "value"}).encode(),
            b"plain_text",
            json.dumps([1, 2, 3]).encode(),
        ]
        mock_client.lrange = AsyncMock(return_value=mock_values)
        cache.redis_client = mock_client

        result = await cache.lrange("list_key", 0, -1)

        assert result == [{"data": "value"}, "plain_text", [1, 2, 3]]

    @pytest.mark.asyncio
    async def test_lrange_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 빈 리스트를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.lrange = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.lrange("list_key", 0, -1)

        assert result == []
        assert "Cache lrange error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= zadd =============

    @pytest.mark.asyncio
    async def test_zadd_adds_single_member(self, cache):
        """정렬된 집합에 단일 멤버를 추가한다."""
        mock_client = AsyncMock()
        mock_client.zadd = AsyncMock(return_value=1)
        cache.redis_client = mock_client

        mapping = {"member1": 100.0}

        result = await cache.zadd("sorted_set_key", mapping)

        mock_client.zadd.assert_awaited_once_with("sorted_set_key", mapping)
        assert result == 1

    @pytest.mark.asyncio
    async def test_zadd_adds_multiple_members(self, cache):
        """정렬된 집합에 여러 멤버를 추가한다."""
        mock_client = AsyncMock()
        mock_client.zadd = AsyncMock(return_value=3)
        cache.redis_client = mock_client

        mapping = {"member1": 100.0, "member2": 200.0, "member3": 300.0}

        result = await cache.zadd("sorted_set_key", mapping)

        mock_client.zadd.assert_awaited_once_with("sorted_set_key", mapping)
        assert result == 3

    @pytest.mark.asyncio
    async def test_zadd_updates_existing_member_score(self, cache):
        """기존 멤버의 점수를 업데이트할 때 0을 반환한다."""
        mock_client = AsyncMock()
        mock_client.zadd = AsyncMock(return_value=0)  # 기존 멤버 업데이트 시
        cache.redis_client = mock_client

        mapping = {"existing_member": 150.0}

        result = await cache.zadd("sorted_set_key", mapping)

        assert result == 0

    @pytest.mark.asyncio
    async def test_zadd_handles_empty_mapping(self, cache):
        """빈 딕셔너리로 호출 시 0을 반환한다."""
        mock_client = AsyncMock()
        mock_client.zadd = AsyncMock(return_value=0)
        cache.redis_client = mock_client

        result = await cache.zadd("sorted_set_key", {})

        mock_client.zadd.assert_awaited_once_with("sorted_set_key", {})
        assert result == 0

    @pytest.mark.asyncio
    async def test_zadd_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 0을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.zadd = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.zadd("sorted_set_key", {"member": 100.0})

        assert result == 0
        assert "Cache zadd error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= zrange =============

    @pytest.mark.asyncio
    async def test_zrange_returns_members_without_scores(self, cache):
        """점수 없이 멤버만 반환한다."""
        mock_client = AsyncMock()
        mock_client.zrange = AsyncMock(return_value=[b"member1", b"member2", b"member3"])
        cache.redis_client = mock_client

        result = await cache.zrange("sorted_set_key", 0, -1, withscores=False)

        mock_client.zrange.assert_awaited_once_with("sorted_set_key", 0, -1, withscores=False)
        assert result == [b"member1", b"member2", b"member3"]

    @pytest.mark.asyncio
    async def test_zrange_returns_members_with_scores(self, cache):
        """점수와 함께 멤버를 반환한다."""
        mock_client = AsyncMock()
        mock_client.zrange = AsyncMock(return_value=[(b"member1", 100.0), (b"member2", 200.0), (b"member3", 300.0)])
        cache.redis_client = mock_client

        result = await cache.zrange("sorted_set_key", 0, -1, withscores=True)

        mock_client.zrange.assert_awaited_once_with("sorted_set_key", 0, -1, withscores=True)
        assert result == [(b"member1", 100.0), (b"member2", 200.0), (b"member3", 300.0)]

    @pytest.mark.asyncio
    async def test_zrange_with_specific_range(self, cache):
        """특정 범위의 멤버만 가져온다."""
        mock_client = AsyncMock()
        mock_client.zrange = AsyncMock(return_value=[b"member2", b"member3"])
        cache.redis_client = mock_client

        result = await cache.zrange("sorted_set_key", 1, 2)

        mock_client.zrange.assert_awaited_once_with("sorted_set_key", 1, 2, withscores=False)
        assert result == [b"member2", b"member3"]

    @pytest.mark.asyncio
    async def test_zrange_returns_empty_list_when_no_members(self, cache):
        """멤버가 없을 때 빈 리스트를 반환한다."""
        mock_client = AsyncMock()
        mock_client.zrange = AsyncMock(return_value=[])
        cache.redis_client = mock_client

        result = await cache.zrange("sorted_set_key", 0, -1)

        mock_client.zrange.assert_awaited_once_with("sorted_set_key", 0, -1, withscores=False)
        assert result == []

    @pytest.mark.asyncio
    async def test_zrange_default_withscores_is_false(self, cache):
        """withscores의 기본값은 False이다."""
        mock_client = AsyncMock()
        mock_client.zrange = AsyncMock(return_value=[b"member1"])
        cache.redis_client = mock_client

        result = await cache.zrange("sorted_set_key", 0, 0)

        # withscores=False가 기본값으로 전달되어야 함
        mock_client.zrange.assert_awaited_once_with("sorted_set_key", 0, 0, withscores=False)
        assert result == [b"member1"]

    @pytest.mark.asyncio
    async def test_zrange_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 빈 리스트를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.zrange = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.zrange("sorted_set_key", 0, -1)

        assert result == []
        assert "Cache zrange error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= expire =============

    @pytest.mark.asyncio
    async def test_expire_sets_expiration_time(self, cache):
        """키의 만료 시간을 설정한다."""
        mock_client = AsyncMock()
        mock_client.expire = AsyncMock(return_value=True)
        cache.redis_client = mock_client

        result = await cache.expire("test_key", 300)

        mock_client.expire.assert_awaited_once_with("test_key", 300)
        assert result is True

    @pytest.mark.asyncio
    async def test_expire_returns_false_when_key_not_exists(self, cache):
        """키가 존재하지 않을 때 False를 반환한다."""
        mock_client = AsyncMock()
        mock_client.expire = AsyncMock(return_value=False)
        cache.redis_client = mock_client

        result = await cache.expire("nonexistent_key", 300)

        mock_client.expire.assert_awaited_once_with("nonexistent_key", 300)
        assert result is False

    @pytest.mark.asyncio
    async def test_expire_with_different_ttl_values(self, cache):
        """다양한 TTL 값으로 만료 시간을 설정한다."""
        mock_client = AsyncMock()
        mock_client.expire = AsyncMock(return_value=True)
        cache.redis_client = mock_client

        # 60초
        result1 = await cache.expire("key1", 60)
        assert result1 is True

        # 3600초 (1시간)
        result2 = await cache.expire("key2", 3600)
        assert result2 is True

        # 1초
        result3 = await cache.expire("key3", 1)
        assert result3 is True

        assert mock_client.expire.await_count == 3

    @pytest.mark.asyncio
    async def test_expire_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 False를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.expire = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.expire("test_key", 300)

        assert result is False
        assert "Cache expire error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= ttl =============

    @pytest.mark.asyncio
    async def test_ttl_returns_remaining_time(self, cache):
        """키의 남은 TTL을 반환한다."""
        mock_client = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=300)
        cache.redis_client = mock_client

        result = await cache.ttl("test_key")

        mock_client.ttl.assert_awaited_once_with("test_key")
        assert result == 300

    @pytest.mark.asyncio
    async def test_ttl_returns_minus_2_when_key_not_exists(self, cache):
        """키가 존재하지 않을 때 -2를 반환한다."""
        mock_client = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=-2)
        cache.redis_client = mock_client

        result = await cache.ttl("nonexistent_key")

        mock_client.ttl.assert_awaited_once_with("nonexistent_key")
        assert result == -2

    @pytest.mark.asyncio
    async def test_ttl_returns_minus_1_when_no_expiration(self, cache):
        """키에 만료 시간이 없을 때 -1을 반환한다."""
        mock_client = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=-1)
        cache.redis_client = mock_client

        result = await cache.ttl("persistent_key")

        mock_client.ttl.assert_awaited_once_with("persistent_key")
        assert result == -1

    @pytest.mark.asyncio
    async def test_ttl_returns_various_remaining_times(self, cache):
        """다양한 남은 시간 값을 반환한다."""
        mock_client = AsyncMock()
        cache.redis_client = mock_client

        # 10초 남음
        mock_client.ttl = AsyncMock(return_value=10)
        result1 = await cache.ttl("key1")
        assert result1 == 10

        # 3600초 (1시간) 남음
        mock_client.ttl = AsyncMock(return_value=3600)
        result2 = await cache.ttl("key2")
        assert result2 == 3600

        # 1초 남음
        mock_client.ttl = AsyncMock(return_value=1)
        result3 = await cache.ttl("key3")
        assert result3 == 1

    @pytest.mark.asyncio
    async def test_ttl_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 -1을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.ttl = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.ttl("test_key")

        assert result == -1
        assert "Cache ttl error" in caplog.text
        assert "Redis connection error" in caplog.text

    # ============= get_statistics =============

    @pytest.mark.asyncio
    async def test_get_statistics_returns_all_metrics(self, cache):
        """캐시 통계 정보를 모두 반환한다."""
        mock_client = AsyncMock()
        mock_info = {
            "used_memory": 1024 * 1024 * 10,  # 10MB in bytes
            "connected_clients": 5,
            "total_commands_processed": 1000,
            "keyspace_hits": 800,
            "keyspace_misses": 200,
            "evicted_keys": 10,
            "expired_keys": 50,
        }
        mock_client.info = AsyncMock(return_value=mock_info)
        cache.redis_client = mock_client

        result = await cache.get_statistics()

        mock_client.info.assert_awaited_once()
        assert result["used_memory_mb"] == 10.0
        assert result["connected_clients"] == 5
        assert result["total_commands_processed"] == 1000
        assert result["keyspace_hits"] == 800
        assert result["keyspace_misses"] == 200
        assert result["hit_rate"] == 80.0  # 800/(800+200) * 100
        assert result["evicted_keys"] == 10
        assert result["expired_keys"] == 50

    @pytest.mark.asyncio
    async def test_get_statistics_calculates_hit_rate_correctly(self, cache):
        """캐시 히트율을 정확하게 계산한다."""
        mock_client = AsyncMock()
        cache.redis_client = mock_client

        # 100% 히트율
        mock_client.info = AsyncMock(return_value={"keyspace_hits": 100, "keyspace_misses": 0})
        result = await cache.get_statistics()
        assert result["hit_rate"] == 100.0

        # 50% 히트율
        mock_client.info = AsyncMock(return_value={"keyspace_hits": 50, "keyspace_misses": 50})
        result = await cache.get_statistics()
        assert result["hit_rate"] == 50.0

        # 0% 히트율
        mock_client.info = AsyncMock(return_value={"keyspace_hits": 0, "keyspace_misses": 100})
        result = await cache.get_statistics()
        assert result["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_statistics_handles_zero_hits_and_misses(self, cache):
        """히트와 미스가 모두 0일 때 0% 반환한다."""
        mock_client = AsyncMock()
        mock_client.info = AsyncMock(return_value={"keyspace_hits": 0, "keyspace_misses": 0})
        cache.redis_client = mock_client

        result = await cache.get_statistics()

        assert result["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_statistics_handles_missing_fields(self, cache):
        """일부 필드가 누락되어도 기본값 0을 사용한다."""
        mock_client = AsyncMock()
        mock_client.info = AsyncMock(
            return_value={
                "keyspace_hits": 100,
                # 다른 필드들은 누락
            }
        )
        cache.redis_client = mock_client

        result = await cache.get_statistics()

        assert result["used_memory_mb"] == 0.0
        assert result["connected_clients"] == 0
        assert result["total_commands_processed"] == 0
        assert result["keyspace_hits"] == 100
        assert result["keyspace_misses"] == 0
        assert result["evicted_keys"] == 0
        assert result["expired_keys"] == 0

    @pytest.mark.asyncio
    async def test_get_statistics_converts_memory_to_mb(self, cache):
        """메모리를 바이트에서 MB로 변환한다."""
        mock_client = AsyncMock()
        cache.redis_client = mock_client

        # 1MB = 1024 * 1024 bytes
        mock_client.info = AsyncMock(return_value={"used_memory": 1024 * 1024})
        result = await cache.get_statistics()
        assert result["used_memory_mb"] == 1.0

        # 100MB
        mock_client.info = AsyncMock(return_value={"used_memory": 1024 * 1024 * 100})
        result = await cache.get_statistics()
        assert result["used_memory_mb"] == 100.0

        # 0.5MB
        mock_client.info = AsyncMock(return_value={"used_memory": 1024 * 512})
        result = await cache.get_statistics()
        assert result["used_memory_mb"] == 0.5

    @pytest.mark.asyncio
    async def test_get_statistics_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 빈 딕셔너리를 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.info = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.get_statistics()

        assert result == {}
        assert "Failed to get cache stats" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_get_statistics_returns_all_expected_keys(self, cache):
        """반환된 통계에 모든 예상 키가 포함되어 있다."""
        mock_client = AsyncMock()
        mock_client.info = AsyncMock(return_value={})
        cache.redis_client = mock_client

        result = await cache.get_statistics()

        expected_keys = {
            "used_memory_mb",
            "connected_clients",
            "total_commands_processed",
            "keyspace_hits",
            "keyspace_misses",
            "hit_rate",
            "evicted_keys",
            "expired_keys",
        }
        assert set(result.keys()) == expected_keys

    # ============= publish =============

    @pytest.mark.asyncio
    async def test_publish_sends_dict_message(self, cache):
        """딕셔너리 메시지를 채널에 발행한다."""
        import json

        mock_client = AsyncMock()
        mock_client.publish = AsyncMock(return_value=3)  # 3명의 구독자가 수신
        cache.redis_client = mock_client

        test_message = {"event": "trade", "symbol": "BTC", "price": 50000}

        result = await cache.publish("trade_channel", test_message)

        mock_client.publish.assert_awaited_once_with("trade_channel", json.dumps(test_message))
        assert result == 3

    @pytest.mark.asyncio
    async def test_publish_sends_list_message(self, cache):
        """리스트 메시지를 채널에 발행한다."""
        import json

        mock_client = AsyncMock()
        mock_client.publish = AsyncMock(return_value=2)
        cache.redis_client = mock_client

        test_message = [1, 2, 3, 4, 5]

        result = await cache.publish("list_channel", test_message)

        mock_client.publish.assert_awaited_once_with("list_channel", json.dumps(test_message))
        assert result == 2

    @pytest.mark.asyncio
    async def test_publish_sends_string_message(self, cache):
        """문자열 메시지를 채널에 발행한다."""
        mock_client = AsyncMock()
        mock_client.publish = AsyncMock(return_value=5)
        cache.redis_client = mock_client

        test_message = "Hello, subscribers!"

        result = await cache.publish("message_channel", test_message)

        mock_client.publish.assert_awaited_once_with("message_channel", test_message)
        assert result == 5

    @pytest.mark.asyncio
    async def test_publish_uses_channel_mapping(self, cache):
        """channels 매핑에 정의된 채널 이름을 사용한다."""
        import json

        mock_client = AsyncMock()
        mock_client.publish = AsyncMock(return_value=1)
        cache.redis_client = mock_client

        # channels 매핑 설정
        cache.channels = {"trade": "app:trade:channel", "user": "app:user:channel"}

        test_message = {"data": "test"}

        result = await cache.publish("trade", test_message)

        # 매핑된 채널 이름으로 발행되어야 함
        mock_client.publish.assert_awaited_once_with("app:trade:channel", json.dumps(test_message))
        assert result == 1

    @pytest.mark.asyncio
    async def test_publish_uses_channel_name_directly_if_not_in_mapping(self, cache):
        """channels 매핑에 없는 채널은 이름을 직접 사용한다."""
        import json

        mock_client = AsyncMock()
        mock_client.publish = AsyncMock(return_value=1)
        cache.redis_client = mock_client

        cache.channels = {"trade": "app:trade:channel"}

        test_message = {"data": "test"}

        result = await cache.publish("custom_channel", test_message)

        # 매핑에 없으므로 채널 이름을 직접 사용
        mock_client.publish.assert_awaited_once_with("custom_channel", json.dumps(test_message))
        assert result == 1

    @pytest.mark.asyncio
    async def test_publish_returns_zero_when_no_subscribers(self, cache):
        """구독자가 없을 때 0을 반환한다."""
        mock_client = AsyncMock()
        mock_client.publish = AsyncMock(return_value=0)
        cache.redis_client = mock_client

        result = await cache.publish("empty_channel", "message")

        assert result == 0

    @pytest.mark.asyncio
    async def test_publish_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 0을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.publish = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.publish("test_channel", "message")

        assert result == 0
        assert "Cache publish error" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_publish_converts_int_to_string(self, cache):
        """정수 메시지를 문자열로 변환하여 발행한다."""
        mock_client = AsyncMock()
        mock_client.publish = AsyncMock(return_value=1)
        cache.redis_client = mock_client

        test_message = 12345

        result = await cache.publish("number_channel", test_message)

        mock_client.publish.assert_awaited_once_with("number_channel", "12345")
        assert result == 1

    # ============= subscribe =============

    @pytest.mark.asyncio
    async def test_subscribe_to_single_channel(self, cache):
        """단일 채널을 구독한다."""
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        cache.redis_client = mock_client

        result = await cache.subscribe("test_channel")

        mock_client.pubsub.assert_called_once()
        mock_pubsub.subscribe.assert_awaited_once_with("test_channel")
        assert result == mock_pubsub

    @pytest.mark.asyncio
    async def test_subscribe_to_multiple_channels(self, cache):
        """여러 채널을 동시에 구독한다."""
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        cache.redis_client = mock_client

        result = await cache.subscribe("channel1", "channel2", "channel3")

        mock_client.pubsub.assert_called_once()
        mock_pubsub.subscribe.assert_awaited_once_with("channel1", "channel2", "channel3")
        assert result == mock_pubsub

    @pytest.mark.asyncio
    async def test_subscribe_uses_channel_mapping(self, cache):
        """channels 매핑에 정의된 채널 이름을 사용한다."""
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        cache.redis_client = mock_client

        cache.channels = {"trade": "app:trade:channel", "user": "app:user:channel"}

        result = await cache.subscribe("trade", "user")

        # 매핑된 채널 이름으로 구독되어야 함
        mock_pubsub.subscribe.assert_awaited_once_with("app:trade:channel", "app:user:channel")
        assert result == mock_pubsub

    @pytest.mark.asyncio
    async def test_subscribe_uses_channel_name_directly_if_not_in_mapping(self, cache):
        """channels 매핑에 없는 채널은 이름을 직접 사용한다."""
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        cache.redis_client = mock_client

        cache.channels = {"trade": "app:trade:channel"}

        result = await cache.subscribe("custom_channel")

        # 매핑에 없으므로 채널 이름을 직접 사용
        mock_pubsub.subscribe.assert_awaited_once_with("custom_channel")
        assert result == mock_pubsub

    @pytest.mark.asyncio
    async def test_subscribe_mixed_mapped_and_unmapped_channels(self, cache):
        """매핑된 채널과 매핑되지 않은 채널을 혼합하여 구독한다."""
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        cache.redis_client = mock_client

        cache.channels = {"trade": "app:trade:channel"}

        result = await cache.subscribe("trade", "custom_channel")

        # trade는 매핑된 이름, custom_channel은 직접 사용
        mock_pubsub.subscribe.assert_awaited_once_with("app:trade:channel", "custom_channel")
        assert result == mock_pubsub

    @pytest.mark.asyncio
    async def test_subscribe_returns_pubsub_object(self, cache):
        """PubSub 객체를 반환한다."""
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        cache.redis_client = mock_client

        result = await cache.subscribe("test_channel")

        assert result is mock_pubsub

    @pytest.mark.asyncio
    async def test_subscribe_creates_new_pubsub_instance(self, cache):
        """구독할 때마다 새로운 PubSub 인스턴스를 생성한다."""
        mock_client = AsyncMock()
        mock_pubsub1 = AsyncMock()
        mock_pubsub2 = AsyncMock()
        mock_pubsub1.subscribe = AsyncMock()
        mock_pubsub2.subscribe = AsyncMock()

        # pubsub()이 호출될 때마다 다른 객체 반환
        mock_client.pubsub = MagicMock(side_effect=[mock_pubsub1, mock_pubsub2])
        cache.redis_client = mock_client

        result1 = await cache.subscribe("channel1")
        result2 = await cache.subscribe("channel2")

        assert result1 is mock_pubsub1
        assert result2 is mock_pubsub2
        assert result1 is not result2
        assert mock_client.pubsub.call_count == 2

    # ============= incr =============

    @pytest.mark.asyncio
    async def test_incr_increments_value_by_one(self, cache):
        """값을 1씩 증가시킨다."""
        mock_client = AsyncMock()
        mock_client.incrby = AsyncMock(return_value=1)
        cache.redis_client = mock_client

        result = await cache.incr("counter")

        mock_client.incrby.assert_awaited_once_with("counter", 1)
        assert result == 1

    @pytest.mark.asyncio
    async def test_incr_increments_value_by_custom_amount(self, cache):
        """값을 지정한 양만큼 증가시킨다."""
        mock_client = AsyncMock()
        mock_client.incrby = AsyncMock(return_value=15)
        cache.redis_client = mock_client

        result = await cache.incr("counter", amount=10)

        mock_client.incrby.assert_awaited_once_with("counter", 10)
        assert result == 15

    @pytest.mark.asyncio
    async def test_incr_returns_incremented_value(self, cache):
        """증가 후의 값을 반환한다."""
        mock_client = AsyncMock()
        mock_client.incrby = AsyncMock(return_value=100)
        cache.redis_client = mock_client

        result = await cache.incr("views", amount=5)

        assert result == 100

    @pytest.mark.asyncio
    async def test_incr_with_large_amount(self, cache):
        """큰 값으로도 증가시킬 수 있다."""
        mock_client = AsyncMock()
        mock_client.incrby = AsyncMock(return_value=1000000)
        cache.redis_client = mock_client

        result = await cache.incr("big_counter", amount=999999)

        mock_client.incrby.assert_awaited_once_with("big_counter", 999999)
        assert result == 1000000

    @pytest.mark.asyncio
    async def test_incr_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 0을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.incrby = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.incr("counter")

        assert result == 0
        assert "Cache incr error" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_incr_multiple_times_returns_accumulated_value(self, cache):
        """여러 번 증가시킬 수 있다."""
        mock_client = AsyncMock()
        mock_client.incrby = AsyncMock(side_effect=[1, 2, 3, 4, 5])
        cache.redis_client = mock_client

        result1 = await cache.incr("counter")
        result2 = await cache.incr("counter")
        result3 = await cache.incr("counter")

        assert result1 == 1
        assert result2 == 2
        assert result3 == 3
        assert mock_client.incrby.await_count == 3

    @pytest.mark.asyncio
    async def test_incr_with_negative_amount_decreases_value(self, cache):
        """음수 양으로 증가시키면 값이 감소한다."""
        mock_client = AsyncMock()
        mock_client.incrby = AsyncMock(return_value=5)
        cache.redis_client = mock_client

        result = await cache.incr("counter", amount=-5)

        mock_client.incrby.assert_awaited_once_with("counter", -5)
        assert result == 5

    # ============= decr =============

    @pytest.mark.asyncio
    async def test_decr_decrements_value_by_one(self, cache):
        """값을 1씩 감소시킨다."""
        mock_client = AsyncMock()
        mock_client.decrby = AsyncMock(return_value=9)
        cache.redis_client = mock_client

        result = await cache.decr("counter")

        mock_client.decrby.assert_awaited_once_with("counter", 1)
        assert result == 9

    @pytest.mark.asyncio
    async def test_decr_decrements_value_by_custom_amount(self, cache):
        """값을 지정한 양만큼 감소시킨다."""
        mock_client = AsyncMock()
        mock_client.decrby = AsyncMock(return_value=5)
        cache.redis_client = mock_client

        result = await cache.decr("counter", amount=10)

        mock_client.decrby.assert_awaited_once_with("counter", 10)
        assert result == 5

    @pytest.mark.asyncio
    async def test_decr_returns_decremented_value(self, cache):
        """감소 후의 값을 반환한다."""
        mock_client = AsyncMock()
        mock_client.decrby = AsyncMock(return_value=50)
        cache.redis_client = mock_client

        result = await cache.decr("stock", amount=5)

        assert result == 50

    @pytest.mark.asyncio
    async def test_decr_can_go_negative(self, cache):
        """값이 음수가 될 수 있다."""
        mock_client = AsyncMock()
        mock_client.decrby = AsyncMock(return_value=-5)
        cache.redis_client = mock_client

        result = await cache.decr("balance", amount=10)

        mock_client.decrby.assert_awaited_once_with("balance", 10)
        assert result == -5

    @pytest.mark.asyncio
    async def test_decr_with_large_amount(self, cache):
        """큰 값으로도 감소시킬 수 있다."""
        mock_client = AsyncMock()
        mock_client.decrby = AsyncMock(return_value=1)
        cache.redis_client = mock_client

        result = await cache.decr("big_counter", amount=999999)

        mock_client.decrby.assert_awaited_once_with("big_counter", 999999)
        assert result == 1

    @pytest.mark.asyncio
    async def test_decr_handles_redis_error(self, cache, caplog):
        """Redis 오류 발생 시 0을 반환하고 로그를 남긴다."""
        mock_client = AsyncMock()
        mock_client.decrby = AsyncMock(side_effect=Exception("Redis connection error"))
        cache.redis_client = mock_client

        with caplog.at_level("ERROR"):
            result = await cache.decr("counter")

        assert result == 0
        assert "Cache decr error" in caplog.text
        assert "Redis connection error" in caplog.text

    @pytest.mark.asyncio
    async def test_decr_multiple_times_returns_accumulated_value(self, cache):
        """여러 번 감소시킬 수 있다."""
        mock_client = AsyncMock()
        mock_client.decrby = AsyncMock(side_effect=[9, 8, 7, 6, 5])
        cache.redis_client = mock_client

        result1 = await cache.decr("counter")
        result2 = await cache.decr("counter")
        result3 = await cache.decr("counter")

        assert result1 == 9
        assert result2 == 8
        assert result3 == 7
        assert mock_client.decrby.await_count == 3

    @pytest.mark.asyncio
    async def test_decr_with_negative_amount_increases_value(self, cache):
        """음수 양으로 감소시키면 값이 증가한다."""
        mock_client = AsyncMock()
        mock_client.decrby = AsyncMock(return_value=15)
        cache.redis_client = mock_client

        result = await cache.decr("counter", amount=-5)

        mock_client.decrby.assert_awaited_once_with("counter", -5)
        assert result == 15
