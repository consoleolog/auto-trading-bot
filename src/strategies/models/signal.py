from dataclasses import dataclass
from decimal import Decimal

from ...trading.exchanges.upbit.codes import Timeframe


@dataclass
class Signal:
    """
    전략에서 발생한 신호

    Attributes:
        strategy_name: 전략 이름
        market: 페어 코드
        timeframe: 거래 중인 페어의 기간
        stop_loss: 손절가
        take_profit: 익절가
    """

    strategy_name: str
    market: str
    timeframe: Timeframe

    stop_loss: Decimal | None
    take_profit: Decimal | None

    metadata: dict | None

    def __post_init__(self):
        for field_name in ["stop_loss", "take_profit"]:
            value = getattr(self, field_name)
            if value is not None and isinstance(value, (int, float, str)):
                setattr(self, field_name, Decimal(str(value)))
