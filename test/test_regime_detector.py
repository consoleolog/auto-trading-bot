from decimal import Decimal
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.strategies.codes import MarketRegime
from src.strategies.regime_detector import RegimeDetector

# ============================================================================
# Helpers
# ============================================================================


def make_candles(n: int, price: float = 100.0) -> list:
    """n개의 Mock 캔들을 생성합니다."""
    candles = []
    for _ in range(n):
        c = MagicMock()
        c.trade_price = Decimal(str(price))
        candles.append(c)
    return candles


def patch_ema(short: float, mid: float, long: float):
    """calculate_ema 를 (short, mid, long) 순서로 반환하도록 패치합니다."""
    return patch(
        "src.strategies.regime_detector.calculate_ema",
        side_effect=[
            np.array([short]),
            np.array([mid]),
            np.array([long]),
        ],
    )


# ============================================================================
# Tests
# ============================================================================


class TestRegimeDetectorInit:
    def test_default_regime_is_unknown(self):
        """기본 국면은 UNKNOWN이다."""
        detector = RegimeDetector()
        assert detector.current_regime == MarketRegime.UNKNOWN

    def test_custom_default_regime_is_applied(self):
        """default_regime 파라미터가 current_regime 초기값으로 적용된다."""
        detector = RegimeDetector(default_regime=MarketRegime.STABLE_BULL)
        assert detector.current_regime == MarketRegime.STABLE_BULL

    def test_default_ema_periods(self):
        """EMA 기간의 기본값이 5 / 20 / 40 이다."""
        detector = RegimeDetector()
        assert detector._ema_short_period == 5
        assert detector._ema_mid_period == 20
        assert detector._ema_long_period == 40

    def test_custom_ema_periods_from_config(self):
        """config 로 EMA 기간을 덮어쓸 수 있다."""
        config = {"ema_short_period": 10, "ema_mid_period": 30, "ema_long_period": 60}
        detector = RegimeDetector(config=config)
        assert detector._ema_short_period == 10
        assert detector._ema_mid_period == 30
        assert detector._ema_long_period == 60


class TestRegimeDetectorInsufficientData:
    def test_returns_current_regime_when_candles_are_fewer_than_long_period(self, caplog):
        """ema_long_period 미만의 캔들이면 현재 국면을 그대로 반환한다."""
        detector = RegimeDetector()
        candles = make_candles(39)  # 기본 long_period(40) - 1

        result = detector.detect(candles)

        assert result == MarketRegime.UNKNOWN

    def test_logs_warning_when_candles_are_insufficient(self, caplog):
        """캔들이 부족하면 경고 로그를 남긴다."""
        detector = RegimeDetector()
        candles = make_candles(5)

        with caplog.at_level("WARNING"):
            detector.detect(candles)

        assert "데이터 부족" in caplog.text
        assert "5" in caplog.text

    def test_returns_custom_default_regime_on_insufficient_data(self):
        """기본 국면이 STABLE_BEAR 일 때 데이터 부족 시 STABLE_BEAR 를 반환한다."""
        detector = RegimeDetector(default_regime=MarketRegime.STABLE_BEAR)
        candles = make_candles(10)

        result = detector.detect(candles)

        assert result == MarketRegime.STABLE_BEAR

    def test_uses_ema_long_period_as_minimum_candle_count(self):
        """custom long_period 도 최소 캔들 수 기준으로 적용된다."""
        config = {"ema_long_period": 20}
        detector = RegimeDetector(config=config)

        assert detector.detect(make_candles(19)) == MarketRegime.UNKNOWN

        with patch_ema(short=110, mid=105, long=100):
            assert detector.detect(make_candles(20)) == MarketRegime.STABLE_BULL


class TestRegimeDetectorClassification:
    """EMA 배열(순서)에 따른 국면 분류 테스트"""

    @pytest.fixture
    def detector(self):
        return RegimeDetector()

    @pytest.fixture
    def candles(self):
        return make_candles(40)

    # ── 6가지 EMA 배열 케이스 ──────────────────────────────────────────────

    @pytest.mark.parametrize(
        "short, mid, long, expected",
        [
            (110.0, 105.0, 100.0, MarketRegime.STABLE_BULL),  # s > m > l
            (105.0, 110.0, 100.0, MarketRegime.END_OF_BULL),  # m > s > l
            (100.0, 110.0, 105.0, MarketRegime.START_OF_BEAR),  # m > l > s
            (100.0, 105.0, 110.0, MarketRegime.STABLE_BEAR),  # l > m > s
            (105.0, 100.0, 110.0, MarketRegime.END_OF_BEAR),  # l > s > m
            (110.0, 100.0, 105.0, MarketRegime.START_OF_BULL),  # s > l > m
        ],
        ids=[
            "STABLE_BULL(s>m>l)",
            "END_OF_BULL(m>s>l)",
            "START_OF_BEAR(m>l>s)",
            "STABLE_BEAR(l>m>s)",
            "END_OF_BEAR(l>s>m)",
            "START_OF_BULL(s>l>m)",
        ],
    )
    def test_ema_ordering_maps_to_correct_regime(self, detector, candles, short, mid, long, expected):
        """EMA 배열이 각 국면을 올바르게 반환한다."""
        with patch_ema(short=short, mid=mid, long=long):
            result = detector.detect(candles)
        assert result == expected

    def test_returns_unknown_when_all_ema_values_are_equal(self, detector, candles):
        """세 EMA 값이 모두 같으면 UNKNOWN을 반환한다."""
        with patch_ema(short=100.0, mid=100.0, long=100.0):
            result = detector.detect(candles)
        assert result == MarketRegime.UNKNOWN

    def test_returns_unknown_when_short_equals_mid(self, detector, candles):
        """단기=중기이면 어느 케이스에도 해당하지 않아 UNKNOWN을 반환한다."""
        with patch_ema(short=105.0, mid=105.0, long=100.0):
            result = detector.detect(candles)
        assert result == MarketRegime.UNKNOWN


class TestRegimeDetectorCalculateEmaCall:
    """calculate_ema 호출 방식 검증"""

    def test_calls_calculate_ema_three_times(self):
        """detect 는 short, mid, long EMA 계산을 위해 calculate_ema를 3번 호출한다."""
        detector = RegimeDetector()
        candles = make_candles(40)

        with patch("src.strategies.regime_detector.calculate_ema") as mock_ema:
            mock_ema.side_effect = [
                np.array([110.0]),
                np.array([105.0]),
                np.array([100.0]),
            ]
            detector.detect(candles)

        assert mock_ema.call_count == 3

    def test_passes_ema_periods_in_correct_order(self):
        """calculate_ema 호출 순서가 short → mid → long 이다."""
        config = {"ema_short_period": 3, "ema_mid_period": 10, "ema_long_period": 20}
        detector = RegimeDetector(config=config)
        candles = make_candles(20)

        with patch("src.strategies.regime_detector.calculate_ema") as mock_ema:
            mock_ema.side_effect = [
                np.array([110.0]),
                np.array([105.0]),
                np.array([100.0]),
            ]
            detector.detect(candles)

        periods_called = [call.args[1] for call in mock_ema.call_args_list]
        assert periods_called == [3, 10, 20]

    def test_passes_candle_trade_prices_as_numpy_array(self):
        """detect가 candle.trade_price 값을 numpy 배열로 변환하여 전달한다."""
        detector = RegimeDetector()
        candles = make_candles(40, price=50000.0)

        with patch("src.strategies.regime_detector.calculate_ema") as mock_ema:
            mock_ema.side_effect = [
                np.array([110.0]),
                np.array([105.0]),
                np.array([100.0]),
            ]
            detector.detect(candles)

        prices_passed = mock_ema.call_args_list[0].args[0]
        assert isinstance(prices_passed, np.ndarray)
        assert len(prices_passed) == 40
        assert all(p == 50000.0 for p in prices_passed)
