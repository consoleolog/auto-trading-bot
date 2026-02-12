from abc import ABC, abstractmethod
from decimal import Decimal

from ..database import DataStorage
from ..trading.exchanges.upbit.codes import Timeframe
from ..trading.exchanges.upbit.models import Candle
from .models import Signal


class BaseStrategy(ABC):
    """
    거래에 사용할 전략의 추상 클래스
    """

    def __init__(self, config: dict, storage: DataStorage):
        self.name = config.get("name")
        self.config = config
        self._storage = storage

    @abstractmethod
    async def evaluate(self, candles: list[Candle], timeframe: Timeframe) -> Signal | None:
        """
        전략을 평가하고 조건이 충족되면 시그널 발생

        Args:
            candles: 캔들 리스트
            timeframe: 캔들 조회 기간
        """
        raise NotImplementedError()

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def create_signal(
        self, market: str, timeframe: Timeframe, stop_loss: Decimal, take_profit: Decimal, metadata: dict
    ) -> Signal:
        return Signal(
            strategy_name=self.config.get("name"),
            market=market,
            timeframe=timeframe,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata=metadata,
        )
