import logging
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np

from src.decision.models.trade_candidate import TradeCandidate
from src.strategies.codes import SignalDirection
from src.strategies.models import Signal

logger = logging.getLogger(__name__)


class ConfluenceChecker:
    """
    신호 일치 여부를 확인합니다.

    거래 전에 동일한 방향의 여러 신호가 필요합니다.
    """

    def __init__(self, min_signals: int = 2):
        """
        신호 일치 확인기를 초기화합니다.

        Args:
            min_signals: 동일 방향으로 필요한 최소 신호 개수
        """
        self.min_signals = min_signals

    def check(self, signals: list[Signal]) -> TradeCandidate | None:
        """
        신호 일치를 확인하고 유효한 경우 거래 후보를 생성합니다.

        Args:
            signals: 심볼에 대한 신호 목록

        Returns:
            일치하는 신호가 발견되면 TradeCandidate, 그렇지 않으면 None
        """
        if len(signals) < self.min_signals:
            return None

        # 방향별 신호 카운트
        direction_counts = {}
        for signal in signals:
            direction = signal.direction
            if direction not in direction_counts:
                direction_counts[direction] = []
            direction_counts[direction].append(signal)

        # 다수 방향 찾기
        best_direction = None
        best_signals = []

        for direction, dir_signals in direction_counts.items():
            if direction == SignalDirection.HOLD:
                continue
            if len(dir_signals) >= self.min_signals and len(dir_signals) > len(best_signals):
                best_direction = direction
                best_signals = dir_signals

        if not best_direction or len(best_signals) < self.min_signals:
            return None

        # 결합된 강도 계산
        combined_strength = self._calculate_combined_strength(best_signals)

        # 신호로부터 제안 가격 추출
        entry_prices = [s.entry_price for s in best_signals if s.entry_price]
        stop_losses = [s.stop_loss for s in best_signals if s.stop_loss]
        take_profits = [s.take_profit for s in best_signals if s.take_profit]

        suggested_entry = sum(entry_prices) / len(entry_prices) if entry_prices else Decimal("0")
        suggested_stop = min(stop_losses) if stop_losses else Decimal("0")
        suggested_tp = max(take_profits) if take_profits else Decimal("0")

        logger.info(
            f"신호 일치 발견: {best_direction.value} {best_signals[0].market} "
            f"({len(best_signals)}개 신호, 강도={combined_strength:.2f})"
        )

        return TradeCandidate(
            market=best_signals[0].market,
            direction=best_direction,
            combined_strength=combined_strength,
            contributing_signals=best_signals,
            suggested_entry=suggested_entry,
            suggested_stop_loss=suggested_stop,
            suggested_take_profit=suggested_tp,
            timestamp=datetime.now(tz=timezone.utc),
        )

    @staticmethod
    def _calculate_combined_strength(
        signals: list[Signal], time_decay_factor: float = 0.1, consistency_bonus: float = 0.15
    ) -> float:
        """
        고급 신호 강도 계산 - 시간 가중치, 이상치 제거, 일관성 점수 적용.

        Args:
            signals: 신호 목록
            time_decay_factor: 시간 감쇠 계수 (높을수록 최근 신호 가중치 증가)
            consistency_bonus: 신호 일관성에 대한 보너스 계수

        Returns:
            결합된 신호 강도 (0.0 - 1.0)
        """
        if not signals:
            return 0.0

        now = datetime.now(tz=timezone.utc)

        # 1. 기본 데이터 추출
        strengths = np.array([s.strength for s in signals])
        confidences = np.array([s.confidence for s in signals])
        timestamps = np.array(
            [
                (now - s.timestamp).total_seconds() / 3600  # 시간 단위
                for s in signals
            ]
        )

        # 2. 이상치 제거 (IQR 방식)
        if len(strengths) >= 4:
            q1, q3 = np.percentile(strengths, [25, 75])
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            mask = (strengths >= lower_bound) & (strengths <= upper_bound)

            if mask.sum() >= 2:  # 최소 2개 이상 남아야 함
                strengths = strengths[mask]
                confidences = confidences[mask]
                timestamps = timestamps[mask]

        # 3. 시간 감쇠 가중치 (지수 감쇠)
        # 최근 신호일수록 높은 가중치
        time_weights = np.exp(-time_decay_factor * timestamps)
        time_weights = time_weights / time_weights.sum()  # 정규화

        # 4. 신뢰도 가중치 정규화
        confidence_weights = (
            confidences / confidences.sum() if confidences.sum() > 0 else np.ones_like(confidences) / len(confidences)
        )

        # 5. 최종 가중치 결합 (시간 * 신뢰도)
        combined_weights = time_weights * confidence_weights
        combined_weights = combined_weights / combined_weights.sum()  # 재정규화

        # 6. 가중 평균 계산
        weighted_strength = np.sum(strengths * combined_weights)

        # 7. 일관성 보너스 (낮은 분산 = 높은 일관성)
        if len(strengths) >= 2:
            # 변동계수(CV)를 사용하여 일관성 측정
            std = np.std(strengths)
            mean = np.mean(strengths)
            cv = std / mean if mean > 0 else 1.0

            # CV가 낮을수록 일관성이 높음 (0에 가까울수록 보너스 최대)
            consistency_score = max(0, 1 - cv) * consistency_bonus
            weighted_strength = min(1.0, weighted_strength + consistency_score)

        return float(np.clip(weighted_strength, 0.0, 1.0))
