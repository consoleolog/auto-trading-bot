from decimal import Decimal

import pytest

from src.risk.codes import RiskDecision, RiskSeverity
from src.risk.models import RiskContext
from src.risk.risk_engine import RiskEngine
from src.risk.risk_rule import RiskRule

# ============= 테스트용 구체적인 RiskRule 구현 클래스들 =============


class AlwaysPassRule(RiskRule):
    """항상 통과하는 규칙 (테스트용)"""

    priority = 100
    default_severity = RiskSeverity.INFO

    @property
    def name(self) -> str:
        return "AlwaysPassRule"

    def evaluate(self, context: RiskContext):
        return None


class InfoLevelRule(RiskRule):
    """INFO 수준 규칙"""

    priority = 200
    default_severity = RiskSeverity.INFO

    @property
    def name(self) -> str:
        return "InfoLevelRule"

    def evaluate(self, context: RiskContext):
        return self._create_triggered(message="정보성 메시지", suggested_action="참고하세요")


class WarningLevelRule(RiskRule):
    """WARNING 수준 규칙"""

    priority = 150
    default_severity = RiskSeverity.WARNING

    @property
    def name(self) -> str:
        return "WarningLevelRule"

    def evaluate(self, context: RiskContext):
        return self._create_triggered(message="경고 메시지", suggested_action="포지션 축소 권장")


class CriticalLevelRule(RiskRule):
    """CRITICAL 수준 규칙"""

    priority = 50
    default_severity = RiskSeverity.CRITICAL

    @property
    def name(self) -> str:
        return "CriticalLevelRule"

    def evaluate(self, context: RiskContext):
        return self._create_triggered(message="치명적 문제 발생", suggested_action="거래 중단")


class EmergencyLevelRule(RiskRule):
    """EMERGENCY 수준 규칙"""

    priority = 10
    default_severity = RiskSeverity.EMERGENCY

    @property
    def name(self) -> str:
        return "EmergencyLevelRule"

    def evaluate(self, context: RiskContext):
        return self._create_triggered(message="긴급 상황", suggested_action="모든 포지션 청산")


class ConditionalRule(RiskRule):
    """조건부 규칙 (드로다운 > 10%일 때만 트리거)"""

    priority = 100
    default_severity = RiskSeverity.WARNING

    @property
    def name(self) -> str:
        return "ConditionalRule"

    def evaluate(self, context: RiskContext):
        if context.current_drawdown_percent > Decimal("10"):
            return self._create_triggered(message="드로다운 10% 초과", suggested_action="리스크 감소")
        return None


# ============= 테스트 클래스 =============


class TestRiskEngine:
    """RiskEngine 테스트"""

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

    @pytest.fixture
    def high_drawdown_context(self):
        """높은 드로다운 컨텍스트"""
        return RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=2,
            total_position_value_krw=Decimal("10000000"),
            portfolio_value_krw=Decimal("40000000"),  # 20% 하락
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("-5000000"),
            daily_pnl_percent=Decimal("-10"),
            weekly_pnl_krw=Decimal("-10000000"),
            weekly_pnl_percent=Decimal("-20"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("20"),
        )

    # ============= 초기화 테스트 =============

    def test_engine_initializes_with_rules(self):
        """엔진이 규칙 리스트로 초기화된다."""
        rule1 = AlwaysPassRule()
        rule2 = WarningLevelRule()

        engine = RiskEngine([rule1, rule2])

        assert len(engine.rules) == 2

    def test_engine_sorts_rules_by_priority(self):
        """엔진이 규칙을 우선순위 순으로 정렬한다."""
        rule1 = AlwaysPassRule()  # priority = 100
        rule2 = WarningLevelRule()  # priority = 150
        rule3 = CriticalLevelRule()  # priority = 50

        engine = RiskEngine([rule1, rule2, rule3])

        # priority 순서: 50, 100, 150
        assert engine.rules[0].priority == 50
        assert engine.rules[1].priority == 100
        assert engine.rules[2].priority == 150

    def test_engine_can_initialize_with_empty_rules(self):
        """빈 규칙 리스트로 초기화할 수 있다."""
        engine = RiskEngine([])

        assert len(engine.rules) == 0

    # ============= evaluate() 메서드 테스트 =============

    def test_evaluate_returns_risk_record(self, basic_context):
        """evaluate가 RiskRecord를 반환한다."""
        engine = RiskEngine([AlwaysPassRule()])

        record = engine.evaluate(basic_context, "decision_123")

        assert record is not None
        assert record.input_decision_id == "decision_123"
        assert record.risk_decision is not None
        assert record.reason is not None

    def test_evaluate_allows_when_all_rules_pass(self, basic_context):
        """모든 규칙이 통과하면 ALLOW를 반환한다."""
        rule = AlwaysPassRule()
        engine = RiskEngine([rule])

        record = engine.evaluate(basic_context, "decision_123")

        assert record.risk_decision == RiskDecision.ALLOW
        assert "통과" in record.reason
        assert len(record.triggered_rules) == 0

    def test_evaluate_triggers_emergency_stop_on_emergency_severity(self, basic_context):
        """EMERGENCY 심각도일 때 EMERGENCY_STOP을 반환한다."""
        rule = EmergencyLevelRule()
        engine = RiskEngine([rule])

        record = engine.evaluate(basic_context, "decision_123")

        assert record.risk_decision == RiskDecision.EMERGENCY_STOP
        assert "긴급" in record.reason
        assert len(record.triggered_rules) == 1
        assert record.triggered_rules[0].severity == RiskSeverity.EMERGENCY

    def test_evaluate_forces_no_action_on_critical_severity(self, basic_context):
        """CRITICAL 심각도일 때 FORCE_NO_ACTION을 반환한다."""
        rule = CriticalLevelRule()
        engine = RiskEngine([rule])

        record = engine.evaluate(basic_context, "decision_123")

        assert record.risk_decision == RiskDecision.FORCE_NO_ACTION
        assert "차단" in record.reason
        assert len(record.triggered_rules) == 1
        assert record.triggered_rules[0].severity == RiskSeverity.CRITICAL

    def test_evaluate_reduces_size_on_warning_severity(self, basic_context):
        """WARNING 심각도일 때 REDUCE_SIZE를 반환한다."""
        rule = WarningLevelRule()
        engine = RiskEngine([rule])

        record = engine.evaluate(basic_context, "decision_123")

        assert record.risk_decision == RiskDecision.REDUCE_SIZE
        assert "경고" in record.reason
        assert len(record.triggered_rules) == 1
        assert record.triggered_rules[0].severity == RiskSeverity.WARNING
        assert record.max_allowed_size_krw is not None

    def test_evaluate_allows_with_info_on_info_severity(self, basic_context):
        """INFO 심각도일 때 ALLOW를 반환한다."""
        rule = InfoLevelRule()
        engine = RiskEngine([rule])

        record = engine.evaluate(basic_context, "decision_123")

        assert record.risk_decision == RiskDecision.ALLOW
        assert "정보" in record.reason
        assert len(record.triggered_rules) == 1
        assert record.triggered_rules[0].severity == RiskSeverity.INFO

    def test_evaluate_respects_severity_hierarchy(self, basic_context):
        """심각도 우선순위를 준수한다 (EMERGENCY > CRITICAL > WARNING > INFO)."""
        # 모든 심각도의 규칙 추가
        rules = [
            InfoLevelRule(),
            WarningLevelRule(),
            CriticalLevelRule(),
            EmergencyLevelRule(),
        ]
        engine = RiskEngine(rules)

        record = engine.evaluate(basic_context, "decision_123")

        # EMERGENCY가 최우선이므로 EMERGENCY_STOP이어야 함
        assert record.risk_decision == RiskDecision.EMERGENCY_STOP

    def test_evaluate_collects_all_triggered_rules(self, basic_context):
        """트리거된 모든 규칙을 수집한다."""
        rules = [
            InfoLevelRule(),
            WarningLevelRule(),
            CriticalLevelRule(),
        ]
        engine = RiskEngine(rules)

        record = engine.evaluate(basic_context, "decision_123")

        # 3개 규칙이 모두 트리거됨
        assert len(record.triggered_rules) == 3

    # ============= _aggregate_decision() 테스트 =============

    def test_aggregate_decision_returns_allow_when_no_rules_triggered(self):
        """트리거된 규칙이 없을 때 ALLOW를 반환한다."""
        decision, reason, action = RiskEngine._aggregate_decision([])

        assert decision == RiskDecision.ALLOW
        assert "통과" in reason
        assert action is None

    def test_aggregate_decision_prioritizes_emergency(self):
        """EMERGENCY가 최우선이다."""
        from src.risk.models import TriggeredRule

        rules = [
            TriggeredRule(
                rule_name="Warning",
                severity=RiskSeverity.WARNING,
                message="경고",
                suggested_action=None,
            ),
            TriggeredRule(
                rule_name="Emergency",
                severity=RiskSeverity.EMERGENCY,
                message="긴급",
                suggested_action=None,
            ),
        ]

        decision, reason, action = RiskEngine._aggregate_decision(rules)

        assert decision == RiskDecision.EMERGENCY_STOP
        assert "긴급" in reason

    def test_aggregate_decision_prioritizes_critical_over_warning(self):
        """CRITICAL이 WARNING보다 우선한다."""
        from src.risk.models import TriggeredRule

        rules = [
            TriggeredRule(
                rule_name="Warning",
                severity=RiskSeverity.WARNING,
                message="경고",
                suggested_action=None,
            ),
            TriggeredRule(
                rule_name="Critical",
                severity=RiskSeverity.CRITICAL,
                message="치명적",
                suggested_action="중단",
            ),
        ]

        decision, reason, action = RiskEngine._aggregate_decision(rules)

        assert decision == RiskDecision.FORCE_NO_ACTION
        assert "차단" in reason

    def test_aggregate_decision_returns_reduce_size_for_warning(self):
        """WARNING만 있을 때 REDUCE_SIZE를 반환한다."""
        from src.risk.models import TriggeredRule

        rules = [
            TriggeredRule(
                rule_name="Warning",
                severity=RiskSeverity.WARNING,
                message="경고",
                suggested_action="축소",
            ),
        ]

        decision, reason, action = RiskEngine._aggregate_decision(rules)

        assert decision == RiskDecision.REDUCE_SIZE
        assert "경고" in reason
        assert action == "축소"

    def test_aggregate_decision_returns_allow_for_info_only(self):
        """INFO만 있을 때 ALLOW를 반환한다."""
        from src.risk.models import TriggeredRule

        rules = [
            TriggeredRule(
                rule_name="Info",
                severity=RiskSeverity.INFO,
                message="정보",
                suggested_action=None,
            ),
        ]

        decision, reason, action = RiskEngine._aggregate_decision(rules)

        assert decision == RiskDecision.ALLOW
        assert "정보" in reason

    # ============= _calculate_max_size() 테스트 =============

    def test_calculate_max_size_returns_base_percentage(self, basic_context):
        """기본 최대 크기는 포트폴리오의 2%이다."""
        max_size = RiskEngine._calculate_max_size(basic_context)

        # 50,000,000 * 0.02 = 1,000,000
        expected = 1_000_000
        assert abs(max_size - expected) < 1

    def test_calculate_max_size_reduces_on_high_drawdown(self, high_drawdown_context):
        """드로다운이 10%를 초과하면 50% 감축한다."""
        max_size = RiskEngine._calculate_max_size(high_drawdown_context)

        # 40,000,000 * 0.02 * 0.5 = 400,000
        expected = 400_000
        assert abs(max_size - expected) < 1

    def test_calculate_max_size_with_zero_drawdown(self):
        """드로다운이 0%일 때 감축 없음."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
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

        max_size = RiskEngine._calculate_max_size(context)

        # 50,000,000 * 0.02 = 1,000,000 (감축 없음)
        expected = 1_000_000
        assert abs(max_size - expected) < 1

    def test_calculate_max_size_with_exact_10_percent_drawdown(self):
        """드로다운이 정확히 10%일 때 감축 없음."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=0,
            total_position_value_krw=Decimal("0"),
            portfolio_value_krw=Decimal("45000000"),
            starting_capital_krw=Decimal("50000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("50000000"),
            current_drawdown_percent=Decimal("10"),  # 정확히 10%
        )

        max_size = RiskEngine._calculate_max_size(context)

        # 45,000,000 * 0.02 = 900,000 (감축 없음, > 10%가 아님)
        expected = 900_000
        assert abs(max_size - expected) < 1

    # ============= add_rule() 테스트 =============

    def test_add_rule_increases_rule_count(self):
        """add_rule이 규칙 개수를 증가시킨다."""
        engine = RiskEngine([AlwaysPassRule()])
        assert len(engine.rules) == 1

        engine.add_rule(WarningLevelRule())
        assert len(engine.rules) == 2

    def test_add_rule_maintains_priority_order(self):
        """add_rule이 우선순위 순서를 유지한다."""
        engine = RiskEngine([AlwaysPassRule()])  # priority = 100

        engine.add_rule(CriticalLevelRule())  # priority = 50
        engine.add_rule(WarningLevelRule())  # priority = 150

        # 우선순위 순서: 50, 100, 150
        assert engine.rules[0].priority == 50
        assert engine.rules[1].priority == 100
        assert engine.rules[2].priority == 150

    def test_add_rule_to_empty_engine(self):
        """빈 엔진에 규칙을 추가할 수 있다."""
        engine = RiskEngine([])

        engine.add_rule(AlwaysPassRule())

        assert len(engine.rules) == 1

    # ============= remove_rule() 테스트 =============

    def test_remove_rule_by_name(self):
        """이름으로 규칙을 제거한다."""
        rule1 = AlwaysPassRule()
        rule2 = WarningLevelRule()

        engine = RiskEngine([rule1, rule2])
        assert len(engine.rules) == 2

        removed = engine.remove_rule("WarningLevelRule")

        assert removed is True
        assert len(engine.rules) == 1
        assert engine.rules[0].name == "AlwaysPassRule"

    def test_remove_rule_returns_false_when_not_found(self):
        """존재하지 않는 규칙을 제거하면 False를 반환한다."""
        engine = RiskEngine([AlwaysPassRule()])

        removed = engine.remove_rule("NonExistentRule")

        assert removed is False
        assert len(engine.rules) == 1

    def test_remove_rule_from_empty_engine(self):
        """빈 엔진에서 규칙을 제거하면 False를 반환한다."""
        engine = RiskEngine([])

        removed = engine.remove_rule("AnyRule")

        assert removed is False
        assert len(engine.rules) == 0

    def test_remove_multiple_rules(self):
        """여러 규칙을 순차적으로 제거할 수 있다."""
        rules = [
            AlwaysPassRule(),
            WarningLevelRule(),
            CriticalLevelRule(),
        ]
        engine = RiskEngine(rules)
        assert len(engine.rules) == 3

        engine.remove_rule("WarningLevelRule")
        assert len(engine.rules) == 2

        engine.remove_rule("CriticalLevelRule")
        assert len(engine.rules) == 1

        engine.remove_rule("AlwaysPassRule")
        assert len(engine.rules) == 0

    # ============= 통합 시나리오 테스트 =============

    def test_end_to_end_all_rules_pass(self, basic_context):
        """모든 규칙이 통과하는 전체 플로우."""
        engine = RiskEngine([AlwaysPassRule(), AlwaysPassRule()])

        record = engine.evaluate(basic_context, "decision_123")

        assert record.risk_decision == RiskDecision.ALLOW
        assert len(record.triggered_rules) == 0

    def test_end_to_end_conditional_rules(self, basic_context, high_drawdown_context):
        """조건부 규칙이 컨텍스트에 따라 다르게 동작한다."""
        engine = RiskEngine([ConditionalRule()])

        # 드로다운이 없는 컨텍스트: 통과
        record1 = engine.evaluate(basic_context, "decision_1")
        assert record1.risk_decision == RiskDecision.ALLOW

        # 드로다운이 높은 컨텍스트: 경고
        record2 = engine.evaluate(high_drawdown_context, "decision_2")
        assert record2.risk_decision == RiskDecision.REDUCE_SIZE

    def test_end_to_end_mixed_severity_rules(self, basic_context):
        """다양한 심각도의 규칙이 혼합된 시나리오."""
        rules = [
            InfoLevelRule(),
            WarningLevelRule(),
            CriticalLevelRule(),
        ]
        engine = RiskEngine(rules)

        record = engine.evaluate(basic_context, "decision_123")

        # CRITICAL이 우선이므로 FORCE_NO_ACTION
        assert record.risk_decision == RiskDecision.FORCE_NO_ACTION
        assert len(record.triggered_rules) == 3

    def test_engine_with_dynamic_rule_management(self, basic_context):
        """규칙을 동적으로 추가/제거하는 시나리오."""
        engine = RiskEngine([AlwaysPassRule()])

        # 초기: 모두 통과
        record1 = engine.evaluate(basic_context, "decision_1")
        assert record1.risk_decision == RiskDecision.ALLOW

        # CRITICAL 규칙 추가
        engine.add_rule(CriticalLevelRule())
        record2 = engine.evaluate(basic_context, "decision_2")
        assert record2.risk_decision == RiskDecision.FORCE_NO_ACTION

        # CRITICAL 규칙 제거
        engine.remove_rule("CriticalLevelRule")
        record3 = engine.evaluate(basic_context, "decision_3")
        assert record3.risk_decision == RiskDecision.ALLOW

    # ============= 엣지 케이스 테스트 =============

    def test_evaluate_with_very_large_portfolio(self):
        """매우 큰 포트폴리오에서도 정상 작동한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="LIVE",
            open_positions_count=0,
            total_position_value_krw=Decimal("0"),
            portfolio_value_krw=Decimal("10000000000"),  # 100억
            starting_capital_krw=Decimal("10000000000"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("10000000000"),
            current_drawdown_percent=Decimal("0"),
        )

        engine = RiskEngine([AlwaysPassRule()])
        record = engine.evaluate(context, "decision_123")

        assert record.risk_decision == RiskDecision.ALLOW

    def test_evaluate_with_zero_portfolio_value(self):
        """포트폴리오 가치가 0일 때도 정상 작동한다."""
        context = RiskContext(
            system_state="RUNNING",
            mode="PAPER",
            open_positions_count=0,
            total_position_value_krw=Decimal("0"),
            portfolio_value_krw=Decimal("0"),
            starting_capital_krw=Decimal("0"),
            daily_pnl_krw=Decimal("0"),
            daily_pnl_percent=Decimal("0"),
            weekly_pnl_krw=Decimal("0"),
            weekly_pnl_percent=Decimal("0"),
            peak_portfolio_value_krw=Decimal("0"),
            current_drawdown_percent=Decimal("0"),
        )

        engine = RiskEngine([AlwaysPassRule()])
        record = engine.evaluate(context, "decision_123")

        assert record.risk_decision == RiskDecision.ALLOW

    def test_config_references_are_included(self, basic_context):
        """감사 추적을 위한 설정 참조가 포함된다."""
        engine = RiskEngine([AlwaysPassRule()])

        record = engine.evaluate(basic_context, "decision_123")

        assert record.config_reference is not None
        assert "risk_limits" in record.config_reference
        assert "position_rules" in record.config_reference

    def test_timestamp_is_recorded(self, basic_context):
        """타임스탬프가 기록된다."""
        engine = RiskEngine([AlwaysPassRule()])

        record = engine.evaluate(basic_context, "decision_123")

        assert record.timestamp > 0
        assert isinstance(record.timestamp, int)
