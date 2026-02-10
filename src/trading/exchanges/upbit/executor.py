import hashlib
import importlib
import logging
import uuid
from urllib.parse import unquote, urlencode

import jwt

from src.trading.exchanges.upbit import error_handler

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

    # ========================================================================
    # REQUEST HELPERS
    # ========================================================================

    def _sign_request(self, params: dict | None = None) -> str:
        payload = {
            "access_key": self.api_key,
            "nonce": str(uuid.uuid4()),
        }
        if params:
            query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")
            m = hashlib.sha512()
            m.update(query_string)
            query_hash = m.hexdigest()

            payload["query_hash"] = query_hash
            payload["query_hash_alg"] = "SHA512"

        return jwt.encode(payload, self.api_secret, algorithm="HS256")

    @error_handler
    async def _request(
        self, method: str, endpoint: str, params: dict | None = None, headers: dict | None = None, signed: bool = False
    ) -> aiohttp.client.ClientResponse:
        await self._ensure_session()

        params = params or {}
        headers = headers or {}
        if signed:
            headers["Authorization"] = f"Bearer {self._sign_request(params)}"

        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                return await self._session.get(url, headers=headers, params=params)
            elif method == "POST":
                return await self._session.post(url, headers=headers, json=params)
            elif method == "DELETE":
                return await self._session.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unknown method: {method}")
        except aiohttp.ClientError as exception:
            logger.error(f"Request Failed: {exception}")
            raise
