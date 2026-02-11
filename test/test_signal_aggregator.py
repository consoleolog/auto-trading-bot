from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.decision.signal_aggregator import SignalAggregator
from src.strategies.codes import SignalDirection
from src.strategies.models.signal import Signal
from src.trading.exchanges.upbit.codes import Timeframe


class TestSignalAggregator:
    """SignalAggregator 테스트"""

    @pytest.fixture
    def sample_signal(self):
        """테스트용 샘플 신호"""
        return Signal(
            strategy_id="test_strategy",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.8,
            confidence=0.75,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.DAY,
            timestamp=datetime.now(tz=timezone.utc),
        )

    @pytest.fixture
    def low_confidence_signal(self):
        """낮은 신뢰도 신호"""
        return Signal(
            strategy_id="low_conf_strategy",
            market="USDT-ETH",
            direction=SignalDirection.SHORT,
            strength=0.5,
            confidence=0.4,  # 낮은 신뢰도
            entry_price=Decimal("3000"),
            stop_loss=Decimal("3200"),
            take_profit=Decimal("2700"),
            timeframe=Timeframe.DAY,
            timestamp=datetime.now(tz=timezone.utc),
        )

    @pytest.fixture
    def multiple_signals(self):
        """여러 심볼에 대한 신호들"""
        return [
            Signal(
                strategy_id="strategy_1",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.8,
                confidence=0.75,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_2",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.7,
                confidence=0.65,
                entry_price=Decimal("50100"),
                stop_loss=Decimal("48100"),
                take_profit=Decimal("55100"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_3",
                market="USDT-ETH",
                direction=SignalDirection.SHORT,
                strength=0.9,
                confidence=0.85,
                entry_price=Decimal("3000"),
                stop_loss=Decimal("3200"),
                take_profit=Decimal("2700"),
                timeframe=Timeframe.DAY,
            ),
        ]

    # ============= 초기화 테스트 =============

    def test_aggregator_initializes_with_default_min_confidence(self):
        """집계기는 기본 최소 신뢰도로 초기화된다."""
        aggregator = SignalAggregator()
        assert aggregator.min_confidence == 0.6

    def test_aggregator_initializes_with_custom_min_confidence(self):
        """집계기는 커스텀 최소 신뢰도로 초기화된다."""
        aggregator = SignalAggregator(min_confidence=0.8)
        assert aggregator.min_confidence == 0.8

    def test_aggregator_starts_with_empty_signals(self):
        """집계기는 빈 신호 목록으로 시작한다."""
        aggregator = SignalAggregator()
        assert aggregator.signal_count == 0
        assert aggregator.get_all_signals() == {}

    # ============= 신호 추가 테스트 =============

    def test_add_signal_accepts_signal_with_sufficient_confidence(self, sample_signal):
        """신뢰도가 충분한 신호를 수락한다."""
        aggregator = SignalAggregator(min_confidence=0.6)
        aggregator.add_signal(sample_signal)

        assert aggregator.signal_count == 1
        signals = aggregator.get_signals("USDT-BTC")
        assert len(signals) == 1
        assert signals[0] == sample_signal

    def test_add_signal_rejects_signal_with_low_confidence(self, low_confidence_signal):
        """신뢰도가 낮은 신호를 거부한다."""
        aggregator = SignalAggregator(min_confidence=0.6)
        aggregator.add_signal(low_confidence_signal)

        assert aggregator.signal_count == 0
        assert aggregator.get_signals("USDT-ETH") == []

    def test_add_signal_groups_by_market(self, multiple_signals):
        """신호를 심볼별로 그룹화한다."""
        aggregator = SignalAggregator(min_confidence=0.6)
        for signal in multiple_signals:
            aggregator.add_signal(signal)

        assert aggregator.signal_count == 3
        assert len(aggregator.get_signals("USDT-BTC")) == 2
        assert len(aggregator.get_signals("USDT-ETH")) == 1

    def test_add_signal_maintains_order(self, sample_signal):
        """신호는 추가된 순서대로 유지된다."""
        signal1 = sample_signal
        signal2 = Signal(
            strategy_id="strategy_2",
            market="USDT-BTC",
            direction=SignalDirection.SHORT,
            strength=0.7,
            confidence=0.7,
            entry_price=Decimal("51000"),
            stop_loss=Decimal("53000"),
            take_profit=Decimal("48000"),
            timeframe=Timeframe.HOUR,
        )

        aggregator = SignalAggregator()
        aggregator.add_signal(signal1)
        aggregator.add_signal(signal2)

        signals = aggregator.get_signals("USDT-BTC")
        assert signals[0].strategy_id == "test_strategy"
        assert signals[1].strategy_id == "strategy_2"

    def test_add_signal_allows_multiple_signals_same_strategy_different_markets(self):
        """같은 전략에서 다른 심볼에 대한 신호를 허용한다."""
        signal1 = Signal(
            strategy_id="same_strategy",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.8,
            confidence=0.75,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
        )
        signal2 = Signal(
            strategy_id="same_strategy",
            market="USDT-ETH",
            direction=SignalDirection.LONG,
            strength=0.8,
            confidence=0.75,
            entry_price=Decimal("3000"),
            stop_loss=Decimal("2900"),
            take_profit=Decimal("3300"),
            timeframe=Timeframe.HOUR,
        )

        aggregator = SignalAggregator()
        aggregator.add_signal(signal1)
        aggregator.add_signal(signal2)

        assert aggregator.signal_count == 2
        assert len(aggregator.get_signals("USDT-BTC")) == 1
        assert len(aggregator.get_signals("USDT-ETH")) == 1

    # ============= 신호 조회 테스트 =============

    def test_get_signals_returns_empty_list_for_unknown_symbol(self):
        """알 수 없는 심볼에 대해 빈 리스트를 반환한다."""
        aggregator = SignalAggregator()
        assert aggregator.get_signals("USDT-UNKNOWN") == []

    def test_get_signals_returns_all_signals_for_symbol(self, multiple_signals):
        """특정 심볼의 모든 신호를 반환한다."""
        aggregator = SignalAggregator(min_confidence=0.6)
        for signal in multiple_signals:
            aggregator.add_signal(signal)

        btc_signals = aggregator.get_signals("USDT-BTC")
        assert len(btc_signals) == 2
        assert all(s.market == "USDT-BTC" for s in btc_signals)

    def test_get_all_signals_returns_grouped_signals(self, multiple_signals):
        """모든 신호를 심볼별로 그룹화하여 반환한다."""
        aggregator = SignalAggregator(min_confidence=0.6)
        for signal in multiple_signals:
            aggregator.add_signal(signal)

        all_signals = aggregator.get_all_signals()
        assert "USDT-BTC" in all_signals
        assert "USDT-ETH" in all_signals
        assert len(all_signals["USDT-BTC"]) == 2
        assert len(all_signals["USDT-ETH"]) == 1

    def test_get_all_signals_returns_copy(self, sample_signal):
        """get_all_signals는 복사본을 반환한다."""
        aggregator = SignalAggregator()
        aggregator.add_signal(sample_signal)

        signals1 = aggregator.get_all_signals()
        signals2 = aggregator.get_all_signals()

        # 서로 다른 객체여야 함
        assert signals1 is not signals2

    # ============= 신호 초기화 테스트 =============

    def test_clear_removes_all_signals(self, multiple_signals):
        """clear는 모든 신호를 제거한다."""
        aggregator = SignalAggregator(min_confidence=0.6)
        for signal in multiple_signals:
            aggregator.add_signal(signal)

        assert aggregator.signal_count > 0

        aggregator.clear()

        assert aggregator.signal_count == 0
        assert aggregator.get_all_signals() == {}
        assert aggregator.get_signals("USDT-BTC") == []
        assert aggregator.get_signals("USDT-ETH") == []

    def test_clear_allows_adding_signals_after_clear(self, sample_signal):
        """clear 후 새로운 신호를 추가할 수 있다."""
        aggregator = SignalAggregator()
        aggregator.add_signal(sample_signal)
        aggregator.clear()

        new_signal = Signal(
            strategy_id="new_strategy",
            market="USDT-BTC",
            direction=SignalDirection.SHORT,
            strength=0.9,
            confidence=0.85,
            entry_price=Decimal("52000"),
            stop_loss=Decimal("54000"),
            take_profit=Decimal("49000"),
            timeframe=Timeframe.HOUR,
        )
        aggregator.add_signal(new_signal)

        assert aggregator.signal_count == 1
        assert aggregator.get_signals("USDT-BTC")[0] == new_signal

    # ============= signal_count 프로퍼티 테스트 =============

    def test_signal_count_returns_zero_for_empty_aggregator(self):
        """빈 집계기는 0을 반환한다."""
        aggregator = SignalAggregator()
        assert aggregator.signal_count == 0

    def test_signal_count_returns_correct_count_for_single_symbol(self, sample_signal):
        """단일 심볼에 대한 신호 개수를 정확히 반환한다."""
        aggregator = SignalAggregator()
        aggregator.add_signal(sample_signal)
        assert aggregator.signal_count == 1

    def test_signal_count_returns_correct_count_for_multiple_symbols(self, multiple_signals):
        """여러 심볼에 대한 전체 신호 개수를 정확히 반환한다."""
        aggregator = SignalAggregator(min_confidence=0.6)
        for signal in multiple_signals:
            aggregator.add_signal(signal)

        assert aggregator.signal_count == 3

    def test_signal_count_updates_after_clear(self, multiple_signals):
        """clear 후 signal_count가 업데이트된다."""
        aggregator = SignalAggregator(min_confidence=0.6)
        for signal in multiple_signals:
            aggregator.add_signal(signal)

        assert aggregator.signal_count == 3

        aggregator.clear()
        assert aggregator.signal_count == 0

    # ============= 엣지 케이스 테스트 =============

    def test_min_confidence_boundary_exactly_at_threshold(self):
        """신뢰도가 정확히 임계값과 같을 때 수락된다."""
        signal = Signal(
            strategy_id="boundary_test",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.8,
            confidence=0.6,  # 정확히 임계값
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
        )

        aggregator = SignalAggregator(min_confidence=0.6)
        aggregator.add_signal(signal)

        assert aggregator.signal_count == 1

    def test_min_confidence_boundary_just_below_threshold(self):
        """신뢰도가 임계값보다 약간 낮을 때 거부된다."""
        signal = Signal(
            strategy_id="boundary_test",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.8,
            confidence=0.59,  # 임계값보다 약간 낮음
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
        )

        aggregator = SignalAggregator(min_confidence=0.6)
        aggregator.add_signal(signal)

        assert aggregator.signal_count == 0

    def test_multiple_strategies_same_market_different_directions(self):
        """같은 심볼에 대해 서로 다른 방향의 신호를 허용한다."""
        signal_long = Signal(
            strategy_id="strategy_1",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.8,
            confidence=0.75,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
        )
        signal_short = Signal(
            strategy_id="strategy_2",
            market="USDT-BTC",
            direction=SignalDirection.SHORT,
            strength=0.7,
            confidence=0.7,
            entry_price=Decimal("51000"),
            stop_loss=Decimal("53000"),
            take_profit=Decimal("48000"),
            timeframe=Timeframe.HOUR,
        )

        aggregator = SignalAggregator()
        aggregator.add_signal(signal_long)
        aggregator.add_signal(signal_short)

        signals = aggregator.get_signals("USDT-BTC")
        assert len(signals) == 2
        assert signals[0].direction == SignalDirection.LONG
        assert signals[1].direction == SignalDirection.SHORT

    def test_aggregator_with_zero_min_confidence_accepts_all_signals(self):
        """최소 신뢰도 0은 모든 신호를 수락한다."""
        low_conf_signal = Signal(
            strategy_id="low_conf",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.3,
            confidence=0.1,  # 매우 낮은 신뢰도
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
        )

        aggregator = SignalAggregator(min_confidence=0.0)
        aggregator.add_signal(low_conf_signal)

        assert aggregator.signal_count == 1

    def test_aggregator_with_very_high_min_confidence_rejects_most_signals(self, sample_signal):
        """매우 높은 최소 신뢰도는 대부분의 신호를 거부한다."""
        aggregator = SignalAggregator(min_confidence=0.95)
        aggregator.add_signal(sample_signal)  # confidence = 0.75

        assert aggregator.signal_count == 0
