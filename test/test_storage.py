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

        from src.trading.exchanges.upbit.codes import OrderSide, OrderType, TimeInForce
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
            smp_type=None,
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

        from src.trading.exchanges.upbit.codes import OrderSide, OrderType, TimeInForce
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
            smp_type=None,
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

        from src.trading.exchanges.upbit.codes import OrderSide, OrderType, TimeInForce
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
            smp_type=None,
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

    # ============= save_candle =============

    @pytest.mark.asyncio
    async def test_save_candle_inserts_new_candle(self, storage):
        """새로운 캔들을 DB에 저장한다."""
        from datetime import datetime, timezone
        from decimal import Decimal

        from src.trading.exchanges.upbit.codes import Timeframe, Unit
        from src.trading.exchanges.upbit.models import Candle

        candle = Candle(
            market="KRW-BTC",
            candle_date_time_utc=datetime(2026, 2, 12, 10, 0, 0, tzinfo=timezone.utc),
            candle_date_time_kst=datetime(2026, 2, 12, 19, 0, 0),
            opening_price=Decimal("50000000"),
            high_price=Decimal("51000000"),
            low_price=Decimal("49500000"),
            trade_price=Decimal("50500000"),
            timestamp=1707732000000,
            candle_acc_trade_price=Decimal("5000000000"),
            candle_acc_trade_volume=Decimal("100"),
            unit=Unit.MINUTE_1,
            prev_closing_price=Decimal("50000000"),
            change_price=Decimal("500000"),
            change_rate=Decimal("0.01"),
            converted_trade_price=Decimal("50500000"),
            first_day_of_period=datetime(2026, 2, 12, 0, 0, 0, tzinfo=timezone.utc),
        )

        mock_conn = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        await storage.save_candle(candle, Timeframe.MINUTE_1)

        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.await_args
        sql = call_args[0][0]
        assert "INSERT INTO trading.candles" in sql
        assert "ON CONFLICT DO NOTHING" in sql

        # 파라미터 검증
        params = call_args[0][1:]
        assert params[0] == Timeframe.MINUTE_1.value  # timeframe
        assert params[1] == "KRW-BTC"  # market
        assert params[2] == candle.candle_date_time_utc
        assert params[3] == candle.candle_date_time_kst

    @pytest.mark.asyncio
    async def test_save_candle_does_nothing_when_disconnected(self, storage):
        """연결되지 않은 상태에서는 아무 작업도 하지 않는다."""
        from datetime import datetime, timezone
        from decimal import Decimal

        from src.trading.exchanges.upbit.codes import Timeframe, Unit
        from src.trading.exchanges.upbit.models import Candle

        candle = Candle(
            market="KRW-BTC",
            candle_date_time_utc=datetime(2026, 2, 12, 10, 0, 0, tzinfo=timezone.utc),
            candle_date_time_kst=datetime(2026, 2, 12, 19, 0, 0),
            opening_price=Decimal("50000000"),
            high_price=Decimal("51000000"),
            low_price=Decimal("49500000"),
            trade_price=Decimal("50500000"),
            timestamp=1707732000000,
            candle_acc_trade_price=Decimal("5000000000"),
            candle_acc_trade_volume=Decimal("100"),
            unit=Unit.MINUTE_1,
            prev_closing_price=Decimal("50000000"),
            change_price=Decimal("500000"),
            change_rate=Decimal("0.01"),
            converted_trade_price=Decimal("50500000"),
            first_day_of_period=datetime(2026, 2, 12, 0, 0, 0, tzinfo=timezone.utc),
        )

        storage._connected = False
        storage._pool = None

        await storage.save_candle(candle, Timeframe.MINUTE_1)

    # ============= get_candles =============

    @pytest.mark.asyncio
    async def test_get_candles_returns_candles_in_range(self, storage):
        """특정 기간의 캔들을 조회한다."""
        from datetime import datetime, timezone
        from decimal import Decimal

        from src.trading.exchanges.upbit.codes import Timeframe

        start = datetime(2026, 2, 12, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 2, 12, 11, 0, 0, tzinfo=timezone.utc)

        mock_rows = [
            {
                "market": "KRW-BTC",
                "candle_date_time_utc": datetime(2026, 2, 12, 10, 0, 0, tzinfo=timezone.utc),
                "candle_date_time_kst": datetime(2026, 2, 12, 19, 0, 0),
                "opening_price": Decimal("50000000"),
                "high_price": Decimal("51000000"),
                "low_price": Decimal("49500000"),
                "trade_price": Decimal("50500000"),
                "timestamp": 1707732000000,
                "candle_acc_trade_price": Decimal("5000000000"),
                "candle_acc_trade_volume": Decimal("100"),
                "unit": 1,
                "prev_closing_price": Decimal("50000000"),
                "change_price": Decimal("500000"),
                "change_rate": Decimal("0.01"),
                "converted_trade_price": Decimal("50500000"),
            },
            {
                "market": "KRW-BTC",
                "candle_date_time_utc": datetime(2026, 2, 12, 10, 1, 0, tzinfo=timezone.utc),
                "candle_date_time_kst": datetime(2026, 2, 12, 19, 1, 0),
                "opening_price": Decimal("50500000"),
                "high_price": Decimal("51500000"),
                "low_price": Decimal("50000000"),
                "trade_price": Decimal("51000000"),
                "timestamp": 1707732060000,
                "candle_acc_trade_price": Decimal("5100000000"),
                "candle_acc_trade_volume": Decimal("101"),
                "unit": 1,
                "prev_closing_price": Decimal("50500000"),
                "change_price": Decimal("500000"),
                "change_rate": Decimal("0.01"),
                "converted_trade_price": Decimal("51000000"),
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = mock_rows

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        candles = await storage.get_candles(
            market="KRW-BTC", timeframe=Timeframe.MINUTE_1, start=start, end=end, limit=1000
        )

        assert len(candles) == 2
        assert candles[0].market == "KRW-BTC"
        assert candles[0].trade_price == Decimal("50500000")
        assert candles[1].trade_price == Decimal("51000000")

        mock_conn.fetch.assert_awaited_once()
        call_args = mock_conn.fetch.await_args
        sql = call_args[0][0]
        assert "FROM trading.candles AS c" in sql
        assert "WHERE c.market = $1" in sql
        assert "AND c.timeframe = $5" in sql

        # 파라미터 검증
        params = call_args[0][1:]
        assert params[0] == "KRW-BTC"
        assert params[1] == start
        assert params[2] == end
        assert params[3] == 1000
        assert params[4] == Timeframe.MINUTE_1.value

    @pytest.mark.asyncio
    async def test_get_candles_uses_current_time_when_end_not_provided(self, storage):
        """end가 제공되지 않으면 현재 시각을 사용한다."""
        from datetime import datetime, timezone

        from src.trading.exchanges.upbit.codes import Timeframe

        start = datetime(2026, 2, 12, 10, 0, 0, tzinfo=timezone.utc)

        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        await storage.get_candles(
            market="KRW-BTC",
            timeframe=Timeframe.MINUTE_1,
            start=start,
        )

        mock_conn.fetch.assert_awaited_once()
        call_args = mock_conn.fetch.await_args
        params = call_args[0][1:]
        # end 파라미터 (params[2])가 datetime 객체인지 확인
        assert isinstance(params[2], datetime)

    @pytest.mark.asyncio
    async def test_get_candles_returns_empty_when_disconnected(self, storage):
        """연결되지 않은 상태에서는 빈 리스트를 반환한다."""
        from datetime import datetime, timezone

        from src.trading.exchanges.upbit.codes import Timeframe

        storage._connected = False
        storage._pool = None

        start = datetime(2026, 2, 12, 10, 0, 0, tzinfo=timezone.utc)

        candles = await storage.get_candles(
            market="KRW-BTC",
            timeframe=Timeframe.MINUTE_1,
            start=start,
        )

        assert candles == []

    # ============= get_latest_candles =============

    @pytest.mark.asyncio
    async def test_get_latest_candles_returns_recent_candles(self, storage):
        """최근 캔들을 조회한다."""
        from datetime import datetime, timezone
        from decimal import Decimal

        from src.trading.exchanges.upbit.codes import Timeframe

        mock_rows = [
            {
                "market": "KRW-BTC",
                "candle_date_time_utc": datetime(2026, 2, 12, 10, 2, 0, tzinfo=timezone.utc),
                "candle_date_time_kst": datetime(2026, 2, 12, 19, 2, 0),
                "opening_price": Decimal("51000000"),
                "high_price": Decimal("52000000"),
                "low_price": Decimal("50500000"),
                "trade_price": Decimal("51500000"),
                "timestamp": 1707732120000,
                "candle_acc_trade_price": Decimal("5200000000"),
                "candle_acc_trade_volume": Decimal("102"),
                "unit": 1,
                "prev_closing_price": Decimal("51000000"),
                "change_price": Decimal("500000"),
                "change_rate": Decimal("0.01"),
                "converted_trade_price": Decimal("51500000"),
            },
            {
                "market": "KRW-BTC",
                "candle_date_time_utc": datetime(2026, 2, 12, 10, 1, 0, tzinfo=timezone.utc),
                "candle_date_time_kst": datetime(2026, 2, 12, 19, 1, 0),
                "opening_price": Decimal("50500000"),
                "high_price": Decimal("51500000"),
                "low_price": Decimal("50000000"),
                "trade_price": Decimal("51000000"),
                "timestamp": 1707732060000,
                "candle_acc_trade_price": Decimal("5100000000"),
                "candle_acc_trade_volume": Decimal("101"),
                "unit": 1,
                "prev_closing_price": Decimal("50500000"),
                "change_price": Decimal("500000"),
                "change_rate": Decimal("0.01"),
                "converted_trade_price": Decimal("51000000"),
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = mock_rows

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        candles = await storage.get_latest_candles(market="KRW-BTC", timeframe=Timeframe.MINUTE_1, count=200)

        assert len(candles) == 2
        assert candles[0].market == "KRW-BTC"
        # DESC 정렬이므로 최신 캔들이 먼저 온다
        assert candles[0].trade_price == Decimal("51500000")
        assert candles[1].trade_price == Decimal("51000000")

        mock_conn.fetch.assert_awaited_once()
        call_args = mock_conn.fetch.await_args
        sql = call_args[0][0]
        assert "FROM trading.candles AS c" in sql
        assert "WHERE c.market = $1" in sql
        assert "AND c.timeframe = $2" in sql
        assert "ORDER BY time DESC" in sql
        assert "LIMIT $3" in sql

        # 파라미터 검증
        params = call_args[0][1:]
        assert params[0] == "KRW-BTC"
        assert params[1] == Timeframe.MINUTE_1.value
        assert params[2] == 200

    @pytest.mark.asyncio
    async def test_get_latest_candles_returns_empty_when_disconnected(self, storage):
        """연결되지 않은 상태에서는 빈 리스트를 반환한다."""
        from src.trading.exchanges.upbit.codes import Timeframe

        storage._connected = False
        storage._pool = None

        candles = await storage.get_latest_candles(market="KRW-BTC", timeframe=Timeframe.MINUTE_1, count=200)

        assert candles == []

    # ============= save_signal =============

    @pytest.mark.asyncio
    async def test_save_signal_inserts_new_signal(self, storage):
        """새로운 신호를 DB에 저장한다."""
        from datetime import datetime, timezone

        from src.strategies.codes import MarketRegime
        from src.strategies.models import Signal
        from src.trading.exchanges.upbit.codes import Timeframe

        signal = Signal(
            strategy_name="rsi_strategy",
            market="KRW-BTC",
            timeframe=Timeframe.HOUR,
            market_regime=MarketRegime.STABLE_BULL,
            metadata={"rsi": 70.5},
            created_at=datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
        )

        mock_conn = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        await storage.save_signal(signal)

        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.await_args
        sql = call_args[0][0]
        assert "INSERT INTO trading.signals" in sql
        assert "ON CONFLICT" in sql

        params = call_args[0][1:]
        assert params[0] == "rsi_strategy"
        assert params[1] == "KRW-BTC"
        assert params[2] == Timeframe.HOUR.value
        assert params[3] == MarketRegime.STABLE_BULL.value
        assert params[4] == {"rsi": 70.5}

    @pytest.mark.asyncio
    async def test_save_signal_updates_on_conflict(self, storage):
        """동일 (strategy_name, market, timeframe) 조합이 존재하면 업데이트한다."""
        from datetime import datetime, timezone

        from src.strategies.codes import MarketRegime
        from src.strategies.models import Signal
        from src.trading.exchanges.upbit.codes import Timeframe

        signal = Signal(
            strategy_name="rsi_strategy",
            market="KRW-BTC",
            timeframe=Timeframe.HOUR,
            market_regime=MarketRegime.STABLE_BULL,
            metadata={"rsi": 25.0},
            created_at=datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
        )

        mock_conn = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        await storage.save_signal(signal)

        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.await_args
        sql = call_args[0][0]
        assert "DO UPDATE SET" in sql

    @pytest.mark.asyncio
    async def test_save_signal_does_nothing_when_disconnected(self, storage):
        """연결되지 않은 상태에서는 아무 작업도 하지 않는다."""
        from datetime import datetime, timezone

        from src.strategies.codes import MarketRegime
        from src.strategies.models import Signal
        from src.trading.exchanges.upbit.codes import Timeframe

        signal = Signal(
            strategy_name="rsi_strategy",
            market="KRW-BTC",
            timeframe=Timeframe.HOUR,
            market_regime=MarketRegime.STABLE_BULL,
            metadata={},
            created_at=datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
        )

        storage._connected = False
        storage._pool = None

        await storage.save_signal(signal)

    @pytest.mark.asyncio
    async def test_save_signal_handles_none_timeframe_and_regime(self, storage):
        """timeframe, market_regime 이 None 이어도 저장할 수 있다."""
        from datetime import datetime, timezone

        from src.strategies.models import Signal

        signal = Signal(
            strategy_name="rsi_strategy",
            market="KRW-BTC",
            timeframe=None,
            market_regime=None,
            metadata=None,
            created_at=datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
        )

        mock_conn = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        await storage.save_signal(signal)

        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.await_args
        params = call_args[0][1:]
        assert params[2] is None  # timeframe
        assert params[3] is None  # market_regime

    # ============= get_signal =============

    @pytest.mark.asyncio
    async def test_get_signal_returns_signal_when_found(self, storage):
        """저장된 신호를 market, timeframe, strategy_name 으로 조회한다."""
        from datetime import datetime, timezone

        from src.trading.exchanges.upbit.codes import Timeframe

        mock_row = {
            "strategy_name": "rsi_strategy",
            "market": "KRW-BTC",
            "timeframe": Timeframe.HOUR.value,
            "market_regime": "BULL",
            "metadata": {"rsi": 70.5},
            "created_at": datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 13, 9, 0, 0, tzinfo=timezone.utc),
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

        signal = await storage.get_signal(
            market="KRW-BTC",
            timeframe=Timeframe.HOUR,
            strategy_name="rsi_strategy",
        )

        assert signal is not None
        assert signal.strategy_name == "rsi_strategy"
        assert signal.market == "KRW-BTC"
        assert signal.metadata == {"rsi": 70.5}

        mock_conn.fetchrow.assert_awaited_once()
        call_args = mock_conn.fetchrow.await_args
        sql = call_args[0][0]
        assert "FROM trading.signals AS s" in sql
        assert "WHERE s.market = $1" in sql
        assert "AND s.timeframe = $2" in sql
        assert "AND s.strategy_name = $3" in sql

        params = call_args[0][1:]
        assert params[0] == "KRW-BTC"
        assert params[1] == Timeframe.HOUR.value
        assert params[2] == "rsi_strategy"

    @pytest.mark.asyncio
    async def test_get_signal_returns_none_when_not_found(self, storage):
        """신호가 없으면 None을 반환한다."""
        from src.trading.exchanges.upbit.codes import Timeframe

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_ctx

        storage._pool = mock_pool
        storage._connected = True

        signal = await storage.get_signal(
            market="KRW-BTC",
            timeframe=Timeframe.HOUR,
            strategy_name="nonexistent_strategy",
        )

        assert signal is None

    @pytest.mark.asyncio
    async def test_get_signal_returns_none_when_disconnected(self, storage):
        """연결되지 않은 상태에서는 None을 반환한다."""
        from src.trading.exchanges.upbit.codes import Timeframe

        storage._connected = False
        storage._pool = None

        signal = await storage.get_signal(
            market="KRW-BTC",
            timeframe=Timeframe.HOUR,
            strategy_name="rsi_strategy",
        )

        assert signal is None
