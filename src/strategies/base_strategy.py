from abc import ABC, abstractmethod

from ..trading.exchanges.upbit.codes import Timeframe
from ..trading.exchanges.upbit.models import Candle
from .codes import MarketRegime
from .models import Signal


class BaseStrategy(ABC):
    """
    거래에 사용할 전략의 추상 클래스
    """

    def __init__(self, config: dict, storage):
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

    @abstractmethod
    def get_supported_regimes(self) -> list[MarketRegime]:
        """
        거래를 진행할 추세 시점을 리스트로 반환
        """
        raise NotImplementedError()

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def create_signal(
        self,
        market: str,
        timeframe: Timeframe,
        market_regime: MarketRegime,
        metadata: dict,
    ) -> Signal:
        return Signal(
            strategy_name=self.config.get("name"),
            market=market,
            timeframe=timeframe,
            market_regime=market_regime,
            metadata=metadata,
        )

    def should_run(self, regime: MarketRegime) -> bool:
        """
        전략을 실행할 수 있는 추세 시점인지 확인

        Args:
            regime: 현재 추세

        Returns:
            True if strategy should run
        """
        return regime in self.get_supported_regimes()
