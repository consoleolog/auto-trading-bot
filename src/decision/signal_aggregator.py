import logging

from src.strategies.models.signal import Signal

logger = logging.getLogger(__name__)


class SignalAggregator:
    """
    여러 전략으로부터 신호를 집계합니다.

    신호를 수집하고 심볼별로 그룹화하여 신호 일치 여부를 확인합니다.
    """

    def __init__(self, min_confidence: float = 0.6):
        """
        신호 집계기를 초기화합니다.

        Args:
            min_confidence: 신호를 수락할 최소 신뢰도
        """
        self.min_confidence = min_confidence
        self._signals: dict[str, list[Signal]] = {}  # 심볼별로 그룹화

    def add_signal(self, signal: Signal) -> None:
        """집계기에 신호를 추가합니다."""
        if signal.confidence < self.min_confidence:
            logger.debug(f"신호 거부 (낮은 신뢰도): {signal.strategy_id} {signal.market} conf={signal.confidence}")
            return

        if signal.market not in self._signals:
            self._signals[signal.market] = []

        self._signals[signal.market].append(signal)
        logger.debug(f"신호 추가됨: {signal.strategy_id} {signal.direction.value} {signal.market}")

    def get_signals(self, symbol: str) -> list[Signal]:
        """특정 심볼의 모든 신호를 가져옵니다."""
        return self._signals.get(symbol, [])

    def get_all_signals(self) -> dict[str, list[Signal]]:
        """심볼별로 그룹화된 모든 신호를 가져옵니다."""
        return self._signals.copy()

    def clear(self) -> None:
        """모든 신호를 초기화합니다."""
        self._signals.clear()

    @property
    def signal_count(self) -> int:
        """전체 신호 개수를 반환합니다."""
        return sum(len(signals) for signals in self._signals.values())
