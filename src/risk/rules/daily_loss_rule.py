"""
일일 손실 한도 규칙 - 일일 손실 임계값 초과 시 거래 중단.

요구사항:
- -5% 일일 손실 한도 (거래 일시 중단)
"""

from decimal import Decimal

from src.risk import RiskRule
from src.risk.codes import RiskSeverity
from src.risk.models import RiskContext, TriggeredRule


class DailyLossLimitRule(RiskRule):
    """
    일일 손익을 모니터링하고 한도 초과 시 거래를 일시 중단합니다.

    단계:
    - >3%: WARNING (주의)
    - >5%: CRITICAL (당일 거래 일시 중단)
    """

    priority = 20
    default_severity = RiskSeverity.CRITICAL

    def __init__(self, warning_threshold: Decimal = Decimal("3"), critical_threshold: Decimal = Decimal("5")):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    @property
    def name(self) -> str:
        return "DailyLossLimitRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        # 일일 손실은 음수 손익이므로 pnl < -threshold 인지 확인
        daily_loss = -context.daily_pnl_percent

        if daily_loss >= self.critical_threshold:
            return self._create_triggered(
                f"일일 손실 {daily_loss:.2f}%가 {self.critical_threshold}%를 초과했습니다",
                severity=RiskSeverity.CRITICAL,
                suggested_action="다음 날까지 거래 중단, 신규 포지션 금지",
            )

        if daily_loss >= self.warning_threshold:
            return self._create_triggered(
                f"일일 손실 {daily_loss:.2f}%가 한도에 근접하고 있습니다",
                severity=RiskSeverity.WARNING,
                suggested_action="포지션 크기 축소, 거래 중단 고려",
            )

        return None
