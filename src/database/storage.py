import importlib
import logging

from src.strategies.codes import SignalDirection, SignalStrength, SignalType
from src.strategies.models import TechnicalSignal
from src.trading.exchanges.upbit.codes import OrderSide, OrderType, SelfMatchPreventionType, TimeInForce
from src.trading.exchanges.upbit.codes.order_state import OrderState
from src.trading.exchanges.upbit.models import Order

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
                order.side,
                order.ord_type,
                order.price,
                order.state,
                order.created_at,
                order.volume,
                order.remaining_volume,
                order.executed_volume,
                order.reserved_fee,
                order.remaining_fee,
                order.paid_fee,
                order.locked,
                order.trades_count,
                order.time_in_force,
                order.identifier,
                order.smp_type,
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

        return Order(
            market=row["market"],
            uuid=row["uuid"],
            side=OrderSide(row["side"]),
            ord_type=OrderType(row["ord_type"]),
            price=row["price"],
            state=OrderState(row["state"]),
            created_at=row["created_at"],
            volume=row["volume"],
            remaining_volume=row["remaining_volume"],
            executed_volume=row["executed_volume"],
            reserved_fee=row["reserved_fee"],
            remaining_fee=row["remaining_fee"],
            paid_fee=row["paid_fee"],
            locked=row["locked"],
            trades_count=row["trades_count"],
            time_in_force=TimeInForce(row.get("time_in_force", None)),
            identifier=row["identifier"],
            smp_type=SelfMatchPreventionType(row.get("smp_type", None)),
            prevented_volume=row["prevented_volume"],
            prevented_locked=row["prevented_locked"],
        )

    # ========================================================================
    # TECHNICAL SIGNAL OPERATIONS
    # ========================================================================

    async def save_technical_signal(self, technical_signal: TechnicalSignal):
        if not self.is_connected:
            return

        sql = """
        INSERT INTO analytics.technical_signals (signal_name,
                                         signal_type,
                                         signal_value,
                                         signal_strength,
                                         signal_direction)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT
            DO UPDATE SET signal_name = $1,
                          signal_type = $2,
                          signal_value = $3,
                          signal_strength = $4,
                          signal_direction = $5,
                          last_updated_at = NOW();
        """

        async with self._pool.acquire() as conn:
            await conn.execute(
                sql,
                technical_signal.signal_name,
                technical_signal.signal_type,
                technical_signal.signal_value,
                technical_signal.signal_strength,
                technical_signal.signal_direction,
            )

    async def get_technical_signal(self, signal_name: str, signal_type: str):
        if not self.is_connected:
            return None

        sql = """
        SELECT t.signal_name,
               t.signal_type,
               t.signal_value,
               t.signal_strength,
               t.signal_direction,
               t.created_at,
               t.last_updated_at
        FROM analytics.technical_signals AS t
        WHERE t.signal_name = $1
          AND t.signal_type = $2;
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, signal_name, signal_type)

        if row is None:
            return None

        return TechnicalSignal(
            signal_name=row["signal_name"],
            signal_type=SignalType(row["signal_type"]),
            signal_value=row["signal_value"],
            signal_strength=SignalStrength(row["signal_strength"]),
            signal_direction=SignalDirection(row["signal_direction"]),
        )
