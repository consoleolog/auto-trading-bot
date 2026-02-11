"""
Risk Engine - 중앙 리스크 통제 장치.

실거래(Live Trading) 요건에 맞게 대폭 확장됨:
- 우선순위에 따른 다중 규칙 평가
- 심각도 집계 로직
- 긴급 정지(Emergency Stop) 기능
- 상세 감사 기록 생성
"""

import time
from decimal import Decimal

from .codes import RiskDecision, RiskSeverity
from .models import RiskContext, RiskRecord, TriggeredRule
from .risk_rule import RiskRule


class RiskEngine:
    """
    리스크 관리 권한을 가진 중앙 엔진.

    주요 역할:
    - 거래 실행 전 모든 리스크 규칙 평가
    - 리스크 한도를 초과하는 거래 차단
    - 필요 시 긴급 정지(Emergency Stop) 트리거
    - 상세한 감사 기록(Audit Record) 제공

    책임 제외 범위:
    - 포지션 사이징 (별도 모듈 담당)
    - 전략적 의사결정 (전략은 제안하고, 리스크 엔진은 승인/거절만 수행)
    - 주문 실행 (실행 레이어 담당)

    Attributes:
        rules (List[RiskRule]): 우선순위에 따라 정렬된 리스크 규칙 리스트.
    """

    def __init__(self, rules: list[RiskRule]):
        """
        리스크 규칙 리스트를 사용하여 엔진을 초기화합니다.

        Args:
            rules: 평가에 사용할 RiskRule 인스턴스 리스트.
        """
        # 규칙을 우선순위(낮은 숫자 우선)에 따라 정렬
        self.rules = sorted(rules, key=lambda r: r.priority)

    def evaluate(self, context: RiskContext, decision_id: str) -> RiskRecord:
        """
        현재 컨텍스트를 바탕으로 모든 리스크 규칙을 평가합니다.

        Args:
            context: 현재 리스크 상태 스냅샷.
            decision_id: 평가 대상이 되는 의사결정/거래 ID.

        Returns:
            평가 결과가 담긴 RiskRecord 객체.
        """
        triggered_rules: list[TriggeredRule] = []

        # 모든 규칙 평가 수행
        for rule in self.rules:
            result = rule.evaluate(context)
            if result is not None:
                triggered_rules.append(result)

        # 트리거된 규칙들을 종합하여 최종 의사결정 도출
        risk_decision, reason, recommended_action = self._aggregate_decision(triggered_rules)

        # REDUCE_SIZE 결정 시 허용 가능한 최대 규모 계산
        max_allowed_size = None
        if risk_decision == RiskDecision.REDUCE_SIZE:
            max_allowed_size = self._calculate_max_size(context)

        return RiskRecord(
            timestamp=int(time.time()),
            input_decision_id=decision_id,
            risk_decision=risk_decision,
            reason=reason,
            triggered_rules=triggered_rules,
            recommended_action=recommended_action,
            max_allowed_size_krw=max_allowed_size,
            config_reference=self._get_config_refs(),
        )

    @staticmethod
    def _aggregate_decision(triggered_rules: list[TriggeredRule]) -> tuple[RiskDecision, str, str | None]:
        """
        트리거된 여러 규칙을 종합하여 하나의 최종 결정을 내립니다.

        Returns:
            (결정사항, 사유, 권장 조치) 튜플.
        """
        if not triggered_rules:
            return (RiskDecision.ALLOW, "모든 리스크 규칙 통과", None)

        # 1순위: EMERGENCY 심각도 확인
        emergencies = [r for r in triggered_rules if r.severity == RiskSeverity.EMERGENCY]
        if emergencies:
            return (
                RiskDecision.EMERGENCY_STOP,
                f"긴급 상황: {emergencies[0].message}",
                "즉시 모든 포지션을 청산(Flatten)하십시오.",
            )

        # 2순위: CRITICAL 심각도 확인
        criticals = [r for r in triggered_rules if r.severity == RiskSeverity.CRITICAL]
        if criticals:
            return RiskDecision.FORCE_NO_ACTION, f"차단됨: {criticals[0].message}", criticals[0].suggested_action

        # 3순위: WARNING 심각도 확인 (거래는 허용하되 규모 축소)
        warnings = [r for r in triggered_rules if r.severity == RiskSeverity.WARNING]
        if warnings:
            return RiskDecision.REDUCE_SIZE, f"경고: {warnings[0].message}", warnings[0].suggested_action

        # 4순위: INFO 수준 - 거래 허용 및 내용 기록
        return RiskDecision.ALLOW, f"정보: {triggered_rules[0].message}", None

    @staticmethod
    def _calculate_max_size(context: RiskContext) -> float:
        """
        허용 가능한 최대 포지션 규모를 계산합니다.

        보수적인 접근 방식을 사용하며, 경고 발생 시 통상 규모의 50%로 제한합니다.
        """
        # 기본 최대치: 포트폴리오의 2%
        base_max = float(context.portfolio_value_krw) * 0.02

        # 이미 드로다운(낙폭)이 10%를 초과한 경우 추가로 50% 감축
        if context.current_drawdown_percent > Decimal("10"):
            base_max *= 0.5

        return base_max

    @staticmethod
    def _get_config_refs() -> dict:
        """감사 추적을 위한 설정 파일 참조 정보를 반환합니다."""
        return {"risk_limits": "config/risk_limits.yaml", "position_rules": "config/position_rules.yaml"}

    def add_rule(self, rule: RiskRule) -> None:
        """새로운 규칙을 추가하고 우선순위에 따라 재정렬합니다."""
        self.rules.append(rule)
        self.rules = sorted(self.rules, key=lambda r: r.priority)

    def remove_rule(self, rule_name: str) -> bool:
        """이름으로 규칙을 제거합니다. 제거 성공 시 True를 반환합니다."""
        original_len = len(self.rules)
        self.rules = [r for r in self.rules if r.name != rule_name]
        return len(self.rules) < original_len
