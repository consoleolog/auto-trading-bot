import hashlib
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import unquote, urlencode

import jwt
import pytest

from src.trading.exchanges.upbit.codes import (
    OrderSide,
    OrderType,
    PriceChangeState,
    SelfMatchPreventionType,
    Timeframe,
    TimeInForce,
)
from src.trading.exchanges.upbit.executor import UpbitExecutor

# ============= Fixtures =============


@pytest.fixture
def executor():
    """기본 UpbitExecutor 인스턴스를 생성한다."""
    return UpbitExecutor(api_key="test-key", api_secret="test-secret-key-that-is-long-enough-for-hs256")


@pytest.fixture
def mock_session():
    """테스트용 aiohttp.ClientSession mock을 생성한다."""
    session = AsyncMock()
    session.closed = False
    return session


# ============= __init__ =============


class TestInit:
    def test_stores_api_key(self, executor: UpbitExecutor):
        """api_key가 인스턴스 속성으로 저장된다."""
        assert executor.api_key == "test-key"

    def test_stores_api_secret(self, executor: UpbitExecutor):
        """api_secret이 인스턴스 속성으로 저장된다."""
        assert executor.api_secret == "test-secret-key-that-is-long-enough-for-hs256"

    def test_default_test_mode_is_true(self, executor: UpbitExecutor):
        """기본 test 모드가 True이다."""
        assert executor.test is True

    def test_custom_test_mode(self):
        """test 모드를 False로 설정할 수 있다."""
        executor = UpbitExecutor(api_key="k", api_secret="s", test=False)
        assert executor.test is False

    def test_base_url_is_upbit_api(self, executor: UpbitExecutor):
        """base_url이 Upbit API v1 주소이다."""
        assert executor.base_url == "https://api.upbit.com/v1"

    def test_session_is_none_initially(self, executor: UpbitExecutor):
        """초기 _session이 None이다."""
        assert executor._session is None


# ============= connect =============


class TestConnect:
    @pytest.mark.asyncio
    async def test_creates_session(self, executor: UpbitExecutor):
        """세션이 없을 때 connect 호출 시 ClientSession이 생성된다."""
        await executor.connect()

        assert executor._session is not None

    @pytest.mark.asyncio
    async def test_skips_if_session_already_open(self, executor: UpbitExecutor, mock_session):
        """이미 열린 세션이 있으면 새로 생성하지 않는다."""
        executor._session = mock_session

        await executor.connect()

        assert executor._session is mock_session

    @pytest.mark.asyncio
    async def test_reconnects_if_session_closed(self, executor: UpbitExecutor, mock_session):
        """세션이 닫혀 있으면 새로 생성한다."""
        mock_session.closed = True
        executor._session = mock_session

        await executor.connect()

        assert executor._session is not mock_session
        assert executor._session is not None

    @pytest.mark.asyncio
    async def test_logs_connection(self, executor: UpbitExecutor, caplog):
        """연결 시 로그가 출력된다."""
        with caplog.at_level("INFO"):
            await executor.connect()

        assert "Connected to Upbit" in caplog.text

    @pytest.mark.asyncio
    async def test_returns_none_without_aiohttp(self, executor: UpbitExecutor, caplog):
        """aiohttp가 없으면 에러 로그를 남기고 반환한다."""
        with patch("src.trading.exchanges.upbit.executor.HAS_AIOHTTP", False), caplog.at_level("ERROR"):
            await executor.connect()

        assert executor._session is None
        assert "aiohttp is not installed" in caplog.text


# ============= disconnect =============


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_closes_open_session(self, executor: UpbitExecutor, mock_session):
        """열린 세션을 닫고 None으로 설정한다."""
        executor._session = mock_session

        await executor.disconnect()

        mock_session.close.assert_awaited_once()
        assert executor._session is None

    @pytest.mark.asyncio
    async def test_logs_disconnection(self, executor: UpbitExecutor, mock_session, caplog):
        """연결 해제 시 로그가 출력된다."""
        executor._session = mock_session

        with caplog.at_level("INFO"):
            await executor.disconnect()

        assert "Disconnected from Upbit" in caplog.text

    @pytest.mark.asyncio
    async def test_noop_if_session_is_none(self, executor: UpbitExecutor):
        """세션이 None이면 아무 동작도 하지 않는다."""
        await executor.disconnect()

        assert executor._session is None

    @pytest.mark.asyncio
    async def test_noop_if_session_already_closed(self, executor: UpbitExecutor, mock_session):
        """세션이 이미 닫혀 있으면 아무 동작도 하지 않는다."""
        mock_session.closed = True
        executor._session = mock_session

        await executor.disconnect()

        mock_session.close.assert_not_awaited()


# ============= _ensure_session =============


class TestEnsureSession:
    @pytest.mark.asyncio
    async def test_calls_connect_when_no_session(self, executor: UpbitExecutor):
        """세션이 없으면 connect를 호출하여 세션을 생성한다."""
        await executor._ensure_session()

        assert executor._session is not None

    @pytest.mark.asyncio
    async def test_calls_connect_when_session_closed(self, executor: UpbitExecutor, mock_session):
        """세션이 닫혀 있으면 connect를 호출한다."""
        mock_session.closed = True
        executor._session = mock_session

        await executor._ensure_session()

        assert executor._session is not mock_session

    @pytest.mark.asyncio
    async def test_skips_connect_when_session_open(self, executor: UpbitExecutor, mock_session):
        """세션이 열려 있으면 connect를 호출하지 않는다."""
        executor._session = mock_session

        await executor._ensure_session()

        assert executor._session is mock_session


# ============= _sign_request =============


class TestSignRequest:
    def test_returns_valid_jwt(self, executor: UpbitExecutor):
        """유효한 JWT 토큰을 반환한다."""
        token = executor._sign_request()
        decoded = jwt.decode(token, "test-secret-key-that-is-long-enough-for-hs256", algorithms=["HS256"])

        assert decoded["access_key"] == "test-key"
        assert "nonce" in decoded

    def test_jwt_without_params_has_no_query_hash(self, executor: UpbitExecutor):
        """params가 없으면 query_hash가 포함되지 않는다."""
        token = executor._sign_request()
        decoded = jwt.decode(token, "test-secret-key-that-is-long-enough-for-hs256", algorithms=["HS256"])

        assert "query_hash" not in decoded
        assert "query_hash_alg" not in decoded

    def test_jwt_with_params_includes_query_hash(self, executor: UpbitExecutor):
        """params가 있으면 query_hash와 query_hash_alg가 포함된다."""
        params = {"market": "KRW-BTC"}
        token = executor._sign_request(params)
        decoded = jwt.decode(token, "test-secret-key-that-is-long-enough-for-hs256", algorithms=["HS256"])

        assert "query_hash" in decoded
        assert decoded["query_hash_alg"] == "SHA512"

    def test_query_hash_matches_sha512_of_params(self, executor: UpbitExecutor):
        """query_hash가 params의 SHA512 해시와 일치한다."""
        params = {"market": "KRW-BTC", "count": "10"}
        token = executor._sign_request(params)
        decoded = jwt.decode(token, "test-secret-key-that-is-long-enough-for-hs256", algorithms=["HS256"])

        query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")
        expected_hash = hashlib.sha512(query_string).hexdigest()

        assert decoded["query_hash"] == expected_hash

    def test_nonce_is_unique_per_call(self, executor: UpbitExecutor):
        """호출할 때마다 nonce가 다르다."""
        token1 = executor._sign_request()
        token2 = executor._sign_request()

        decoded1 = jwt.decode(token1, "test-secret-key-that-is-long-enough-for-hs256", algorithms=["HS256"])
        decoded2 = jwt.decode(token2, "test-secret-key-that-is-long-enough-for-hs256", algorithms=["HS256"])

        assert decoded1["nonce"] != decoded2["nonce"]

    def test_empty_params_treated_as_no_params(self, executor: UpbitExecutor):
        """빈 dict params는 query_hash를 포함하지 않는다."""
        token = executor._sign_request({})
        decoded = jwt.decode(token, "test-secret-key-that-is-long-enough-for-hs256", algorithms=["HS256"])

        assert "query_hash" not in decoded


# ============= _request =============


def _make_response(status: int, json_data: dict) -> AsyncMock:
    """테스트용 aiohttp 응답 mock을 생성한다."""
    response = AsyncMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data)
    response.release = MagicMock()
    return response


class TestRequest:
    @pytest.mark.asyncio
    async def test_get_request(self, executor: UpbitExecutor, mock_session):
        """GET 요청이 올바른 URL과 파라미터로 호출된다."""
        executor._session = mock_session
        mock_session.get.return_value = _make_response(200, {"result": "ok"})

        result = await executor._request("GET", "/orders", params={"market": "KRW-BTC"})

        mock_session.get.assert_awaited_once()
        call_kwargs = mock_session.get.call_args
        assert call_kwargs[0][0] == "https://api.upbit.com/v1/orders"
        assert call_kwargs[1]["params"] == {"market": "KRW-BTC"}
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_post_request(self, executor: UpbitExecutor, mock_session):
        """POST 요청이 json 파라미터로 호출된다."""
        executor._session = mock_session
        mock_session.post.return_value = _make_response(200, {"uuid": "abc"})

        result = await executor._request("POST", "/orders", params={"market": "KRW-BTC"})

        mock_session.post.assert_awaited_once()
        call_kwargs = mock_session.post.call_args
        assert call_kwargs[1]["json"] == {"market": "KRW-BTC"}
        assert result == {"uuid": "abc"}

    @pytest.mark.asyncio
    async def test_delete_request(self, executor: UpbitExecutor, mock_session):
        """DELETE 요청이 올바르게 호출된다."""
        executor._session = mock_session
        mock_session.delete.return_value = _make_response(200, {"uuid": "abc"})

        result = await executor._request("DELETE", "/order", params={"uuid": "abc"})

        mock_session.delete.assert_awaited_once()
        assert result == {"uuid": "abc"}

    @pytest.mark.asyncio
    async def test_unknown_method_raises_value_error(self, executor: UpbitExecutor, mock_session):
        """지원하지 않는 HTTP 메서드는 ValueError를 발생시킨다."""
        executor._session = mock_session

        with pytest.raises(ValueError, match="Unknown method: PATCH"):
            await executor._request("PATCH", "/orders")

    @pytest.mark.asyncio
    async def test_signed_request_adds_authorization_header(self, executor: UpbitExecutor, mock_session):
        """signed=True이면 Authorization 헤더가 추가된다."""
        executor._session = mock_session
        mock_session.get.return_value = _make_response(200, {"data": "ok"})

        await executor._request("GET", "/accounts", signed=True)

        call_kwargs = mock_session.get.call_args
        auth_header = call_kwargs[1]["headers"]["Authorization"]
        assert auth_header.startswith("Bearer ")

        token = auth_header.removeprefix("Bearer ")
        decoded = jwt.decode(token, "test-secret-key-that-is-long-enough-for-hs256", algorithms=["HS256"])
        assert decoded["access_key"] == "test-key"

    @pytest.mark.asyncio
    async def test_unsigned_request_has_no_authorization(self, executor: UpbitExecutor, mock_session):
        """signed=False이면 Authorization 헤더가 없다."""
        executor._session = mock_session
        mock_session.get.return_value = _make_response(200, {"data": "ok"})

        await executor._request("GET", "/ticker")

        call_kwargs = mock_session.get.call_args
        assert "Authorization" not in call_kwargs[1]["headers"]

    @pytest.mark.asyncio
    async def test_ensures_session_before_request(self, executor: UpbitExecutor):
        """요청 전에 _ensure_session이 호출된다."""
        assert executor._session is None

        with patch.object(executor, "_ensure_session", new_callable=AsyncMock) as mock_ensure:
            mock_ensure.side_effect = Exception("stop here")

            with pytest.raises(Exception, match="stop here"):
                await executor._request("GET", "/test")

            mock_ensure.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_default_params_and_headers_are_empty_dict(self, executor: UpbitExecutor, mock_session):
        """params와 headers의 기본값이 빈 dict으로 처리된다."""
        executor._session = mock_session
        mock_session.get.return_value = _make_response(200, {})

        await executor._request("GET", "/test")

        call_kwargs = mock_session.get.call_args
        assert call_kwargs[1]["params"] == {}
        assert call_kwargs[1]["headers"] == {}

    @pytest.mark.asyncio
    async def test_client_error_is_logged_and_reraised(self, executor: UpbitExecutor, mock_session, caplog):
        """aiohttp.ClientError 발생 시 로그를 남기고 다시 발생시킨다."""
        import aiohttp

        executor._session = mock_session
        mock_session.get.side_effect = aiohttp.ClientError("connection failed")

        with caplog.at_level("ERROR"), pytest.raises(aiohttp.ClientError):
            await executor._request("GET", "/test")

        assert "Request Failed" in caplog.text


# ============= get_candles =============

SAMPLE_CANDLE_RESPONSE = {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-06-24T00:00:00",
    "candle_date_time_kst": "2025-06-24T09:00:00",
    "opening_price": 50000000,
    "high_price": 51000000,
    "low_price": 49000000,
    "trade_price": 50500000,
    "timestamp": 1719187200000,
    "candle_acc_trade_price": 1000000000,
    "candle_acc_trade_volume": 20.5,
}


class TestGetCandles:
    @pytest.mark.asyncio
    async def test_returns_candle_list(self, executor: UpbitExecutor):
        """응답 데이터를 Candle 객체 리스트로 변환하여 반환한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [SAMPLE_CANDLE_RESPONSE.copy()]

            result = await executor.get_candles("KRW-BTC")

        assert len(result) == 1
        assert result[0].market == "KRW-BTC"
        assert result[0].trade_price == Decimal("50500000")

    @pytest.mark.asyncio
    async def test_default_timeframe_is_day(self, executor: UpbitExecutor):
        """기본 timeframe이 DAY이다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_candles("KRW-BTC")

        mock_req.assert_awaited_once()
        assert mock_req.call_args[0][1] == "/candles/days"

    @pytest.mark.asyncio
    async def test_custom_timeframe(self, executor: UpbitExecutor):
        """지정한 timeframe의 endpoint로 요청한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_candles("KRW-BTC", timeframe=Timeframe.MINUTE_1)

        assert mock_req.call_args[0][1] == f"/candles/{Timeframe.MINUTE_1.value}"

    @pytest.mark.asyncio
    async def test_default_count_is_200(self, executor: UpbitExecutor):
        """기본 count가 200이다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_candles("KRW-BTC")

        params = mock_req.call_args[1]["params"]
        assert params["count"] == 200

    @pytest.mark.asyncio
    async def test_custom_count(self, executor: UpbitExecutor):
        """지정한 count가 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_candles("KRW-BTC", count=50)

        params = mock_req.call_args[1]["params"]
        assert params["count"] == 50

    @pytest.mark.asyncio
    async def test_market_in_params(self, executor: UpbitExecutor):
        """market이 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_candles("KRW-ETH")

        params = mock_req.call_args[1]["params"]
        assert params["market"] == "KRW-ETH"

    @pytest.mark.asyncio
    async def test_to_param_included_when_specified(self, executor: UpbitExecutor):
        """to를 지정하면 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_candles("KRW-BTC", to="2025-06-24T00:00:00Z")

        params = mock_req.call_args[1]["params"]
        assert params["to"] == "2025-06-24T00:00:00Z"

    @pytest.mark.asyncio
    async def test_to_param_excluded_when_none(self, executor: UpbitExecutor):
        """to를 지정하지 않으면 params에 포함되지 않는다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_candles("KRW-BTC")

        params = mock_req.call_args[1]["params"]
        assert "to" not in params

    @pytest.mark.asyncio
    async def test_uses_get_method(self, executor: UpbitExecutor):
        """GET 메서드로 요청한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_candles("KRW-BTC")

        assert mock_req.call_args[0][0] == "GET"

    @pytest.mark.asyncio
    async def test_multiple_candles(self, executor: UpbitExecutor):
        """여러 개의 캔들 응답을 모두 Candle 객체로 변환한다."""
        first = SAMPLE_CANDLE_RESPONSE.copy()
        first["trade_price"] = 50500000

        second = SAMPLE_CANDLE_RESPONSE.copy()
        second["trade_price"] = 51000000

        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [first, second]
            result = await executor.get_candles("KRW-BTC")

        assert len(result) == 2
        assert result[0].trade_price == Decimal("51000000")
        assert result[1].trade_price == Decimal("50500000")


# ============= get_tickers =============

SAMPLE_TICKER_RESPONSE = {
    "market": "KRW-BTC",
    "trade_date": "20250624",
    "trade_time": "153045",
    "trade_date_kst": "20250625",
    "trade_time_kst": "003045",
    "trade_timestamp": 1719244245000,
    "opening_price": 50000000,
    "high_price": 51000000,
    "low_price": 49000000,
    "trade_price": 50500000,
    "prev_closing_price": 49800000,
    "change": "RISE",
    "change_price": 700000,
    "change_rate": 0.014,
    "response": 0.014,
    "signed_change_price": 700000,
    "signed_change_rate": 0.014,
    "trade_volume": 0.5,
    "acc_trade_price": 1000000000,
    "acc_trade_price_24h": 2500000000,
    "acc_trade_volume": 20.5,
    "acc_trade_volume_24h": 50.3,
    "highest_52_week_price": 60000000,
    "highest_52_week_date": "2025-03-15",
    "lowest_52_week_price": 30000000,
    "lowest_52_week_date": "2024-09-10",
    "timestamp": 1719244245000,
}


class TestGetTickers:
    @pytest.mark.asyncio
    async def test_returns_ticker_list(self, executor: UpbitExecutor):
        """응답 데이터를 Ticker 객체 리스트로 변환하여 반환한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [SAMPLE_TICKER_RESPONSE.copy()]

            result = await executor.get_tickers(["KRW-BTC"])

        assert len(result) == 1
        assert result[0].market == "KRW-BTC"
        assert result[0].trade_price == Decimal("50500000")

    @pytest.mark.asyncio
    async def test_markets_joined_with_comma(self, executor: UpbitExecutor):
        """markets 리스트가 쉼표로 결합되어 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_tickers(["KRW-BTC", "KRW-ETH"])

        params = mock_req.call_args[1]["params"]
        assert params["markets"] == "KRW-BTC,KRW-ETH"

    @pytest.mark.asyncio
    async def test_single_market_in_params(self, executor: UpbitExecutor):
        """단일 market이 쉼표 없이 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_tickers(["KRW-BTC"])

        params = mock_req.call_args[1]["params"]
        assert params["markets"] == "KRW-BTC"

    @pytest.mark.asyncio
    async def test_uses_get_method(self, executor: UpbitExecutor):
        """GET 메서드로 요청한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_tickers(["KRW-BTC"])

        assert mock_req.call_args[0][0] == "GET"

    @pytest.mark.asyncio
    async def test_calls_ticker_endpoint(self, executor: UpbitExecutor):
        """/ticker 엔드포인트로 요청한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_tickers(["KRW-BTC"])

        assert mock_req.call_args[0][1] == "/ticker"

    @pytest.mark.asyncio
    async def test_multiple_tickers(self, executor: UpbitExecutor):
        """여러 개의 티커 응답을 모두 Ticker 객체로 변환한다."""
        first = SAMPLE_TICKER_RESPONSE.copy()
        first["market"] = "KRW-BTC"
        first["trade_price"] = 50500000

        second = SAMPLE_TICKER_RESPONSE.copy()
        second["market"] = "KRW-ETH"
        second["trade_price"] = 4000000

        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [first, second]

            result = await executor.get_tickers(["KRW-BTC", "KRW-ETH"])

        assert len(result) == 2
        assert result[0].market == "KRW-BTC"
        assert result[0].trade_price == Decimal("50500000")
        assert result[1].market == "KRW-ETH"
        assert result[1].trade_price == Decimal("4000000")

    @pytest.mark.asyncio
    async def test_converts_change_to_enum(self, executor: UpbitExecutor):
        """change 필드가 PriceChangeState enum으로 변환된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [SAMPLE_TICKER_RESPONSE.copy()]

            result = await executor.get_tickers(["KRW-BTC"])

        assert result[0].change == PriceChangeState.RISE


# ============= get_ticker =============


class TestGetTicker:
    @pytest.mark.asyncio
    async def test_returns_single_ticker(self, executor: UpbitExecutor):
        """단일 Ticker 객체를 반환한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [SAMPLE_TICKER_RESPONSE.copy()]

            result = await executor.get_ticker("KRW-BTC")

        assert result.market == "KRW-BTC"
        assert result.trade_price == Decimal("50500000")

    @pytest.mark.asyncio
    async def test_delegates_to_get_tickers(self, executor: UpbitExecutor):
        """get_tickers를 호출하여 결과를 가져온다."""
        with patch.object(executor, "get_tickers", new_callable=AsyncMock) as mock_get_tickers:
            mock_ticker = MagicMock()
            mock_get_tickers.return_value = [mock_ticker]

            result = await executor.get_ticker("KRW-ETH")

        mock_get_tickers.assert_awaited_once_with(markets=["KRW-ETH"])
        assert result is mock_ticker

    @pytest.mark.asyncio
    async def test_returns_first_element(self, executor: UpbitExecutor):
        """get_tickers 결과의 첫 번째 요소를 반환한다."""
        with patch.object(executor, "get_tickers", new_callable=AsyncMock) as mock_get_tickers:
            first = MagicMock()
            second = MagicMock()
            mock_get_tickers.return_value = [first, second]

            result = await executor.get_ticker("KRW-BTC")

        assert result is first


# ============= create_order =============

SAMPLE_ORDER_RESPONSE = {
    "market": "KRW-BTC",
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "side": "bid",
    "ord_type": "limit",
    "price": "50000000",
    "state": "wait",
    "created_at": "2025-06-24T13:56:53+09:00",
    "volume": "0.001",
    "remaining_volume": "0.001",
    "executed_volume": "0",
    "reserved_fee": "25000",
    "remaining_fee": "25000",
    "paid_fee": "0",
    "locked": "50025000",
    "trades_count": 0,
    "time_in_force": "ioc",
    "identifier": "my-order-1",
    "smp_type": "cancel_maker",
    "prevented_volume": "0",
    "prevented_locked": "0",
}


class TestCreateOrder:
    @pytest.mark.asyncio
    async def test_returns_order(self, executor: UpbitExecutor):
        """응답 데이터를 Order 객체로 변환하여 반환한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            result = await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
                volume=Decimal("0.001"),
                price=Decimal("50000000"),
            )

        assert result.market == "KRW-BTC"
        assert result.uuid == "550e8400-e29b-41d4-a716-446655440000"

    @pytest.mark.asyncio
    async def test_uses_post_method(self, executor: UpbitExecutor):
        """POST 메서드로 요청한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
            )

        assert mock_req.call_args[0][0] == "POST"

    @pytest.mark.asyncio
    async def test_test_mode_uses_test_endpoint(self, executor: UpbitExecutor):
        """test=True이면 /orders/test 엔드포인트를 사용한다."""
        assert executor.test is True

        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
            )

        assert mock_req.call_args[0][1] == "/orders/test"

    @pytest.mark.asyncio
    async def test_production_mode_uses_orders_endpoint(self):
        """test=False이면 /orders 엔드포인트를 사용한다."""
        executor = UpbitExecutor(
            api_key="test-key",
            api_secret="test-secret-key-that-is-long-enough-for-hs256",
            test=False,
        )

        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
            )

        assert mock_req.call_args[0][1] == "/orders"

    @pytest.mark.asyncio
    async def test_signed_request(self, executor: UpbitExecutor):
        """signed=True로 요청한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
            )

        assert mock_req.call_args[1]["signed"] is True

    @pytest.mark.asyncio
    async def test_required_params(self, executor: UpbitExecutor):
        """market, side, ord_type가 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
            )

        params = mock_req.call_args[0][2]
        assert params["market"] == "KRW-BTC"
        assert params["side"] == "bid"
        assert params["ord_type"] == "limit"

    @pytest.mark.asyncio
    async def test_volume_included_when_specified(self, executor: UpbitExecutor):
        """volume을 지정하면 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
                volume=Decimal("0.001"),
            )

        params = mock_req.call_args[0][2]
        assert params["volume"] == "0.001"

    @pytest.mark.asyncio
    async def test_price_included_when_specified(self, executor: UpbitExecutor):
        """price를 지정하면 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
                price=Decimal("50000000"),
            )

        params = mock_req.call_args[0][2]
        assert params["price"] == "50000000"

    @pytest.mark.asyncio
    async def test_volume_excluded_when_none(self, executor: UpbitExecutor):
        """volume이 None이면 params에 포함되지 않는다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
            )

        params = mock_req.call_args[0][2]
        assert "volume" not in params

    @pytest.mark.asyncio
    async def test_price_excluded_when_none(self, executor: UpbitExecutor):
        """price가 None이면 params에 포함되지 않는다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
            )

        params = mock_req.call_args[0][2]
        assert "price" not in params

    @pytest.mark.asyncio
    async def test_time_in_force_included_when_specified(self, executor: UpbitExecutor):
        """time_in_force를 지정하면 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
                time_in_force=TimeInForce.IOC,
            )

        params = mock_req.call_args[0][2]
        assert params["time_in_force"] == "ioc"

    @pytest.mark.asyncio
    async def test_identifier_included_when_specified(self, executor: UpbitExecutor):
        """identifier를 지정하면 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
                identifier="my-order-1",
            )

        params = mock_req.call_args[0][2]
        assert params["identifier"] == "my-order-1"

    @pytest.mark.asyncio
    async def test_smp_type_included_when_specified(self, executor: UpbitExecutor):
        """smp_type을 지정하면 params에 포함된다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            await executor.create_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
                smp_type=SelfMatchPreventionType.CANCEL_MAKER,
            )

        params = mock_req.call_args[0][2]
        assert params["smp_type"] == "cancel_maker"

    @pytest.mark.asyncio
    async def test_post_only_with_smp_type_raises_error(self, executor: UpbitExecutor):
        """post_only와 smp_type을 함께 사용하면 ValueError가 발생한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_ORDER_RESPONSE.copy()

            with pytest.raises(ValueError, match="post_only.*smp_type"):
                await executor.create_order(
                    market="KRW-BTC",
                    side=OrderSide.BID,
                    ord_type=OrderType.LIMIT,
                    time_in_force=TimeInForce.POST_ONLY,
                    smp_type=SelfMatchPreventionType.CANCEL_MAKER,
                )


# ============= limit_order =============


class TestLimitOrder:
    @pytest.mark.asyncio
    async def test_delegates_to_create_order(self, executor: UpbitExecutor):
        """create_order에 OrderType.LIMIT로 위임한다."""
        with patch.object(executor, "create_order", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()

            await executor.limit_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                volume=Decimal("0.001"),
                price=Decimal("50000000"),
            )

        mock_create.assert_awaited_once_with(
            "KRW-BTC",
            OrderSide.BID,
            ord_type=OrderType.LIMIT,
            volume=Decimal("0.001"),
            price=Decimal("50000000"),
            time_in_force=None,
            smp_type=None,
            identifier=None,
        )

    @pytest.mark.asyncio
    async def test_passes_optional_params(self, executor: UpbitExecutor):
        """선택적 파라미터가 create_order에 전달된다."""
        with patch.object(executor, "create_order", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()

            await executor.limit_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                time_in_force=TimeInForce.IOC,
                smp_type=SelfMatchPreventionType.CANCEL_TAKER,
                identifier="test-id",
            )

        call_kwargs = mock_create.call_args
        assert call_kwargs[1]["time_in_force"] == TimeInForce.IOC
        assert call_kwargs[1]["smp_type"] == SelfMatchPreventionType.CANCEL_TAKER
        assert call_kwargs[1]["identifier"] == "test-id"


# ============= market_order =============


class TestMarketOrder:
    @pytest.mark.asyncio
    async def test_delegates_to_create_order_with_ask_and_market(self, executor: UpbitExecutor):
        """create_order에 OrderSide.ASK, OrderType.MARKET으로 위임한다."""
        with patch.object(executor, "create_order", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()

            await executor.market_order(market="KRW-BTC", volume=Decimal("0.5"))

        mock_create.assert_awaited_once_with(
            "KRW-BTC",
            side=OrderSide.ASK,
            ord_type=OrderType.MARKET,
            volume=Decimal("0.5"),
            smp_type=None,
            identifier=None,
        )

    @pytest.mark.asyncio
    async def test_passes_optional_params(self, executor: UpbitExecutor):
        """선택적 파라미터가 create_order에 전달된다."""
        with patch.object(executor, "create_order", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()

            await executor.market_order(
                market="KRW-BTC",
                volume=Decimal("0.5"),
                smp_type=SelfMatchPreventionType.REDUCE,
                identifier="sell-1",
            )

        call_kwargs = mock_create.call_args
        assert call_kwargs[1]["smp_type"] == SelfMatchPreventionType.REDUCE
        assert call_kwargs[1]["identifier"] == "sell-1"


# ============= price_order =============


class TestPriceOrder:
    @pytest.mark.asyncio
    async def test_delegates_to_create_order_with_bid_and_price_type(self, executor: UpbitExecutor):
        """create_order에 OrderSide.BID, OrderType.PRICE로 위임한다."""
        with patch.object(executor, "create_order", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()

            await executor.price_order(market="KRW-BTC", price=Decimal("100000"))

        mock_create.assert_awaited_once_with(
            "KRW-BTC",
            side=OrderSide.BID,
            ord_type=OrderType.PRICE,
            price=Decimal("100000"),
            smp_type=None,
            identifier=None,
        )

    @pytest.mark.asyncio
    async def test_passes_optional_params(self, executor: UpbitExecutor):
        """선택적 파라미터가 create_order에 전달된다."""
        with patch.object(executor, "create_order", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()

            await executor.price_order(
                market="KRW-BTC",
                price=Decimal("100000"),
                smp_type=SelfMatchPreventionType.CANCEL_MAKER,
                identifier="buy-1",
            )

        call_kwargs = mock_create.call_args
        assert call_kwargs[1]["smp_type"] == SelfMatchPreventionType.CANCEL_MAKER
        assert call_kwargs[1]["identifier"] == "buy-1"


# ============= best_order =============


class TestBestOrder:
    @pytest.mark.asyncio
    async def test_delegates_to_create_order_with_best_type(self, executor: UpbitExecutor):
        """create_order에 OrderType.BEST로 위임한다."""
        with patch.object(executor, "create_order", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()

            await executor.best_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                time_in_force=TimeInForce.IOC,
                volume=Decimal("0.001"),
            )

        mock_create.assert_awaited_once_with(
            "KRW-BTC",
            OrderSide.BID,
            ord_type=OrderType.BEST,
            price=None,
            volume=Decimal("0.001"),
            time_in_force=TimeInForce.IOC,
            smp_type=None,
            identifier=None,
        )

    @pytest.mark.asyncio
    async def test_raises_error_when_time_in_force_is_none(self, executor: UpbitExecutor):
        """time_in_force가 None이면 ValueError가 발생한다."""
        with pytest.raises(ValueError, match="time_in_force"):
            await executor.best_order(
                market="KRW-BTC",
                side=OrderSide.BID,
                time_in_force=None,
            )

    @pytest.mark.asyncio
    async def test_passes_all_optional_params(self, executor: UpbitExecutor):
        """모든 선택적 파라미터가 create_order에 전달된다."""
        with patch.object(executor, "create_order", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()

            await executor.best_order(
                market="KRW-BTC",
                side=OrderSide.ASK,
                time_in_force=TimeInForce.FOK,
                price=Decimal("50000000"),
                volume=Decimal("0.001"),
                smp_type=SelfMatchPreventionType.CANCEL_TAKER,
                identifier="best-1",
            )

        call_kwargs = mock_create.call_args
        assert call_kwargs[1]["price"] == Decimal("50000000")
        assert call_kwargs[1]["volume"] == Decimal("0.001")
        assert call_kwargs[1]["smp_type"] == SelfMatchPreventionType.CANCEL_TAKER
        assert call_kwargs[1]["identifier"] == "best-1"


# ============= get_accounts =============

SAMPLE_ACCOUNT_RESPONSE = {
    "currency": "KRW",
    "balance": "1000000",
    "locked": "0",
    "avg_buy_price": "0",
    "avg_buy_price_modified": False,
    "unit_currency": "KRW",
}


class TestGetAccounts:
    @pytest.mark.asyncio
    async def test_returns_account_list(self, executor: UpbitExecutor):
        """응답 데이터를 Account 객체 리스트로 변환하여 반환한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [SAMPLE_ACCOUNT_RESPONSE.copy()]

            result = await executor.get_accounts()

        assert len(result) == 1
        assert result[0].currency == "KRW"
        assert result[0].balance == Decimal("1000000")

    @pytest.mark.asyncio
    async def test_uses_get_method(self, executor: UpbitExecutor):
        """GET 메서드로 요청한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_accounts()

        assert mock_req.call_args[0][0] == "GET"

    @pytest.mark.asyncio
    async def test_calls_accounts_endpoint(self, executor: UpbitExecutor):
        """/accounts 엔드포인트로 요청한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_accounts()

        assert mock_req.call_args[0][1] == "/accounts"

    @pytest.mark.asyncio
    async def test_signed_request(self, executor: UpbitExecutor):
        """signed=True로 요청한다."""
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await executor.get_accounts()

        assert mock_req.call_args[1]["signed"] is True

    @pytest.mark.asyncio
    async def test_multiple_accounts(self, executor: UpbitExecutor):
        """여러 개의 계정 응답을 모두 Account 객체로 변환한다."""
        krw_account = SAMPLE_ACCOUNT_RESPONSE.copy()
        krw_account["currency"] = "KRW"
        krw_account["balance"] = "1000000"

        btc_account = SAMPLE_ACCOUNT_RESPONSE.copy()
        btc_account["currency"] = "BTC"
        btc_account["balance"] = "0.5"
        btc_account["avg_buy_price"] = "50000000"
        btc_account["unit_currency"] = "KRW"

        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [krw_account, btc_account]

            result = await executor.get_accounts()

        assert len(result) == 2
        assert result[0].currency == "KRW"
        assert result[0].balance == Decimal("1000000")
        assert result[1].currency == "BTC"
        assert result[1].balance == Decimal("0.5")
        assert result[1].avg_buy_price == Decimal("50000000")

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_exception(self, executor: UpbitExecutor, caplog):
        """예외 발생 시 에러 로그를 남기고 빈 리스트를 반환한다."""
        with (
            patch.object(executor, "_request", new_callable=AsyncMock) as mock_req,
            caplog.at_level("ERROR"),
        ):
            mock_req.side_effect = Exception("API error")

            result = await executor.get_accounts()

        assert result == []
        assert "get_accounts() 실행 중 오류 발생" in caplog.text


# ============= get_account =============


class TestGetAccount:
    @pytest.mark.asyncio
    async def test_returns_matching_account(self, executor: UpbitExecutor):
        """지정한 currency와 일치하는 Account를 반환한다."""
        krw_account = SAMPLE_ACCOUNT_RESPONSE.copy()
        krw_account["currency"] = "KRW"

        btc_account = SAMPLE_ACCOUNT_RESPONSE.copy()
        btc_account["currency"] = "BTC"

        with patch.object(executor, "get_accounts", new_callable=AsyncMock) as mock_get_accounts:
            from src.trading.exchanges.upbit.models import Account

            mock_get_accounts.return_value = [
                Account.from_dict(krw_account),
                Account.from_dict(btc_account),
            ]

            result = await executor.get_account("BTC")

        assert result is not None
        assert result.currency == "BTC"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, executor: UpbitExecutor):
        """일치하는 currency가 없으면 None을 반환한다."""
        krw_account = SAMPLE_ACCOUNT_RESPONSE.copy()
        krw_account["currency"] = "KRW"

        with patch.object(executor, "get_accounts", new_callable=AsyncMock) as mock_get_accounts:
            from src.trading.exchanges.upbit.models import Account

            mock_get_accounts.return_value = [Account.from_dict(krw_account)]

            result = await executor.get_account("ETH")

        assert result is None

    @pytest.mark.asyncio
    async def test_delegates_to_get_accounts(self, executor: UpbitExecutor):
        """get_accounts를 호출하여 계정 목록을 가져온다."""
        with patch.object(executor, "get_accounts", new_callable=AsyncMock) as mock_get_accounts:
            mock_get_accounts.return_value = []

            await executor.get_account("BTC")

        mock_get_accounts.assert_awaited_once()


# ============= get_krw =============


class TestGetKrw:
    @pytest.mark.asyncio
    async def test_calls_get_account_with_krw(self, executor: UpbitExecutor):
        """get_account('KRW')를 호출한다."""
        with patch.object(executor, "get_account", new_callable=AsyncMock) as mock_get_account:
            mock_get_account.return_value = MagicMock()

            await executor.get_krw()

        mock_get_account.assert_awaited_once_with("KRW")

    @pytest.mark.asyncio
    async def test_returns_krw_account(self, executor: UpbitExecutor):
        """KRW 계정을 반환한다."""
        from src.trading.exchanges.upbit.models import Account

        krw_account = Account.from_dict(SAMPLE_ACCOUNT_RESPONSE.copy())

        with patch.object(executor, "get_account", new_callable=AsyncMock) as mock_get_account:
            mock_get_account.return_value = krw_account

            result = await executor.get_krw()

        assert result is krw_account

    @pytest.mark.asyncio
    async def test_returns_none_when_krw_not_found(self, executor: UpbitExecutor):
        """KRW 계정이 없으면 None을 반환한다."""
        with patch.object(executor, "get_account", new_callable=AsyncMock) as mock_get_account:
            mock_get_account.return_value = None

            result = await executor.get_krw()

        assert result is None


# ============= get_usdt =============


class TestGetUsdt:
    @pytest.mark.asyncio
    async def test_calls_get_account_with_usdt(self, executor: UpbitExecutor):
        """get_account('USDT')를 호출한다."""
        with patch.object(executor, "get_account", new_callable=AsyncMock) as mock_get_account:
            mock_get_account.return_value = MagicMock()

            await executor.get_usdt()

        mock_get_account.assert_awaited_once_with("USDT")

    @pytest.mark.asyncio
    async def test_returns_usdt_account(self, executor: UpbitExecutor):
        """USDT 계정을 반환한다."""
        from src.trading.exchanges.upbit.models import Account

        usdt_account_data = SAMPLE_ACCOUNT_RESPONSE.copy()
        usdt_account_data["currency"] = "USDT"
        usdt_account = Account.from_dict(usdt_account_data)

        with patch.object(executor, "get_account", new_callable=AsyncMock) as mock_get_account:
            mock_get_account.return_value = usdt_account

            result = await executor.get_usdt()

        assert result is usdt_account

    @pytest.mark.asyncio
    async def test_returns_none_when_usdt_not_found(self, executor: UpbitExecutor):
        """USDT 계정이 없으면 None을 반환한다."""
        with patch.object(executor, "get_account", new_callable=AsyncMock) as mock_get_account:
            mock_get_account.return_value = None

            result = await executor.get_usdt()

        assert result is None
