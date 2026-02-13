import logging
from decimal import Decimal

import numpy as np

from ..math import calculate_ema
from ..trading.exchanges.upbit.models import Candle
from .codes import MarketRegime

logger = logging.getLogger(__name__)


class RegimeDetector:
    def __init__(
        self,
        config: dict | None = None,
        default_regime: MarketRegime = MarketRegime.UNKNOWN,
    ):
        self._config = config or {}
        self._current_regime = default_regime

        self._ema_short_period = self._config.get("ema_short_period", 5)
        self._ema_mid_period = self._config.get("ema_mid_period", 20)
        self._ema_long_period = self._config.get("ema_long_period", 40)

    @property
    def current_regime(self) -> MarketRegime:
        return self._current_regime

    # ========================================================================
    # PUBLIC INTERFACE
    # ========================================================================

    def detect(self, candles: list[Candle]) -> MarketRegime:
        """
        현재 시장 국면을 감지합니다.

        Args:
            candles: 분석할 캔들 리스트
        Returns:
            현재 시장 국면
        """
        if len(candles) < self._ema_long_period:
            logger.warning(f"시장 국면 감지를 위한 데이터 부족: {len(candles)} 캔들")
            return self._current_regime

        prices = [float(c.trade_price) for c in candles]

        ema_short = calculate_ema(np.array(prices), self._ema_short_period)
        ema_mid = calculate_ema(np.array(prices), self._ema_mid_period)
        ema_long = calculate_ema(np.array(prices), self._ema_long_period)

        short, mid, long = Decimal(str(ema_short[-1])), Decimal(str(ema_mid[-1])), Decimal(str(ema_long[-1]))

        # 단기 > 중기 > 장기 -> 안정적인 상승 추세
        if short > mid > long:
            return MarketRegime.STABLE_BULL
        # 중기 > 단기 > 장기 -> 상승 추세의 끝
        elif mid > short > long:
            return MarketRegime.END_OF_BULL
        # 중기 > 장기 > 단기 -> 하락 추세의 시작
        elif mid > long > short:
            return MarketRegime.START_OF_BEAR
        # 장기 > 중기 > 단기 -> 안정적인 하락 추세
        elif long > mid > short:
            return MarketRegime.STABLE_BEAR
        # 장기 > 단기 > 중기 -> 하락 추세의 끝
        elif long > short > mid:
            return MarketRegime.END_OF_BEAR
        # 단기 > 장기 > 중기 -> 상승 추세의 시작
        elif short > long > mid:
            return MarketRegime.START_OF_BULL
        else:
            return MarketRegime.UNKNOWN
