from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from src.strategies.codes import SignalDirection
from src.trading.exchanges.upbit.codes import Timeframe


@dataclass
class Signal:
    """전략으로부터 생성된 트레이딩 신호.

    개별 전략이 분석 결과를 바탕으로 생성하는 매매 신호입니다.
    신호의 방향, 강도, 신뢰도 및 진입/청산 가격을 포함합니다.

    Attributes:
        strategy_id: 신호를 생성한 전략의 고유 식별자
        market: 거래 대상 심볼 (예: USDT-BTC)
        direction: 신호 방향 (LONG, SHORT, CLOSE, HOLD)
        strength: 신호의 강도 (0.0 - 1.0, 높을수록 강한 신호)
        confidence: 신호에 대한 신뢰도 (0.0 - 1.0, 높을수록 신뢰)
        entry_price: 제안된 진입 가격
        stop_loss: 제안된 손절 가격
        take_profit: 제안된 익절 가격
        timeframe: 신호가 기반한 시간대 (기본값: 4h)
        timestamp: 신호 생성 시각 (UTC)
        metadata: 추가 메타데이터를 저장하는 딕셔너리
    """

    strategy_id: str
    market: str
    direction: SignalDirection
    strength: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    timeframe: Timeframe
    timestamp: datetime = field(default=datetime.now(tz=timezone.utc))
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        for field_name in ["entry_price", "stop_loss", "take_profit"]:
            value = getattr(self, field_name)
            if value is not None and isinstance(value, (int, float, str)):
                setattr(self, field_name, Decimal(str(value)))
