from decimal import Decimal

import pytest

from src.risk.models.risk_context import RiskContext


class TestRiskContext:
    @pytest.fixture
    def basic_context(self):
        """기본 RiskContext 인스턴스"""
        return RiskContext(
            system_state="RUNNING",
            mode="PAPER",
            open_positions_count=2,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

    # ============= RiskContext 생성 =============

    def test_create_risk_context_with_required_fields(self):
        """필수 필드로 RiskContext를 생성한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="DRY_RUN",
            open_positions_count=0,
            total_position_value_krw=Decimal("0"),
            portfolio_value_krw=Decimal("100000000"),
            starting_capital_krw=Decimal("100000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("100000000"),
            current_drawdown_percent=Decimal("0"),
        )

        assert context.system_state == "RUNNING"
        assert context.mode == "DRY_RUN"
        assert context.open_positions_count == 0
        assert context.total_position_value_krw == Decimal("0")
        assert context.portfolio_value_krw == Decimal("100000000")
        assert context.starting_capital_krw == Decimal("100000000")
        assert context.proposed_trade_size_krw is None
        assert context.proposed_trade_risk_percent is None

    def test_create_risk_context_with_all_fields(self):
        """모든 필드를 포함하여 RiskContext를 생성한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=3,
            total_position_value_krw=Decimal("15000000"),
            portfolio_value_krw=Decimal("60000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("500000"),
            daily_pnl_percent=Decimal("0.83"),
            weekly_pnl_krw=Decimal("2000000"),
            weekly_pnl_percent=Decimal("3.33"),
            peak_portfolio_value_krw=Decimal("65000000"),
            current_drawdown_percent=Decimal("7.69"),
            proposed_trade_size_krw=Decimal("5000000"),
            proposed_trade_risk_percent=Decimal("2.5"),
        )

        assert context.system_state == "RUNNING"
        assert context.mode == "LIVE"
        assert context.open_positions_count == 3
        assert context.total_position_value_krw == Decimal("15000000")
        assert context.portfolio_value_krw == Decimal("60000000")
        assert context.starting_capital_krw == Decimal("50000000")
        assert context.daily_pnl_krw == Decimal("500000")
        assert context.daily_pnl_percent == Decimal("0.83")
        assert context.weekly_pnl_krw == Decimal("2000000")
        assert context.weekly_pnl_percent == Decimal("3.33")
        assert context.peak_portfolio_value_krw == Decimal("65000000")
        assert context.current_drawdown_percent == Decimal("7.69")
        assert context.proposed_trade_size_krw == Decimal("5000000")
        assert context.proposed_trade_risk_percent == Decimal("2.5")

    def test_risk_context_is_immutable(self, basic_context):
        """RiskContext는 불변 객체이므로 수정할 수 없다."""
        with pytest.raises((AttributeError, TypeError)):
            basic_context.system_state = "STOPPED"

        with pytest.raises((AttributeError, TypeError)):
            basic_context.portfolio_value_krw = Decimal("1000000")

    # ============= total_pnl_percent 속성 =============

    def test_total_pnl_percent_returns_zero_when_no_change(self):
        """시작 자본과 포트폴리오 가치가 같으면 0%를 반환한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="PAPER",
            open_positions_count=0,
            total_position_value_krw=Decimal("0"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        assert context.total_pnl_percent == Decimal("0")

    def test_total_pnl_percent_calculates_profit_correctly(self):
        """수익이 발생한 경우 총 손익률을 올바르게 계산한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("60000000"),  # +10M profit
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("1000000"),
            daily_pnl_percent=Decimal("1.67"),
            weekly_pnl_krw=Decimal("10000000"),
            weekly_pnl_percent=Decimal("16.67"),
            peak_portfolio_value_krw=Decimal("60000000"),
            current_drawdown_percent=Decimal("0"),
        )

        # (60M - 50M) / 50M * 100 = 20%
        assert context.total_pnl_percent == Decimal("20")

    def test_total_pnl_percent_calculates_loss_correctly(self):
        """손실이 발생한 경우 총 손익률을 올바르게 계산한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("5000000"),
            portfolio_value_krw=Decimal("40000000"),  # -10M loss
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-2000000"),
            daily_pnl_percent=Decimal("-4"),
            weekly_pnl_krw=Decimal("-10000000"),
            weekly_pnl_percent=Decimal("-20"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("20"),
        )

        # (40M - 50M) / 50M * 100 = -20%
        assert context.total_pnl_percent == Decimal("-20")

    def test_total_pnl_percent_returns_zero_when_starting_capital_is_zero(self):
        """시작 자본이 0이면 0%를 반환한다 (ZeroDivisionError 방지)."""
        context = RiskContext(
            system_state="RUNNING",
            mode="DRY_RUN",
            open_positions_count=0,
            total_position_value_krw=Decimal("0"),
            portfolio_value_krw=Decimal("10000000"),
            starting_capital_krw=Decimal("0"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("10000000"),
            current_drawdown_percent=Decimal("0"),
        )

        assert context.total_pnl_percent == Decimal("0")

    # ============= position_utilization_percent 속성 =============

    def test_position_utilization_percent_calculates_correctly(self):
        """포지션 활용률을 올바르게 계산한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=2,
            total_position_value_krw=Decimal("20000000"),  # 20M positions
            portfolio_value_krw=Decimal("50000000"),  # 50M total
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        # 20M / 50M * 100 = 40%
        assert context.position_utilization_percent == Decimal("40")

    def test_position_utilization_percent_returns_zero_when_no_positions(self):
        """포지션이 없으면 0%를 반환한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="PAPER",
            open_positions_count=0,
            total_position_value_krw=Decimal("0"),
            portfolio_value_krw=Decimal("100000000"),
            starting_capital_krw=Decimal("100000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("100000000"),
            current_drawdown_percent=Decimal("0"),
        )

        assert context.position_utilization_percent == Decimal("0")

    def test_position_utilization_percent_returns_zero_when_portfolio_is_zero(self):
        """포트폴리오 가치가 0이면 0%를 반환한다 (ZeroDivisionError 방지)."""
        context = RiskContext(
            system_state="STOPPED",
            mode="DRY_RUN",
            open_positions_count=1,
            total_position_value_krw=Decimal("5000000"),
            portfolio_value_krw=Decimal("0"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-50000000"),
            daily_pnl_percent=Decimal("-100"),
            weekly_pnl_krw=Decimal("-50000000"),
            weekly_pnl_percent=Decimal("-100"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("100"),
        )

        assert context.position_utilization_percent == Decimal("0")

    def test_position_utilization_percent_can_exceed_100_percent(self):
        """레버리지 사용 시 포지션 활용률이 100%를 초과할 수 있다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=3,
            total_position_value_krw=Decimal("75000000"),  # 75M positions
            portfolio_value_krw=Decimal("50000000"),  # 50M total (1.5x leverage)
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        # 75M / 50M * 100 = 150%
        assert context.position_utilization_percent == Decimal("150")

    # ============= 다양한 시스템 상태 테스트 =============

    def test_context_with_paused_system_state(self):
        """시스템 상태가 PAUSED인 컨텍스트를 생성한다."""
        context = RiskContext(
            system_state="PAUSED",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("5000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        assert context.system_state == "PAUSED"

    def test_context_with_stopped_system_state(self):
        """시스템 상태가 STOPPED인 컨텍스트를 생성한다."""
        context = RiskContext(
            system_state="STOPPED",
            mode="PAPER",
            open_positions_count=0,
            total_position_value_krw=Decimal("0"),
            portfolio_value_krw=Decimal("45000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-5000000"),
            daily_pnl_percent=Decimal("-10"),
            weekly_pnl_krw=Decimal("-5000000"),
            weekly_pnl_percent=Decimal("-10"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("10"),
        )

        assert context.system_state == "STOPPED"
        assert context.total_pnl_percent == Decimal("-10")
