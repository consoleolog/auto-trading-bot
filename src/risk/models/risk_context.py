from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskContext:
    """
    리스크 관련 컨텍스트의 불변 스냅샷.

    RiskEngine에서 모든 리스크 규칙을 평가할 때 사용됩니다.
    매번 의사결정 평가 직전에 새로 생성됩니다.

    Attributes:
        system_state (str): 시스템 상태 ("RUNNING", "PAUSED", "STOPPED").
        mode (str): 작동 모드 ("DRY_RUN", "PAPER", "LIVE").
        open_positions_count (int): 현재 열려 있는 포지션의 개수.
        total_position_value_krw (Decimal): 현재 보유한 모든 포지션의 가치 합계 (KRW).
        portfolio_value_krw (Decimal): 현재 총 포트폴리오 가치 (자산 총액, KRW).
        starting_capital_krw (Decimal): 초기 시작 자본금 (KRW).
        daily_pnl_krw (Decimal): 일일 손익 금액 (KRW).
        daily_pnl_percent (Decimal): 일일 손익률 (%).
        weekly_pnl_krw (Decimal): 주간 손익 금액 (KRW).
        weekly_pnl_percent (Decimal): 주간 손익률 (%).
        peak_portfolio_value_krw (Decimal): 포트폴리오의 역사적 최고점 가치 (KRW).
        current_drawdown_percent (Decimal): 현재 고점 대비 낙폭(Drawdown) 비율 (%).
        proposed_trade_size_krw (Optional[Decimal]): 제안된 신규 거래 규모 (KRW).
        proposed_trade_risk_percent (Optional[Decimal]): 제안된 신규 거래의 리스크 비중 (%).
    """

    # 시스템 상태
    system_state: str
    mode: str

    # 포지션 추적
    open_positions_count: int
    total_position_value_krw: Decimal

    # 포트폴리오 지표
    portfolio_value_krw: Decimal
    starting_capital_krw: Decimal

    # 손익(P&L) 추적
    daily_pnl_krw: Decimal
    daily_pnl_percent: Decimal
    weekly_pnl_krw: Decimal
    weekly_pnl_percent: Decimal

    # 드로다운(Drawdown) 추적
    peak_portfolio_value_krw: Decimal
    current_drawdown_percent: Decimal

    # 거래 관련 컨텍스트 (포지션 사이징용)
    proposed_trade_size_krw: Decimal | None = None
    proposed_trade_risk_percent: Decimal | None = None

    @property
    def total_pnl_percent(self) -> Decimal:
        """시작 시점 이후의 총 손익률을 계산합니다."""
        if self.starting_capital_krw == 0:
            return Decimal("0")
        return (self.portfolio_value_krw - self.starting_capital_krw) / self.starting_capital_krw * 100

    @property
    def position_utilization_percent(self) -> Decimal:
        """전체 포트폴리오 중 포지션이 차지하는 비중(%)을 계산합니다."""
        if self.portfolio_value_krw == 0:
            return Decimal("0")
        return self.total_position_value_krw / self.portfolio_value_krw * 100
