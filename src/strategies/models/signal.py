from dataclasses import dataclass
from datetime import datetime, timezone

from ...trading.exchanges.upbit.codes import Timeframe
from ..codes import MarketRegime


@dataclass
class Signal:
    """
    전략에서 발생한 신호

    Attributes:
        strategy_name: 전략 이름
        market: 페어 코드
        timeframe: 거래 중인 페어의 기간
        market_regime: 시장 국면
        metadata: 세부 데이터
    """

    strategy_name: str
    market: str
    timeframe: Timeframe | None
    market_regime: MarketRegime | None
    metadata: dict | None
    created_at: datetime | None
    updated_at: datetime | None

    def __post_init__(self):
        if isinstance(self.market_regime, MarketRegime):
            self.market_regime = MarketRegime(self.market_regime)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            strategy_name=data.get("strategy_name", ""),
            market=data.get("market", ""),
            timeframe=data.get("timeframe"),
            market_regime=data.get("market_regime"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now(tz=timezone.utc)),
            updated_at=data.get("updated_at", datetime.now(tz=timezone.utc)),
        )

    def to_dict(self):
        return {
            "strategy_name": self.strategy_name,
            "market": self.market,
            "timeframe": self.timeframe,
            "market_regime": self.market_regime,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
