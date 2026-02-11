import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from src.database import DataStorage
from src.portfolio.models import PortfolioState
from src.trading.exchanges.upbit.models import Candle

from .codes import MarketRegime
from .models import Signal, StrategyConfig

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    트레이딩 전략을 위한 추상 기본 클래스.

    모든 전략은 다음을 구현해야 합니다:
    - evaluate(): 시장 데이터를 기반으로 신호 생성
    - get_supported_regimes(): 전략이 작동하는 시장 국면 리스트 반환
    """

    def __init__(self, config: StrategyConfig, data_storage: DataStorage):
        """
        전략 초기화.

        Args:
            config: 전략 설정
            data_storage: 과거 데이터를 위한 데이터 저장소
        """
        self.strategy_id = config.id
        self.name = config.name
        self.enabled = config.enabled
        self.capital_allocation = config.capital_allocation
        self.parameters = config.parameters

        self._data_storage = data_storage
        self._state: dict[str, Any] = {}

        # 포지션 추적
        self._has_open_position = False
        self._position_market: str | None = None
        self._entry_price: Decimal | None = None

        logger.info(f"Strategy {self.name} ({self.strategy_id}) initialized")

    # ========================================================================
    # ABSTRACT METHODS
    # ========================================================================

    @abstractmethod
    async def evaluate(
        self,
        candles: list[Candle],
        regime: MarketRegime,
        portfolio: PortfolioState,
    ) -> Signal | None:
        """
        전략을 평가하고 조건이 충족되면 신호를 생성합니다.

        Args:
            candles: 최신 완성된 캔들
            regime: 현재 시장 국면
            portfolio: 현재 포트폴리오 상태

        Returns:
            조건이 충족되면 Signal, 그렇지 않으면 None
        """
        raise NotImplementedError()

    @abstractmethod
    def get_supported_regimes(self) -> list[MarketRegime]:
        """
        이 전략이 작동하는 시장 국면 리스트를 반환합니다.

        Returns:
            지원되는 MarketRegime 값들의 리스트
        """
        raise NotImplementedError()

    # ========================================================================
    # PUBLIC METHODS
    # ========================================================================

    def should_run(self, regime: MarketRegime) -> bool:
        """
        현재 시장 국면에서 전략이 실행되어야 하는지 확인합니다.

        Args:
            regime: 현재 시장 국면

        Returns:
            전략이 실행되어야 하면 True
        """
        return self.enabled and regime in self.get_supported_regimes()

    def reset_state(self) -> None:
        """전략 상태를 초기화합니다 (예: 포지션 청산 후)."""
        self._state = {}
        self._has_open_position = False
        self._position_market = None
        self._entry_price = None
        logger.debug(f"전략 {self.strategy_id} 상태 초기화됨")

    def set_position(self, market: str, entry_price: Decimal) -> None:
        """전략이 열린 포지션을 가지고 있다고 표시합니다."""
        self._has_open_position = True
        self._position_market = market
        self._entry_price = entry_price

    def clear_position(self) -> None:
        """전략이 열린 포지션을 가지고 있지 않다고 표시합니다."""
        self._has_open_position = False
        self._position_market = None
        self._entry_price = None

    @property
    def has_position(self) -> bool:
        """전략이 열린 포지션을 가지고 있는지 확인합니다."""
        return self._has_open_position
