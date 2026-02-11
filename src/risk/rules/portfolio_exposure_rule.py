"""
포트폴리오 노출 규칙 - 총 포지션 가치를 포트폴리오 대비 %로 제한.

요구사항:
- 최대 30-40% 포지션 크기 (포트폴리오 대비 %)
"""

from decimal import Decimal

from ..codes import RiskSeverity
from ..models import RiskContext, TriggeredRule
from ..risk_rule import RiskRule


class PortfolioExposureRule(RiskRule):
    """
    최대 포트폴리오 노출을 강제합니다 (총 포지션 / 포트폴리오 가치).

    단계:
    - >30%: WARNING (한도에 근접)
    - >40%: CRITICAL (신규 포지션 금지)
    - >60%: CRITICAL (과다 노출, 축소 고려)
    """

    priority = 105
    default_severity = RiskSeverity.WARNING

    def __init__(
        self,
        warning_threshold: Decimal = Decimal("30"),
        max_exposure: Decimal = Decimal("40"),
        critical_exposure: Decimal = Decimal("60"),
    ):
        self.warning_threshold = warning_threshold
        self.max_exposure = max_exposure
        self.critical_exposure = critical_exposure

    @property
    def name(self) -> str:
        return "PortfolioExposureRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        exposure = context.position_utilization_percent

        if exposure >= self.critical_exposure:
            return self._create_triggered(
                f"포트폴리오 노출 {exposure:.1f}%가 위험 수준입니다",
                severity=RiskSeverity.CRITICAL,
                suggested_action="포지션 축소, 신규 거래 금지",
            )

        if exposure >= self.max_exposure:
            return self._create_triggered(
                f"포트폴리오 노출 {exposure:.1f}%가 최대치에 도달했습니다",
                severity=RiskSeverity.CRITICAL,
                suggested_action="노출이 감소할 때까지 신규 포지션 금지",
            )

        if exposure >= self.warning_threshold:
            return self._create_triggered(
                f"포트폴리오 노출 {exposure:.1f}%가 한도에 근접하고 있습니다",
                severity=RiskSeverity.WARNING,
                suggested_action="신규 포지션 진입 시 주의 필요",
            )

        return None
