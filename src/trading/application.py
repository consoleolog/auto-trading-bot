import asyncio
import logging
from datetime import datetime, timedelta
from signal import SIGINT, SIGTERM, Signals, signal
from types import FrameType

from src.config import ConfigManager
from src.database.cache import RedisCache
from src.database.storage import DataStorage
from src.strategies import RegimeDetector
from src.strategies.codes import MarketRegime
from src.trading.exchanges.upbit import UpbitExecutor
from src.trading.exchanges.upbit.codes import Timeframe

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
        self._regime_detector: RegimeDetector | None = None

        # Runtime state
        self._running = False

        # Trading Infos
        self.markets: list[str] = self.config.get("trading.markets") or ["USDT-BTC", "USDT-ETH"]
        self.timeframes: list[Timeframe] = [Timeframe(t) for t in self.config.get("trading.timeframes")] or [
            Timeframe.HOUR,
            Timeframe.DAY,
        ]

        # Cooldowns (market:timeframe -> next_trade_time)
        self.market_cooldowns: dict[str, datetime] = {}
        self.cooldown_durations = {
            Timeframe.SECOND: timedelta(seconds=1),
            Timeframe.MINUTE_1: timedelta(minutes=1),
            Timeframe.MINUTE_3: timedelta(minutes=3),
            Timeframe.MINUTE_5: timedelta(minutes=5),
            Timeframe.MINUTE_10: timedelta(minutes=10),
            Timeframe.MINUTE_15: timedelta(minutes=15),
            Timeframe.HALF_HOUR: timedelta(minutes=30),
            Timeframe.HOUR: timedelta(hours=1),
            Timeframe.HOUR_4: timedelta(hours=4),
            Timeframe.DAY: timedelta(days=1),
            Timeframe.WEEK: timedelta(weeks=1),
            Timeframe.MONTH: timedelta(weeks=4),
            Timeframe.YEAR: timedelta(days=365),
        }

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
            self.logger.info(f"✅ Exchange adapter initialized (mode={self.mode})")

            # 4. Initialize Regime Detector
            self._regime_detector = RegimeDetector(
                config=self.config.get("strategies.regime_detector"), default_regime=MarketRegime.UNKNOWN
            )
            logger.info("✅ Regime detector initialized")

            self.logger.info("🚀 TradingApplication setup complete!")
            return True
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}", exc_info=True)
            return False

    async def start(self):
        if self._running:
            self.logger.warning("TradingApplication already running!")
            return

        if self._storage is None:
            success = await self.setup()
            if not success:
                raise RuntimeError("TradingApplication setup failed!")

        self._running = True

        try:
            tasks = [asyncio.create_task(self._shutdown_monitor())]
            for timeframe in self.timeframes:
                for market in self.markets:
                    task = asyncio.create_task(
                        self._trading_cycle(market, timeframe), name=f"trading_{market}_{timeframe.value}"
                    )
                    tasks.append(task)
                    self.logger.info(f"✅ Started trading task: {market}:{timeframe.value}")

            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                if not task.cancelled() and task.exception():
                    self.logger.error(f"Task failed: {task.exception()}")

            self._running = False
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        except Exception as e:
            self.logger.error(f"Critical error in main loop: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def _trading_cycle(self, market: str, timeframe: Timeframe):
        key = f"{market}:{timeframe.value}"
        cooldown_seconds = self.cooldown_durations[timeframe].total_seconds()

        while self._running:
            try:
                # Execute trading logic
                self.logger.info(f"⚡ Executing: {key}")

                # 1. Loading Candles
                candles = await self._exchange.get_candles(market, timeframe)

                # 2. Get Market Regime
                regime = self._regime_detector.detect(candles)
                self.logger.info(f"Current regime: {regime.value}")

                # Sleep until next execution
                self.logger.debug(f"💤 {key}: Sleeping for {cooldown_seconds}s")
                await asyncio.sleep(cooldown_seconds)
            except asyncio.CancelledError:
                # Task was cancelled (likely due to config change or shutdown)
                self.logger.info(f"🛑 Trading task cancelled: {key}")
                break
            except Exception as e:
                self.logger.error(f"❌ Error in trading task {key}: {e}", exc_info=True)
                await asyncio.sleep(min(60.0, cooldown_seconds))

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
