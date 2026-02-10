from unittest.mock import AsyncMock, patch

import pytest

from src.trading.exchanges.upbit.executor import UpbitExecutor

# ============= Fixtures =============


@pytest.fixture
def executor():
    """기본 UpbitExecutor 인스턴스를 생성한다."""
    return UpbitExecutor(api_key="test-key", api_secret="test-secret")


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
        assert executor.api_secret == "test-secret"

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
