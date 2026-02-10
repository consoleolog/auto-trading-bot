import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import unquote, urlencode

import jwt
import pytest

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
