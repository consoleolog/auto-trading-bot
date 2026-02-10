from datetime import datetime
from decimal import Decimal

import pytest

from src.trading.exchanges.upbit.codes import Unit
from src.trading.exchanges.upbit.models import Candle


@pytest.fixture
def bullish_candle():
    """상승(양봉) 캔들을 생성한다."""
    return Candle(
        market="KRW-BTC",
        candle_date_time_utc=datetime(2025, 1, 1, 0, 0, 0),
        candle_date_time_kst=datetime(2025, 1, 1, 9, 0, 0),
        opening_price=Decimal("50000000"),
        high_price=Decimal("52000000"),
        low_price=Decimal("49000000"),
        trade_price=Decimal("51500000"),
        timestamp=1735689600000,
        candle_acc_trade_price=Decimal("1000000000"),
        candle_acc_trade_volume=Decimal("20.5"),
    )


@pytest.fixture
def bearish_candle():
    """하락(음봉) 캔들을 생성한다."""
    return Candle(
        market="KRW-BTC",
        candle_date_time_utc=datetime(2025, 1, 1, 0, 0, 0),
        candle_date_time_kst=datetime(2025, 1, 1, 9, 0, 0),
        opening_price=Decimal("51500000"),
        high_price=Decimal("52000000"),
        low_price=Decimal("49000000"),
        trade_price=Decimal("50000000"),
        timestamp=1735689600000,
        candle_acc_trade_price=Decimal("1000000000"),
        candle_acc_trade_volume=Decimal("20.5"),
    )


@pytest.fixture
def doji_candle():
    """시가와 종가가 동일한 도지(Doji) 캔들을 생성한다."""
    return Candle(
        market="KRW-BTC",
        candle_date_time_utc=datetime(2025, 1, 1, 0, 0, 0),
        candle_date_time_kst=datetime(2025, 1, 1, 9, 0, 0),
        opening_price=Decimal("50000000"),
        high_price=Decimal("50000000"),
        low_price=Decimal("50000000"),
        trade_price=Decimal("50000000"),
        timestamp=1735689600000,
        candle_acc_trade_price=Decimal("500000000"),
        candle_acc_trade_volume=Decimal("10.0"),
    )


@pytest.fixture
def api_response():
    """업비트 API 분봉 응답 데이터를 생성한다."""
    return {
        "market": "KRW-ETH",
        "candle_date_time_utc": datetime(2025, 6, 15, 12, 0, 0),
        "candle_date_time_kst": datetime(2025, 6, 15, 21, 0, 0),
        "opening_price": 5000000,
        "high_price": 5100000,
        "low_price": 4950000,
        "trade_price": 5050000,
        "timestamp": 1750000000000,
        "candle_acc_trade_price": 800000000,
        "candle_acc_trade_volume": 160.25,
        "unit": 15,
    }


@pytest.fixture
def daily_api_response(api_response):
    """업비트 API 일봉 응답 데이터를 생성한다."""
    response = {**api_response}
    response.pop("unit")
    response.update(
        {
            "prev_closing_price": 4980000,
            "change_price": 70000,
            "change_rate": 0.014,
            "converted_trade_price": 5050000,
        }
    )
    return response


# ============= __post_init__ =============


class TestPostInit:
    def test_converts_int_to_decimal(self):
        """int 값이 Decimal 로 변환된다."""
        candle = Candle(
            market="KRW-BTC",
            candle_date_time_utc=datetime(2025, 1, 1),
            candle_date_time_kst=datetime(2025, 1, 1),
            opening_price=50000,
            high_price=51000,
            low_price=49000,
            trade_price=50500,
            timestamp=1735689600000,
            candle_acc_trade_price=1000000,
            candle_acc_trade_volume=20,
        )

        assert isinstance(candle.opening_price, Decimal)
        assert isinstance(candle.high_price, Decimal)
        assert isinstance(candle.trade_price, Decimal)
        assert candle.opening_price == Decimal("50000")

    def test_converts_float_to_decimal(self):
        """float 값이 Decimal 로 변환된다."""
        candle = Candle(
            market="KRW-BTC",
            candle_date_time_utc=datetime(2025, 1, 1),
            candle_date_time_kst=datetime(2025, 1, 1),
            opening_price=50000.5,
            high_price=51000.0,
            low_price=49000.0,
            trade_price=50500.0,
            timestamp=1735689600000,
            candle_acc_trade_price=1000000.0,
            candle_acc_trade_volume=20.5,
        )

        assert isinstance(candle.opening_price, Decimal)
        assert candle.candle_acc_trade_volume == Decimal("20.5")

    def test_converts_str_to_decimal(self):
        """str 값이 Decimal 로 변환된다."""
        candle = Candle(
            market="KRW-BTC",
            candle_date_time_utc=datetime(2025, 1, 1),
            candle_date_time_kst=datetime(2025, 1, 1),
            opening_price="50000",
            high_price="51000",
            low_price="49000",
            trade_price="50500",
            timestamp=1735689600000,
            candle_acc_trade_price="1000000",
            candle_acc_trade_volume="20",
        )

        assert isinstance(candle.opening_price, Decimal)
        assert candle.opening_price == Decimal("50000")

    def test_keeps_decimal_as_is(self, bullish_candle):
        """이미 Decimal 인 값은 그대로 유지된다."""
        assert bullish_candle.opening_price == Decimal("50000000")
        assert isinstance(bullish_candle.opening_price, Decimal)

    def test_converts_optional_fields_with_defaults(self):
        """기본값이 있는 선택 필드도 Decimal 로 변환된다."""
        candle = Candle(
            market="KRW-BTC",
            candle_date_time_utc=datetime(2025, 1, 1),
            candle_date_time_kst=datetime(2025, 1, 1),
            opening_price=Decimal("50000"),
            high_price=Decimal("51000"),
            low_price=Decimal("49000"),
            trade_price=Decimal("50500"),
            timestamp=1735689600000,
            candle_acc_trade_price=Decimal("1000000"),
            candle_acc_trade_volume=Decimal("20"),
            prev_closing_price=49000,
            change_price=1500,
            change_rate=0.03,
        )

        assert isinstance(candle.prev_closing_price, Decimal)
        assert isinstance(candle.change_price, Decimal)
        assert isinstance(candle.change_rate, Decimal)


# ============= Properties =============


class TestBodySize:
    def test_bullish_body_size(self, bullish_candle):
        """양봉의 몸통 크기는 종가 - 시가 의 절대값이다."""
        assert bullish_candle.body_size == Decimal("1500000")

    def test_bearish_body_size(self, bearish_candle):
        """음봉의 몸통 크기는 시가 - 종가 의 절대값이다."""
        assert bearish_candle.body_size == Decimal("1500000")

    def test_doji_body_size_is_zero(self, doji_candle):
        """도지 캔들의 몸통 크기는 0 이다."""
        assert doji_candle.body_size == Decimal("0")


class TestRangeSize:
    def test_range_size(self, bullish_candle):
        """레인지 크기는 고가 - 저가 이다."""
        assert bullish_candle.range_size == Decimal("3000000")

    def test_doji_range_size_is_zero(self, doji_candle):
        """고가와 저가가 동일하면 레인지 크기는 0 이다."""
        assert doji_candle.range_size == Decimal("0")


class TestBodyRatio:
    def test_body_ratio(self, bullish_candle):
        """몸통 비율은 body_size / range_size 이다."""
        expected = 1500000 / 3000000  # 0.5
        assert bullish_candle.body_ratio == pytest.approx(expected)

    def test_doji_body_ratio_is_zero(self, doji_candle):
        """range_size 가 0 이면 body_ratio 는 0.0 이다."""
        assert doji_candle.body_ratio == 0.0


class TestBullishBearish:
    def test_bullish_candle(self, bullish_candle):
        """종가 > 시가 이면 양봉(bullish) 이다."""
        assert bullish_candle.is_bullish is True
        assert bullish_candle.is_bearish is False

    def test_bearish_candle(self, bearish_candle):
        """종가 < 시가 이면 음봉(bearish) 이다."""
        assert bearish_candle.is_bearish is True
        assert bearish_candle.is_bullish is False

    def test_doji_is_neither(self, doji_candle):
        """시가 == 종가 이면 양봉도 음봉도 아니다."""
        assert doji_candle.is_bullish is False
        assert doji_candle.is_bearish is False


# ============= Default Values =============


class TestDefaultValues:
    def test_unit_defaults_to_none(self, bullish_candle):
        """unit 기본값은 Unit.NONE 이다."""
        assert bullish_candle.unit == Unit.NONE

    def test_prev_closing_price_defaults_to_zero(self, bullish_candle):
        """prev_closing_price 기본값은 0.0 이다."""
        assert bullish_candle.prev_closing_price == Decimal("0.0")

    def test_first_day_of_period_defaults_to_none(self, bullish_candle):
        """first_day_of_period 기본값은 None 이다."""
        assert bullish_candle.first_day_of_period is None


# ============= from_response =============


class TestFromResponse:
    def test_creates_candle_from_minute_response(self, api_response):
        """분봉 API 응답으로 Candle 을 생성한다."""
        candle = Candle.from_response(api_response)

        assert candle.market == "KRW-ETH"
        assert candle.opening_price == Decimal("5000000")
        assert candle.high_price == Decimal("5100000")
        assert candle.low_price == Decimal("4950000")
        assert candle.trade_price == Decimal("5050000")
        assert candle.unit == Unit.MINUTE_15

    def test_creates_candle_from_daily_response(self, daily_api_response):
        """일봉 API 응답으로 Candle 을 생성한다."""
        candle = Candle.from_response(daily_api_response)

        assert candle.prev_closing_price == Decimal("4980000")
        assert candle.change_price == Decimal("70000")
        assert candle.change_rate == Decimal("0.014")
        assert candle.converted_trade_price == Decimal("5050000")

    def test_missing_optional_fields_use_defaults(self, api_response):
        """응답에 선택 필드가 없으면 기본값을 사용한다."""
        candle = Candle.from_response(api_response)

        assert candle.prev_closing_price == Decimal("0.0")
        assert candle.change_price == Decimal("0.0")
        assert candle.first_day_of_period is None

    def test_converts_numeric_response_to_decimal(self, api_response):
        """API 응답의 숫자 값이 Decimal 로 변환된다."""
        candle = Candle.from_response(api_response)

        assert isinstance(candle.opening_price, Decimal)
        assert isinstance(candle.candle_acc_trade_price, Decimal)
        assert isinstance(candle.candle_acc_trade_volume, Decimal)

    def test_preserves_datetime_fields(self, api_response):
        """datetime 필드가 그대로 유지된다."""
        candle = Candle.from_response(api_response)

        assert candle.candle_date_time_utc == datetime(2025, 6, 15, 12, 0, 0)
        assert candle.candle_date_time_kst == datetime(2025, 6, 15, 21, 0, 0)

    def test_unit_none_when_not_in_response(self, daily_api_response):
        """응답에 unit 이 없으면 Unit.NONE 으로 설정된다."""
        candle = Candle.from_response(daily_api_response)

        assert candle.unit == Unit.NONE

    def test_weekly_response_with_first_day_of_period(self, api_response):
        """주봉 응답의 first_day_of_period 가 설정된다."""
        api_response.pop("unit")
        api_response["first_day_of_period"] = datetime(2025, 6, 9)

        candle = Candle.from_response(api_response)

        assert candle.first_day_of_period == datetime(2025, 6, 9)
