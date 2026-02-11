from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database import DataStorage


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

    # ============= save_order =============

    @pytest.mark.asyncio
    async def test_save_order_inserts_new_order(self, storage):
        """새로운 주문을 DB에 저장한다."""
        from datetime import datetime
        from decimal import Decimal

        from src.trading.exchanges.upbit.codes import OrderSide, OrderType, SelfMatchPreventionType, TimeInForce
        from src.trading.exchanges.upbit.codes.order_state import OrderState
        from src.trading.exchanges.upbit.models import Order

        order = Order(
            market="KRW-BTC",
            uuid="test-uuid-123",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=Decimal("50000000"),
            state=OrderState.WAIT,
            created_at=datetime(2026, 2, 10, 12, 0, 0),
            volume=Decimal("0.1"),
            remaining_volume=Decimal("0.1"),
            executed_volume=Decimal("0"),
            reserved_fee=Decimal("25000"),
            remaining_fee=Decimal("25000"),
            paid_fee=Decimal("0"),
            locked=Decimal("5025000"),
            trades_count=0,
            time_in_force=TimeInForce.IOC,
            identifier="test-identifier",
            smp_type=SelfMatchPreventionType.NONE,
            prevented_volume=Decimal("0"),
            prevented_locked=Decimal("0"),
        )

        mock_conn = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        await storage.save_order(order)

        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.await_args
        sql = call_args[0][0]
        assert "INSERT INTO trading.orders" in sql
        assert "ON CONFLICT (uuid)" in sql

    @pytest.mark.asyncio
    async def test_save_order_updates_existing_order_on_conflict(self, storage):
        """동일한 uuid가 존재하면 업데이트한다."""
        from datetime import datetime
        from decimal import Decimal

        from src.trading.exchanges.upbit.codes import OrderSide, OrderType, SelfMatchPreventionType, TimeInForce
        from src.trading.exchanges.upbit.codes.order_state import OrderState
        from src.trading.exchanges.upbit.models import Order

        order = Order(
            market="KRW-BTC",
            uuid="existing-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=Decimal("50000000"),
            state=OrderState.DONE,
            created_at=datetime(2026, 2, 10, 12, 0, 0),
            volume=Decimal("0.1"),
            remaining_volume=Decimal("0"),
            executed_volume=Decimal("0.1"),
            reserved_fee=Decimal("25000"),
            remaining_fee=Decimal("0"),
            paid_fee=Decimal("25000"),
            locked=Decimal("0"),
            trades_count=1,
            time_in_force=TimeInForce.IOC,
            identifier="test-identifier",
            smp_type=SelfMatchPreventionType.NONE,
            prevented_volume=Decimal("0"),
            prevented_locked=Decimal("0"),
        )

        mock_conn = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        await storage.save_order(order)

        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.await_args
        sql = call_args[0][0]
        assert "DO UPDATE SET" in sql

    @pytest.mark.asyncio
    async def test_save_order_does_nothing_when_disconnected(self, storage):
        """연결되지 않은 상태에서는 아무 작업도 하지 않는다."""
        from datetime import datetime
        from decimal import Decimal

        from src.trading.exchanges.upbit.codes import OrderSide, OrderType, SelfMatchPreventionType, TimeInForce
        from src.trading.exchanges.upbit.codes.order_state import OrderState
        from src.trading.exchanges.upbit.models import Order

        order = Order(
            market="KRW-BTC",
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=Decimal("50000000"),
            state=OrderState.WAIT,
            created_at=datetime(2026, 2, 10, 12, 0, 0),
            volume=Decimal("0.1"),
            remaining_volume=Decimal("0.1"),
            executed_volume=Decimal("0"),
            reserved_fee=Decimal("25000"),
            remaining_fee=Decimal("25000"),
            paid_fee=Decimal("0"),
            locked=Decimal("5025000"),
            trades_count=0,
            time_in_force=TimeInForce.IOC,
            identifier="test-identifier",
            smp_type=SelfMatchPreventionType.NONE,
            prevented_volume=Decimal("0"),
            prevented_locked=Decimal("0"),
        )

        storage._connected = False
        storage._pool = None

        await storage.save_order(order)

    # ============= get_order =============

    @pytest.mark.asyncio
    async def test_get_order_by_uuid(self, storage):
        """uuid로 주문을 조회한다."""
        from datetime import datetime
        from decimal import Decimal

        mock_row = {
            "market": "KRW-BTC",
            "uuid": "test-uuid-123",
            "side": "bid",
            "ord_type": "limit",
            "price": Decimal("50000000"),
            "state": "wait",
            "created_at": datetime(2026, 2, 10, 12, 0, 0),
            "volume": Decimal("0.1"),
            "remaining_volume": Decimal("0.1"),
            "executed_volume": Decimal("0"),
            "reserved_fee": Decimal("25000"),
            "remaining_fee": Decimal("25000"),
            "paid_fee": Decimal("0"),
            "locked": Decimal("5025000"),
            "trades_count": 0,
            "time_in_force": "ioc",
            "identifier": "test-identifier",
            "smp_type": None,
            "prevented_volume": Decimal("0"),
            "prevented_locked": Decimal("0"),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        order = await storage.get_order(uuid="test-uuid-123")

        assert order is not None
        assert order.uuid == "test-uuid-123"
        assert order.market == "KRW-BTC"
        mock_conn.fetchrow.assert_awaited_once()
        call_args = mock_conn.fetchrow.await_args
        sql = call_args[0][0]
        assert "WHERE o.uuid = $1" in sql

    @pytest.mark.asyncio
    async def test_get_order_by_identifier(self, storage):
        """identifier로 주문을 조회한다."""
        from datetime import datetime
        from decimal import Decimal

        mock_row = {
            "market": "KRW-ETH",
            "uuid": "another-uuid",
            "side": "ask",
            "ord_type": "market",
            "price": None,
            "state": "done",
            "created_at": datetime(2026, 2, 10, 13, 0, 0),
            "volume": Decimal("1.0"),
            "remaining_volume": Decimal("0"),
            "executed_volume": Decimal("1.0"),
            "reserved_fee": Decimal("0"),
            "remaining_fee": Decimal("0"),
            "paid_fee": Decimal("5000"),
            "locked": Decimal("0"),
            "trades_count": 1,
            "time_in_force": "ioc",
            "identifier": "my-custom-id",
            "smp_type": "cancel_taker",
            "prevented_volume": Decimal("0"),
            "prevented_locked": Decimal("0"),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        order = await storage.get_order(identifier="my-custom-id")

        assert order is not None
        assert order.identifier == "my-custom-id"
        assert order.uuid == "another-uuid"
        mock_conn.fetchrow.assert_awaited_once()
        call_args = mock_conn.fetchrow.await_args
        sql = call_args[0][0]
        assert "WHERE o.identifier = $1" in sql

    @pytest.mark.asyncio
    async def test_get_order_by_uuid_and_identifier(self, storage):
        """uuid와 identifier 둘 다로 주문을 조회한다 (AND 조건)."""
        from datetime import datetime
        from decimal import Decimal

        mock_row = {
            "market": "KRW-XRP",
            "uuid": "specific-uuid",
            "side": "bid",
            "ord_type": "limit",
            "price": Decimal("1000"),
            "state": "wait",
            "created_at": datetime(2026, 2, 10, 14, 0, 0),
            "volume": Decimal("100"),
            "remaining_volume": Decimal("100"),
            "executed_volume": Decimal("0"),
            "reserved_fee": Decimal("50"),
            "remaining_fee": Decimal("50"),
            "paid_fee": Decimal("0"),
            "locked": Decimal("100050"),
            "trades_count": 0,
            "time_in_force": "ioc",
            "identifier": "specific-identifier",
            "smp_type": "reduce",
            "prevented_volume": Decimal("0"),
            "prevented_locked": Decimal("0"),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        order = await storage.get_order(uuid="specific-uuid", identifier="specific-identifier")

        assert order is not None
        assert order.uuid == "specific-uuid"
        assert order.identifier == "specific-identifier"
        mock_conn.fetchrow.assert_awaited_once()
        call_args = mock_conn.fetchrow.await_args
        sql = call_args[0][0]
        assert "o.uuid = $1" in sql
        assert "o.identifier = $2" in sql
        assert "AND" in sql

    @pytest.mark.asyncio
    async def test_get_order_returns_none_when_not_found(self, storage):
        """주문이 없으면 None을 반환한다."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        order = await storage.get_order(uuid="non-existent-uuid")

        assert order is None

    @pytest.mark.asyncio
    async def test_get_order_returns_none_when_disconnected(self, storage):
        """연결되지 않은 상태에서는 None을 반환한다."""
        storage._connected = False
        storage._pool = None

        order = await storage.get_order(uuid="any-uuid")

        assert order is None

    @pytest.mark.asyncio
    async def test_get_order_raises_error_when_no_params_given(self, storage):
        """uuid와 identifier 둘 다 None이면 ValueError를 발생시킨다."""
        storage._connected = True
        storage._pool = MagicMock()

        with pytest.raises(ValueError, match="uuid 또는 identifier 중 하나는 반드시 지정해야 합니다"):
            await storage.get_order()
