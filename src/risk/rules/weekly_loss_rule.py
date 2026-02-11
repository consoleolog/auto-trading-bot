"""
주간 손실 한도 규칙 - 주간 손실 임계값 초과 시 노출 축소.

요구사항:
- -10% 주간 손실 한도 (노출 축소)
"""

from decimal import Decimal

from ..codes import RiskSeverity
from ..models import RiskContext, TriggeredRule
from ..risk_rule import RiskRule


class WeeklyLossLimitRule(RiskRule):
    """
    주간 손익을 모니터링하고 한도 초과 시 노출을 축소합니다.

    단계:
    - >7%: WARNING (주의, 크기 축소)
    - >10%: CRITICAL (노출 대폭 축소)
    """

    priority = 25
    default_severity = RiskSeverity.WARNING

    def __init__(self, warning_threshold: Decimal = Decimal("7"), critical_threshold: Decimal = Decimal("10")):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    @property
    def name(self) -> str:
        return "WeeklyLossLimitRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        weekly_loss = -context.weekly_pnl_percent

        if weekly_loss >= self.critical_threshold:
            return self._create_triggered(
                f"주간 손실 {weekly_loss:.2f}%가 {self.critical_threshold}%를 초과했습니다",
                severity=RiskSeverity.CRITICAL,
                suggested_action="노출을 평소의 25%로 축소, 보수적 모드 전환",
            )

        if weekly_loss >= self.warning_threshold:
            return self._create_triggered(
                f"주간 손실 {weekly_loss:.2f}%가 한도에 근접하고 있습니다",
                severity=RiskSeverity.WARNING,
                suggested_action="포지션 크기 50% 축소",
            )

        return None
