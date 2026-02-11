from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from src.decision.codes import DecisionStatus
from src.strategies.codes import SignalDirection


@dataclass
class Decision:
    """리스크 체크 및 실행 준비가 완료된 트레이딩 의사결정.

    리스크 관리를 통과하고 실행 가능한 상태의 거래 결정입니다.
    포지션 크기, 리스크 금액 등이 계산되어 있으며 실행 대기 상태입니다.

    Attributes:
        decision_id: 의사결정 고유 식별자 (UUID)
        market: 거래 대상 심볼
        direction: 거래 방향
        volume: 거래 수량 (계약 수 또는 코인 개수)
        entry_price: 진입 가격
        stop_loss: 손절 가격
        take_profit: 익절 가격
        risk_amount: 이 거래에서 위험에 노출되는 금액
        risk_percent: 전체 자본 대비 리스크 비율 (백분율)
        contributing_signals: 이 결정에 기여한 신호들의 strategy_id 리스트
        timestamp: 의사결정 생성 시각 (UTC)
        status: 의사결정 상태 (PENDING, APPROVED, REJECTED 등)
    """

    market: str
    volume: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    risk_amount: Decimal
    risk_percent: float
    decision_id: UUID = field(default_factory=uuid4)
    direction: SignalDirection = SignalDirection.HOLD
    contributing_signals: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    status: DecisionStatus = DecisionStatus.PENDING
