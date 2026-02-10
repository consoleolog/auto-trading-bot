import logging
from datetime import datetime, timedelta

from src.trading.exchanges.upbit.codes import Timeframe

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(
        self,
        mode: str = "development",
        markets: list[str] | None = None,
        timeframes: list[Timeframe] | None = None,
    ):
        self.mode = mode

        self.is_running = False
        self.verbose_signals = True

        # Trading Infos
        self.markets: list[str] = markets or ["USDT-BTC", "USDT-ETH"]
        self.timeframes: list[Timeframe] = timeframes or [Timeframe.HOUR, Timeframe.DAY]

        # Cooldowns (market:timeframe -> next_trade_time)
        self.market_cooldowns: dict[str, datetime] = {}
        self.cooldown_durations = {
            Timeframe.SECOND: timedelta(seconds=1),
            Timeframe.MINUTE_1: timedelta(minutes=1),
            Timeframe.MINUTE_3: timedelta(minutes=3),
            Timeframe.MINUTE_5: timedelta(minutes=5),
            Timeframe.MINUTE_10: timedelta(minutes=10),
            Timeframe.MINUTE_15: timedelta(minutes=15),
            Timeframe.HALF_HOUR: timedelta(minutes=30),
            Timeframe.HOUR: timedelta(hours=1),
            Timeframe.HOUR_4: timedelta(hours=4),
            Timeframe.DAY: timedelta(days=1),
            Timeframe.WEEK: timedelta(weeks=1),
            Timeframe.MONTH: timedelta(weeks=4),
            Timeframe.YEAR: timedelta(days=365),
        }

    async def _trading_cycle(self):
        for timeframe in self.timeframes:
            for market in self.markets:
                key = f"{market}:{timeframe.value}"

                try:
                    # 1. Check cooldown if include in `self.market_cooldowns`
                    if key in self.market_cooldowns:
                        # 쿨타임 중이면 다음 마켓으로 넘김
                        if datetime.now() < self.market_cooldowns[key]:
                            remaining = (self.market_cooldowns[key] - datetime.now()).seconds
                            if self.verbose_signals:
                                logger.debug(f"  {key}: Skipped - cooldown ({remaining}s remaining)")
                            continue
                        else:
                            self.market_cooldowns[key] = datetime.now() + self.cooldown_durations[timeframe]
                    else:
                        self.market_cooldowns[key] = datetime.now() + self.cooldown_durations[timeframe]
                except Exception as e:
                    logger.error(f"Error in trading cycle: {e}")
