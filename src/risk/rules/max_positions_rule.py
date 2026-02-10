"""
최대 포지션 규칙 - 동시 보유 포지션 수 제한.

소규모 자본으로 과도한 분산투자를 방지합니다.
"""

from src.risk import RiskRule
from src.risk.codes import RiskSeverity
from src.risk.models import RiskContext, TriggeredRule


class MaxPositionsRule(RiskRule):
    """
    최대 오픈 포지션 수를 강제합니다.

    $100 시작 자본의 경우, 너무 많은 포지션 = 포지션당 금액 너무 적음.
    권장: 최대 3-5개 포지션.
    """

    priority = 110
    default_severity = RiskSeverity.WARNING

    def __init__(self, max_positions: int = 5):
        self.max_positions = max_positions

    @property
    def name(self) -> str:
        return "MaxPositionsRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        if context.open_positions_count >= self.max_positions:
            return self._create_triggered(
                f"최대 포지션 수({self.max_positions})에 도달했습니다",
                severity=RiskSeverity.CRITICAL,
                suggested_action="신규 포지션 진입 전 기존 포지션 청산 필요",
            )

        if context.open_positions_count >= self.max_positions - 1:
            return self._create_triggered(
                f"최대 포지션 수에 근접({context.open_positions_count}/{self.max_positions})",
                severity=RiskSeverity.INFO,
                suggested_action="신규 거래 전 포지션 수 고려 필요",
            )

        return None
