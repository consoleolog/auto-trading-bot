import hashlib
import importlib
import logging
import uuid
from decimal import Decimal
from urllib.parse import unquote, urlencode

import jwt

from src.trading.exchanges.upbit import error_handler
from src.trading.exchanges.upbit.codes import OrderSide, OrderType, SelfMatchPreventionType, Timeframe, TimeInForce
from src.trading.exchanges.upbit.models import Candle, Order, Ticker
from src.utils import rate_limit, retry_async

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

    # ========================================================================
    # CANDLE DATA
    # ========================================================================

    @rate_limit(calls=9)
    @retry_async(max_retries=3)
    async def get_candles(
        self, market: str, timeframe: Timeframe = Timeframe.DAY, count: int = 200, to: str | None = None
    ) -> list[Candle]:
        """
        캔들 조회 (괴거 -> 최신 순)

        Args:
            market: 조회하고자 하는 페어(거래쌍)
            timeframe: 조회하고자 하는 기간
            count: 조회하고자 하는 캔들의 개수. 최대 200개의 캔들 조회를 지원하며, 기본값은 200입니다.
            to: 조회 기간의 종료 시각.
                지정한 시각 이전 캔들을 조회합니다. 미지정시 요청 시각을 기준으로 최근 캔들이 조회됩니다.

                ISO 8601 형식의 datetime으로 아래와 같이 요청 할 수 있습니다.
                실제 요청 시에는 공백 및 특수문자가 정상적으로 처리되도록 URL 인코딩을 수행해야 합니다.
                [예시]
                2025-06-24T04:56:53Z
                2025-06-24 04:56:53
                2025-06-24T13:56:53+09:00
        """
        params = {"market": market, "count": count}
        if to:
            params["to"] = to
        response = await self._request("GET", f"/candles/{timeframe.value}", params=params)
        # response 는 최신 -> 과거 데이터이기 때문에 슬라이싱으로 과거 -> 최신으로 정렬
        candles = [Candle.from_response(r) for r in response[::-1]]
        return candles

    @rate_limit(calls=9)
    @retry_async(max_retries=3)
    async def get_tickers(self, markets: list[str]) -> list[Ticker]:
        """
        지정한 페어의 현재가를 조회합니다.
        요청 시점 기준으로 해당 페어의 티커 스냅샷이 반환됩니다.

        Args:
            markets: 조회하고자 하는 페어(거래쌍) 목록.
        """
        params = {"markets": ",".join(markets)}
        response = await self._request("GET", "/ticker", params=params)
        tickers = [Ticker.from_response(r) for r in response]
        return tickers

    async def get_ticker(self, market: str) -> Ticker:
        """
        현재가 조회

        Args:
            market: 조회하고자 하는 페어 코드
        """
        tickers = await self.get_tickers(markets=[market])
        return tickers[0]

    # ========================================================================
    # ORDER OPERATIONS
    # ========================================================================

    @rate_limit(calls=7)
    @retry_async(max_retries=2)
    async def create_order(
        self,
        market: str,
        side: OrderSide,
        ord_type: OrderType,
        volume: Decimal | None = None,
        price: Decimal | None = None,
        time_in_force: TimeInForce | None = None,
        smp_type: SelfMatchPreventionType | None = None,
        identifier: str | None = None,
    ) -> Order:
        params = {"market": market, "side": side.value, "ord_type": ord_type.value}

        if volume:
            params["volume"] = volume.to_eng_string()
        if price:
            params["price"] = price.to_eng_string()
        if time_in_force:
            params["time_in_force"] = time_in_force.value
            if time_in_force == TimeInForce.POST_ONLY and smp_type is not None:
                raise ValueError("`post_only` 옵션은 `smp_type` 옵션과 함께 사용할 수 없습니다.")
        if identifier:
            params["identifier"] = identifier
        if smp_type:
            params["smp_type"] = smp_type.value

        endpoint = f"/orders{'/test' if self.test else ''}"

        response = await self._request("POST", endpoint, params, signed=True)
        order = Order.from_response(response)
        return order

    async def limit_order(
        self,
        market: str,
        side: OrderSide,
        volume: Decimal | None = None,
        price: Decimal | None = None,
        time_in_force: TimeInForce | None = None,
        smp_type: SelfMatchPreventionType | None = None,
        identifier: str | None = None,
    ) -> Order:
        """지정가 매도 매수 주문"""
        return await self.create_order(
            market,
            side,
            ord_type=OrderType.LIMIT,
            volume=volume,
            price=price,
            time_in_force=time_in_force,
            smp_type=smp_type,
            identifier=identifier,
        )

    async def market_order(
        self,
        market: str,
        volume: Decimal,
        smp_type: SelfMatchPreventionType | None = None,
        identifier: str | None = None,
    ) -> Order:
        """시장가 매도 주문"""
        return await self.create_order(
            market,
            side=OrderSide.ASK,
            ord_type=OrderType.MARKET,
            volume=volume,
            smp_type=smp_type,
            identifier=identifier,
        )

    async def price_order(
        self,
        market: str,
        price: Decimal,
        smp_type: SelfMatchPreventionType | None = None,
        identifier: str | None = None,
    ) -> Order:
        """시장가 매수 주문"""
        return await self.create_order(
            market, side=OrderSide.BID, ord_type=OrderType.PRICE, price=price, smp_type=smp_type, identifier=identifier
        )

    async def best_order(
        self,
        market: str,
        side: OrderSide,
        time_in_force: TimeInForce,
        price: Decimal | None = None,
        volume: Decimal | None = None,
        smp_type: SelfMatchPreventionType | None = None,
        identifier: str | None = None,
    ) -> Order:
        """최유리 지정가 매도 매수 주문"""
        if time_in_force is None:
            raise ValueError("최유리 지정가 주문에서는 `time_in_force` 는 필수값 입니다!")

        return await self.create_order(
            market,
            side,
            ord_type=OrderType.BEST,
            price=price,
            volume=volume,
            time_in_force=time_in_force,
            smp_type=smp_type,
            identifier=identifier,
        )
