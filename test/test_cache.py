from unittest.mock import AsyncMock, patch

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
