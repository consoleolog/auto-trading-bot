from decimal import Decimal

import pytest

from src.risk.codes import RiskSeverity
from src.risk.models import RiskContext, TriggeredRule
from src.risk.risk_rule import CompositeRiskRule, RiskRule

# ============= 테스트용 구체적인 RiskRule 구현 클래스들 =============


class AlwaysPassRule(RiskRule):
    """항상 통과하는 규칙 (테스트용)"""

    priority = 100
    default_severity = RiskSeverity.INFO

    @property
    def name(self) -> str:
        return "AlwaysPassRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        return None


class AlwaysFailRule(RiskRule):
    """항상 실패하는 규칙 (테스트용)"""

    priority = 50
    default_severity = RiskSeverity.CRITICAL

    @property
    def name(self) -> str:
        return "AlwaysFailRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        return self._create_triggered(message="This rule always fails", suggested_action="Fix the issue")


class MaxPositionCountRule(RiskRule):
    """포지션 개수 제한 규칙 (테스트용)"""

    priority = 150
    default_severity = RiskSeverity.WARNING

    def __init__(self, max_positions: int):
        self.max_positions = max_positions

    @property
    def name(self) -> str:
        return "MaxPositionCountRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        if context.open_positions_count > self.max_positions:
            return self._create_triggered(
                message=f"Open positions ({context.open_positions_count}) exceeds limit ({self.max_positions})",
                suggested_action=f"Close positions to reduce count to {self.max_positions} or less",
            )
        return None


class MaxDrawdownRule(RiskRule):
    """최대 드로다운 제한 규칙 (테스트용)"""

    priority = 10
    default_severity = RiskSeverity.EMERGENCY

    def __init__(self, max_drawdown_percent: Decimal):
        self.max_drawdown_percent = max_drawdown_percent

    @property
    def name(self) -> str:
        return "MaxDrawdownRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        if context.current_drawdown_percent > self.max_drawdown_percent:
            return self._create_triggered(
                message=f"Drawdown ({context.current_drawdown_percent}%) exceeds limit ({self.max_drawdown_percent}%)",
                severity=RiskSeverity.EMERGENCY,
                suggested_action="Emergency stop - flatten all positions",
            )
        return None


# ============= RiskRule 테스트 =============


class TestRiskRule:
    @pytest.fixture
    def basic_context(self):
        """기본 RiskContext"""
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

    # ============= RiskRule 기본 동작 =============

    def test_risk_rule_has_default_priority_and_severity(self):
        """RiskRule은 기본 priority와 default_severity를 가진다."""
        rule = AlwaysPassRule()
        assert rule.priority == 100
        assert rule.default_severity == RiskSeverity.INFO

    def test_risk_rule_name_property_is_implemented(self):
        """RiskRule의 name 속성이 구현되어 있다."""
        rule = AlwaysPassRule()
        assert rule.name == "AlwaysPassRule"

    def test_risk_rule_evaluate_returns_none_when_passed(self, basic_context):
        """규칙이 통과하면 evaluate는 None을 반환한다."""
        rule = AlwaysPassRule()
        result = rule.evaluate(basic_context)
        assert result is None

    def test_risk_rule_evaluate_returns_triggered_rule_when_failed(self, basic_context):
        """규칙이 실패하면 evaluate는 TriggeredRule을 반환한다."""
        rule = AlwaysFailRule()
        result = rule.evaluate(basic_context)

        assert result is not None
        assert isinstance(result, TriggeredRule)
        assert result.rule_name == "AlwaysFailRule"
        assert result.severity == RiskSeverity.CRITICAL
        assert result.message == "This rule always fails"
        assert result.suggested_action == "Fix the issue"

    def test_risk_rule_create_triggered_helper_uses_default_severity(self):
        """_create_triggered 헬퍼는 severity가 없으면 default_severity를 사용한다."""
        rule = AlwaysFailRule()
        triggered = rule._create_triggered(message="Test message")

        assert triggered.rule_name == "AlwaysFailRule"
        assert triggered.severity == RiskSeverity.CRITICAL  # default_severity
        assert triggered.message == "Test message"
        assert triggered.suggested_action is None

    def test_risk_rule_create_triggered_helper_uses_custom_severity(self):
        """_create_triggered 헬퍼는 명시적으로 전달된 severity를 사용한다."""
        rule = AlwaysPassRule()
        triggered = rule._create_triggered(
            message="Custom message", severity=RiskSeverity.EMERGENCY, suggested_action="Take action"
        )

        assert triggered.rule_name == "AlwaysPassRule"
        assert triggered.severity == RiskSeverity.EMERGENCY  # custom severity
        assert triggered.message == "Custom message"
        assert triggered.suggested_action == "Take action"

    # ============= 구체적인 규칙 동작 테스트 =============

    def test_max_position_count_rule_passes_when_within_limit(self, basic_context):
        """포지션 개수가 제한 내에 있으면 통과한다."""
        rule = MaxPositionCountRule(max_positions=5)
        result = rule.evaluate(basic_context)  # open_positions_count = 2

        assert result is None

    def test_max_position_count_rule_fails_when_exceeds_limit(self):
        """포지션 개수가 제한을 초과하면 실패한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=6,  # exceeds limit of 5
            total_position_value_krw=Decimal("30000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        rule = MaxPositionCountRule(max_positions=5)
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "MaxPositionCountRule"
        assert result.severity == RiskSeverity.WARNING
        assert "exceeds limit" in result.message
        assert "6" in result.message
        assert "5" in result.message

    def test_max_drawdown_rule_passes_when_within_limit(self, basic_context):
        """드로다운이 제한 내에 있으면 통과한다."""
        rule = MaxDrawdownRule(max_drawdown_percent=Decimal("20"))
        result = rule.evaluate(basic_context)  # current_drawdown_percent = 0

        assert result is None

    def test_max_drawdown_rule_fails_when_exceeds_limit(self):
        """드로다운이 제한을 초과하면 실패한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("35000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-5000000"),
            daily_pnl_percent=Decimal("-12.5"),
            weekly_pnl_krw=Decimal("-15000000"),
            weekly_pnl_percent=Decimal("-30"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("30"),  # exceeds 20%
        )

        rule = MaxDrawdownRule(max_drawdown_percent=Decimal("20"))
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "MaxDrawdownRule"
        assert result.severity == RiskSeverity.EMERGENCY
        assert "Drawdown" in result.message
        assert "30" in result.message
        assert "20" in result.message
        assert "Emergency stop" in result.suggested_action


# ============= CompositeRiskRule 테스트 =============


class TestCompositeRiskRule:
    @pytest.fixture
    def basic_context(self):
        """기본 RiskContext"""
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

    def test_composite_rule_has_default_name(self):
        """CompositeRiskRule은 기본 이름을 가진다."""
        composite = CompositeRiskRule([])
        assert composite.name == "CompositeRule"

    def test_composite_rule_sorts_rules_by_priority(self):
        """CompositeRiskRule은 규칙들을 우선순위 순으로 정렬한다."""
        rule1 = AlwaysPassRule()  # priority = 100
        rule2 = AlwaysFailRule()  # priority = 50
        rule3 = MaxPositionCountRule(max_positions=5)  # priority = 150

        composite = CompositeRiskRule([rule1, rule2, rule3])

        # priority 순서: 50, 100, 150
        assert composite.rules[0].priority == 50
        assert composite.rules[1].priority == 100
        assert composite.rules[2].priority == 150

    def test_composite_rule_returns_none_when_all_rules_pass(self, basic_context):
        """모든 하위 규칙이 통과하면 None을 반환한다."""
        rule1 = AlwaysPassRule()
        rule2 = MaxPositionCountRule(max_positions=10)

        composite = CompositeRiskRule([rule1, rule2])
        result = composite.evaluate(basic_context)

        assert result is None

    def test_composite_rule_returns_first_triggered_rule(self, basic_context):
        """첫 번째로 트리거된 규칙을 반환한다."""
        rule1 = AlwaysPassRule()  # priority = 100
        rule2 = AlwaysFailRule()  # priority = 50

        composite = CompositeRiskRule([rule1, rule2])
        result = composite.evaluate(basic_context)

        # priority 50인 AlwaysFailRule이 먼저 평가되고 실패함
        assert result is not None
        assert result.rule_name == "AlwaysFailRule"

    def test_composite_rule_stops_at_first_failure(self):
        """첫 번째 실패 후 나머지 규칙은 평가하지 않는다."""
        rule1 = MaxDrawdownRule(max_drawdown_percent=Decimal("20"))  # priority = 10
        rule2 = AlwaysFailRule()  # priority = 50
        rule3 = MaxPositionCountRule(max_positions=1)  # priority = 150

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=2,  # would fail MaxPositionCountRule
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("35000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-15000000"),
            daily_pnl_percent=Decimal("-30"),
            weekly_pnl_krw=Decimal("-15000000"),
            weekly_pnl_percent=Decimal("-30"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("30"),  # fails MaxDrawdownRule (priority 10)
        )

        composite = CompositeRiskRule([rule1, rule2, rule3])
        result = composite.evaluate(context)

        # priority 10인 MaxDrawdownRule이 먼저 실패함
        assert result is not None
        assert result.rule_name == "MaxDrawdownRule"
        assert result.severity == RiskSeverity.EMERGENCY

    def test_composite_rule_with_empty_rules_list(self, basic_context):
        """규칙이 없는 CompositeRiskRule은 항상 None을 반환한다."""
        composite = CompositeRiskRule([])
        result = composite.evaluate(basic_context)

        assert result is None

    def test_composite_rule_evaluates_in_correct_priority_order(self):
        """CompositeRiskRule은 우선순위 순서대로 규칙을 평가한다."""
        # 모두 실패하는 규칙들을 다른 우선순위로 생성
        rule1 = MaxPositionCountRule(max_positions=1)  # priority = 150
        rule2 = AlwaysFailRule()  # priority = 50
        rule3 = MaxDrawdownRule(max_drawdown_percent=Decimal("5"))  # priority = 10

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=2,  # fails all rules
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("40000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-10000000"),
            daily_pnl_percent=Decimal("-20"),
            weekly_pnl_krw=Decimal("-10000000"),
            weekly_pnl_percent=Decimal("-20"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("20"),
        )

        composite = CompositeRiskRule([rule1, rule2, rule3])
        result = composite.evaluate(context)

        # priority가 가장 낮은(10) MaxDrawdownRule이 먼저 실패해야 함
        assert result is not None
        assert result.rule_name == "MaxDrawdownRule"


# ============= 실제 규칙 구현 테스트 =============


class TestDailyLossLimitRule:
    """DailyLossLimitRule 테스트"""

    def test_daily_loss_rule_passes_when_within_threshold(self):
        """일일 손실이 임계값 내에 있으면 통과한다."""
        from src.risk.rules.daily_loss_rule import DailyLossLimitRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("49000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-1000000"),
            daily_pnl_percent=Decimal("-2"),  # -2% loss (< 3% warning)
            weekly_pnl_krw=Decimal("-1000000"),
            weekly_pnl_percent=Decimal("-2"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("2"),
        )

        rule = DailyLossLimitRule()
        result = rule.evaluate(context)

        assert result is None

    def test_daily_loss_rule_warns_at_warning_threshold(self):
        """일일 손실이 경고 임계값을 초과하면 WARNING을 반환한다."""
        from src.risk.rules.daily_loss_rule import DailyLossLimitRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("46500000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-1750000"),
            daily_pnl_percent=Decimal("-3.5"),  # -3.5% loss (>= 3% warning)
            weekly_pnl_krw=Decimal("-3500000"),
            weekly_pnl_percent=Decimal("-7"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("7"),
        )

        rule = DailyLossLimitRule(warning_threshold=Decimal("3"), critical_threshold=Decimal("5"))
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "DailyLossLimitRule"
        assert result.severity == RiskSeverity.WARNING
        assert "3.5" in result.message
        assert "근접" in result.message

    def test_daily_loss_rule_critical_at_critical_threshold(self):
        """일일 손실이 임계 임계값을 초과하면 CRITICAL을 반환한다."""
        from src.risk.rules.daily_loss_rule import DailyLossLimitRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("5000000"),
            portfolio_value_krw=Decimal("44000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-3000000"),
            daily_pnl_percent=Decimal("-6"),  # -6% loss (>= 5% critical)
            weekly_pnl_krw=Decimal("-6000000"),
            weekly_pnl_percent=Decimal("-12"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("12"),
        )

        rule = DailyLossLimitRule(warning_threshold=Decimal("3"), critical_threshold=Decimal("5"))
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "DailyLossLimitRule"
        assert result.severity == RiskSeverity.CRITICAL
        assert "6.0" in result.message
        assert "초과" in result.message
        assert "거래 중단" in result.suggested_action


class TestWeeklyLossLimitRule:
    """WeeklyLossLimitRule 테스트"""

    def test_weekly_loss_rule_passes_when_within_threshold(self):
        """주간 손실이 임계값 내에 있으면 통과한다."""
        from src.risk.rules.weekly_loss_rule import WeeklyLossLimitRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("47000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-500000"),
            daily_pnl_percent=Decimal("-1"),
            weekly_pnl_krw=Decimal("-3000000"),
            weekly_pnl_percent=Decimal("-6"),  # -6% loss (< 7% warning)
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("6"),
        )

        rule = WeeklyLossLimitRule()
        result = rule.evaluate(context)

        assert result is None

    def test_weekly_loss_rule_warns_at_warning_threshold(self):
        """주간 손실이 경고 임계값을 초과하면 WARNING을 반환한다."""
        from src.risk.rules.weekly_loss_rule import WeeklyLossLimitRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("46000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-1000000"),
            daily_pnl_percent=Decimal("-2"),
            weekly_pnl_krw=Decimal("-4000000"),
            weekly_pnl_percent=Decimal("-8"),  # -8% loss (>= 7% warning)
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("8"),
        )

        rule = WeeklyLossLimitRule(warning_threshold=Decimal("7"), critical_threshold=Decimal("10"))
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "WeeklyLossLimitRule"
        assert result.severity == RiskSeverity.WARNING
        assert "8.0" in result.message
        assert "50%" in result.suggested_action

    def test_weekly_loss_rule_critical_at_critical_threshold(self):
        """주간 손실이 임계 임계값을 초과하면 CRITICAL을 반환한다."""
        from src.risk.rules.weekly_loss_rule import WeeklyLossLimitRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("5000000"),
            portfolio_value_krw=Decimal("43500000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-1500000"),
            daily_pnl_percent=Decimal("-3"),
            weekly_pnl_krw=Decimal("-6500000"),
            weekly_pnl_percent=Decimal("-13"),  # -13% loss (>= 10% critical)
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("13"),
        )

        rule = WeeklyLossLimitRule(warning_threshold=Decimal("7"), critical_threshold=Decimal("10"))
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "WeeklyLossLimitRule"
        assert result.severity == RiskSeverity.CRITICAL
        assert "13.0" in result.message
        assert "25%" in result.suggested_action


class TestMaxDrawdownRuleActual:
    """실제 MaxDrawdownRule 테스트"""

    def test_max_drawdown_rule_passes_when_within_threshold(self):
        """드로다운이 임계값 내에 있으면 통과한다."""
        from src.risk.rules.max_drawdown_rule import MaxDrawdownRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("46000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-500000"),
            daily_pnl_percent=Decimal("-1"),
            weekly_pnl_krw=Decimal("-4000000"),
            weekly_pnl_percent=Decimal("-8"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("8"),  # 8% (< 10% warning)
        )

        rule = MaxDrawdownRule()
        result = rule.evaluate(context)

        assert result is None

    def test_max_drawdown_rule_warns_at_warning_threshold(self):
        """드로다운이 경고 임계값을 초과하면 WARNING을 반환한다."""
        from src.risk.rules.max_drawdown_rule import MaxDrawdownRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("44000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-1000000"),
            daily_pnl_percent=Decimal("-2"),
            weekly_pnl_krw=Decimal("-6000000"),
            weekly_pnl_percent=Decimal("-12"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("12"),  # 12% (>= 10% warning)
        )

        rule = MaxDrawdownRule()
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "MaxDrawdownRule"
        assert result.severity == RiskSeverity.WARNING
        assert "12" in result.message
        assert "50%" in result.suggested_action

    def test_max_drawdown_rule_critical_at_critical_threshold(self):
        """드로다운이 임계 임계값을 초과하면 CRITICAL을 반환한다."""
        from src.risk.rules.max_drawdown_rule import MaxDrawdownRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("8000000"),
            portfolio_value_krw=Decimal("41000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-2000000"),
            daily_pnl_percent=Decimal("-4"),
            weekly_pnl_krw=Decimal("-9000000"),
            weekly_pnl_percent=Decimal("-18"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("18"),  # 18% (>= 15% critical)
        )

        rule = MaxDrawdownRule()
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "MaxDrawdownRule"
        assert result.severity == RiskSeverity.CRITICAL
        assert "18" in result.message
        assert "신규 거래 금지" in result.suggested_action

    def test_max_drawdown_rule_emergency_at_emergency_threshold(self):
        """드로다운이 긴급 임계값을 초과하면 EMERGENCY를 반환한다."""
        from src.risk.rules.max_drawdown_rule import MaxDrawdownRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("5000000"),
            portfolio_value_krw=Decimal("38000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-3000000"),
            daily_pnl_percent=Decimal("-7"),
            weekly_pnl_krw=Decimal("-12000000"),
            weekly_pnl_percent=Decimal("-24"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("24"),  # 24% (>= 20% emergency)
        )

        rule = MaxDrawdownRule()
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "MaxDrawdownRule"
        assert result.severity == RiskSeverity.EMERGENCY
        assert "24" in result.message
        assert "모든 포지션 청산" in result.suggested_action


class TestMaxPositionsRule:
    """MaxPositionsRule 테스트"""

    def test_max_positions_rule_passes_when_below_limit(self):
        """포지션 수가 제한보다 적으면 통과한다."""
        from src.risk.rules.max_positions_rule import MaxPositionsRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
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

        rule = MaxPositionsRule(max_positions=5)
        result = rule.evaluate(context)

        assert result is None

    def test_max_positions_rule_info_when_near_limit(self):
        """포지션 수가 제한에 근접하면 INFO를 반환한다."""
        from src.risk.rules.max_positions_rule import MaxPositionsRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=4,  # max-1 = 4
            total_position_value_krw=Decimal("20000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        rule = MaxPositionsRule(max_positions=5)
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "MaxPositionsRule"
        assert result.severity == RiskSeverity.INFO
        assert "4/5" in result.message

    def test_max_positions_rule_critical_at_limit(self):
        """포지션 수가 제한에 도달하면 CRITICAL을 반환한다."""
        from src.risk.rules.max_positions_rule import MaxPositionsRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=5,  # max = 5
            total_position_value_krw=Decimal("25000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        rule = MaxPositionsRule(max_positions=5)
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "MaxPositionsRule"
        assert result.severity == RiskSeverity.CRITICAL
        assert "기존 포지션 청산" in result.suggested_action


class TestPortfolioExposureRule:
    """PortfolioExposureRule 테스트"""

    def test_portfolio_exposure_rule_passes_when_below_threshold(self):
        """노출이 임계값 내에 있으면 통과한다."""
        from src.risk.rules.portfolio_exposure_rule import PortfolioExposureRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=2,
            total_position_value_krw=Decimal("10000000"),  # 20% exposure
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        rule = PortfolioExposureRule()
        result = rule.evaluate(context)

        assert result is None

    def test_portfolio_exposure_rule_warns_at_warning_threshold(self):
        """노출이 경고 임계값을 초과하면 WARNING을 반환한다."""
        from src.risk.rules.portfolio_exposure_rule import PortfolioExposureRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=3,
            total_position_value_krw=Decimal("16000000"),  # 32% exposure
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        rule = PortfolioExposureRule()
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "PortfolioExposureRule"
        assert result.severity == RiskSeverity.WARNING
        assert "32" in result.message

    def test_portfolio_exposure_rule_critical_at_max_exposure(self):
        """노출이 최대 임계값을 초과하면 CRITICAL을 반환한다."""
        from src.risk.rules.portfolio_exposure_rule import PortfolioExposureRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=4,
            total_position_value_krw=Decimal("22000000"),  # 44% exposure
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
        )

        rule = PortfolioExposureRule()
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "PortfolioExposureRule"
        assert result.severity == RiskSeverity.CRITICAL
        assert "44" in result.message
        assert "신규 포지션 금지" in result.suggested_action


class TestPositionSizeRule:
    """PositionSizeRule 테스트"""

    def test_position_size_rule_passes_when_below_threshold(self):
        """거래 리스크가 임계값 내에 있으면 통과한다."""
        from src.risk.rules.position_size_rule import PositionSizeRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
            proposed_trade_risk_percent=Decimal("1.0"),  # 1% risk
        )

        rule = PositionSizeRule()
        result = rule.evaluate(context)

        assert result is None

    def test_position_size_rule_returns_none_when_no_proposed_trade(self):
        """제안된 거래가 없으면 None을 반환한다."""
        from src.risk.rules.position_size_rule import PositionSizeRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
            proposed_trade_risk_percent=None,
        )

        rule = PositionSizeRule()
        result = rule.evaluate(context)

        assert result is None

    def test_position_size_rule_info_at_warning_threshold(self):
        """거래 리스크가 경고 임계값을 초과하면 INFO를 반환한다."""
        from src.risk.rules.position_size_rule import PositionSizeRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
            proposed_trade_risk_percent=Decimal("1.7"),  # 1.7% risk (>= 1.5% warning)
        )

        rule = PositionSizeRule()
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "PositionSizeRule"
        assert result.severity == RiskSeverity.INFO
        assert "1.7" in result.message

    def test_position_size_rule_warns_at_max_risk(self):
        """거래 리스크가 최대 리스크를 초과하면 WARNING을 반환한다."""
        from src.risk.rules.position_size_rule import PositionSizeRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
            proposed_trade_risk_percent=Decimal("2.5"),  # 2.5% risk (>= 2% max)
        )

        rule = PositionSizeRule()
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "PositionSizeRule"
        assert result.severity == RiskSeverity.WARNING
        assert "2.5" in result.message

    def test_position_size_rule_critical_at_hard_limit(self):
        """거래 리스크가 절대 한도를 초과하면 CRITICAL을 반환한다."""
        from src.risk.rules.position_size_rule import PositionSizeRule

        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=1,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("50000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("0"),
            proposed_trade_risk_percent=Decimal("3.5"),  # 3.5% risk (>= 3% hard limit)
        )

        rule = PositionSizeRule()
        result = rule.evaluate(context)

        assert result is not None
        assert result.rule_name == "PositionSizeRule"
        assert result.severity == RiskSeverity.CRITICAL
        assert "3.5" in result.message
        assert "절대 한도" in result.message
