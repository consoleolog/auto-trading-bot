import importlib
import logging

try:
    aiohttp = importlib.import_module("aiohttp")
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger(__name__)


class UpbitExecutor:
    def __init__(self, api_key: str, api_secret: str, test: bool = True):
        self.base_url = "https://api.upbit.com/v1"

        self.api_key = api_key
        self.api_secret = api_secret
        self.test = test

        self._session: aiohttp.ClientSession | None = None

    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================

    async def connect(self):
        if not HAS_AIOHTTP:
            logger.error("aiohttp is not installed")
            return

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            logger.info("Connected to Upbit")

    async def disconnect(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("Disconnected from Upbit")

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            await self.connect()
