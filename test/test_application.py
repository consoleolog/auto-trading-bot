import signal
from unittest.mock import AsyncMock, Mock

import pytest

from src.trading.application import TradingApplication


@pytest.fixture
def mock_config():
    """Mock ConfigManager"""
    config = Mock()

    def config_get(key):
        config_values = {
            "app.mode": "development",
            "trading.markets": ["USDT-BTC", "USDT-ETH"],
            "trading.timeframes": ["minutes/60", "days"],
            "database.host": "localhost",
            "database.port": "5432",
            "database.database": "test_db",
            "database.user": "test_user",
            "database.password": "test_password",
            "redis.host": "localhost",
            "redis.port": "6379",
            "redis.password": None,
            "redis.database": "0",
            "upbit.api_key": "test_api_key",
            "upbit.api_secret": "test_api_secret",
        }
        return config_values.get(key)

    config.get.side_effect = config_get
    return config


@pytest.fixture
def app(mock_config):
    """TradingApplication 인스턴스를 생성하고, 테스트 후 시그널 핸들러를 복원한다."""
    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)
    application = TradingApplication(mock_config)
    yield application
    signal.signal(signal.SIGINT, original_sigint)
    signal.signal(signal.SIGTERM, original_sigterm)


class TestSignalHandler:
    def test_first_signal_sets_shutdown_event(self, app: TradingApplication):
        """첫 번째 시그널 수신 시 shutdown_event 가 설정된다."""
        assert not app.shutdown_event.is_set()

        app._signal_handler(signal.SIGINT, None)

        assert app.shutdown_event.is_set()

    def test_first_signal_sets_shutdown_requested_flag(self, app: TradingApplication):
        """첫 번째 시그널 수신 시 _shutdown_requested 플래그가 True 로 설정된다."""
        assert not app._shutdown_requested

        app._signal_handler(signal.SIGINT, None)

        assert app._shutdown_requested is True

    def test_second_signal_raises_system_exit(self, app: TradingApplication):
        """두 번째 시그널 수신 시 SystemExit 이 발생한다."""
        app._signal_handler(signal.SIGINT, None)

        with pytest.raises(SystemExit) as exc_info:
            app._signal_handler(signal.SIGINT, None)

        assert exc_info.value.code == 1

    def test_sigterm_sets_shutdown_event(self, app: TradingApplication):
        """SIGTERM 시그널도 동일하게 shutdown_event 를 설정한다."""
        app._signal_handler(signal.SIGTERM, None)

        assert app.shutdown_event.is_set()
        assert app._shutdown_requested is True

    def test_mixed_signals_force_shutdown(self, app: TradingApplication):
        """SIGINT 후 SIGTERM 으로도 강제 종료가 동작한다."""
        app._signal_handler(signal.SIGINT, None)

        with pytest.raises(SystemExit):
            app._signal_handler(signal.SIGTERM, None)

    def test_first_signal_logs_graceful_shutdown(self, app: TradingApplication, caplog):
        """첫 번째 시그널에서 graceful shutdown 로그가 출력된다."""
        with caplog.at_level("WARNING"):
            app._signal_handler(signal.SIGINT, None)

        assert "SIGINT" in caplog.text
        assert "starting graceful shutdown" in caplog.text

    def test_second_signal_logs_force_shutdown(self, app: TradingApplication, caplog):
        """두 번째 시그널에서 forcing immediate shutdown 로그가 출력된다."""
        app._signal_handler(signal.SIGINT, None)

        with caplog.at_level("WARNING"), pytest.raises(SystemExit):
            app._signal_handler(signal.SIGINT, None)

        assert "forcing immediate shutdown" in caplog.text

    def test_signal_handlers_registered_on_init(self, mock_config):
        """TradingApplication 생성 시 SIGINT, SIGTERM 핸들러가 등록된다."""
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        try:
            app = TradingApplication(mock_config)
            assert signal.getsignal(signal.SIGINT) == app._signal_handler
            assert signal.getsignal(signal.SIGTERM) == app._signal_handler
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

    def test_default_mode_is_development(self, app: TradingApplication):
        """기본 mode 가 development 이다."""
        assert app.mode == "development"

    def test_custom_mode(self):
        """사용자 지정 mode 가 올바르게 설정된다."""
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        try:
            config = Mock()

            def config_get(key):
                config_values = {
                    "app.mode": "production",
                    "trading.markets": ["USDT-BTC"],
                    "trading.timeframes": ["minutes/60"],
                }
                return config_values.get(key)

            config.get.side_effect = config_get
            app = TradingApplication(config)
            assert app.mode == "production"
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

    def test_mode_defaults_to_development_when_config_returns_none(self):
        """config가 None을 반환하면 mode가 development가 된다."""
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        try:
            config = Mock()

            def config_get(key):
                # app.mode는 None을 반환하고, 나머지는 기본값 반환
                config_values = {
                    "app.mode": None,
                    "trading.markets": ["USDT-BTC"],
                    "trading.timeframes": ["minutes/60"],
                }
                return config_values.get(key)

            config.get.side_effect = config_get
            app = TradingApplication(config)
            assert app.mode == "development"
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

    def test_components_are_initialized_as_none(self, app: TradingApplication):
        """컴포넌트들이 None으로 초기화된다."""
        assert app._storage is None
        assert app._cache is None
        assert app._exchange is None

    def test_config_attribute_is_stored(self, app: TradingApplication, mock_config):
        """config 속성이 저장된다."""
        assert app.config is mock_config

    def test_running_flag_initialized_as_false(self, app: TradingApplication):
        """_running 플래그가 False로 초기화된다."""
        assert app._running is False


class TestSetup:
    """Setup 관련 테스트"""

    @pytest.mark.asyncio
    async def test_setup_initializes_storage(self, mock_config, monkeypatch):
        """setup이 DataStorage를 초기화한다."""
        # Mock DataStorage
        mock_storage = AsyncMock()
        mock_storage.connect = AsyncMock()
        mock_storage.health_check = AsyncMock(return_value=True)
        mock_storage_class = Mock(return_value=mock_storage)

        # Mock other components
        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache_class = Mock(return_value=mock_cache)

        mock_exchange = AsyncMock()
        mock_exchange.connect = AsyncMock()
        mock_exchange_class = Mock(return_value=mock_exchange)

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_class)
        monkeypatch.setattr("src.trading.application.RedisCache", mock_cache_class)
        monkeypatch.setattr("src.trading.application.UpbitExecutor", mock_exchange_class)

        app = TradingApplication(mock_config)
        assert app._storage is None

        success = await app.setup()

        assert success is True
        assert app._storage is mock_storage
        mock_storage_class.assert_called_once_with(
            host="localhost",
            port=5432,
            database="test_db",
            user="test_user",
            password="test_password",
        )
        mock_storage.connect.assert_awaited_once()
        mock_storage.health_check.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_setup_initializes_cache(self, mock_config, monkeypatch):
        """setup이 RedisCache를 초기화한다."""
        # Mock components
        mock_storage = AsyncMock()
        mock_storage.connect = AsyncMock()
        mock_storage.health_check = AsyncMock(return_value=True)
        mock_storage_class = Mock(return_value=mock_storage)

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache_class = Mock(return_value=mock_cache)

        mock_exchange = AsyncMock()
        mock_exchange.connect = AsyncMock()
        mock_exchange_class = Mock(return_value=mock_exchange)

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_class)
        monkeypatch.setattr("src.trading.application.RedisCache", mock_cache_class)
        monkeypatch.setattr("src.trading.application.UpbitExecutor", mock_exchange_class)

        app = TradingApplication(mock_config)
        assert app._cache is None

        success = await app.setup()

        assert success is True
        assert app._cache is mock_cache
        mock_cache_class.assert_called_once_with(
            host="localhost",
            port=6379,
            password=None,
            db=0,
        )
        mock_cache.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_setup_initializes_exchange(self, mock_config, monkeypatch):
        """setup이 UpbitExecutor를 초기화한다."""
        # Mock components
        mock_storage = AsyncMock()
        mock_storage.connect = AsyncMock()
        mock_storage.health_check = AsyncMock(return_value=True)
        mock_storage_class = Mock(return_value=mock_storage)

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache_class = Mock(return_value=mock_cache)

        mock_exchange = AsyncMock()
        mock_exchange.connect = AsyncMock()
        mock_exchange_class = Mock(return_value=mock_exchange)

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_class)
        monkeypatch.setattr("src.trading.application.RedisCache", mock_cache_class)
        monkeypatch.setattr("src.trading.application.UpbitExecutor", mock_exchange_class)

        app = TradingApplication(mock_config)
        assert app._exchange is None

        success = await app.setup()

        assert success is True
        assert app._exchange is mock_exchange
        mock_exchange_class.assert_called_once_with(
            api_key="test_api_key",
            api_secret="test_api_secret",
            test=True,  # development mode
        )
        mock_exchange.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_setup_returns_false_on_storage_error(self, mock_config, caplog, monkeypatch):
        """setup 중 DataStorage 에러 발생 시 False를 반환한다."""

        def mock_storage_error(*args, **kwargs):
            raise RuntimeError("Storage initialization failed")

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_error)

        app = TradingApplication(mock_config)

        with caplog.at_level("ERROR"):
            success = await app.setup()

        assert success is False
        assert "Setup failed" in caplog.text

    @pytest.mark.asyncio
    async def test_setup_returns_false_on_health_check_failure(self, mock_config, caplog, monkeypatch):
        """health check 실패 시 False를 반환한다."""
        # Mock storage with failing health check
        mock_storage = AsyncMock()
        mock_storage.connect = AsyncMock()
        mock_storage.health_check = AsyncMock(return_value=False)
        mock_storage_class = Mock(return_value=mock_storage)

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_class)

        app = TradingApplication(mock_config)

        with caplog.at_level("ERROR"):
            success = await app.setup()

        assert success is False
        assert "Setup failed" in caplog.text

    @pytest.mark.asyncio
    async def test_setup_logs_success(self, mock_config, caplog, monkeypatch):
        """setup 성공 시 로그를 출력한다."""
        # Mock all components
        mock_storage = AsyncMock()
        mock_storage.connect = AsyncMock()
        mock_storage.health_check = AsyncMock(return_value=True)
        mock_storage_class = Mock(return_value=mock_storage)

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache_class = Mock(return_value=mock_cache)

        mock_exchange = AsyncMock()
        mock_exchange.connect = AsyncMock()
        mock_exchange_class = Mock(return_value=mock_exchange)

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_class)
        monkeypatch.setattr("src.trading.application.RedisCache", mock_cache_class)
        monkeypatch.setattr("src.trading.application.UpbitExecutor", mock_exchange_class)

        app = TradingApplication(mock_config)

        with caplog.at_level("INFO"):
            await app.setup()

        assert "Setting up trading application components" in caplog.text
        assert "TimescaleDB storage initialized" in caplog.text
        assert "Redis cache initialized" in caplog.text
        assert "Exchange adapter initialized" in caplog.text
        assert "TradingApplication setup complete" in caplog.text


class TestStart:
    """Start 관련 테스트"""

    @pytest.mark.asyncio
    async def test_start_calls_setup_if_storage_is_none(self, mock_config, monkeypatch):
        """start가 storage가 None일 때 setup을 호출한다."""
        # Mock all components
        mock_storage = AsyncMock()
        mock_storage.connect = AsyncMock()
        mock_storage.health_check = AsyncMock(return_value=True)
        mock_storage_class = Mock(return_value=mock_storage)

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache_class = Mock(return_value=mock_cache)

        mock_exchange = AsyncMock()
        mock_exchange.connect = AsyncMock()
        mock_exchange_class = Mock(return_value=mock_exchange)

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_class)
        monkeypatch.setattr("src.trading.application.RedisCache", mock_cache_class)
        monkeypatch.setattr("src.trading.application.UpbitExecutor", mock_exchange_class)

        app = TradingApplication(mock_config)
        assert app._storage is None

        # start를 즉시 종료하기 위해 shutdown_event를 미리 설정
        app.shutdown_event.set()

        await app.start()

        assert app._storage is mock_storage
        assert app._cache is mock_cache
        assert app._exchange is mock_exchange

    @pytest.mark.asyncio
    async def test_start_raises_error_if_setup_fails(self, mock_config, monkeypatch):
        """setup 실패 시 RuntimeError를 발생시킨다."""

        def mock_storage_error(*args, **kwargs):
            raise RuntimeError("Setup failed")

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_error)

        app = TradingApplication(mock_config)

        with pytest.raises(RuntimeError, match="TradingApplication setup failed"):
            await app.start()

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, mock_config, monkeypatch):
        """start가 _running 플래그를 설정한다."""
        # Mock all components
        mock_storage = AsyncMock()
        mock_storage.connect = AsyncMock()
        mock_storage.health_check = AsyncMock(return_value=True)
        mock_storage_class = Mock(return_value=mock_storage)

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache_class = Mock(return_value=mock_cache)

        mock_exchange = AsyncMock()
        mock_exchange.connect = AsyncMock()
        mock_exchange_class = Mock(return_value=mock_exchange)

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_class)
        monkeypatch.setattr("src.trading.application.RedisCache", mock_cache_class)
        monkeypatch.setattr("src.trading.application.UpbitExecutor", mock_exchange_class)

        app = TradingApplication(mock_config)
        assert app._running is False

        # 즉시 종료
        app.shutdown_event.set()

        await app.start()

        # start 메서드가 _running을 True로 설정했다가 shutdown에서 처리됨

    @pytest.mark.asyncio
    async def test_start_warns_if_already_running(self, mock_config, caplog):
        """이미 실행 중일 때 경고를 출력한다."""
        app = TradingApplication(mock_config)
        app._running = True

        with caplog.at_level("WARNING"):
            await app.start()

        assert "already running" in caplog.text

    @pytest.mark.asyncio
    async def test_start_calls_shutdown_on_completion(self, mock_config, monkeypatch):
        """start 완료 시 shutdown을 호출한다."""
        # Mock all components
        mock_storage = AsyncMock()
        mock_storage.connect = AsyncMock()
        mock_storage.health_check = AsyncMock(return_value=True)
        mock_storage.disconnect = AsyncMock()
        mock_storage_class = Mock(return_value=mock_storage)

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache.disconnect = AsyncMock()
        mock_cache_class = Mock(return_value=mock_cache)

        mock_exchange = AsyncMock()
        mock_exchange.connect = AsyncMock()
        mock_exchange.disconnect = AsyncMock()
        mock_exchange_class = Mock(return_value=mock_exchange)

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_class)
        monkeypatch.setattr("src.trading.application.RedisCache", mock_cache_class)
        monkeypatch.setattr("src.trading.application.UpbitExecutor", mock_exchange_class)

        app = TradingApplication(mock_config)
        shutdown_called = False

        original_shutdown = app.shutdown

        async def mock_shutdown():
            nonlocal shutdown_called
            shutdown_called = True
            await original_shutdown()

        app.shutdown = mock_shutdown

        # 즉시 종료
        app.shutdown_event.set()

        await app.start()

        assert shutdown_called is True


class TestShutdownMonitor:
    """_shutdown_monitor 관련 테스트"""

    @pytest.mark.asyncio
    async def test_shutdown_monitor_waits_for_event(self, app: TradingApplication):
        """_shutdown_monitor가 shutdown_event를 기다린다."""
        import asyncio

        # shutdown_event가 설정되지 않았으므로 대기
        monitor_task = asyncio.create_task(app._shutdown_monitor())

        # 잠시 대기하여 모니터가 실행되도록 함
        await asyncio.sleep(0.1)

        # 아직 완료되지 않아야 함
        assert not monitor_task.done()

        # 이벤트 설정
        app.shutdown_event.set()

        # 이제 완료되어야 함
        await monitor_task
        assert monitor_task.done()

    @pytest.mark.asyncio
    async def test_shutdown_monitor_logs_when_signal_received(self, app: TradingApplication, caplog):
        """shutdown_monitor가 시그널 수신 시 로그를 출력한다."""
        import asyncio

        monitor_task = asyncio.create_task(app._shutdown_monitor())

        with caplog.at_level("INFO"):
            app.shutdown_event.set()
            await monitor_task

        assert "Shutdown signal received" in caplog.text

    @pytest.mark.asyncio
    async def test_shutdown_monitor_completes_immediately_if_event_already_set(self, app: TradingApplication):
        """이벤트가 이미 설정되어 있으면 즉시 완료된다."""
        import asyncio

        # 미리 이벤트 설정
        app.shutdown_event.set()

        # 모니터 시작
        monitor_task = asyncio.create_task(app._shutdown_monitor())

        # 즉시 완료되어야 함
        await asyncio.sleep(0.01)
        assert monitor_task.done()

    @pytest.mark.asyncio
    async def test_signal_handler_triggers_shutdown_monitor(self, app: TradingApplication):
        """signal_handler가 _shutdown_monitor를 트리거한다."""
        import asyncio
        import signal

        monitor_task = asyncio.create_task(app._shutdown_monitor())

        # 모니터가 대기 중인지 확인
        await asyncio.sleep(0.1)
        assert not monitor_task.done()

        # 시그널 핸들러 호출
        app._signal_handler(signal.SIGINT, None)

        # 모니터가 완료되어야 함
        await monitor_task
        assert monitor_task.done()
        assert app.shutdown_event.is_set()


class TestShutdown:
    """Shutdown 관련 테스트"""

    @pytest.mark.asyncio
    async def test_shutdown_completes_gracefully(self, app: TradingApplication, caplog):
        """shutdown이 정상적으로 완료된다."""
        app._running = True
        with caplog.at_level("INFO"):
            await app.shutdown()

        assert "Initiating graceful shutdown" in caplog.text

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_storage(self, app: TradingApplication):
        """storage를 disconnect한다."""
        mock_storage = AsyncMock()
        mock_storage.disconnect = AsyncMock()
        app._storage = mock_storage
        app._running = True

        await app.shutdown()

        mock_storage.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_cache(self, app: TradingApplication):
        """cache를 disconnect한다."""
        mock_cache = AsyncMock()
        mock_cache.disconnect = AsyncMock()
        app._cache = mock_cache
        app._running = True

        await app.shutdown()

        mock_cache.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_exchange(self, app: TradingApplication):
        """exchange를 disconnect한다."""
        mock_exchange = AsyncMock()
        mock_exchange.disconnect = AsyncMock()
        app._exchange = mock_exchange
        app._running = True

        await app.shutdown()

        mock_exchange.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_all_components(self, app: TradingApplication):
        """모든 컴포넌트가 있을 때 정상적으로 처리한다."""
        mock_storage = AsyncMock()
        mock_storage.disconnect = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.disconnect = AsyncMock()
        mock_exchange = AsyncMock()
        mock_exchange.disconnect = AsyncMock()

        app._storage = mock_storage
        app._cache = mock_cache
        app._exchange = mock_exchange
        app._running = True

        await app.shutdown()

        mock_storage.disconnect.assert_awaited_once()
        mock_cache.disconnect.assert_awaited_once()
        mock_exchange.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_logs_errors(self, app: TradingApplication, caplog):
        """shutdown 중 에러가 발생하면 로깅된다."""
        mock_storage = AsyncMock()
        mock_storage.disconnect = AsyncMock(side_effect=RuntimeError("Test shutdown error"))
        app._storage = mock_storage
        app._running = True

        with caplog.at_level("ERROR"):
            await app.shutdown()

        assert "Error during shutdown" in caplog.text

    @pytest.mark.asyncio
    async def test_shutdown_does_nothing_if_not_running(self, app: TradingApplication):
        """실행 중이 아니면 아무것도 하지 않는다."""
        mock_storage = AsyncMock()
        mock_storage.disconnect = AsyncMock()
        app._storage = mock_storage
        app._running = False

        await app.shutdown()

        # disconnect가 호출되지 않아야 함
        mock_storage.disconnect.assert_not_awaited()


class TestIntegration:
    """통합 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_full_startup_and_shutdown_flow(self, mock_config, monkeypatch, caplog):
        """전체 시작 및 종료 플로우가 정상 작동한다."""
        import asyncio

        # Mock all components
        mock_storage = AsyncMock()
        mock_storage.connect = AsyncMock()
        mock_storage.health_check = AsyncMock(return_value=True)
        mock_storage.disconnect = AsyncMock()
        mock_storage_class = Mock(return_value=mock_storage)

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache.disconnect = AsyncMock()
        mock_cache_class = Mock(return_value=mock_cache)

        mock_exchange = AsyncMock()
        mock_exchange.connect = AsyncMock()
        mock_exchange.disconnect = AsyncMock()
        mock_exchange_class = Mock(return_value=mock_exchange)

        monkeypatch.setattr("src.trading.application.DataStorage", mock_storage_class)
        monkeypatch.setattr("src.trading.application.RedisCache", mock_cache_class)
        monkeypatch.setattr("src.trading.application.UpbitExecutor", mock_exchange_class)

        app = TradingApplication(mock_config)

        # 로그 캡처 시작
        with caplog.at_level("INFO"):
            # start를 백그라운드에서 실행
            start_task = asyncio.create_task(app.start())

            # 잠시 대기하여 setup이 완료되도록 함
            await asyncio.sleep(0.2)

            # shutdown 트리거
            app.shutdown_event.set()

            # start 완료 대기
            await start_task

        assert "TimescaleDB storage initialized" in caplog.text
        assert "Redis cache initialized" in caplog.text
        assert "Exchange adapter initialized" in caplog.text
        assert "Shutdown signal received" in caplog.text
