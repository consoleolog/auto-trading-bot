import asyncio
import logging
from signal import SIGINT, SIGTERM, Signals, signal
from types import FrameType

from src.config import ConfigManager
from src.database import DataStorage
from src.database.cache import RedisCache
from src.trading.core import TradingEngine
from src.trading.exchanges.upbit import UpbitExecutor

logger = logging.getLogger(__name__)


class TradingApplication:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.mode = config.get("app.mode") or "development"
        self.logger = logger

        # Components (initialized in setup())
        self._storage: DataStorage | None = None
        self._cache: RedisCache | None = None
        self._exchange: UpbitExecutor | None = None
        self._engine: TradingEngine | None = None

        # Runtime state
        self._running = False

        # shutdown 설정
        self.shutdown_event = asyncio.Event()
        self._shutdown_requested = False

        # signal handlers 설정
        signal(SIGINT, self._signal_handler)
        signal(SIGTERM, self._signal_handler)

    async def setup(self) -> bool:
        self.logger.info("Setting up trading application components...")
        try:
            # 1. Initialize Storage (TimescaleDB with asyncpg)
            self._storage = DataStorage(
                host=self.config.get("database.host"),
                port=int(self.config.get("database.port")),
                database=self.config.get("database.database"),
                user=self.config.get("database.user"),
                password=self.config.get("database.password"),
            )
            await self._storage.connect()
            self.logger.info("✅ TimescaleDB storage initialized (asyncpg)")

            # Health check
            if not await self._storage.health_check():
                raise RuntimeError("Database health check failed")

            # 2. Initialize Cache (Redis)
            self._cache = RedisCache(
                host=self.config.get("redis.host"),
                port=int(self.config.get("redis.port")),
                password=self.config.get("redis.password"),
                db=int(self.config.get("redis.database")),
            )
            await self._cache.connect()
            self.logger.info("✅ Redis cache initialized")

            # 3. Initialize Exchange Adapter
            self._exchange = UpbitExecutor(
                api_key=self.config.get("upbit.api_key"),
                api_secret=self.config.get("upbit.api_secret"),
                test=(self.mode == "development"),
            )
            await self._exchange.connect()
            self.logger.info(f"✅ Exchange adapter initialized (mode={self.mode.value})")

            # 4. Initialize Trading Engine
            self._engine = TradingEngine(
                mode=self.mode,
                markets=self.config.get("trading.markets"),
                timeframes=self.config.get("trading.timeframes"),
            )
            self.logger.info(f"✅ TradingEngine initialized (mode={self.mode})")

            self.logger.info("🚀 TradingApplication setup complete!")
            return True
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}", exc_info=True)
            return False

    async def start(self):
        if self._running:
            self.logger.warning("TradingApplication already running!")
            return

        if self._engine is None:
            success = await self.setup()
            if not success:
                raise RuntimeError("TradingApplication setup failed!")

        self._running = True

        try:
            # TODO: Start main loop

            tasks = [
                # asyncio.create_task(self.engine)
                asyncio.create_task(self._shutdown_monitor())
            ]

            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

            for task in done:
                if task.exception():
                    self.logger.error(f"Task failed: {task.exception()}")

            for task in pending:
                task.cancel()
        except Exception as e:
            self.logger.error(f"Critical error in main loop: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def _shutdown_monitor(self):
        """Monitor for shutdown signal"""
        await self.shutdown_event.wait()
        self.logger.info("Shutdown signal received")

    async def shutdown(self):
        """Graceful shutdown"""
        if not self._running:
            return
        self.logger.info("Initiating graceful shutdown...")
        self._running = False

        try:
            if self._storage:
                await self._storage.disconnect()
            if self._cache:
                await self._cache.disconnect()
            if self._exchange:
                await self._exchange.disconnect()
            if self._engine:
                # TODO: engine shutdown or disconnect
                pass
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def _signal_handler(self, signum: int | Signals, _: FrameType | None) -> None:
        """Graceful shutdown 을 위한 handler

        첫 번째 시그널: shutdown_event 를 설정하여 graceful shutdown 시작
        두 번째 시그널: 즉시 강제 종료 (SystemExit)
        """
        sig_name = Signals(signum).name

        if self._shutdown_requested:
            self.logger.warning(f"Received {sig_name} again, forcing immediate shutdown")
            raise SystemExit(1)

        self._shutdown_requested = True
        self.logger.warning(f"Received {sig_name}, starting graceful shutdown")
        self.shutdown_event.set()
