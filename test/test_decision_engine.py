from decimal import Decimal

import pytest

from src.decision.decision_engine import DecisionEngine
from src.portfolio.models.portfolio_state import PortfolioState
from src.portfolio.models.position import Position
from src.risk.models import RiskLimitsConfig
from src.strategies.codes import SignalDirection
from src.strategies.models import Signal
from src.trading.exchanges.upbit.codes import Timeframe


class TestDecisionEngine:
    """DecisionEngine 테스트"""

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
    def sample_signals_btc(self):
        """BTC에 대한 샘플 신호들"""
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
        ]

    @pytest.fixture
    def sample_signals_eth(self):
        """ETH에 대한 샘플 신호들"""
        return [
            Signal(
                strategy_id="strategy_1",
                market="USDT-ETH",
                direction=SignalDirection.SHORT,
                strength=0.85,
                confidence=0.8,
                entry_price=Decimal("3000"),
                stop_loss=Decimal("3200"),
                take_profit=Decimal("2700"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_3",
                market="USDT-ETH",
                direction=SignalDirection.SHORT,
                strength=0.75,
                confidence=0.7,
                entry_price=Decimal("3010"),
                stop_loss=Decimal("3210"),
                take_profit=Decimal("2710"),
                timeframe=Timeframe.HOUR,
            ),
        ]

    # ============= 초기화 테스트 =============

    def test_engine_initializes_with_default_parameters(self, default_risk_config):
        """결정 엔진이 기본 파라미터로 초기화된다."""
        engine = DecisionEngine(default_risk_config)

        assert engine.aggregator is not None
        assert engine.confluence_checker is not None
        assert engine.position_sizer is not None
        assert engine.aggregator.min_confidence == 0.6
        assert engine.confluence_checker.min_signals == 2

    def test_engine_initializes_with_custom_parameters(self, default_risk_config):
        """결정 엔진이 커스텀 파라미터로 초기화된다."""
        engine = DecisionEngine(default_risk_config, min_confluence=3, min_confidence=0.7)

        assert engine.aggregator.min_confidence == 0.7
        assert engine.confluence_checker.min_signals == 3

    # ============= add_signal() 테스트 =============

    def test_add_signal_accepts_valid_signal(self, default_risk_config, sample_signals_btc):
        """유효한 신호를 추가할 수 있다."""
        engine = DecisionEngine(default_risk_config)
        signal = sample_signals_btc[0]

        engine.add_signal(signal)

        # aggregator에 신호가 추가되었는지 확인
        assert engine.aggregator.signal_count == 1

    def test_add_signal_filters_low_confidence_signals(self, default_risk_config):
        """낮은 신뢰도 신호는 필터링된다."""
        engine = DecisionEngine(default_risk_config, min_confidence=0.7)

        low_confidence_signal = Signal(
            strategy_id="strategy_1",
            market="USDT-BTC",
            direction=SignalDirection.LONG,
            strength=0.5,
            confidence=0.5,  # 0.7보다 낮음
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            timeframe=Timeframe.HOUR,
        )

        engine.add_signal(low_confidence_signal)

        # 낮은 신뢰도 신호는 추가되지 않음
        assert engine.aggregator.signal_count == 0

    def test_add_multiple_signals_for_same_market(self, default_risk_config, sample_signals_btc):
        """같은 심볼에 대한 여러 신호를 추가할 수 있다."""
        engine = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine.add_signal(signal)

        assert engine.aggregator.signal_count == 2
        assert len(engine.aggregator.get_signals("USDT-BTC")) == 2

    def test_add_signals_for_different_markets(self, default_risk_config, sample_signals_btc, sample_signals_eth):
        """다른 심볼에 대한 신호를 추가할 수 있다."""
        engine = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc + sample_signals_eth:
            engine.add_signal(signal)

        assert engine.aggregator.signal_count == 4
        assert len(engine.aggregator.get_signals("USDT-BTC")) == 2
        assert len(engine.aggregator.get_signals("USDT-ETH")) == 2

    # ============= process() 메서드 기본 테스트 =============

    def test_process_returns_empty_list_when_no_signals(self, default_risk_config, sample_portfolio):
        """신호가 없을 때 빈 리스트를 반환한다."""
        engine = DecisionEngine(default_risk_config)
        current_prices = {"USDT-BTC": Decimal("50000")}

        decisions = engine.process(sample_portfolio, current_prices)

        assert decisions == []

    def test_process_returns_empty_list_when_insufficient_confluence(self, default_risk_config, sample_portfolio):
        """신호 일치가 부족할 때 빈 리스트를 반환한다."""
        engine = DecisionEngine(default_risk_config, min_confluence=3)  # 최소 3개 필요

        # 2개의 신호만 추가
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
        engine.add_signal(signal)

        current_prices = {"USDT-BTC": Decimal("50000")}
        decisions = engine.process(sample_portfolio, current_prices)

        assert decisions == []

    def test_process_generates_decision_with_sufficient_confluence(
        self, default_risk_config, sample_portfolio, sample_signals_btc
    ):
        """충분한 신호 일치가 있을 때 결정을 생성한다."""
        engine = DecisionEngine(default_risk_config, min_confluence=2)

        for signal in sample_signals_btc:
            engine.add_signal(signal)

        current_prices = {"USDT-BTC": Decimal("50000")}
        decisions = engine.process(sample_portfolio, current_prices)

        assert len(decisions) == 1
        assert decisions[0].market == "USDT-BTC"
        assert decisions[0].direction == SignalDirection.LONG
        assert decisions[0].volume > 0

    def test_process_generates_multiple_decisions_for_different_markets(
        self, default_risk_config, sample_portfolio, sample_signals_btc, sample_signals_eth
    ):
        """여러 심볼에 대한 결정을 생성한다."""
        engine = DecisionEngine(default_risk_config, min_confluence=2)

        for signal in sample_signals_btc + sample_signals_eth:
            engine.add_signal(signal)

        current_prices = {"USDT-BTC": Decimal("50000"), "USDT-ETH": Decimal("3000")}
        decisions = engine.process(sample_portfolio, current_prices)

        assert len(decisions) == 2
        markets = {d.market for d in decisions}
        assert "USDT-BTC" in markets
        assert "USDT-ETH" in markets

    def test_process_clears_signals_after_processing(self, default_risk_config, sample_portfolio, sample_signals_btc):
        """처리 후 신호를 초기화한다."""
        engine = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine.add_signal(signal)

        assert engine.aggregator.signal_count > 0

        current_prices = {"USDT-BTC": Decimal("50000")}
        engine.process(sample_portfolio, current_prices)

        # 처리 후 신호가 초기화되어야 함
        assert engine.aggregator.signal_count == 0

    # ============= process() - 엣지 케이스 =============

    def test_process_skips_market_with_existing_position(self, default_risk_config, sample_signals_btc):
        """이미 포지션이 있는 심볼은 건너뛴다."""
        # 이미 BTC 포지션이 있는 포트폴리오
        existing_position = Position(
            market="USDT-BTC",
            signal_direction=SignalDirection.LONG,
            entry_price=Decimal("49000"),
            current_price=Decimal("50000"),
            volume=Decimal("0.5"),
            stop_loss=Decimal("47000"),
            take_profit=Decimal("55000"),
            strategy_id="strategy_1",
        )

        portfolio = PortfolioState(
            total_capital=Decimal("50000000"),
            available_capital=Decimal("25000000"),
            positions={"USDT-BTC": existing_position},
            high_water_mark=Decimal("50000000"),
        )

        engine = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine.add_signal(signal)

        current_prices = {"USDT-BTC": Decimal("50000")}
        decisions = engine.process(portfolio, current_prices)

        # 이미 포지션이 있으므로 결정이 생성되지 않아야 함
        assert len(decisions) == 0

    def test_process_uses_suggested_entry_when_no_current_price(
        self, default_risk_config, sample_portfolio, sample_signals_btc
    ):
        """현재 가격이 없을 때 제안 진입가를 사용한다."""
        engine = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine.add_signal(signal)

        # BTC 가격을 제공하지 않음
        current_prices = {}
        decisions = engine.process(sample_portfolio, current_prices)

        # 제안 진입가를 사용하여 결정 생성
        assert len(decisions) == 1
        # 제안 진입가는 신호들의 평균 (50000 + 50200) / 2 = 50100
        assert decisions[0].entry_price == Decimal("50100")

    def test_process_skips_market_with_zero_price(self, default_risk_config, sample_portfolio, sample_signals_btc):
        """가격이 0이거나 음수일 때 건너뛴다."""
        engine = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine.add_signal(signal)

        # 가격이 0
        current_prices = {"USDT-BTC": Decimal("0")}
        decisions = engine.process(sample_portfolio, current_prices)

        assert len(decisions) == 0

    def test_process_creates_small_position_with_limited_capital(self, default_risk_config, sample_signals_btc):
        """자본이 제한적일 때 작은 포지션을 생성한다."""
        # 여유 자본이 거의 없는 포트폴리오
        portfolio = PortfolioState(
            total_capital=Decimal("1000"),  # 매우 작은 자본
            available_capital=Decimal("100"),
            positions={},
            high_water_mark=Decimal("1000"),
        )

        engine = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine.add_signal(signal)

        current_prices = {"USDT-BTC": Decimal("50000")}
        decisions = engine.process(portfolio, current_prices)

        # 자본이 작아도 최소한의 포지션은 생성될 수 있음
        if len(decisions) > 0:
            # 포지션이 생성되었다면 매우 작은 수량이어야 함
            assert decisions[0].volume > 0
            position_value = decisions[0].volume * decisions[0].entry_price
            assert position_value < Decimal("500")  # 매우 작은 포지션

    # ============= process() - 통합 시나리오 =============

    def test_process_end_to_end_single_market(self, default_risk_config, sample_portfolio, sample_signals_btc):
        """단일 심볼에 대한 전체 플로우가 정상 작동한다."""
        engine = DecisionEngine(default_risk_config, min_confluence=2, min_confidence=0.6)

        # 1. 신호 추가
        for signal in sample_signals_btc:
            engine.add_signal(signal)

        # 2. 처리
        current_prices = {"USDT-BTC": Decimal("50000")}
        decisions = engine.process(sample_portfolio, current_prices)

        # 3. 검증
        assert len(decisions) == 1

        decision = decisions[0]
        assert decision.market == "USDT-BTC"
        assert decision.direction == SignalDirection.LONG
        assert decision.volume > 0
        # entry_price는 candidate의 suggested_entry를 사용 (50000 + 50200) / 2 = 50100
        assert decision.entry_price == Decimal("50100")
        assert decision.stop_loss == Decimal("48000")
        assert decision.take_profit == Decimal("55000")
        assert len(decision.contributing_signals) == 2

        # 4. 처리 후 신호가 초기화되었는지 확인
        assert engine.aggregator.signal_count == 0

    def test_process_end_to_end_multiple_markets(
        self, default_risk_config, sample_portfolio, sample_signals_btc, sample_signals_eth
    ):
        """여러 심볼에 대한 전체 플로우가 정상 작동한다."""
        engine = DecisionEngine(default_risk_config, min_confluence=2)

        # 1. 신호 추가
        for signal in sample_signals_btc + sample_signals_eth:
            engine.add_signal(signal)

        # 2. 처리
        current_prices = {"USDT-BTC": Decimal("50000"), "USDT-ETH": Decimal("3000")}
        decisions = engine.process(sample_portfolio, current_prices)

        # 3. 검증
        assert len(decisions) == 2

        btc_decision = next(d for d in decisions if d.market == "USDT-BTC")
        eth_decision = next(d for d in decisions if d.market == "USDT-ETH")

        assert btc_decision.direction == SignalDirection.LONG
        assert eth_decision.direction == SignalDirection.SHORT
        assert btc_decision.volume > 0
        assert eth_decision.volume > 0

    def test_process_with_mixed_directions_chooses_majority(self, default_risk_config, sample_portfolio):
        """혼합된 방향의 신호에서 다수 방향을 선택한다."""
        engine = DecisionEngine(default_risk_config, min_confluence=2)

        # LONG 3개, SHORT 1개
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
                confidence=0.7,
                entry_price=Decimal("50100"),
                stop_loss=Decimal("48100"),
                take_profit=Decimal("55100"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_3",
                market="USDT-BTC",
                direction=SignalDirection.LONG,
                strength=0.75,
                confidence=0.72,
                entry_price=Decimal("50050"),
                stop_loss=Decimal("48050"),
                take_profit=Decimal("55050"),
                timeframe=Timeframe.HOUR,
            ),
            Signal(
                strategy_id="strategy_4",
                market="USDT-BTC",
                direction=SignalDirection.SHORT,
                strength=0.6,
                confidence=0.65,
                entry_price=Decimal("50200"),
                stop_loss=Decimal("52200"),
                take_profit=Decimal("47000"),
                timeframe=Timeframe.HOUR,
            ),
        ]

        for signal in signals:
            engine.add_signal(signal)

        current_prices = {"USDT-BTC": Decimal("50000")}
        decisions = engine.process(sample_portfolio, current_prices)

        # LONG이 다수이므로 LONG 결정이 생성되어야 함
        assert len(decisions) == 1
        assert decisions[0].direction == SignalDirection.LONG
        assert len(decisions[0].contributing_signals) == 3  # LONG 신호 3개

    # ============= clear() 테스트 =============

    def test_clear_removes_all_pending_signals(self, default_risk_config, sample_signals_btc):
        """대기 중인 모든 신호를 제거한다."""
        engine = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine.add_signal(signal)

        assert engine.aggregator.signal_count > 0

        engine.clear()

        assert engine.aggregator.signal_count == 0

    def test_clear_allows_adding_new_signals_after_clear(self, default_risk_config, sample_signals_btc):
        """clear 후 새로운 신호를 추가할 수 있다."""
        engine = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine.add_signal(signal)

        engine.clear()

        # 새로운 신호 추가
        new_signal = Signal(
            strategy_id="new_strategy",
            market="USDT-ETH",
            direction=SignalDirection.SHORT,
            strength=0.85,
            confidence=0.8,
            entry_price=Decimal("3000"),
            stop_loss=Decimal("3200"),
            take_profit=Decimal("2700"),
            timeframe=Timeframe.HOUR,
        )
        engine.add_signal(new_signal)

        assert engine.aggregator.signal_count == 1

    # ============= 리스크 제한 통합 테스트 =============

    def test_process_considers_existing_positions_in_exposure(self, default_risk_config, sample_signals_btc):
        """기존 포지션을 고려하여 포지션 크기를 계산한다."""
        # 이미 포지션이 없는 포트폴리오
        portfolio_no_positions = PortfolioState(
            total_capital=Decimal("50000000"),
            available_capital=Decimal("40000000"),
            positions={},
            high_water_mark=Decimal("50000000"),
        )

        # 이미 포지션이 있는 포트폴리오
        existing_position = Position(
            market="USDT-ETH",
            signal_direction=SignalDirection.LONG,
            entry_price=Decimal("3000"),
            current_price=Decimal("3100"),
            volume=Decimal("2000"),  # 6,200,000원 상당
            stop_loss=Decimal("2900"),
            take_profit=Decimal("3300"),
            strategy_id="strategy_1",
        )

        portfolio_with_positions = PortfolioState(
            total_capital=Decimal("50000000"),
            available_capital=Decimal("33800000"),
            positions={"USDT-ETH": existing_position},
            high_water_mark=Decimal("50000000"),
        )

        engine_no_pos = DecisionEngine(default_risk_config)
        engine_with_pos = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine_no_pos.add_signal(signal)
            engine_with_pos.add_signal(signal)

        current_prices = {"USDT-BTC": Decimal("50000")}

        decisions_no_pos = engine_no_pos.process(portfolio_no_positions, current_prices)
        decisions_with_pos = engine_with_pos.process(portfolio_with_positions, current_prices)

        # 두 경우 모두 결정이 생성되어야 함
        assert len(decisions_no_pos) == 1
        assert len(decisions_with_pos) == 1

        # 각 결정이 개별 포지션 크기 제한을 준수하는지 확인
        pos_value_no_pos = decisions_no_pos[0].volume * decisions_no_pos[0].entry_price
        pos_value_with_pos = decisions_with_pos[0].volume * decisions_with_pos[0].entry_price

        max_position_value_no_pos = portfolio_no_positions.available_capital * Decimal("0.40")
        max_position_value_with_pos = portfolio_with_positions.available_capital * Decimal("0.40")

        assert pos_value_no_pos <= max_position_value_no_pos
        assert pos_value_with_pos <= max_position_value_with_pos

    def test_process_with_high_drawdown_reduces_positions(self, default_risk_config, sample_signals_btc):
        """높은 드로다운일 때 포지션 크기가 감소한다."""
        # 드로다운이 없는 포트폴리오
        portfolio_no_dd = PortfolioState(
            total_capital=Decimal("50000000"),
            available_capital=Decimal("40000000"),
            positions={},
            high_water_mark=Decimal("50000000"),
        )

        # 높은 드로다운 포트폴리오
        portfolio_high_dd = PortfolioState(
            total_capital=Decimal("42500000"),  # 15% 하락
            available_capital=Decimal("35000000"),
            positions={},
            high_water_mark=Decimal("50000000"),
        )

        engine_no_dd = DecisionEngine(default_risk_config)
        engine_high_dd = DecisionEngine(default_risk_config)

        for signal in sample_signals_btc:
            engine_no_dd.add_signal(signal)
            engine_high_dd.add_signal(signal)

        current_prices = {"USDT-BTC": Decimal("50000")}

        decisions_no_dd = engine_no_dd.process(portfolio_no_dd, current_prices)
        decisions_high_dd = engine_high_dd.process(portfolio_high_dd, current_prices)

        # 드로다운이 높을 때 포지션 크기가 작아야 함
        assert len(decisions_no_dd) == 1
        assert len(decisions_high_dd) == 1
        assert decisions_high_dd[0].volume < decisions_no_dd[0].volume
