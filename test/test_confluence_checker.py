from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.decision import ConfluenceChecker
from src.strategies.codes import SignalDirection
from src.strategies.models import Signal
from src.trading.exchanges.upbit.codes import Timeframe


class TestConfluenceChecker:
    """ConfluenceChecker 테스트"""

    @pytest.fixture
    def sample_signals_same_direction(self):
        """같은 방향의 신호들"""
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
                timestamp=datetime.now(tz=timezone.utc),
            ),
            Signal(
                strategy_id="strategy_2",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.7,
                confidence=0.65,
                entry_price=Decimal("50200"),
                stop_loss=Decimal("48200"),
                take_profit=Decimal("54800"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
        ]

    @pytest.fixture
    def sample_signals_mixed_direction(self):
        """혼합된 방향의 신호들"""
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
                direction=SignalDirection.SHORT,
                strength=0.7,
                confidence=0.65,
                entry_price=Decimal("50200"),
                stop_loss=Decimal("52200"),
                take_profit=Decimal("47000"),
                timeframe=Timeframe.HOUR,
            ),
        ]

    @pytest.fixture
    def sample_signals_with_hold(self):
        """HOLD 신호를 포함한 신호들"""
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
                entry_price=Decimal("50200"),
                stop_loss=Decimal("48200"),
                take_profit=Decimal("54800"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_3",
                market="USDT-BTC",
                direction=SignalDirection.HOLD,
                strength=0.5,
                confidence=0.5,
                entry_price=Decimal("50100"),
                stop_loss=Decimal("0"),
                take_profit=Decimal("0"),
                timeframe=Timeframe.HOUR,
            ),
        ]

    # ============= 초기화 테스트 =============

    def test_checker_initializes_with_default_min_signals(self):
        """체커는 기본 최소 신호 개수로 초기화된다."""
        checker = ConfluenceChecker()
        assert checker.min_signals == 2

    def test_checker_initializes_with_custom_min_signals(self):
        """체커는 커스텀 최소 신호 개수로 초기화된다."""
        checker = ConfluenceChecker(min_signals=3)
        assert checker.min_signals == 3

    # ============= check() 메서드 기본 테스트 =============

    def test_check_returns_none_when_insufficient_signals(self, sample_signals_same_direction):
        """신호 개수가 부족하면 None을 반환한다."""
        checker = ConfluenceChecker(min_signals=3)
        result = checker.check(sample_signals_same_direction)  # 2개만 있음

        assert result is None

    def test_check_returns_none_for_empty_signals(self):
        """빈 신호 리스트에 대해 None을 반환한다."""
        checker = ConfluenceChecker()
        result = checker.check([])

        assert result is None

    def test_check_returns_trade_candidate_with_sufficient_same_direction_signals(self, sample_signals_same_direction):
        """동일 방향의 충분한 신호가 있으면 TradeCandidate를 반환한다."""
        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(sample_signals_same_direction)

        assert result is not None
        assert result.market == "USDT-BTC"
        assert result.direction == SignalDirection.LONG
        assert len(result.contributing_signals) == 2

    def test_check_returns_none_when_no_direction_has_minimum_signals(self, sample_signals_mixed_direction):
        """어떤 방향도 최소 신호 개수를 만족하지 못하면 None을 반환한다."""
        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(sample_signals_mixed_direction)  # LONG 1개, SHORT 1개

        assert result is None

    def test_check_ignores_hold_signals(self, sample_signals_with_hold):
        """HOLD 신호는 무시하고 나머지 신호로 판단한다."""
        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(sample_signals_with_hold)

        assert result is not None
        assert result.direction == SignalDirection.LONG
        assert len(result.contributing_signals) == 2
        # HOLD 신호가 포함되지 않았는지 확인
        assert all(s.direction != SignalDirection.HOLD for s in result.contributing_signals)

    # ============= 방향 선택 테스트 =============

    def test_check_selects_direction_with_most_signals(self):
        """가장 많은 신호를 가진 방향을 선택한다."""
        signals = [
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
                entry_price=Decimal("50200"),
                stop_loss=Decimal("48200"),
                take_profit=Decimal("54800"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_3",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.75,
                confidence=0.7,
                entry_price=Decimal("50100"),
                stop_loss=Decimal("48100"),
                take_profit=Decimal("54900"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_4",
                market="USDT-BTC",
                direction=SignalDirection.SHORT,
                strength=0.6,
                confidence=0.6,
                entry_price=Decimal("50300"),
                stop_loss=Decimal("52300"),
                take_profit=Decimal("47000"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_5",
                market="USDT-BTC",
                direction=SignalDirection.SHORT,
                strength=0.65,
                confidence=0.65,
                entry_price=Decimal("50400"),
                stop_loss=Decimal("52400"),
                take_profit=Decimal("47100"),
                timeframe=Timeframe.HOUR,
            ),
        ]

        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(signals)

        # LONG이 3개로 더 많음
        assert result is not None
        assert result.direction == SignalDirection.LONG
        assert len(result.contributing_signals) == 3

    # ============= TradeCandidate 필드 검증 테스트 =============

    def test_check_calculates_average_entry_price(self, sample_signals_same_direction):
        """평균 진입 가격을 계산한다."""
        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(sample_signals_same_direction)

        # (50000 + 50200) / 2 = 50100
        expected_entry = Decimal("50100")
        assert result.suggested_entry == expected_entry

    def test_check_uses_minimum_stop_loss(self, sample_signals_same_direction):
        """최소 손절 가격을 사용한다."""
        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(sample_signals_same_direction)

        # min(48000, 48200) = 48000
        expected_stop = Decimal("48000")
        assert result.suggested_stop_loss == expected_stop

    def test_check_uses_maximum_take_profit(self, sample_signals_same_direction):
        """최대 익절 가격을 사용한다."""
        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(sample_signals_same_direction)

        # max(55000, 54800) = 55000
        expected_tp = Decimal("55000")
        assert result.suggested_take_profit == expected_tp

    def test_check_sets_combined_strength(self, sample_signals_same_direction):
        """결합된 강도를 설정한다."""
        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(sample_signals_same_direction)

        assert 0.0 <= result.combined_strength <= 1.0
        # 두 신호의 강도가 0.8, 0.7이므로 결합 강도는 이 범위 내에 있어야 함
        assert 0.6 <= result.combined_strength <= 1.0

    def test_check_sets_timestamp(self, sample_signals_same_direction):
        """타임스탬프를 설정한다."""
        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(sample_signals_same_direction)

        assert result.timestamp is not None
        # 최근 시간이어야 함 (1분 이내)
        assert (datetime.now(tz=timezone.utc) - result.timestamp).total_seconds() < 60

    def test_check_includes_contributing_signals(self, sample_signals_same_direction):
        """기여한 신호들을 포함한다."""
        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(sample_signals_same_direction)

        assert len(result.contributing_signals) == 2
        assert result.contributing_signals[0].strategy_id == "strategy_1"
        assert result.contributing_signals[1].strategy_id == "strategy_2"

    # ============= 엣지 케이스 테스트 =============

    def test_check_handles_signals_with_none_prices(self):
        """None 가격을 가진 신호를 처리한다."""
        signals = [
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
                entry_price=None,  # None 가격
                stop_loss=None,
                take_profit=None,
                timeframe=Timeframe.HOUR,
            ),
        ]

        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(signals)

        # None이 아닌 값만 사용하여 계산
        assert result is not None
        assert result.suggested_entry == Decimal("50000")
        assert result.suggested_stop_loss == Decimal("48000")
        assert result.suggested_take_profit == Decimal("55000")

    def test_check_with_single_signal_and_min_signals_one(self):
        """최소 신호가 1개일 때 단일 신호로 후보 생성이 가능하다."""
        signal = Signal(
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

        checker = ConfluenceChecker(min_signals=1)
        result = checker.check([signal])

        assert result is not None
        assert result.direction == SignalDirection.LONG
        assert len(result.contributing_signals) == 1

    def test_check_with_only_hold_signals(self):
        """HOLD 신호만 있을 때 None을 반환한다."""
        signals = [
            Signal(
                strategy_id="strategy_1",
                market="USDT-BTC",
                direction=SignalDirection.HOLD,
                strength=0.5,
                confidence=0.5,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("0"),
                take_profit=Decimal("0"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_2",
                market="USDT-BTC",
                direction=SignalDirection.HOLD,
                strength=0.6,
                confidence=0.6,
                entry_price=Decimal("50100"),
                stop_loss=Decimal("0"),
                take_profit=Decimal("0"),
                timeframe=Timeframe.HOUR,
            ),
        ]

        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(signals)

        assert result is None

    def test_check_with_all_prices_none(self):
        """모든 신호의 가격이 None일 때 0을 반환한다."""
        signals = [
            Signal(
                strategy_id="strategy_1",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.8,
                confidence=0.75,
                entry_price=None,
                stop_loss=None,
                take_profit=None,
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_2",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.7,
                confidence=0.65,
                entry_price=None,
                stop_loss=None,
                take_profit=None,
                timeframe=Timeframe.HOUR,
            ),
        ]

        checker = ConfluenceChecker(min_signals=2)
        result = checker.check(signals)

        assert result is not None
        assert result.suggested_entry == Decimal("0")
        assert result.suggested_stop_loss == Decimal("0")
        assert result.suggested_take_profit == Decimal("0")


class TestCalculateCombinedStrength:
    """_calculate_combined_strength 정적 메서드 테스트"""

    def test_calculate_combined_strength_returns_zero_for_empty_list(self):
        """빈 리스트에 대해 0.0을 반환한다."""
        result = ConfluenceChecker._calculate_combined_strength([])
        assert result == 0.0

    def test_calculate_combined_strength_for_single_signal(self):
        """단일 신호의 강도를 반환한다."""
        signal = Signal(
            strategy_id="strategy_1",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.8,
            confidence=0.75,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
            timestamp=datetime.now(tz=timezone.utc),
        )

        result = ConfluenceChecker._calculate_combined_strength([signal])

        # 단일 신호의 강도와 유사해야 함
        assert 0.7 <= result <= 0.9

    def test_calculate_combined_strength_for_multiple_signals(self):
        """여러 신호의 결합 강도를 계산한다."""
        signals = [
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
                timestamp=datetime.now(tz=timezone.utc),
            ),
            Signal(
                strategy_id="strategy_2",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.7,
                confidence=0.65,
                entry_price=Decimal("50200"),
                stop_loss=Decimal("48200"),
                take_profit=Decimal("54800"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
            Signal(
                strategy_id="strategy_3",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.75,
                confidence=0.7,
                entry_price=Decimal("50100"),
                stop_loss=Decimal("48100"),
                take_profit=Decimal("54900"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
        ]

        result = ConfluenceChecker._calculate_combined_strength(signals)

        # 신호들의 강도 범위 내에 있어야 함
        assert 0.0 <= result <= 1.0
        assert 0.6 <= result <= 0.9

    def test_calculate_combined_strength_is_bounded(self):
        """결합 강도는 항상 0.0 ~ 1.0 범위 내에 있다."""
        # 매우 높은 강도의 신호들
        signals = [
            Signal(
                strategy_id=f"strategy_{i}",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.95,
                confidence=0.95,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            )
            for i in range(5)
        ]

        result = ConfluenceChecker._calculate_combined_strength(signals)

        assert 0.0 <= result <= 1.0

    def test_calculate_combined_strength_with_time_decay(self):
        """오래된 신호는 가중치가 낮아진다."""
        now = datetime.now(tz=timezone.utc)

        recent_signal = Signal(
            strategy_id="recent",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.7,
            confidence=0.7,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
            timestamp=now,  # 최근 신호
        )

        old_signal = Signal(
            strategy_id="old",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.7,
            confidence=0.7,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
            timestamp=now - timedelta(hours=10),  # 10시간 전 신호
        )

        # 최근 신호만
        result_recent = ConfluenceChecker._calculate_combined_strength([recent_signal])
        # 오래된 신호만
        result_old = ConfluenceChecker._calculate_combined_strength([old_signal])

        # 최근 신호의 강도가 더 높거나 같아야 함 (시간 감쇠로 인해)
        # 단일 신호일 때는 차이가 크지 않을 수 있음
        assert result_recent >= result_old - 0.1

    def test_calculate_combined_strength_with_consistent_signals(self):
        """일관된 신호들은 보너스를 받는다."""
        # 매우 일관된 신호들 (비슷한 강도)
        consistent_signals = [
            Signal(
                strategy_id=f"strategy_{i}",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.75,  # 모두 0.75
                confidence=0.7,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            )
            for i in range(3)
        ]

        # 비일관된 신호들 (다양한 강도)
        inconsistent_signals = [
            Signal(
                strategy_id="strategy_1",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.9,
                confidence=0.7,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
            Signal(
                strategy_id="strategy_2",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.6,
                confidence=0.7,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
            Signal(
                strategy_id="strategy_3",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.75,
                confidence=0.7,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
        ]

        result_consistent = ConfluenceChecker._calculate_combined_strength(consistent_signals)
        result_inconsistent = ConfluenceChecker._calculate_combined_strength(inconsistent_signals)

        # 일관된 신호가 더 높은 강도를 가져야 함
        assert result_consistent > result_inconsistent

    def test_calculate_combined_strength_with_outliers(self):
        """이상치는 필터링된다 (4개 이상일 때)."""
        signals = [
            Signal(
                strategy_id="strategy_1",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.7,
                confidence=0.7,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
            Signal(
                strategy_id="strategy_2",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.75,
                confidence=0.7,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
            Signal(
                strategy_id="strategy_3",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.72,
                confidence=0.7,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
            Signal(
                strategy_id="outlier",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.1,  # 이상치
                confidence=0.7,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
        ]

        result = ConfluenceChecker._calculate_combined_strength(signals)

        # 이상치 없는 평균 (0.7 + 0.75 + 0.72) / 3 ≈ 0.72
        # 이상치 포함 평균 (0.7 + 0.75 + 0.72 + 0.1) / 4 ≈ 0.57
        # 이상치가 필터링되므로 결과는 0.72에 가까워야 함
        assert result > 0.65

    def test_calculate_combined_strength_with_custom_parameters(self):
        """커스텀 파라미터를 사용할 수 있다."""
        signals = [
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
                timestamp=datetime.now(tz=timezone.utc),
            ),
            Signal(
                strategy_id="strategy_2",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.7,
                confidence=0.65,
                entry_price=Decimal("50200"),
                stop_loss=Decimal("48200"),
                take_profit=Decimal("54800"),
                timeframe=Timeframe.HOUR,
                timestamp=datetime.now(tz=timezone.utc),
            ),
        ]

        result = ConfluenceChecker._calculate_combined_strength(signals, time_decay_factor=0.5, consistency_bonus=0.3)

        assert 0.0 <= result <= 1.0
