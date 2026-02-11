from dataclasses import dataclass


@dataclass
class RiskLimitsConfig:
    """리스크 제한 설정.

    포트폴리오의 리스크를 관리하기 위한 제한값들을 정의하는 클래스입니다.
    드로다운, 손실 한도, 포지션 크기 등의 제한을 설정합니다.

    Attributes:
        max_drawdown: 최대 허용 드로다운 (0.0 ~ 1.0, 기본값: 0.20 = 20%)
        daily_loss_limit: 일일 최대 손실 한도 (0.0 ~ 1.0, 기본값: 0.05 = 5%)
        weekly_loss_limit: 주간 최대 손실 한도 (0.0 ~ 1.0, 기본값: 0.10 = 10%)
        max_position_size: 단일 포지션 최대 크기 (총 자본 대비, 기본값: 0.40 = 40%)
        max_risk_per_trade: 거래당 최대 리스크 (총 자본 대비, 기본값: 0.02 = 2%)
        max_positions: 동시에 보유 가능한 최대 포지션 개수 (기본값: 5개)
        max_portfolio_exposure: 최대 포트폴리오 노출도 (총 자본 대비, 기본값: 0.40 = 40%)
    """

    max_drawdown: float = 0.20
    daily_loss_limit: float = 0.05
    weekly_loss_limit: float = 0.10
    max_position_size: float = 0.40
    max_risk_per_trade: float = 0.02
    max_positions: int = 5
    max_portfolio_exposure: float = 0.40
