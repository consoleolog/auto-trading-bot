import asyncio
import logging
from signal import SIGINT, SIGTERM, Signals, signal
from types import FrameType

from src.config import ConfigManager
from src.trading.core import TradingEngine

logger = logging.getLogger(__name__)


class TradingApplication:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.mode = config.get("app.mode") or "development"
        self.logger = logger

        # Components (initialized in setup())
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
            # 1. Initialize Trading Engine
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
        self.logger.info("Initiating graceful shutdown...")
        try:
            if self.engine:
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
