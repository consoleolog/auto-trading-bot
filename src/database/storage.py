import importlib
import logging
from datetime import datetime, timezone

from ..strategies.models import Signal
from ..trading.exchanges.upbit.codes import Timeframe
from ..trading.exchanges.upbit.models import Candle, Order

try:
    asyncpg = importlib.import_module("asyncpg")
    HAS_ASYNCPG = True
except ModuleNotFoundError:
    HAS_ASYNCPG = False

logger = logging.getLogger(__name__)


class DataStorage:
    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        min_connections: int = 2,
        max_connections: int = 10,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

        self.min_connections = min_connections
        self.max_connections = max_connections

        self._pool: asyncpg.Pool | None = None
        self._connected = False

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    async def connect(self):
        if not HAS_ASYNCPG:
            logger.warning("asyncpg is not installed - running in mock mode")
            self._connected = False
            return

        try:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=60,
            )
            self._connected = True
            logger.info(f"Connected to TimescaleDB at {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self._connected = False
            raise

    async def disconnect(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._connected = False
            logger.info("Disconnected from database")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._pool is not None

    async def health_check(self) -> bool:
        if not self.is_connected:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    # ========================================================================
    # SIGNAL OPERATIONS
    # ========================================================================

    async def save_signal(self, signal: Signal):
        if not self.is_connected:
            return

        sql = """
        INSERT INTO trading.signals (strategy_name, market, timeframe, market_regime, metadata)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (strategy_name, market, timeframe)
            DO UPDATE SET market_regime = $4,
                          metadata      = $5,
                          updated_at    = NOW();
        """

        async with self._pool.acquire() as conn:
            await conn.execute(
                sql,
                signal.strategy_name,
                signal.market,
                signal.timeframe.value if signal.timeframe else None,
                signal.market_regime.value if signal.market_regime else None,
                signal.metadata,
            )

    async def get_signal(self, market: str, timeframe: Timeframe, strategy_name: str) -> Signal | None:
        if not self.is_connected:
            return None

        sql = """
        SELECT s.strategy_name,
               s.market,
               s.timeframe,
               s.market_regime,
               s.metadata,
               s.created_at,
               s.updated_at
        FROM trading.signals AS s
        WHERE s.market = $1
        AND s.timeframe = $2
        AND s.strategy_name = $3;
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, market, timeframe.value, strategy_name)
        return Signal.from_dict(row) if row is not None else None

    # ========================================================================
    # CANDLE OPERATIONS
    # ========================================================================

    async def save_candle(self, candle: Candle, timeframe: Timeframe):
        if not self.is_connected:
            return

        sql = """

        INSERT INTO trading.candles (timeframe,
                                     market,
                                     candle_date_time_utc,
                                     candle_date_time_kst,
                                     opening_price,
                                     high_price,
                                     low_price,
                                     trade_price,
                                     timestamp,
                                     candle_acc_trade_price,
                                     candle_acc_trade_volume,
                                     unit,
                                     prev_closing_price,
                                     change_price,
                                     change_rate,
                                     converted_trade_price)
        VALUES ($1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                $11,
                $12,
                $13,
                $14,
                $15,
                $16)
        ON CONFLICT DO NOTHING ;
        """

        async with self._pool.acquire() as conn:
            await conn.execute(
                sql,
                timeframe.value,
                candle.market,
                candle.candle_date_time_utc,
                candle.candle_date_time_kst,
                candle.opening_price,
                candle.high_price,
                candle.low_price,
                candle.trade_price,
                candle.timestamp,
                candle.candle_acc_trade_price,
                candle.candle_acc_trade_volume,
                candle.unit,
                candle.prev_closing_price,
                candle.change_price,
                candle.change_rate,
                candle.converted_trade_price,
            )

    async def get_candles(
        self, market: str, timeframe: Timeframe, start: datetime, end: datetime | None = None, limit: int = 1000
    ) -> list[Candle]:
        if not self.is_connected:
            return []

        end = end or datetime.now(tz=timezone.utc)

        sql = """
        SELECT c.market,
               c.candle_date_time_utc,
               c.candle_date_time_kst,
               c.opening_price,
               c.high_price,
               c.low_price,
               c.trade_price,
               c.timestamp,
               c.candle_acc_trade_price,
               c.candle_acc_trade_volume,
               c.unit,
               c.prev_closing_price,
               c.change_price,
               c.change_rate,
               c.converted_trade_price
        FROM trading.candles AS c
        WHERE c.market = $1
        AND c.timeframe = $5
        AND c.candle_date_time_utc >= $2 AND c.candle_date_time_utc < $3
        ORDER BY c.time
        LIMIT $4
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, market, start, end, limit, timeframe.value)

        return [Candle.from_dict(r) for r in rows]

    async def get_latest_candles(self, market: str, timeframe: Timeframe, count: int = 200):
        if not self.is_connected:
            return []
        sql = """
        SELECT c.market,
               c.candle_date_time_utc,
               c.candle_date_time_kst,
               c.opening_price,
               c.high_price,
               c.low_price,
               c.trade_price,
               c.timestamp,
               c.candle_acc_trade_price,
               c.candle_acc_trade_volume,
               c.unit,
               c.prev_closing_price,
               c.change_price,
               c.change_rate,
               c.converted_trade_price
        FROM trading.candles AS c
        WHERE c.market = $1
        AND c.timeframe = $2
        ORDER BY time DESC
        LIMIT $3
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, market, timeframe.value, count)

        return [Candle.from_dict(r) for r in rows]

    # ========================================================================
    # ORDER OPERATIONS
    # ========================================================================

    async def save_order(self, order: Order):
        if not self.is_connected:
            return

        sql = """
                INSERT INTO trading.orders (market,
                                            uuid,
                                            side,
                                            ord_type,
                                            price,
                                            state,
                                            created_at,
                                            volume,
                                            remaining_volume,
                                            executed_volume,
                                            reserved_fee,
                                            remaining_fee,
                                            paid_fee,
                                            locked,
                                            trades_count,
                                            time_in_force,
                                            identifier,
                                            smp_type,
                                            prevented_volume,
                                            prevented_locked)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
        ON CONFLICT (uuid)
            DO UPDATE SET market           = $1,
                          uuid             = $2,
                          side             = $3,
                          ord_type         = $4,
                          price            = $5,
                          state            = $6,
                          created_at       = $7,
                          volume           = $8,
                          remaining_volume = $9,
                          executed_volume  = $10,
                          reserved_fee     = $11,
                          remaining_fee    = $12,
                          paid_fee         = $13,
                          locked           = $14,
                          trades_count     = $15,
                          time_in_force    = $16,
                          identifier       = $17,
                          smp_type         = $18,
                          prevented_volume = $19,
                          prevented_locked = $20;
        """

        async with self._pool.acquire() as conn:
            await conn.execute(
                sql,
                order.market,
                order.uuid,
                order.side.value if order.side else None,
                order.ord_type.value if order.ord_type else None,
                order.price,
                order.state.value,
                order.created_at,
                order.volume,
                order.remaining_volume,
                order.executed_volume,
                order.reserved_fee,
                order.remaining_fee,
                order.paid_fee,
                order.locked,
                order.trades_count,
                order.time_in_force.value if order.time_in_force else None,
                order.identifier,
                order.smp_type.value if order.smp_type else None,
                order.prevented_volume,
                order.prevented_locked,
            )

    async def get_order(self, uuid: str | None = None, identifier: str | None = None) -> Order | None:
        if not self.is_connected:
            return None

        if uuid is None and identifier is None:
            raise ValueError("uuid 또는 identifier 중 하나는 반드시 지정해야 합니다.")

        conditions = []
        params = []
        if uuid is not None:
            params.append(uuid)
            conditions.append(f"o.uuid = ${len(params)}")
        if identifier is not None:
            params.append(identifier)
            conditions.append(f"o.identifier = ${len(params)}")

        where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"""
        SELECT o.market,
               o.uuid,
               o.side,
               o.ord_type,
               o.price,
               o.state,
               o.created_at,
               o.volume,
               o.remaining_volume,
               o.executed_volume,
               o.reserved_fee,
               o.remaining_fee,
               o.paid_fee,
               o.locked,
               o.trades_count,
               o.time_in_force,
               o.identifier,
               o.smp_type,
               o.prevented_volume,
               o.prevented_locked
        FROM trading.orders AS o
        {where_clause};
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params)

        if row is None:
            return None

        return Order.from_dict(row)
