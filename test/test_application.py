import signal

import pytest

from src.trading.application import TradingApplication


@pytest.fixture
def app():
    """TradingApplication 인스턴스를 생성하고, 테스트 후 시그널 핸들러를 복원한다."""
    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)
    application = TradingApplication()
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

    def test_signal_handlers_registered_on_init(self):
        """TradingApplication 생성 시 SIGINT, SIGTERM 핸들러가 등록된다."""
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        try:
            app = TradingApplication()
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
            app = TradingApplication(mode="production")
            assert app.mode == "production"
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)
