from dataclasses import dataclass

from ..codes import RiskSeverity


@dataclass(frozen=True)
class TriggeredRule:
    """
    단일 트리거된 리스크 규칙에 대한 기록.

    Attributes:
        rule_name (str): 실행된 리스크 규칙의 이름.
        severity (RiskSeverity): 해당 규칙 위반의 심각도.
        message (str): 규칙 위반에 대한 상세 설명 메시지.
        suggested_action (Optional[str]): 해당 위반 사항을 해결하기 위한 권장 조치.
    """

    rule_name: str
    severity: RiskSeverity
    message: str
    suggested_action: str | None = None
