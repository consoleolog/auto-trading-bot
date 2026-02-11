import logging
from decimal import Decimal

from src.portfolio.models import PortfolioState
from src.risk.models import RiskLimitsConfig
from src.strategies.models import Signal

from .confluence_checker import ConfluenceChecker
from .models import Decision
from .position_sizer import PositionSizer
from .signal_aggregator import SignalAggregator

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    결정 흐름을 조율하는 메인 결정 엔진입니다.

    흐름:
    1. 전략으로부터 신호 수집
    2. 신호 일치 확인
    3. 포지션 크기 산정
    4. 리스크 확인을 위한 결정 반환
    """

    def __init__(self, risk_config: RiskLimitsConfig, min_confluence: int = 2, min_confidence: float = 0.6):
        """
        결정 엔진을 초기화합니다.

        Args:
            risk_config: 리스크 제한 설정
            min_confluence: 신호 일치를 위한 최소 신호 개수
            min_confidence: 최소 신호 신뢰도
        """
        self.aggregator = SignalAggregator(min_confidence=min_confidence)
        self.confluence_checker = ConfluenceChecker(min_signals=min_confluence)
        self.position_sizer = PositionSizer(risk_config)

    def add_signal(self, signal: Signal) -> None:
        """전략으로부터 신호를 추가합니다."""
        self.aggregator.add_signal(signal)

    def process(self, portfolio: PortfolioState, current_prices: dict[str, Decimal]) -> list[Decision]:
        """
        수집된 모든 신호를 처리하고 결정을 생성합니다.

        Args:
            portfolio: 현재 포트폴리오 상태
            current_prices: 심볼별 현재 시장 가격

        Returns:
            거래 결정 목록
        """
        decisions = []

        # 각 심볼별로 처리
        for market, signals in self.aggregator.get_all_signals().items():
            # 이미 포지션이 있으면 건너뛰기
            if market in portfolio.positions:
                logger.debug(f"{market} 건너뛰기 - 이미 포지션 보유 중")
                continue

            # 신호 일치 확인
            candidate = self.confluence_checker.check(signals)
            if not candidate:
                continue

            # 현재 가격 가져오기
            price = current_prices.get(market, candidate.suggested_entry)
            if price <= 0:
                logger.warning(f"{market} 가격 없음, 건너뛰기")
                continue

            # 포지션 크기 산정
            decision = self.position_sizer.calculate(candidate, portfolio, price)

            if decision.volume > 0:
                decisions.append(decision)
            else:
                logger.warning(f"{market} 포지션 크기가 0, 건너뛰기")

        # 처리 후 신호 초기화
        self.aggregator.clear()

        logger.info(f"결정 엔진이 {len(decisions)}개의 결정 생성")
        return decisions

    def clear(self) -> None:
        """대기 중인 모든 신호를 초기화합니다."""
        self.aggregator.clear()
