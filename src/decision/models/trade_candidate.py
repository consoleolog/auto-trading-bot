from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from src.strategies.codes import SignalDirection
from src.strategies.models import Signal


@dataclass
class TradeCandidate:
    """컨플루언스 체크 후 생성된 거래 후보.

    여러 전략의 신호를 종합하여 생성된 거래 후보입니다.
    복수의 신호가 합의를 이룬 경우 생성되며, 리스크 관리 단계로 전달됩니다.

    Attributes:
        market: 거래 대상 심볼
        direction: 거래 방향
        combined_strength: 여러 신호를 종합한 강도 (0.0 - 1.0)
        contributing_signals: 이 후보를 구성하는 원본 신호들의 리스트
        suggested_entry: 제안된 진입 가격
        suggested_stop_loss: 제안된 손절 가격
        suggested_take_profit: 제안된 익절 가격
        timestamp: 후보 생성 시각 (UTC)
    """

    market: str
    direction: SignalDirection
    combined_strength: float
    contributing_signals: list[Signal]
    suggested_entry: Decimal
    suggested_stop_loss: Decimal
    suggested_take_profit: Decimal
    timestamp: datetime = field(default=datetime.now(tz=timezone.utc))
