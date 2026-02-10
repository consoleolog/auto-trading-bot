"""
포지션 크기 규칙 - 거래당 최대 2% 리스크 강제.

요구사항:
- 거래당 최대 2% 리스크
"""

from decimal import Decimal

from src.risk import RiskRule
from src.risk.codes import RiskSeverity
from src.risk.models import RiskContext, TriggeredRule


class PositionSizeRule(RiskRule):
    """
    단일 거래의 최대 리스크를 강제합니다.

    2% 규칙: 단일 거래에서 포트폴리오의 2% 이상을 리스크에 노출하지 않습니다.

    단계:
    - >1.5%: WARNING (한도에 근접)
    - >2%: CRITICAL (크기 축소)
    - >3%: CRITICAL (거래 완전 차단)
    """

    priority = 100
    default_severity = RiskSeverity.CRITICAL

    def __init__(
        self,
        max_risk_percent: Decimal = Decimal("2"),
        warning_threshold: Decimal = Decimal("1.5"),
        hard_limit_percent: Decimal = Decimal("3"),
    ):
        self.max_risk_percent = max_risk_percent
        self.warning_threshold = warning_threshold
        self.hard_limit_percent = hard_limit_percent

    @property
    def name(self) -> str:
        return "PositionSizeRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        if context.proposed_trade_risk_percent is None:
            return None

        risk = context.proposed_trade_risk_percent

        if risk >= self.hard_limit_percent:
            return self._create_triggered(
                f"거래 리스크 {risk:.2f}%가 절대 한도 {self.hard_limit_percent}%를 초과했습니다",
                severity=RiskSeverity.CRITICAL,
                suggested_action=f"포지션 크기를 최대 {self.max_risk_percent}% 리스크로 축소",
            )

        if risk >= self.max_risk_percent:
            return self._create_triggered(
                f"거래 리스크 {risk:.2f}%가 권장 {self.max_risk_percent}%를 초과했습니다",
                severity=RiskSeverity.WARNING,
                suggested_action=f"{self.max_risk_percent}% 리스크로 축소 고려",
            )

        if risk >= self.warning_threshold:
            return self._create_triggered(
                f"거래 리스크 {risk:.2f}%가 한도에 근접하고 있습니다",
                severity=RiskSeverity.INFO,
                suggested_action="포지션을 면밀히 모니터링",
            )

        return None
