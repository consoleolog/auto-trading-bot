from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.portfolio.models.portfolio_state import PortfolioState
from src.strategies.base_strategy import BaseStrategy
from src.strategies.codes import MarketRegime, SignalDirection
from src.strategies.models import Signal, StrategyConfig
from src.trading.exchanges.upbit.codes import Timeframe
from src.trading.exchanges.upbit.models import Candle

# ============= 테스트용 구체적인 Strategy 구현 =============


class ConcreteTestStrategy(BaseStrategy):
    """테스트용 구체적인 전략 구현"""

    def __init__(self, config: StrategyConfig, data_storage):
        super().__init__(config, data_storage)
        self.evaluate_called = False
        self.evaluate_return_value = None

    async def evaluate(self, candles: list[Candle], regime: MarketRegime, portfolio: PortfolioState) -> Signal | None:
        """테스트용 evaluate 구현"""
        self.evaluate_called = True
        return self.evaluate_return_value

    def get_supported_regimes(self) -> list[MarketRegime]:
        """BULL과 SIDEWAYS 국면을 지원"""
        return [MarketRegime.BULL, MarketRegime.SIDEWAYS]


class AlwaysEnabledStrategy(BaseStrategy):
    """항상 활성화된 전략 (모든 국면 지원)"""

    async def evaluate(self, candles: list[Candle], regime: MarketRegime, portfolio: PortfolioState) -> Signal | None:
        return None

    def get_supported_regimes(self) -> list[MarketRegime]:
        return [MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.SIDEWAYS, MarketRegime.UNKNOWN]


class BullOnlyStrategy(BaseStrategy):
    """BULL 국면만 지원하는 전략"""

    async def evaluate(self, candles: list[Candle], regime: MarketRegime, portfolio: PortfolioState) -> Signal | None:
        return None

    def get_supported_regimes(self) -> list[MarketRegime]:
        return [MarketRegime.BULL]


# ============= 테스트 클래스 =============


class TestBaseStrategy:
    """BaseStrategy 테스트"""

    @pytest.fixture
    def mock_data_storage(self):
        """Mock DataStorage"""
        return Mock()

    @pytest.fixture
    def default_config(self):
        """기본 전략 설정"""
        return StrategyConfig(
            id="test_strategy_1",
            name="Test Strategy",
            capital_allocation=0.25,
            enabled=True,
            parameters={"param1": "value1", "param2": 100},
        )

    @pytest.fixture
    def disabled_config(self):
        """비활성화된 전략 설정"""
        return StrategyConfig(
            id="disabled_strategy",
            name="Disabled Strategy",
            capital_allocation=0.25,
            enabled=False,
        )

    @pytest.fixture
    def sample_candles(self):
        """샘플 캔들 데이터"""
        utc_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        kst_time = datetime(2024, 1, 1, 9, 0, 0)  # KST = UTC+9

        return [
            Candle(
                market="USDT-BTC",
                candle_date_time_utc=utc_time,
                candle_date_time_kst=kst_time,
                opening_price=50000.0,
                high_price=51000.0,
                low_price=49000.0,
                trade_price=50500.0,
                timestamp=1704067200000,  # 2024-01-01 00:00:00 UTC in milliseconds
                candle_acc_trade_volume=100.5,
                candle_acc_trade_price=5000000.0,
            ),
            Candle(
                market="USDT-BTC",
                candle_date_time_utc=datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
                candle_date_time_kst=datetime(2024, 1, 1, 10, 0, 0),
                opening_price=50500.0,
                high_price=52000.0,
                low_price=50000.0,
                trade_price=51500.0,
                timestamp=1704070800000,  # 2024-01-01 01:00:00 UTC in milliseconds
                candle_acc_trade_volume=120.3,
                candle_acc_trade_price=6000000.0,
            ),
        ]

    @pytest.fixture
    def sample_portfolio(self):
        """샘플 포트폴리오"""
        return PortfolioState(
            total_capital=Decimal("50000000"),
            available_capital=Decimal("40000000"),
            positions={},
            high_water_mark=Decimal("50000000"),
        )

    # ============= 초기화 테스트 =============

    def test_strategy_initializes_with_config(self, default_config, mock_data_storage):
        """전략이 설정으로 초기화된다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        assert strategy.strategy_id == "test_strategy_1"
        assert strategy.name == "Test Strategy"
        assert strategy.enabled is True
        assert strategy.capital_allocation == 0.25
        assert strategy.parameters == {"param1": "value1", "param2": 100}

    def test_strategy_initializes_with_empty_state(self, default_config, mock_data_storage):
        """전략이 빈 상태로 초기화된다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        assert strategy._state == {}
        assert strategy._has_open_position is False
        assert strategy._position_market is None
        assert strategy._entry_price is None

    def test_strategy_stores_data_storage_reference(self, default_config, mock_data_storage):
        """전략이 DataStorage 참조를 저장한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        assert strategy._data_storage is mock_data_storage

    # ============= should_run() 테스트 =============

    def test_should_run_returns_true_when_enabled_and_supported_regime(self, default_config, mock_data_storage):
        """활성화되어 있고 지원하는 국면일 때 True를 반환한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # BULL은 지원되는 국면
        assert strategy.should_run(MarketRegime.BULL) is True
        # SIDEWAYS도 지원되는 국면
        assert strategy.should_run(MarketRegime.SIDEWAYS) is True

    def test_should_run_returns_false_when_unsupported_regime(self, default_config, mock_data_storage):
        """지원하지 않는 국면일 때 False를 반환한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # BEAR는 지원되지 않는 국면
        assert strategy.should_run(MarketRegime.BEAR) is False
        # UNKNOWN도 지원되지 않는 국면
        assert strategy.should_run(MarketRegime.UNKNOWN) is False

    def test_should_run_returns_false_when_disabled(self, disabled_config, mock_data_storage):
        """비활성화되어 있을 때 False를 반환한다."""
        strategy = ConcreteTestStrategy(disabled_config, mock_data_storage)

        # 지원하는 국면이지만 비활성화되어 있음
        assert strategy.should_run(MarketRegime.BULL) is False
        assert strategy.should_run(MarketRegime.SIDEWAYS) is False

    def test_should_run_with_all_regimes_supported(self, default_config, mock_data_storage):
        """모든 국면을 지원하는 전략은 모든 국면에서 True를 반환한다."""
        strategy = AlwaysEnabledStrategy(default_config, mock_data_storage)

        assert strategy.should_run(MarketRegime.BULL) is True
        assert strategy.should_run(MarketRegime.BEAR) is True
        assert strategy.should_run(MarketRegime.SIDEWAYS) is True
        assert strategy.should_run(MarketRegime.UNKNOWN) is True

    def test_should_run_with_single_regime_supported(self, default_config, mock_data_storage):
        """하나의 국면만 지원하는 전략은 해당 국면에서만 True를 반환한다."""
        strategy = BullOnlyStrategy(default_config, mock_data_storage)

        assert strategy.should_run(MarketRegime.BULL) is True
        assert strategy.should_run(MarketRegime.BEAR) is False
        assert strategy.should_run(MarketRegime.SIDEWAYS) is False
        assert strategy.should_run(MarketRegime.UNKNOWN) is False

    # ============= reset_state() 테스트 =============

    def test_reset_state_clears_internal_state(self, default_config, mock_data_storage):
        """reset_state가 내부 상태를 초기화한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 상태 설정
        strategy._state = {"key1": "value1", "key2": 123}
        strategy._has_open_position = True
        strategy._position_market = "USDT-BTC"
        strategy._entry_price = Decimal("50000")

        # 초기화
        strategy.reset_state()

        # 모든 상태가 초기화되었는지 확인
        assert strategy._state == {}
        assert strategy._has_open_position is False
        assert strategy._position_market is None
        assert strategy._entry_price is None

    def test_reset_state_can_be_called_multiple_times(self, default_config, mock_data_storage):
        """reset_state를 여러 번 호출할 수 있다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        strategy.reset_state()
        strategy.reset_state()
        strategy.reset_state()

        assert strategy._state == {}
        assert strategy._has_open_position is False

    # ============= 포지션 관리 테스트 =============

    def test_set_position_marks_strategy_as_having_position(self, default_config, mock_data_storage):
        """set_position이 전략을 포지션 보유 상태로 표시한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        market = "USDT-BTC"
        entry_price = Decimal("50000")

        strategy.set_position(market, entry_price)

        assert strategy._has_open_position is True
        assert strategy._position_market == market
        assert strategy._entry_price == entry_price
        assert strategy.has_position is True

    def test_clear_position_marks_strategy_as_having_no_position(self, default_config, mock_data_storage):
        """clear_position이 전략을 포지션 미보유 상태로 표시한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 먼저 포지션 설정
        strategy.set_position("USDT-BTC", Decimal("50000"))
        assert strategy.has_position is True

        # 포지션 제거
        strategy.clear_position()

        assert strategy._has_open_position is False
        assert strategy._position_market is None
        assert strategy._entry_price is None
        assert strategy.has_position is False

    def test_has_position_property_returns_correct_state(self, default_config, mock_data_storage):
        """has_position 프로퍼티가 올바른 상태를 반환한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 초기 상태: 포지션 없음
        assert strategy.has_position is False

        # 포지션 설정 후: 포지션 있음
        strategy.set_position("USDT-BTC", Decimal("50000"))
        assert strategy.has_position is True

        # 포지션 제거 후: 포지션 없음
        strategy.clear_position()
        assert strategy.has_position is False

    def test_set_position_updates_existing_position(self, default_config, mock_data_storage):
        """set_position이 기존 포지션을 업데이트한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 첫 번째 포지션 설정
        strategy.set_position("USDT-BTC", Decimal("50000"))
        assert strategy._position_market == "USDT-BTC"
        assert strategy._entry_price == Decimal("50000")

        # 다른 포지션으로 업데이트
        strategy.set_position("USDT-ETH", Decimal("3000"))
        assert strategy._position_market == "USDT-ETH"
        assert strategy._entry_price == Decimal("3000")

    # ============= 추상 메서드 테스트 =============

    def test_evaluate_is_abstract_method(self, default_config, mock_data_storage):
        """evaluate는 구현되어야 한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # ConcreteTestStrategy는 evaluate를 구현했으므로 호출 가능
        assert hasattr(strategy, "evaluate")
        assert callable(strategy.evaluate)

    def test_get_supported_regimes_is_abstract_method(self, default_config, mock_data_storage):
        """get_supported_regimes는 구현되어야 한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # ConcreteTestStrategy는 get_supported_regimes를 구현했으므로 호출 가능
        regimes = strategy.get_supported_regimes()
        assert isinstance(regimes, list)
        assert MarketRegime.BULL in regimes
        assert MarketRegime.SIDEWAYS in regimes

    @pytest.mark.asyncio
    async def test_evaluate_can_be_called(self, default_config, mock_data_storage, sample_candles, sample_portfolio):
        """evaluate를 호출할 수 있다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # evaluate 호출
        result = await strategy.evaluate(sample_candles, MarketRegime.BULL, sample_portfolio)

        assert strategy.evaluate_called is True
        assert result is None  # ConcreteTestStrategy는 None을 반환하도록 설정됨

    @pytest.mark.asyncio
    async def test_evaluate_can_return_signal(
        self, default_config, mock_data_storage, sample_candles, sample_portfolio
    ):
        """evaluate가 신호를 반환할 수 있다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 반환할 신호 설정
        test_signal = Signal(
            strategy_id="test_strategy_1",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.8,
            confidence=0.75,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
        )
        strategy.evaluate_return_value = test_signal

        # evaluate 호출
        result = await strategy.evaluate(sample_candles, MarketRegime.BULL, sample_portfolio)

        assert result is test_signal
        assert result.strategy_id == "test_strategy_1"
        assert result.direction == SignalDirection.LONG

    # ============= 통합 시나리오 테스트 =============

    def test_full_lifecycle_without_position(self, default_config, mock_data_storage):
        """포지션 없이 전체 라이프사이클을 테스트한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 1. 초기 상태 확인
        assert strategy.has_position is False
        assert strategy.should_run(MarketRegime.BULL) is True

        # 2. 상태 초기화 (이미 초기 상태지만 호출 가능)
        strategy.reset_state()
        assert strategy.has_position is False

    def test_full_lifecycle_with_position(self, default_config, mock_data_storage):
        """포지션과 함께 전체 라이프사이클을 테스트한다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 1. 초기 상태: 포지션 없음
        assert strategy.has_position is False

        # 2. 포지션 진입
        strategy.set_position("USDT-BTC", Decimal("50000"))
        assert strategy.has_position is True
        assert strategy._position_market == "USDT-BTC"

        # 3. 포지션 청산
        strategy.clear_position()
        assert strategy.has_position is False

        # 4. 상태 초기화
        strategy.reset_state()
        assert strategy._state == {}
        assert strategy.has_position is False

    def test_strategy_can_be_disabled_and_enabled(self, default_config, mock_data_storage):
        """전략을 비활성화하고 활성화할 수 있다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 초기: 활성화됨
        assert strategy.enabled is True
        assert strategy.should_run(MarketRegime.BULL) is True

        # 비활성화
        strategy.enabled = False
        assert strategy.should_run(MarketRegime.BULL) is False

        # 재활성화
        strategy.enabled = True
        assert strategy.should_run(MarketRegime.BULL) is True

    def test_multiple_strategies_with_different_regimes(self, default_config, mock_data_storage):
        """다른 국면을 지원하는 여러 전략을 만들 수 있다."""
        strategy1 = ConcreteTestStrategy(default_config, mock_data_storage)  # BULL, SIDEWAYS 지원
        strategy2 = BullOnlyStrategy(default_config, mock_data_storage)  # BULL만 지원
        strategy3 = AlwaysEnabledStrategy(default_config, mock_data_storage)  # 모든 국면 지원

        # BULL 국면
        assert strategy1.should_run(MarketRegime.BULL) is True
        assert strategy2.should_run(MarketRegime.BULL) is True
        assert strategy3.should_run(MarketRegime.BULL) is True

        # BEAR 국면
        assert strategy1.should_run(MarketRegime.BEAR) is False
        assert strategy2.should_run(MarketRegime.BEAR) is False
        assert strategy3.should_run(MarketRegime.BEAR) is True

        # SIDEWAYS 국면
        assert strategy1.should_run(MarketRegime.SIDEWAYS) is True
        assert strategy2.should_run(MarketRegime.SIDEWAYS) is False
        assert strategy3.should_run(MarketRegime.SIDEWAYS) is True

    # ============= 파라미터 테스트 =============

    def test_strategy_can_access_parameters(self, default_config, mock_data_storage):
        """전략이 파라미터에 접근할 수 있다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        assert strategy.parameters["param1"] == "value1"
        assert strategy.parameters["param2"] == 100

    def test_strategy_with_empty_parameters(self, mock_data_storage):
        """빈 파라미터로 전략을 만들 수 있다."""
        config = StrategyConfig(
            id="test_strategy",
            name="Test Strategy",
            capital_allocation=0.25,
            enabled=True,
            parameters={},
        )

        strategy = ConcreteTestStrategy(config, mock_data_storage)

        assert strategy.parameters == {}

    def test_strategy_parameters_are_mutable(self, default_config, mock_data_storage):
        """전략 파라미터를 수정할 수 있다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 파라미터 수정
        strategy.parameters["param1"] = "new_value"
        strategy.parameters["new_param"] = "added"

        assert strategy.parameters["param1"] == "new_value"
        assert strategy.parameters["new_param"] == "added"

    # ============= 엣지 케이스 테스트 =============

    def test_reset_state_when_already_clean(self, default_config, mock_data_storage):
        """이미 깨끗한 상태에서 reset_state를 호출해도 안전하다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        # 이미 초기 상태
        assert strategy._state == {}
        assert strategy.has_position is False

        # reset_state 호출
        strategy.reset_state()

        # 여전히 깨끗한 상태
        assert strategy._state == {}
        assert strategy.has_position is False

    def test_clear_position_when_no_position(self, default_config, mock_data_storage):
        """포지션이 없을 때 clear_position을 호출해도 안전하다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        assert strategy.has_position is False

        # 포지션이 없는 상태에서 clear_position 호출
        strategy.clear_position()

        # 여전히 포지션 없음
        assert strategy.has_position is False

    def test_capital_allocation_is_preserved(self, default_config, mock_data_storage):
        """자본 배분 비율이 유지된다."""
        strategy = ConcreteTestStrategy(default_config, mock_data_storage)

        assert strategy.capital_allocation == 0.25

        # 다양한 작업 후에도 유지됨
        strategy.set_position("USDT-BTC", Decimal("50000"))
        assert strategy.capital_allocation == 0.25

        strategy.reset_state()
        assert strategy.capital_allocation == 0.25
