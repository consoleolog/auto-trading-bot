from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from src.strategies.codes import SignalDirection


@dataclass
class Position:
    """보유 중인 포지션.

    현재 열려있는 거래 포지션의 정보를 담는 클래스입니다.
    진입 가격, 현재 가격, 수량 등을 추적하며 미실현 손익을 계산합니다.

    Attributes:
        market: 거래 대상 심볼 (예: USDT-BTC)
        signal_direction: 포지션 방향 (LONG 또는 SHORT, 향후 사용 예정)
        entry_price: 포지션 진입 가격
        current_price: 현재 시장 가격
        volume: 보유 수량
        stop_loss: 손절 가격
        take_profit: 익절 가격
        opened_at: 포지션 개설 시각 (UTC)
        strategy_id: 이 포지션을 생성한 전략의 ID
    """

    market: str
    signal_direction: SignalDirection
    entry_price: Decimal
    current_price: Decimal
    volume: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    strategy_id: str
    opened_at: datetime = field(default=datetime.now(tz=timezone.utc))

    @property
    def unrealized_pnl(self) -> Decimal:
        """미실현 손익 계산.

        Returns:
            현재 가격 기준 미실현 손익 금액
        """
        if self.signal_direction == SignalDirection.LONG:
            return (self.current_price - self.entry_price) * self.volume
        else:
            return (self.entry_price - self.current_price) * self.volume

    @property
    def unrealized_pnl_percent(self) -> float:
        """미실현 손익률.

        Returns:
            진입 가격 대비 미실현 손익 비율 (백분율)
        """
        if self.entry_price == 0:
            return 0.0
        if self.signal_direction == SignalDirection.LONG:
            return float((self.current_price - self.entry_price) / self.entry_price)
        else:
            return float((self.entry_price - self.current_price) / self.entry_price)

    @property
    def value(self) -> Decimal:
        """현재 포지션 가치.

        Returns:
            현재 가격 기준 포지션의 총 가치
        """
        return self.volume * self.current_price
