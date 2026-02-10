from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database import DataStorage  # 실제 모듈 경로로 수정 필요


class TestDataStorage:
    class TestDataStorage:
        @pytest.fixture
        def config(self):
            return {
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "user": "admin",
                "password": "password",
                "min_connections": 2,
                "max_connections": 10,
            }

        @pytest.fixture
        def storage(self, config):
            return DataStorage(**config)

        # ============= connect =============

        @pytest.mark.asyncio
        async def test_connect_creates_pool_successfully(self, storage, config, caplog):
            """asyncpg가 존재할 때 연결 풀을 생성하고 연결 상태를 True로 설정한다."""

            # [수정 2] patch 경로를 src.storage -> src.database.storage 로 수정
            with (
                patch("src.database.storage.HAS_ASYNCPG", True),
                patch("src.database.storage.asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool,
                caplog.at_level("INFO"),
            ):
                mock_pool = AsyncMock()
                mock_create_pool.return_value = mock_pool

                await storage.connect()

                mock_create_pool.assert_awaited_once_with(
                    host=config["host"],
                    port=config["port"],
                    database=config["database"],
                    user=config["user"],
                    password=config["password"],
                    min_size=config["min_connections"],
                    max_size=config["max_connections"],
                    command_timeout=60,
                )

                assert storage._pool == mock_pool
                assert storage.is_connected is True
                assert "Connected to TimescaleDB" in caplog.text

        @pytest.mark.asyncio
        async def test_connect_aborts_if_asyncpg_missing(self, storage, caplog):
            """asyncpg 모듈이 없으면 경고 로그를 남기고 연결하지 않는다."""

            # [수정 2] patch 경로 수정
            with patch("src.database.storage.HAS_ASYNCPG", False), caplog.at_level("WARNING"):
                await storage.connect()

                assert storage.is_connected is False
                assert storage._pool is None
                assert "asyncpg is not installed" in caplog.text

        @pytest.mark.asyncio
        async def test_connect_raises_exception_on_failure(self, storage, caplog):
            """연결 시도 중 예외가 발생하면 에러 로그를 남기고 예외를 전파한다."""

            # [수정 2] patch 경로 수정
            with (
                patch("src.database.storage.HAS_ASYNCPG", True),
                patch("src.database.storage.asyncpg.create_pool", side_effect=TimeoutError("Connection timeout")),
                caplog.at_level("ERROR"),
            ):
                with pytest.raises(TimeoutError, match="Connection timeout"):
                    await storage.connect()

                assert storage.is_connected is False
                assert "Failed to connect" in caplog.text

        # ============= disconnect =============

        @pytest.mark.asyncio
        async def test_disconnect_closes_pool_and_resets_state(self, storage, caplog):
            """연결 해제 시 풀을 닫고 내부 상태를 초기화한다."""

            mock_pool = AsyncMock()
            storage._pool = mock_pool
            storage._connected = True

            with caplog.at_level("INFO"):
                await storage.disconnect()

            mock_pool.close.assert_awaited_once()
            assert storage._pool is None
            assert storage.is_connected is False
            assert "Disconnected from database" in caplog.text

        @pytest.mark.asyncio
        async def test_disconnect_does_nothing_if_already_closed(self, storage):
            storage._pool = None
            storage._connected = False
            await storage.disconnect()
            assert storage.is_connected is False

        # ============= health_check =============

        @pytest.mark.asyncio
        async def test_health_check_returns_true_on_query_success(self, storage):
            """DB 쿼리가 성공하면 True를 반환한다."""

            # [수정 3] async with 구문을 위한 Mock 구조 개선
            mock_conn = AsyncMock()
            mock_conn.fetchval.return_value = 1

            # acquire()가 반환하는 Context Manager Mock
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_conn
            mock_ctx.__aexit__.return_value = None

            # Pool Mock (acquire 메서드를 가짐)
            mock_pool = MagicMock()
            mock_pool.acquire.return_value = mock_ctx

            # 수동 연결 상태 설정
            storage._pool = mock_pool
            storage._connected = True

            result = await storage.health_check()

            assert result is True
            mock_conn.fetchval.assert_awaited_once_with("SELECT 1")

        @pytest.mark.asyncio
        async def test_health_check_returns_false_on_db_error(self, storage, caplog):
            """DB 쿼리 중 예외가 발생하면 에러 로그를 남기고 False를 반환한다."""

            # [수정 3] Mock 구조 개선
            mock_conn = AsyncMock()
            mock_conn.fetchval.side_effect = Exception("DB connection lost")

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_conn
            mock_ctx.__aexit__.return_value = None

            mock_pool = MagicMock()
            mock_pool.acquire.return_value = mock_ctx

            storage._pool = mock_pool
            storage._connected = True

            with caplog.at_level("ERROR"):
                result = await storage.health_check()

            assert result is False
            assert "Health check failed" in caplog.text

        @pytest.mark.asyncio
        async def test_health_check_returns_false_when_disconnected(self, storage):
            storage._connected = False
            storage._pool = None
            result = await storage.health_check()
            assert result is False
