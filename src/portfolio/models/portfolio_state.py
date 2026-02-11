from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from .position import Position


@dataclass
class PortfolioState:
    """현재 포트폴리오 상태.

    전체 자본, 보유 포지션, 손익 등 포트폴리오의 전반적인 상태를 관리하는 클래스입니다.
    리스크 관리와 포지션 사이징을 위한 핵심 정보를 제공합니다.

    Attributes:
        total_capital: 총 자본 (보유 현금 + 포지션 가치)
        available_capital: 거래 가능한 여유 자본
        positions: 심볼을 키로 하는 보유 포지션 딕셔너리
        daily_pnl: 일일 실현 손익
        weekly_pnl: 주간 실현 손익
        total_pnl: 누적 총 실현 손익
        high_water_mark: 역대 최고 자본 금액 (드로다운 계산용)
        trade_count_today: 오늘 실행한 거래 횟수
        last_updated: 마지막 업데이트 시각 (UTC)
    """

    total_capital: Decimal
    available_capital: Decimal
    positions: dict[str, Position]
    daily_pnl: Decimal = Decimal("0")
    weekly_pnl: Decimal = Decimal("0")
    total_pnl: Decimal = Decimal("0")
    high_water_mark: Decimal = Decimal("100")
    trade_count_today: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @property
    def current_drawdown(self) -> float:
        """최고점 대비 현재 드로다운.

        Returns:
            최고 자본 대비 현재 자본의 하락 비율 (0.0 ~ 1.0)
        """
        if self.high_water_mark == 0:
            return 0.0
        return float((self.high_water_mark - self.total_capital) / self.high_water_mark)

    @property
    def positions_value(self) -> int:
        """모든 포지션의 총 가치.

        Returns:
            현재 보유 중인 모든 포지션의 총 가치 합계
        """
        return sum(pos.value for pos in self.positions.values())

    @property
    def num_positions(self) -> int:
        """보유 포지션 개수.

        Returns:
            현재 열려있는 포지션의 개수
        """
        return len(self.positions)

    @property
    def portfolio_exposure(self) -> float:
        """포트폴리오 노출도.

        Returns:
            총 자본 대비 포지션 가치의 비율 (백분율)
        """
        if self.total_capital == 0:
            return 0.0
        return float(self.positions_value / self.total_capital)
