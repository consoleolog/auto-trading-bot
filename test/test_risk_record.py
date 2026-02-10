import pytest

from src.risk.codes import RiskDecision, RiskSeverity
from src.risk.models import RiskRecord
from src.risk.models.triggered_rule import TriggeredRule


class TestRiskRecord:
    @pytest.fixture
    def sample_triggered_rules(self):
        """테스트용 샘플 TriggeredRule 리스트"""
        return [
            TriggeredRule(
                rule_name="max_position_size",
                severity=RiskSeverity.WARNING,
                message="Position size exceeds 10% of portfolio",
                suggested_action="Reduce position size to 10% or less",
            ),
            TriggeredRule(
                rule_name="daily_loss_limit",
                severity=RiskSeverity.CRITICAL,
                message="Daily loss limit reached",
                suggested_action="Stop trading for today",
            ),
        ]

    @pytest.fixture
    def basic_risk_record(self):
        """기본 RiskRecord 인스턴스"""
        return RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-123",
            risk_decision=RiskDecision.ALLOW,
            reason="All risk checks passed",
        )

    # ============= RiskRecord 생성 =============

    def test_create_risk_record_with_minimal_fields(self):
        """필수 필드만으로 RiskRecord를 생성한다."""
        record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-123",
            risk_decision=RiskDecision.ALLOW,
            reason="All checks passed",
        )

        assert record.timestamp == 1707552000
        assert record.input_decision_id == "decision-123"
        assert record.risk_decision == RiskDecision.ALLOW
        assert record.reason == "All checks passed"
        assert record.triggered_rules == []
        assert record.recommended_action is None
        assert record.max_allowed_size_krw is None
        assert record.config_reference == {}

    def test_create_risk_record_with_all_fields(self, sample_triggered_rules):
        """모든 필드를 포함하여 RiskRecord를 생성한다."""
        record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-456",
            risk_decision=RiskDecision.REDUCE_SIZE,
            reason="Position size too large",
            triggered_rules=sample_triggered_rules,
            recommended_action="Reduce position to 50%",
            max_allowed_size_krw=5000000.0,
            config_reference={"max_position_pct": "10", "version": "1.0"},
        )

        assert record.timestamp == 1707552000
        assert record.input_decision_id == "decision-456"
        assert record.risk_decision == RiskDecision.REDUCE_SIZE
        assert record.reason == "Position size too large"
        assert len(record.triggered_rules) == 2
        assert record.recommended_action == "Reduce position to 50%"
        assert record.max_allowed_size_krw == 5000000.0
        assert record.config_reference == {"max_position_pct": "10", "version": "1.0"}

    def test_risk_record_is_immutable(self, basic_risk_record):
        """RiskRecord는 불변 객체이므로 수정할 수 없다."""
        with pytest.raises((AttributeError, TypeError)):
            basic_risk_record.reason = "New reason"

    # ============= is_blocked 속성 =============

    def test_is_blocked_returns_true_for_force_no_action(self):
        """FORCE_NO_ACTION 결정은 is_blocked가 True를 반환한다."""
        record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-789",
            risk_decision=RiskDecision.FORCE_NO_ACTION,
            reason="High volatility detected",
        )

        assert record.is_blocked is True

    def test_is_blocked_returns_true_for_emergency_stop(self):
        """EMERGENCY_STOP 결정은 is_blocked가 True를 반환한다."""
        record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-999",
            risk_decision=RiskDecision.EMERGENCY_STOP,
            reason="System failure detected",
        )

        assert record.is_blocked is True

    def test_is_blocked_returns_false_for_allow(self):
        """ALLOW 결정은 is_blocked가 False를 반환한다."""
        record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-111",
            risk_decision=RiskDecision.ALLOW,
            reason="All checks passed",
        )

        assert record.is_blocked is False

    def test_is_blocked_returns_false_for_reduce_size(self):
        """REDUCE_SIZE 결정은 is_blocked가 False를 반환한다."""
        record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-222",
            risk_decision=RiskDecision.REDUCE_SIZE,
            reason="Position size exceeds limit",
        )

        assert record.is_blocked is False

    # ============= highest_severity 속성 =============

    def test_highest_severity_returns_none_when_no_triggered_rules(self, basic_risk_record):
        """트리거된 규칙이 없으면 None을 반환한다."""
        assert basic_risk_record.highest_severity is None

    def test_highest_severity_returns_correct_severity_for_single_rule(self):
        """단일 규칙만 있으면 해당 규칙의 심각도를 반환한다."""
        record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-333",
            risk_decision=RiskDecision.ALLOW,
            reason="Minor issue detected",
            triggered_rules=[
                TriggeredRule(
                    rule_name="info_rule",
                    severity=RiskSeverity.INFO,
                    message="FYI: Market opened",
                )
            ],
        )

        assert record.highest_severity == RiskSeverity.INFO

    def test_highest_severity_returns_highest_among_multiple_rules(self, sample_triggered_rules):
        """여러 규칙 중 가장 높은 심각도를 반환한다."""
        record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-444",
            risk_decision=RiskDecision.FORCE_NO_ACTION,
            reason="Multiple violations detected",
            triggered_rules=sample_triggered_rules,  # WARNING, CRITICAL
        )

        assert record.highest_severity == RiskSeverity.CRITICAL

    def test_highest_severity_returns_emergency_when_present(self):
        """EMERGENCY 심각도가 포함되어 있으면 EMERGENCY를 반환한다."""
        rules = [
            TriggeredRule(
                rule_name="info_rule",
                severity=RiskSeverity.INFO,
                message="Info message",
            ),
            TriggeredRule(
                rule_name="warning_rule",
                severity=RiskSeverity.WARNING,
                message="Warning message",
            ),
            TriggeredRule(
                rule_name="emergency_rule",
                severity=RiskSeverity.EMERGENCY,
                message="Emergency detected",
            ),
            TriggeredRule(
                rule_name="critical_rule",
                severity=RiskSeverity.CRITICAL,
                message="Critical message",
            ),
        ]

        record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-555",
            risk_decision=RiskDecision.EMERGENCY_STOP,
            reason="Emergency situation",
            triggered_rules=rules,
        )

        assert record.highest_severity == RiskSeverity.EMERGENCY

    def test_highest_severity_correctly_orders_all_severities(self):
        """모든 심각도 레벨이 올바르게 정렬되는지 확인한다."""
        # INFO < WARNING < CRITICAL < EMERGENCY 순서 확인
        info_record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-1",
            risk_decision=RiskDecision.ALLOW,
            reason="Test",
            triggered_rules=[TriggeredRule(rule_name="r1", severity=RiskSeverity.INFO, message="msg")],
        )
        assert info_record.highest_severity == RiskSeverity.INFO

        warning_record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-2",
            risk_decision=RiskDecision.ALLOW,
            reason="Test",
            triggered_rules=[
                TriggeredRule(rule_name="r1", severity=RiskSeverity.INFO, message="msg"),
                TriggeredRule(rule_name="r2", severity=RiskSeverity.WARNING, message="msg"),
            ],
        )
        assert warning_record.highest_severity == RiskSeverity.WARNING

        critical_record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-3",
            risk_decision=RiskDecision.ALLOW,
            reason="Test",
            triggered_rules=[
                TriggeredRule(rule_name="r1", severity=RiskSeverity.WARNING, message="msg"),
                TriggeredRule(rule_name="r2", severity=RiskSeverity.CRITICAL, message="msg"),
            ],
        )
        assert critical_record.highest_severity == RiskSeverity.CRITICAL

        emergency_record = RiskRecord(
            timestamp=1707552000,
            input_decision_id="decision-4",
            risk_decision=RiskDecision.ALLOW,
            reason="Test",
            triggered_rules=[
                TriggeredRule(rule_name="r1", severity=RiskSeverity.CRITICAL, message="msg"),
                TriggeredRule(rule_name="r2", severity=RiskSeverity.EMERGENCY, message="msg"),
            ],
        )
        assert emergency_record.highest_severity == RiskSeverity.EMERGENCY
