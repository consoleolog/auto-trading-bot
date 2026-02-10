from dataclasses import dataclass, field

from src.risk.codes import RiskDecision, RiskSeverity
from src.risk.models.triggered_rule import TriggeredRule


@dataclass(frozen=True)
class RiskRecord:
    """
    리스크 평가에 대한 감사 가능 기록.

    불변(Immutable) 객체로, 한 번 생성되면 수정할 수 없습니다.
    감사 추적 및 디버깅 용도로 사용됩니다.

    Attributes:
        timestamp (int): 평가가 이루어진 시점의 타임스탬프 (Unix epoch).
        input_decision_id (str): 이 리스크 평가를 요청한 원본 결정 ID.
        risk_decision (RiskDecision): 최종 리스크 판단 결과.
        reason (str): 해당 리스크 판단에 대한 주요 사유.
        triggered_rules (List[TriggeredRule]): 평가 과정에서 탐지된 모든 규칙 리스트.
        recommended_action (Optional[str]): ALLOW가 아닐 경우 취해야 할 후속 권장 조치.
        max_allowed_size_krw (Optional[float]): REDUCE_SIZE 결정 시 허용되는 최대 거래 규모 (USD).
        config_reference (Dict[str, str]): 감사용으로 보관하는 당시의 설정 참조 정보.
    """

    timestamp: int
    input_decision_id: str
    risk_decision: RiskDecision
    reason: str

    triggered_rules: list[TriggeredRule] = field(default_factory=list)
    recommended_action: str | None = None
    max_allowed_size_krw: float | None = None
    config_reference: dict[str, str] = field(default_factory=dict)

    @property
    def is_blocked(self) -> bool:
        """거래 차단 여부 확인 (FORCE_NO_ACTION 또는 EMERGENCY_STOP 상태)."""
        return self.risk_decision in (RiskDecision.FORCE_NO_ACTION, RiskDecision.EMERGENCY_STOP)

    @property
    def highest_severity(self) -> RiskSeverity | None:
        """
        트리거된 모든 규칙 중에서 가장 높은 심각도를 반환합니다.

        Returns:
            Optional[RiskSeverity]: 가장 높은 심각도 수준, 트리거된 규칙이 없으면 None.
        """
        if not self.triggered_rules:
            return None

        severity_order = [RiskSeverity.INFO, RiskSeverity.WARNING, RiskSeverity.CRITICAL, RiskSeverity.EMERGENCY]

        max_idx = 0
        for rule in self.triggered_rules:
            idx = severity_order.index(rule.severity)
            max_idx = max(max_idx, idx)

        return severity_order[max_idx]
