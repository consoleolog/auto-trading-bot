import logging
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal
from uuid import uuid4

import numpy as np

from src.decision.codes import DecisionStatus
from src.decision.models import TradeCandidate
from src.decision.models.decision import Decision
from src.portfolio.models import PortfolioState
from src.risk.models import RiskLimitsConfig

logger = logging.getLogger(__name__)


class PositionSizer:
    """
    리스크 매개변수를 기반으로 포지션 크기를 계산합니다.

    구현 내용:
    - 거래당 고정 비율 리스크
    - 손절가 기반 사이징
    - 최대 포지션 제한
    """

    def __init__(self, risk_config: RiskLimitsConfig):
        """
        포지션 사이저를 초기화합니다.

        Args:
            risk_config: 리스크 제한 설정
        """
        self.max_risk_per_trade = risk_config.max_risk_per_trade
        self.max_position_size = risk_config.max_position_size
        self.max_portfolio_exposure = risk_config.max_portfolio_exposure

    def calculate(
        self,
        candidate: TradeCandidate,
        portfolio: PortfolioState,
        current_price: Decimal,
        atr: Decimal | None = None,
    ) -> Decision:
        """
        고급 포지션 사이징 - 켈리 크라이테리온, 드로다운 조정, 변동성 기반 계산.

        Args:
            candidate: 신호 일치 확인으로부터의 거래 후보
            portfolio: 현재 포트폴리오 상태
            current_price: 현재 시장 가격
            atr: Average True Range (변동성 지표, 선택적)

        Returns:
            계산된 포지션 크기를 포함한 Decision
        """
        entry_price = candidate.suggested_entry if candidate.suggested_entry > 0 else current_price
        stop_loss = candidate.suggested_stop_loss
        take_profit = candidate.suggested_take_profit

        # 1. 기본 리스크 기반 포지션 크기 계산
        base_position_value = self._calculate_base_position(entry_price, stop_loss, portfolio.available_capital)

        # 2. 켈리 크라이테리온 기반 조정
        kelly_multiplier = self._calculate_kelly_fraction(
            candidate.combined_strength, entry_price, stop_loss, take_profit
        )

        # 3. 신호 강도 기반 스케일링
        strength_multiplier = self._calculate_strength_multiplier(candidate.combined_strength)

        # 4. 드로다운 기반 축소
        drawdown_multiplier = self._calculate_drawdown_multiplier(portfolio.current_drawdown)

        # 5. ATR 기반 변동성 조정 (선택적)
        volatility_multiplier = self._calculate_volatility_multiplier(atr, entry_price) if atr else 1.0

        # 6. 최종 포지션 크기 계산
        combined_multiplier = kelly_multiplier * strength_multiplier * drawdown_multiplier * volatility_multiplier
        # 극단적인 배수 방지 (0.2 ~ 1.5 범위)
        combined_multiplier = float(np.clip(combined_multiplier, 0.2, 1.5))

        position_value = base_position_value * Decimal(str(combined_multiplier))

        # 7. 최대 포지션 제한 적용
        max_position_value = portfolio.available_capital * Decimal(str(self.max_position_size))
        position_value = min(position_value, max_position_value)

        # 8. 포트폴리오 노출 제한 확인
        current_exposure = portfolio.positions_value
        max_total_exposure = portfolio.total_capital * Decimal(str(self.max_portfolio_exposure))
        remaining_exposure = max_total_exposure - current_exposure

        if remaining_exposure < position_value:
            position_value = max(Decimal("0"), remaining_exposure)

        # 9. 수량 계산
        if entry_price > 0:
            volume = (position_value / entry_price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        else:
            volume = Decimal("0")

        # 10. 실제 리스크 계산
        if stop_loss > 0 and entry_price > 0 and volume > 0:
            risk_amount = abs(entry_price - stop_loss) * volume
            risk_percent = float(risk_amount / portfolio.total_capital)
        else:
            risk_amount = position_value * Decimal(str(self.max_risk_per_trade))
            risk_percent = self.max_risk_per_trade

        logger.info(
            f"포지션 크기 계산됨: {candidate.market} 수량={volume} 금액={position_value:.2f} "
            f"리스크={risk_percent:.2%} (켈리={kelly_multiplier:.2f}, 강도={strength_multiplier:.2f}, "
            f"드로다운={drawdown_multiplier:.2f}, 변동성={volatility_multiplier:.2f})"
        )

        return Decision(
            decision_id=uuid4(),
            market=candidate.market,
            direction=candidate.direction,
            volume=volume,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            contributing_signals=[s.strategy_id for s in candidate.contributing_signals],
            timestamp=datetime.now(tz=timezone.utc),
            status=DecisionStatus.PENDING,
        )

    def _calculate_base_position(self, entry_price: Decimal, stop_loss: Decimal, available_capital: Decimal) -> Decimal:
        """손절가 기반 기본 포지션 크기 계산."""
        if stop_loss > 0 and entry_price > 0:
            stop_distance = abs(entry_price - stop_loss)
            stop_percent = stop_distance / entry_price

            if stop_percent > 0:
                risk_amount = available_capital * Decimal(str(self.max_risk_per_trade))
                return risk_amount / stop_percent

        # 폴백: 최대 포지션 크기 사용
        return available_capital * Decimal(str(self.max_position_size))

    @staticmethod
    def _calculate_kelly_fraction(
        win_probability: float,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> float:
        """
        켈리 크라이테리온 기반 최적 베팅 비율 계산.

        Kelly % = W - [(1-W) / R]
        W = 승률 (combined_strength 사용)
        R = 리스크/리워드 비율

        보수적으로 Half-Kelly 또는 Quarter-Kelly 사용.
        """
        if entry_price <= 0 or stop_loss <= 0 or take_profit <= 0:
            return 1.0  # 정보 부족 시 기본값

        # 리스크/리워드 비율 계산
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)

        if risk == 0:
            return 1.0

        rr_ratio = float(reward / risk)

        # 켈리 공식
        # W = 승률, R = 평균 수익 / 평균 손실
        w = win_probability
        kelly = w - ((1 - w) / rr_ratio) if rr_ratio > 0 else 0

        # 음수 켈리 = 베팅하지 말라는 의미 -> 최소값 사용
        if kelly <= 0:
            return 0.25  # 최소 25%

        # Half-Kelly 적용 (더 보수적)
        half_kelly = kelly * 0.5

        # 범위 제한 (25% ~ 100%)
        return float(np.clip(half_kelly, 0.25, 1.0))

    @staticmethod
    def _calculate_strength_multiplier(strength: float) -> float:
        """
        신호 강도 기반 포지션 크기 배수 계산.

        강도가 높을수록 포지션 크기 증가.
        시그모이드 함수로 부드럽게 스케일링.
        """
        # 시그모이드 스케일링: 0.5 -> 0.7, 0.7 -> 0.9, 0.9 -> 1.1
        # 중심점을 0.6으로, 기울기 조정
        k = 8  # 기울기 파라미터
        x0 = 0.6  # 중심점

        sigmoid = 1 / (1 + np.exp(-k * (strength - x0)))

        # 0.5 ~ 1.2 범위로 매핑
        return 0.5 + sigmoid * 0.7

    @staticmethod
    def _calculate_drawdown_multiplier(current_drawdown: float) -> float:
        """
        드로다운 기반 포지션 축소 배수 계산.

        드로다운이 심할수록 포지션 크기 축소.
        """
        if current_drawdown <= 0:
            return 1.0

        # 드로다운 임계값
        mild_threshold = 0.05  # 5% 드로다운부터 축소 시작
        severe_threshold = 0.15  # 15% 드로다운에서 최소 배수

        if current_drawdown < mild_threshold:
            return 1.0
        elif current_drawdown >= severe_threshold:
            return 0.3  # 최소 30%

        # 선형 감소
        ratio = (current_drawdown - mild_threshold) / (severe_threshold - mild_threshold)
        return 1.0 - (ratio * 0.7)  # 1.0 -> 0.3

    @staticmethod
    def _calculate_volatility_multiplier(atr: Decimal, current_price: Decimal) -> float:
        """
        ATR 기반 변동성 조정 배수 계산.

        변동성이 높을수록 포지션 크기 축소.
        ATR %를 사용하여 정규화.
        """
        if current_price <= 0 or atr <= 0:
            return 1.0

        # ATR을 가격 대비 %로 변환
        atr_percent = float(atr / current_price)

        # 기준 ATR: 2% (일반적인 변동성)
        base_atr = 0.02

        if atr_percent <= base_atr:
            # 변동성 낮음 -> 배수 증가 (최대 1.2)
            return min(1.2, 1.0 + (base_atr - atr_percent) * 10)
        else:
            # 변동성 높음 -> 배수 감소 (최소 0.5)
            return max(0.5, 1.0 - (atr_percent - base_atr) * 5)
