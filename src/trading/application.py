import asyncio
import logging
from signal import SIGINT, SIGTERM, Signals, signal
from types import FrameType

logger = logging.getLogger(__name__)


class TradingApplication:
    def __init__(self, mode: str = "development"):
        self.mode = mode
        self.engine = None
        self.logger = logger

        # shutdown 설정
        self.shutdown_event = asyncio.Event()
        self._shutdown_requested = False

        # signal handlers 설정
        signal(SIGINT, self._signal_handler)
        signal(SIGTERM, self._signal_handler)

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
