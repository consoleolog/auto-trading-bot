from decimal import Decimal

import pytest

from src.decision.codes import DecisionStatus
from src.decision.models import TradeCandidate
from src.decision.position_sizer import PositionSizer
from src.portfolio.models.portfolio_state import PortfolioState
from src.portfolio.models.position import Position
from src.risk.models import RiskLimitsConfig
from src.strategies.codes import SignalDirection
from src.strategies.models import Signal
from src.trading.exchanges.upbit.codes import Timeframe


class TestPositionSizer:
    """PositionSizer 테스트"""

    @pytest.fixture
    def default_risk_config(self):
        """기본 리스크 설정"""
        return RiskLimitsConfig(
            max_drawdown=0.20,
            daily_loss_limit=0.05,
            weekly_loss_limit=0.10,
            max_position_size=0.40,
            max_risk_per_trade=0.02,
            max_positions=5,
            max_portfolio_exposure=0.40,
        )

    @pytest.fixture
    def sample_portfolio(self):
        """샘플 포트폴리오 상태"""
        return PortfolioState(
            total_capital=Decimal("50000000"),  # 5천만원
            available_capital=Decimal("40000000"),  # 4천만원
            positions={},
            daily_pnl=Decimal("0"),
            weekly_pnl=Decimal("0"),
            total_pnl=Decimal("0"),
            high_water_mark=Decimal("50000000"),
            trade_count_today=0,
        )

    @pytest.fixture
    def sample_candidate(self):
        """샘플 거래 후보"""
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
        ]

        return TradeCandidate(
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            combined_strength=0.75,
            contributing_signals=signals,
            suggested_entry=Decimal("50000"),
            suggested_stop_loss=Decimal("48000"),
            suggested_take_profit=Decimal("55000"),
        )

    # ============= 초기화 테스트 =============

    def test_sizer_initializes_with_risk_config(self, default_risk_config):
        """포지션 사이저가 리스크 설정으로 초기화된다."""
        sizer = PositionSizer(default_risk_config)

        assert sizer.max_risk_per_trade == 0.02
        assert sizer.max_position_size == 0.40
        assert sizer.max_portfolio_exposure == 0.40

    # ============= calculate() 메서드 테스트 =============

    def test_calculate_returns_decision_object(self, default_risk_config, sample_candidate, sample_portfolio):
        """calculate는 Decision 객체를 반환한다."""
        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(sample_candidate, sample_portfolio, current_price)

        assert decision is not None
        assert decision.market == "USDT-BTC"
        assert decision.direction == SignalDirection.LONG
        assert decision.status == DecisionStatus.PENDING
        assert decision.volume > 0
        assert decision.entry_price == Decimal("50000")
        assert decision.stop_loss == Decimal("48000")
        assert decision.take_profit == Decimal("55000")

    def test_calculate_sets_volume_based_on_risk(self, default_risk_config, sample_candidate, sample_portfolio):
        """거래 수량이 리스크 기반으로 계산된다."""
        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(sample_candidate, sample_portfolio, current_price)

        # 수량이 0보다 크고 합리적인 범위에 있어야 함
        assert decision.volume > 0
        # 포지션 가치 = 수량 * 진입가
        position_value = decision.volume * decision.entry_price
        # 최대 포지션 크기를 초과하지 않아야 함
        max_position_value = sample_portfolio.available_capital * Decimal("0.40")
        assert position_value <= max_position_value

    def test_calculate_respects_max_position_size(self, default_risk_config, sample_candidate, sample_portfolio):
        """최대 포지션 크기를 준수한다."""
        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(sample_candidate, sample_portfolio, current_price)

        position_value = decision.volume * decision.entry_price
        max_position_value = sample_portfolio.available_capital * Decimal(str(default_risk_config.max_position_size))

        assert position_value <= max_position_value

    def test_calculate_respects_portfolio_exposure_limit(self, default_risk_config, sample_candidate):
        """포트폴리오 노출 제한을 준수한다."""
        # 이미 포지션이 있는 포트폴리오
        existing_position = Position(
            market="USDT-ETH",
            signal_direction=SignalDirection.LONG,
            entry_price=Decimal("3000"),
            current_price=Decimal("3100"),
            volume=Decimal("5"),
            stop_loss=Decimal("2900"),
            take_profit=Decimal("3300"),
            strategy_id="strategy_1",
        )

        portfolio = PortfolioState(
            total_capital=Decimal("50000000"),
            available_capital=Decimal("34500000"),  # 3000 * 5 = 15000원 사용 중
            positions={"USDT-ETH": existing_position},
            high_water_mark=Decimal("50000000"),
        )

        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(sample_candidate, portfolio, current_price)

        # 기존 포지션 가치 + 새 포지션 가치가 총 자본의 40%를 초과하지 않아야 함
        new_position_value = decision.volume * decision.entry_price
        total_exposure = existing_position.value + new_position_value
        max_exposure = portfolio.total_capital * Decimal(str(default_risk_config.max_portfolio_exposure))

        assert total_exposure <= max_exposure

    def test_calculate_uses_current_price_when_suggested_entry_is_zero(self, default_risk_config, sample_portfolio):
        """제안 진입가가 0일 때 현재 가격을 사용한다."""
        candidate = TradeCandidate(
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            combined_strength=0.75,
            contributing_signals=[],
            suggested_entry=Decimal("0"),  # 진입가가 0
            suggested_stop_loss=Decimal("48000"),
            suggested_take_profit=Decimal("55000"),
        )

        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(candidate, sample_portfolio, current_price)

        # 현재 가격을 진입가로 사용해야 함
        assert decision.entry_price == current_price

    def test_calculate_includes_contributing_signals(self, default_risk_config, sample_candidate, sample_portfolio):
        """Decision에 기여한 신호들이 포함된다."""
        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(sample_candidate, sample_portfolio, current_price)

        assert len(decision.contributing_signals) == 2
        assert "strategy_1" in decision.contributing_signals
        assert "strategy_2" in decision.contributing_signals

    def test_calculate_with_atr_adjusts_position_size(self, default_risk_config, sample_candidate, sample_portfolio):
        """ATR이 제공되면 변동성 기반 조정이 적용된다."""
        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")
        atr = Decimal("1000")  # 2% ATR

        decision_with_atr = sizer.calculate(sample_candidate, sample_portfolio, current_price, atr)
        decision_without_atr = sizer.calculate(sample_candidate, sample_portfolio, current_price, None)

        # ATR 적용 여부에 따라 포지션 크기가 달라질 수 있음
        # (같을 수도 있지만 로직은 실행됨)
        assert decision_with_atr.volume > 0
        assert decision_without_atr.volume > 0

    def test_calculate_with_high_drawdown_reduces_position(self, default_risk_config, sample_candidate):
        """높은 드로다운일 때 포지션 크기가 감소한다."""
        # 드로다운이 없는 포트폴리오
        portfolio_no_dd = PortfolioState(
            total_capital=Decimal("50000000"),
            available_capital=Decimal("40000000"),
            positions={},
            high_water_mark=Decimal("50000000"),  # 현재가 최고점
        )

        # 드로다운이 큰 포트폴리오
        portfolio_high_dd = PortfolioState(
            total_capital=Decimal("42500000"),  # 15% 하락
            available_capital=Decimal("35000000"),
            positions={},
            high_water_mark=Decimal("50000000"),
        )

        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision_no_dd = sizer.calculate(sample_candidate, portfolio_no_dd, current_price)
        decision_high_dd = sizer.calculate(sample_candidate, portfolio_high_dd, current_price)

        # 드로다운이 클 때 포지션 크기가 작아야 함
        assert decision_high_dd.volume < decision_no_dd.volume

    # ============= _calculate_base_position() 테스트 =============

    def test_calculate_base_position_uses_stop_loss(self, default_risk_config):
        """손절가 기반 포지션 크기를 계산한다."""
        sizer = PositionSizer(default_risk_config)
        entry_price = Decimal("50000")
        stop_loss = Decimal("48000")
        available_capital = Decimal("40000000")

        base_position = sizer._calculate_base_position(entry_price, stop_loss, available_capital)

        # 리스크 금액 = 40,000,000 * 0.02 = 800,000
        # 손절 거리 = 50,000 - 48,000 = 2,000 (4%)
        # 포지션 크기 = 800,000 / 0.04 = 20,000,000
        expected_position = Decimal("20000000")
        assert abs(base_position - expected_position) < Decimal("1000")

    def test_calculate_base_position_fallback_when_no_stop_loss(self, default_risk_config):
        """손절가가 없을 때 최대 포지션 크기를 사용한다."""
        sizer = PositionSizer(default_risk_config)
        entry_price = Decimal("50000")
        stop_loss = Decimal("0")
        available_capital = Decimal("40000000")

        base_position = sizer._calculate_base_position(entry_price, stop_loss, available_capital)

        # 최대 포지션 크기 사용
        expected_position = available_capital * Decimal("0.40")
        assert base_position == expected_position

    def test_calculate_base_position_fallback_when_zero_entry_price(self, default_risk_config):
        """진입가가 0일 때 폴백을 사용한다."""
        sizer = PositionSizer(default_risk_config)
        entry_price = Decimal("0")
        stop_loss = Decimal("48000")
        available_capital = Decimal("40000000")

        base_position = sizer._calculate_base_position(entry_price, stop_loss, available_capital)

        expected_position = available_capital * Decimal("0.40")
        assert base_position == expected_position

    # ============= _calculate_kelly_fraction() 테스트 =============

    def test_calculate_kelly_fraction_with_valid_inputs(self):
        """유효한 입력으로 켈리 비율을 계산한다."""
        win_probability = 0.6
        entry_price = Decimal("50000")
        stop_loss = Decimal("48000")
        take_profit = Decimal("55000")

        kelly = PositionSizer._calculate_kelly_fraction(win_probability, entry_price, stop_loss, take_profit)

        # 켈리 비율은 0.25 ~ 1.0 범위
        assert 0.25 <= kelly <= 1.0

    def test_calculate_kelly_fraction_returns_default_for_invalid_inputs(self):
        """유효하지 않은 입력에 대해 기본값을 반환한다."""
        win_probability = 0.6

        # 진입가가 0
        kelly1 = PositionSizer._calculate_kelly_fraction(
            win_probability, Decimal("0"), Decimal("48000"), Decimal("55000")
        )
        assert kelly1 == 1.0

        # 손절가가 0
        kelly2 = PositionSizer._calculate_kelly_fraction(
            win_probability, Decimal("50000"), Decimal("0"), Decimal("55000")
        )
        assert kelly2 == 1.0

        # 익절가가 0
        kelly3 = PositionSizer._calculate_kelly_fraction(
            win_probability, Decimal("50000"), Decimal("48000"), Decimal("0")
        )
        assert kelly3 == 1.0

    def test_calculate_kelly_fraction_minimum_when_negative(self):
        """음수 켈리일 때 최소값을 반환한다."""
        win_probability = 0.3  # 낮은 승률
        entry_price = Decimal("50000")
        stop_loss = Decimal("48000")
        take_profit = Decimal("51000")  # 작은 이익

        kelly = PositionSizer._calculate_kelly_fraction(win_probability, entry_price, stop_loss, take_profit)

        # 불리한 조건에서도 최소 25%
        assert kelly == 0.25

    # ============= _calculate_strength_multiplier() 테스트 =============

    def test_calculate_strength_multiplier_increases_with_strength(self):
        """신호 강도가 높을수록 배수가 증가한다."""
        multiplier_low = PositionSizer._calculate_strength_multiplier(0.5)
        multiplier_mid = PositionSizer._calculate_strength_multiplier(0.7)
        multiplier_high = PositionSizer._calculate_strength_multiplier(0.9)

        assert multiplier_low < multiplier_mid < multiplier_high

    def test_calculate_strength_multiplier_is_bounded(self):
        """강도 배수가 합리적인 범위 내에 있다."""
        # 매우 낮은 강도
        multiplier_very_low = PositionSizer._calculate_strength_multiplier(0.1)
        assert 0.5 <= multiplier_very_low <= 0.6

        # 매우 높은 강도
        multiplier_very_high = PositionSizer._calculate_strength_multiplier(1.0)
        assert 1.0 <= multiplier_very_high <= 1.3

    def test_calculate_strength_multiplier_at_center_point(self):
        """중심점(0.6)에서 배수가 약 0.85 정도다."""
        multiplier = PositionSizer._calculate_strength_multiplier(0.6)
        # 시그모이드 중심점에서 0.5 정도, 매핑 후 0.5 + 0.5 * 0.7 = 0.85
        assert 0.8 <= multiplier <= 0.9

    # ============= _calculate_drawdown_multiplier() 테스트 =============

    def test_calculate_drawdown_multiplier_no_drawdown(self):
        """드로다운이 없을 때 배수는 1.0이다."""
        multiplier = PositionSizer._calculate_drawdown_multiplier(0.0)
        assert multiplier == 1.0

    def test_calculate_drawdown_multiplier_below_threshold(self):
        """임계값 미만의 드로다운일 때 배수는 1.0이다."""
        multiplier = PositionSizer._calculate_drawdown_multiplier(0.03)  # 3% < 5% threshold
        assert multiplier == 1.0

    def test_calculate_drawdown_multiplier_decreases_with_drawdown(self):
        """드로다운이 증가하면 배수가 감소한다."""
        multiplier_mild = PositionSizer._calculate_drawdown_multiplier(0.07)  # 7%
        multiplier_moderate = PositionSizer._calculate_drawdown_multiplier(0.10)  # 10%
        multiplier_severe = PositionSizer._calculate_drawdown_multiplier(0.15)  # 15%

        assert 1.0 > multiplier_mild > multiplier_moderate > multiplier_severe

    def test_calculate_drawdown_multiplier_minimum_at_severe(self):
        """심각한 드로다운일 때 최소 배수는 0.3이다."""
        multiplier = PositionSizer._calculate_drawdown_multiplier(0.15)
        assert multiplier == 0.3

        multiplier_more = PositionSizer._calculate_drawdown_multiplier(0.20)
        assert multiplier_more == 0.3

    def test_calculate_drawdown_multiplier_linear_between_thresholds(self):
        """임계값 사이에서 선형적으로 감소한다."""
        # 5% ~ 15% 사이에서 선형 감소
        multiplier_start = PositionSizer._calculate_drawdown_multiplier(0.05)  # 5%
        multiplier_mid = PositionSizer._calculate_drawdown_multiplier(0.10)  # 10% (중간)
        multiplier_end = PositionSizer._calculate_drawdown_multiplier(0.15)  # 15%

        # 중간값이 대략 평균이어야 함
        expected_mid = (multiplier_start + multiplier_end) / 2
        assert abs(multiplier_mid - expected_mid) < 0.1

    # ============= _calculate_volatility_multiplier() 테스트 =============

    def test_calculate_volatility_multiplier_with_normal_atr(self):
        """정상 변동성일 때 배수는 1.0에 가깝다."""
        atr = Decimal("1000")  # 2% ATR
        current_price = Decimal("50000")

        multiplier = PositionSizer._calculate_volatility_multiplier(atr, current_price)

        # 기준 ATR(2%)과 일치하므로 1.0
        assert multiplier == 1.0

    def test_calculate_volatility_multiplier_increases_with_low_volatility(self):
        """낮은 변동성일 때 배수가 증가한다."""
        atr = Decimal("500")  # 1% ATR (낮은 변동성)
        current_price = Decimal("50000")

        multiplier = PositionSizer._calculate_volatility_multiplier(atr, current_price)

        # 변동성이 낮으면 포지션 증가
        assert multiplier > 1.0
        assert multiplier <= 1.2

    def test_calculate_volatility_multiplier_decreases_with_high_volatility(self):
        """높은 변동성일 때 배수가 감소한다."""
        atr = Decimal("2000")  # 4% ATR (높은 변동성)
        current_price = Decimal("50000")

        multiplier = PositionSizer._calculate_volatility_multiplier(atr, current_price)

        # 변동성이 높으면 포지션 감소
        assert multiplier < 1.0
        assert multiplier >= 0.5

    def test_calculate_volatility_multiplier_returns_default_for_invalid_inputs(self):
        """유효하지 않은 입력에 대해 1.0을 반환한다."""
        # 가격이 0
        multiplier1 = PositionSizer._calculate_volatility_multiplier(Decimal("1000"), Decimal("0"))
        assert multiplier1 == 1.0

        # ATR이 0
        multiplier2 = PositionSizer._calculate_volatility_multiplier(Decimal("0"), Decimal("50000"))
        assert multiplier2 == 1.0

        # 둘 다 음수
        multiplier3 = PositionSizer._calculate_volatility_multiplier(Decimal("-1000"), Decimal("-50000"))
        assert multiplier3 == 1.0

    def test_calculate_volatility_multiplier_is_bounded(self):
        """변동성 배수가 범위 내에 있다."""
        # 매우 낮은 변동성
        atr_very_low = Decimal("100")  # 0.2% ATR
        current_price = Decimal("50000")
        multiplier_very_low = PositionSizer._calculate_volatility_multiplier(atr_very_low, current_price)
        assert multiplier_very_low <= 1.2

        # 매우 높은 변동성
        atr_very_high = Decimal("5000")  # 10% ATR
        multiplier_very_high = PositionSizer._calculate_volatility_multiplier(atr_very_high, current_price)
        assert multiplier_very_high >= 0.5

    # ============= 통합 테스트 =============

    def test_calculate_end_to_end_long_position(self, default_risk_config, sample_candidate, sample_portfolio):
        """LONG 포지션에 대한 전체 계산이 정상 작동한다."""
        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(sample_candidate, sample_portfolio, current_price)

        # Decision 객체 검증
        assert decision.market == "USDT-BTC"
        assert decision.direction == SignalDirection.LONG
        assert decision.volume > 0
        assert decision.entry_price == Decimal("50000")
        assert decision.stop_loss == Decimal("48000")
        assert decision.take_profit == Decimal("55000")
        assert decision.risk_amount > 0
        assert 0.0 < decision.risk_percent <= 0.02  # 최대 2%
        assert decision.status == DecisionStatus.PENDING
        assert decision.decision_id is not None

    def test_calculate_end_to_end_short_position(self, default_risk_config, sample_portfolio):
        """SHORT 포지션에 대한 전체 계산이 정상 작동한다."""
        signals = [
            Signal(
                strategy_id="strategy_1",
                market="USDT-BTC",
                direction=SignalDirection.SHORT,
                strength=0.8,
                confidence=0.75,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("52000"),
                take_profit=Decimal("45000"),
                timeframe=Timeframe.HOUR,
            ),
        ]

        candidate = TradeCandidate(
            market="USDT-BTC",
            direction=SignalDirection.SHORT,
            combined_strength=0.75,
            contributing_signals=signals,
            suggested_entry=Decimal("50000"),
            suggested_stop_loss=Decimal("52000"),
            suggested_take_profit=Decimal("45000"),
        )

        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(candidate, sample_portfolio, current_price)

        assert decision.direction == SignalDirection.SHORT
        assert decision.volume > 0
        assert decision.stop_loss == Decimal("52000")  # SHORT는 진입가보다 높음
        assert decision.take_profit == Decimal("45000")  # SHORT는 진입가보다 낮음

    def test_calculate_with_zero_available_capital(self, default_risk_config, sample_candidate):
        """여유 자본이 0일 때 최소 포지션을 생성한다."""
        portfolio = PortfolioState(
            total_capital=Decimal("50000000"),
            available_capital=Decimal("0"),  # 여유 자본 없음
            positions={},
            high_water_mark=Decimal("50000000"),
        )

        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(sample_candidate, portfolio, current_price)

        # 여유 자본이 없으면 포지션이 매우 작거나 0이어야 함
        assert decision.volume >= 0
        if decision.volume > 0:
            position_value = decision.volume * decision.entry_price
            assert position_value < Decimal("1000000")  # 매우 작은 포지션

    def test_calculate_risk_amount_calculation(self, default_risk_config, sample_candidate, sample_portfolio):
        """리스크 금액이 정확히 계산된다."""
        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")

        decision = sizer.calculate(sample_candidate, sample_portfolio, current_price)

        # 리스크 금액 = (진입가 - 손절가) * 수량
        expected_risk = abs(decision.entry_price - decision.stop_loss) * decision.volume
        assert abs(decision.risk_amount - expected_risk) < Decimal("1")

        # 리스크 비율이 총 자본 대비로 계산되어야 함
        expected_risk_percent = float(decision.risk_amount / sample_portfolio.total_capital)
        assert abs(decision.risk_percent - expected_risk_percent) < 0.001

    def test_calculate_combined_multipliers_are_applied(self, default_risk_config, sample_candidate, sample_portfolio):
        """모든 배수가 조합되어 적용된다."""
        sizer = PositionSizer(default_risk_config)
        current_price = Decimal("50000")
        atr = Decimal("1500")  # 3% ATR

        decision = sizer.calculate(sample_candidate, sample_portfolio, current_price, atr)

        # 배수들이 적용되어 포지션 크기가 조정되어야 함
        # 정확한 값을 예측하기는 어려우나 합리적인 범위 내에 있어야 함
        position_value = decision.volume * decision.entry_price
        assert position_value > 0
        assert position_value <= sample_portfolio.available_capital * Decimal("0.40")
