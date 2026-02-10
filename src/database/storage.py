import importlib
import logging

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
