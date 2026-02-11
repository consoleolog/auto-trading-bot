"""
최대 낙폭 규칙 - 총 낙폭에 대한 서킷 브레이커.

요구사항:
- -15% 허용 가능
- -20% 서킷 브레이커 (긴급 정지)
"""

from decimal import Decimal

from ..codes import RiskSeverity
from ..models import RiskContext, TriggeredRule
from ..risk_rule import RiskRule


class MaxDrawdownRule(RiskRule):
    """
    포트폴리오의 고점 대비 총 낙폭을 모니터링합니다.

    단계:
    - >10%: WARNING (포지션 크기 축소)
    - >15%: CRITICAL (신규 거래 금지)
    - >20%: EMERGENCY (모든 포지션 청산)
    """

    # 최우선 순위 - 가장 먼저 평가됨
    priority = 10
    default_severity = RiskSeverity.CRITICAL

    def __init__(
        self,
        warning_threshold: Decimal = Decimal("10"),
        critical_threshold: Decimal = Decimal("15"),
        emergency_threshold: Decimal = Decimal("20"),
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.emergency_threshold = emergency_threshold

    @property
    def name(self) -> str:
        return "MaxDrawdownRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        dd = context.current_drawdown_percent

        if dd >= self.emergency_threshold:
            return self._create_triggered(
                f"긴급: 낙폭 {dd:.1f}%가 {self.emergency_threshold}%를 초과했습니다",
                severity=RiskSeverity.EMERGENCY,
                suggested_action="모든 포지션 청산, 거래 중단, 수동 검토 필요",
            )

        if dd >= self.critical_threshold:
            return self._create_triggered(
                f"낙폭 {dd:.1f}%가 {self.critical_threshold}%를 초과했습니다",
                severity=RiskSeverity.CRITICAL,
                suggested_action="낙폭이 감소할 때까지 신규 거래 금지",
            )

        if dd >= self.warning_threshold:
            return self._create_triggered(
                f"낙폭 {dd:.1f}%가 한도에 근접하고 있습니다",
                severity=RiskSeverity.WARNING,
                suggested_action="포지션 크기 50% 축소",
            )

        return None
