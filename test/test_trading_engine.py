from datetime import datetime, timedelta

import pytest

from src.trading.core import TradingEngine
from src.trading.exchanges.upbit.codes import Timeframe


@pytest.fixture
def engine():
    """기본 TradingEngine 인스턴스를 생성한다."""
    return TradingEngine()


@pytest.fixture
def custom_engine():
    """커스텀 설정의 TradingEngine 인스턴스를 생성한다."""
    return TradingEngine(
        mode="production",
        markets=["USDT-BTC"],
        timeframes=[Timeframe.MINUTE_1],
    )


class TestInit:
    def test_default_mode_is_development(self, engine: TradingEngine):
        """기본 mode 는 development 이다."""
        assert engine.mode == "development"

    def test_custom_mode(self, custom_engine: TradingEngine):
        """사용자 지정 mode 가 올바르게 설정된다."""
        assert custom_engine.mode == "production"

    def test_is_running_initially_false(self, engine: TradingEngine):
        """초기 is_running 은 False 이다."""
        assert engine.is_running is False

    def test_verbose_signals_initially_true(self, engine: TradingEngine):
        """초기 verbose_signals 는 True 이다."""
        assert engine.verbose_signals is True

    def test_default_markets(self, engine: TradingEngine):
        """기본 마켓은 USDT-BTC, USDT-ETH 이다."""
        assert engine.markets == ["USDT-BTC", "USDT-ETH"]

    def test_custom_markets(self, custom_engine: TradingEngine):
        """사용자 지정 마켓이 올바르게 설정된다."""
        assert custom_engine.markets == ["USDT-BTC"]

    def test_default_timeframes(self, engine: TradingEngine):
        """기본 타임프레임은 HOUR, DAY 이다."""
        assert engine.timeframes == [Timeframe.HOUR, Timeframe.DAY]

    def test_custom_timeframes(self, custom_engine: TradingEngine):
        """사용자 지정 타임프레임이 올바르게 설정된다."""
        assert custom_engine.timeframes == [Timeframe.MINUTE_1]

    def test_cooldown_durations_has_all_timeframes(self, engine: TradingEngine):
        """cooldown_durations 에 모든 Timeframe 에 대한 timedelta 가 포함되어 있다."""
        expected_timeframes = [
            Timeframe.SECOND,
            Timeframe.MINUTE_1,
            Timeframe.MINUTE_3,
            Timeframe.MINUTE_5,
            Timeframe.MINUTE_10,
            Timeframe.MINUTE_15,
            Timeframe.HALF_HOUR,
            Timeframe.HOUR,
            Timeframe.HOUR_4,
            Timeframe.DAY,
            Timeframe.WEEK,
            Timeframe.MONTH,
            Timeframe.YEAR,
        ]
        for tf in expected_timeframes:
            assert tf in engine.cooldown_durations
            assert isinstance(engine.cooldown_durations[tf], timedelta)

    def test_cooldown_duration_values(self, engine: TradingEngine):
        """주요 cooldown_durations 값이 올바르다."""
        assert engine.cooldown_durations[Timeframe.SECOND] == timedelta(seconds=1)
        assert engine.cooldown_durations[Timeframe.MINUTE_1] == timedelta(minutes=1)
        assert engine.cooldown_durations[Timeframe.HOUR] == timedelta(hours=1)
        assert engine.cooldown_durations[Timeframe.DAY] == timedelta(days=1)
        assert engine.cooldown_durations[Timeframe.WEEK] == timedelta(weeks=1)

    def test_market_cooldowns_initially_empty(self, engine: TradingEngine):
        """market_cooldowns 는 초기에 비어 있다."""
        assert engine.market_cooldowns == {}


class TestTradingCycle:
    @pytest.mark.asyncio
    async def test_skips_market_during_cooldown(self, engine: TradingEngine, caplog):
        """쿨타임 중인 마켓은 건너뛴다."""
        key = f"{engine.markets[0]}:{engine.timeframes[0].value}"
        engine.market_cooldowns[key] = datetime.now() + timedelta(hours=1)

        with caplog.at_level("DEBUG"):
            await engine._trading_cycle()

        assert "Skipped - cooldown" in caplog.text

    @pytest.mark.asyncio
    async def test_does_not_skip_when_no_cooldown(self, engine: TradingEngine, caplog):
        """쿨타임이 설정되지 않은 마켓은 건너뛰지 않는다."""
        with caplog.at_level("DEBUG"):
            await engine._trading_cycle()

        assert "Skipped" not in caplog.text

    @pytest.mark.asyncio
    async def test_resets_cooldown_when_expired(self, engine: TradingEngine):
        """쿨타임이 만료된 마켓은 쿨타임을 재설정한다."""
        key = f"{engine.markets[0]}:{engine.timeframes[0].value}"
        engine.market_cooldowns[key] = datetime.now() - timedelta(seconds=1)

        await engine._trading_cycle()

        assert engine.market_cooldowns[key] > datetime.now()

    @pytest.mark.asyncio
    async def test_cooldown_skip_not_logged_when_verbose_off(self, engine: TradingEngine, caplog):
        """verbose_signals 가 False 일 때 쿨타임 스킵 로그가 출력되지 않는다."""
        engine.verbose_signals = False
        key = f"{engine.markets[0]}:{engine.timeframes[0].value}"
        engine.market_cooldowns[key] = datetime.now() + timedelta(hours=1)

        with caplog.at_level("DEBUG"):
            await engine._trading_cycle()

        assert "Skipped" not in caplog.text

    @pytest.mark.asyncio
    async def test_iterates_all_market_timeframe_combinations(self, engine: TradingEngine):
        """모든 마켓-타임프레임 조합을 순회한다."""
        for tf in engine.timeframes:
            for market in engine.markets:
                key = f"{market}:{tf.value}"
                # 쿨타임을 과거로 설정하여 모든 조합이 처리되도록 함
                engine.market_cooldowns[key] = datetime.now() - timedelta(seconds=1)

        await engine._trading_cycle()

        # 모든 조합의 쿨타임이 미래로 재설정되었는지 확인
        for tf in engine.timeframes:
            for market in engine.markets:
                key = f"{market}:{tf.value}"
                assert engine.market_cooldowns[key] > datetime.now()
