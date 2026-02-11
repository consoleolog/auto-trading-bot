from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..codes import SignalDirection, SignalStrength, SignalType


@dataclass
class TechnicalSignal:
    """
    기술적 지표에서 발생한 시그널 정보

    Attributes:
        signal_name: 발생한 시그널 이름 (ex. macd, rsi)
        signal_type: 발생한 시그널의 종류 (ex. CROSS_OVER, OVER_LINE)
        signal_value: 시그널의 값 (golden_cross, dead_cross, ...)
        signal_strength: 시그널 score 를 계산하기 위한 강도
        signal_direction: 시그널을 통해 생성할 매매 방향
        created_at: 생성 시점
        last_updated_at: 업데이트 시점
    """

    signal_name: str
    signal_type: SignalType
    signal_value: str = "hold"
    signal_strength: SignalStrength = SignalStrength.NEUTRAL
    signal_direction: SignalDirection = SignalDirection.HOLD

    created_at: datetime = field(default=datetime.now(tz=timezone.utc))
    last_updated_at: datetime = field(default=datetime.now(tz=timezone.utc))

    def __post_init__(self):
        if isinstance(self.signal_strength, str):
            self.signal_strength = SignalStrength(self.signal_strength)

        if isinstance(self.signal_direction, str):
            self.signal_direction = SignalDirection(self.signal_direction)
