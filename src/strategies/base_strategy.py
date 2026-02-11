import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import numpy as np

from src.database import DataStorage
from src.portfolio.models import PortfolioState
from src.trading.exchanges.upbit.models import Candle

from ..math import calculate_atr
from ..trading.exchanges.upbit.codes import Timeframe
from .codes import MarketRegime, SignalDirection, SignalStrength, SignalType
from .models import Signal, StrategyConfig, TechnicalSignal

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
        timeframe: Timeframe,
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

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def create_signal(
        self,
        market: str,
        direction: SignalDirection,
        strength: float,
        confidence: float,
        entry_price: Decimal | None = None,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        timeframe: Timeframe | None = None,
        metadata: dict | None = None,
    ) -> Signal:
        """트레이딩 신호를 생성합니다."""
        return Signal(
            strategy_id=self.strategy_id,
            market=market,
            direction=direction,
            strength=strength,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timeframe=timeframe,
            timestamp=datetime.now(tz=timezone.utc),
            metadata=metadata or {},
        )

    @staticmethod
    def _calculate_take_profit(candles: list[Candle], multiplier: float = 0.7) -> Decimal:
        """
        익절가 계산

        현재가 + (atr x 배수)
        """
        high_prices = [float(c.high_price) for c in candles]
        low_prices = [float(c.low_price) for c in candles]
        close_prices = [float(c.trade_price) for c in candles]

        atr = calculate_atr(
            highs=np.array(high_prices),
            lows=np.array(low_prices),
            closes=np.array(close_prices),
        )
        current_atr = Decimal(str(atr[-1]))

        current_price = candles[-1].trade_price
        take_profit = current_price + (current_atr * Decimal(str(multiplier)))
        return take_profit

    @staticmethod
    def _calculate_stop_loss(candles: list[Candle], multiplier: float = 1.0) -> Decimal:
        """
        손절가 계산

        현재가 + (atr x 배수)
        """
        high_prices = [float(c.high_price) for c in candles]
        low_prices = [float(c.low_price) for c in candles]
        close_prices = [float(c.trade_price) for c in candles]

        atr = calculate_atr(
            highs=np.array(high_prices),
            lows=np.array(low_prices),
            closes=np.array(close_prices),
        )
        current_atr = Decimal(str(atr[-1]))

        current_price = candles[-1].trade_price
        stop_loss = current_price - (current_atr * Decimal(str(multiplier)))
        return stop_loss

    async def check_crossover(
        self, name: str, one_values: np.ndarray, two_values: np.ndarray
    ) -> TechnicalSignal | None:
        """
        크로스오버 확인

        Args:
            name: 지표 이름
            one_values: 기준이 될 값
            two_values: 비교할 값
        """
        if len(one_values) < 2 or len(two_values) < 2:
            return TechnicalSignal(
                signal_name=name,
                signal_type=SignalType.CROSS_OVER,
                signal_value="hold",
                signal_strength=SignalStrength.NEUTRAL,
                signal_direction=SignalDirection.HOLD,
            )

        prev_one, curr_one = one_values[-2], one_values[-1]
        prev_two, curr_two = two_values[-2], two_values[-1]

        # 과거 (one < two) and 현재 (one > two) -> GOLDEN CROSS
        if prev_one < prev_two and curr_one > curr_two:
            signal = TechnicalSignal(
                signal_name=name,
                signal_type=SignalType.CROSS_OVER,
                signal_value="golden_cross",
                signal_strength=SignalStrength.BID,
                signal_direction=SignalDirection.LONG,
            )
            await self._data_storage.save_technical_signal(signal)
            return signal
        # 과거 (one > two) and 현재 (one < two) -> DEAD CROSS
        elif prev_one > prev_two and curr_one < curr_two:
            signal = TechnicalSignal(
                signal_name=name,
                signal_type=SignalType.CROSS_OVER,
                signal_value="dead_cross",
                signal_strength=SignalStrength.ASK,
                signal_direction=SignalDirection.SHORT,
            )
            await self._data_storage.save_technical_signal(signal)
            return signal
        else:
            return await self._data_storage.get_technical_signal(name, signal_type=SignalType.CROSS_OVER)

    async def check_over_line(self, name: str, value: Decimal, overbought: int, oversold: int) -> TechnicalSignal:
        """
        과매수/과매도 판단

        Args:
            name: 지표 이름
            value: 확인할 값
            overbought: 과매수 임계값
            oversold: 과매도 임계값
        """
        # value > 과매수 임계값 -> OVER BOUGHT
        if value > Decimal(str(overbought)):
            signal = TechnicalSignal(
                signal_name=name,
                signal_type=SignalType.OVER_LINE,
                signal_value="overbought",
                signal_strength=SignalStrength.STRONG_ASK,
                signal_direction=SignalDirection.SHORT,
            )
            await self._data_storage.save_technical_signal(signal)
            return signal
        elif value < Decimal(str(oversold)):
            signal = TechnicalSignal(
                signal_name=name,
                signal_type=SignalType.OVER_LINE,
                signal_value="oversold",
                signal_strength=SignalStrength.STRONG_BID,
                signal_direction=SignalDirection.LONG,
            )
            await self._data_storage.save_technical_signal(signal)
            return signal
        else:
            return await self._data_storage.get_technical_signal(name, signal_type=SignalType.OVER_LINE)
