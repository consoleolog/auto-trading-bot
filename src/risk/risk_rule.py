from abc import ABC, abstractmethod

from .codes import RiskSeverity
from .models import RiskContext, TriggeredRule


class RiskRule(ABC):
    """
    모든 리스크 규칙의 추상 기본 클래스.

    각 규칙은 특정 리스크 조건을 평가하며, 문제가 없을 경우 None을,
    문제가 발견될 경우 TriggeredRule 객체를 반환합니다.

    Attributes:
        priority (int): 규칙 평가 우선순위 (낮을수록 먼저 평가됨).
            - 긴급 규칙(Emergency): 0-99
            - 치명적 규칙(Critical): 100-199
            - 경고 규칙(Warning): 200-299
            - 정보 규칙(Info): 300+
        default_severity (RiskSeverity): 이 규칙이 위반되었을 때 기본적으로 적용할 심각도.
    """

    # 규칙 우선순위 (기본값: 200 - 경고 수준)
    priority: int = 200

    # 이 규칙의 기본 심각도
    default_severity: RiskSeverity = RiskSeverity.WARNING

    @property
    @abstractmethod
    def name(self) -> str:
        """사람이 읽을 수 있는 규칙의 이름."""
        raise NotImplementedError()

    @abstractmethod
    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        """
        현재 컨텍스트를 바탕으로 리스크 규칙을 평가합니다.

        Args:
            context (RiskContext): 평가에 필요한 시스템 및 포트폴리오 상태 정보.

        Returns:
            Optional[TriggeredRule]: 규칙 위반 시 TriggeredRule 객체, 통과 시 None.
        """
        raise NotImplementedError()

    def _create_triggered(
        self, message: str, severity: RiskSeverity | None = None, suggested_action: str | None = None
    ) -> TriggeredRule:
        """TriggeredRule 객체 생성을 도와주는 헬퍼 메서드."""
        return TriggeredRule(
            rule_name=self.name,
            severity=severity or self.default_severity,
            message=message,
            suggested_action=suggested_action,
        )


class CompositeRiskRule(RiskRule):
    """
    여러 개의 하위 규칙을 결합한 복합 규칙 클래스.

    서로 연관된 규칙들을 그룹화하여 관리할 때 유용합니다.

    Attributes:
        rules (list[RiskRule]): 우선순위에 따라 정렬된 하위 규칙 리스트.
    """

    def __init__(self, rules: list[RiskRule]):
        # 생성 시 우선순위에 따라 규칙을 정렬하여 보관
        self.rules = sorted(rules, key=lambda r: r.priority)

    @property
    def name(self) -> str:
        """복합 규칙의 이름 (기본값: CompositeRule)."""
        return "CompositeRule"

    def evaluate(self, context: RiskContext) -> TriggeredRule | None:
        """
        모든 하위 규칙을 평가하고, 가장 먼저 트리거된(위반된) 규칙을 반환합니다.

        Returns:
            Optional[TriggeredRule]: 가장 먼저 탐지된 위반 규칙 정보, 모두 통과 시 None.
        """
        for rule in self.rules:
            result = rule.evaluate(context)
            if result is not None:
                return result
        return None
