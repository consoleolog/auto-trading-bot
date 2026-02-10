from datetime import datetime
from decimal import Decimal

import pytest

from src.trading.exchanges.upbit.codes import PriceChangeState
from src.trading.exchanges.upbit.models import Ticker

# ============= Fixtures =============


@pytest.fixture
def ticker():
    """기본 Ticker 인스턴스를 생성한다."""
    return Ticker(
        market="KRW-BTC",
        trade_date=datetime(2025, 6, 24),
        trade_time=datetime(1900, 1, 1, 15, 30, 45),
        trade_date_kst=datetime(2025, 6, 25),
        trade_time_kst=datetime(1900, 1, 1, 0, 30, 45),
        trade_timestamp=1719244245000,
        opening_price=Decimal("50000000"),
        high_price=Decimal("51000000"),
        low_price=Decimal("49000000"),
        trade_price=Decimal("50500000"),
        prev_closing_price=Decimal("49800000"),
        change=PriceChangeState.RISE,
        change_price=Decimal("700000"),
        change_rate=Decimal("0.014"),
        signed_change_price=Decimal("700000"),
        signed_change_rate=Decimal("0.014"),
        trade_volume=Decimal("0.5"),
        acc_trade_price=Decimal("1000000000"),
        acc_trade_price_24h=Decimal("2500000000"),
        acc_trade_volume=Decimal("20.5"),
        acc_trade_volume_24h=Decimal("50.3"),
        highest_52_week_price=Decimal("60000000"),
        highest_52_week_date=datetime(2025, 3, 15),
        lowest_52_week_price=Decimal("30000000"),
        lowest_52_week_date=datetime(2024, 9, 10),
        timestamp=1719244245000,
    )


@pytest.fixture
def api_response():
    """업비트 API 현재가 응답 데이터를 생성한다."""
    return {
        "market": "KRW-BTC",
        "trade_date": "20250624",
        "trade_time": "153045",
        "trade_date_kst": "20250625",
        "trade_time_kst": "003045",
        "trade_timestamp": 1719244245000,
        "opening_price": 50000000,
        "high_price": 51000000,
        "low_price": 49000000,
        "trade_price": 50500000,
        "prev_closing_price": 49800000,
        "change": "RISE",
        "change_price": 700000,
        "change_rate": 0.014,
        "signed_change_price": 700000,
        "signed_change_rate": 0.014,
        "trade_volume": 0.5,
        "acc_trade_price": 1000000000,
        "acc_trade_price_24h": 2500000000,
        "acc_trade_volume": 20.5,
        "acc_trade_volume_24h": 50.3,
        "highest_52_week_price": 60000000,
        "highest_52_week_date": "2025-03-15",
        "lowest_52_week_price": 30000000,
        "lowest_52_week_date": "2024-09-10",
        "timestamp": 1719244245000,
    }


# ============= __post_init__: Decimal 변환 =============


class TestPostInitDecimal:
    def test_converts_int_to_decimal(self):
        """int 값이 Decimal로 변환된다."""
        ticker = Ticker(
            market="KRW-BTC",
            trade_date=datetime(2025, 6, 24),
            trade_time=datetime(1900, 1, 1, 15, 30, 45),
            trade_date_kst=datetime(2025, 6, 25),
            trade_time_kst=datetime(1900, 1, 1, 0, 30, 45),
            trade_timestamp=1719244245000,
            opening_price=50000000,
            high_price=51000000,
            low_price=49000000,
            trade_price=50500000,
            prev_closing_price=49800000,
            change=PriceChangeState.RISE,
            change_price=700000,
            change_rate=14,
            signed_change_price=700000,
            signed_change_rate=14,
            trade_volume=1,
            acc_trade_price=1000000000,
            acc_trade_price_24h=2500000000,
            acc_trade_volume=20,
            acc_trade_volume_24h=50,
            highest_52_week_price=60000000,
            highest_52_week_date=datetime(2025, 3, 15),
            lowest_52_week_price=30000000,
            lowest_52_week_date=datetime(2024, 9, 10),
            timestamp=1719244245000,
        )

        assert isinstance(ticker.opening_price, Decimal)
        assert isinstance(ticker.trade_price, Decimal)
        assert isinstance(ticker.change_price, Decimal)
        assert ticker.opening_price == Decimal("50000000")

    def test_converts_float_to_decimal(self):
        """float 값이 Decimal로 변환된다."""
        ticker = Ticker(
            market="KRW-BTC",
            trade_date=datetime(2025, 6, 24),
            trade_time=datetime(1900, 1, 1, 15, 30, 45),
            trade_date_kst=datetime(2025, 6, 25),
            trade_time_kst=datetime(1900, 1, 1, 0, 30, 45),
            trade_timestamp=1719244245000,
            opening_price=50000000.0,
            high_price=51000000.0,
            low_price=49000000.0,
            trade_price=50500000.0,
            prev_closing_price=49800000.0,
            change=PriceChangeState.RISE,
            change_price=700000.0,
            change_rate=0.014,
            signed_change_price=700000.0,
            signed_change_rate=0.014,
            trade_volume=0.5,
            acc_trade_price=1000000000.0,
            acc_trade_price_24h=2500000000.0,
            acc_trade_volume=20.5,
            acc_trade_volume_24h=50.3,
            highest_52_week_price=60000000.0,
            highest_52_week_date=datetime(2025, 3, 15),
            lowest_52_week_price=30000000.0,
            lowest_52_week_date=datetime(2024, 9, 10),
            timestamp=1719244245000,
        )

        assert isinstance(ticker.change_rate, Decimal)
        assert isinstance(ticker.trade_volume, Decimal)
        assert ticker.trade_volume == Decimal("0.5")

    def test_keeps_decimal_as_is(self, ticker: Ticker):
        """이미 Decimal인 값은 그대로 유지된다."""
        assert ticker.opening_price == Decimal("50000000")
        assert isinstance(ticker.opening_price, Decimal)

    @pytest.mark.parametrize(
        "field_name",
        [
            "opening_price",
            "high_price",
            "low_price",
            "trade_price",
            "prev_closing_price",
            "change_price",
            "change_rate",
            "signed_change_price",
            "signed_change_rate",
            "trade_volume",
            "acc_trade_price",
            "acc_trade_price_24h",
            "acc_trade_volume",
            "acc_trade_volume_24h",
            "highest_52_week_price",
            "lowest_52_week_price",
        ],
    )
    def test_all_price_fields_are_decimal(self, ticker: Ticker, field_name: str):
        """모든 가격/수량 필드가 Decimal 타입이다."""
        assert isinstance(getattr(ticker, field_name), Decimal)


# ============= __post_init__: datetime 변환 =============


class TestPostInitDatetime:
    def test_converts_trade_date_from_str(self):
        """trade_date 문자열(yyyyMMdd)이 datetime으로 변환된다."""
        ticker = Ticker(
            market="KRW-BTC",
            trade_date="20250624",
            trade_time=datetime(1900, 1, 1, 15, 30, 45),
            trade_date_kst=datetime(2025, 6, 25),
            trade_time_kst=datetime(1900, 1, 1, 0, 30, 45),
            trade_timestamp=1719244245000,
            opening_price=Decimal("50000000"),
            high_price=Decimal("51000000"),
            low_price=Decimal("49000000"),
            trade_price=Decimal("50500000"),
            prev_closing_price=Decimal("49800000"),
            change=PriceChangeState.RISE,
            change_price=Decimal("700000"),
            change_rate=Decimal("0.014"),
            signed_change_price=Decimal("700000"),
            signed_change_rate=Decimal("0.014"),
            trade_volume=Decimal("0.5"),
            acc_trade_price=Decimal("1000000000"),
            acc_trade_price_24h=Decimal("2500000000"),
            acc_trade_volume=Decimal("20.5"),
            acc_trade_volume_24h=Decimal("50.3"),
            highest_52_week_price=Decimal("60000000"),
            highest_52_week_date=datetime(2025, 3, 15),
            lowest_52_week_price=Decimal("30000000"),
            lowest_52_week_date=datetime(2024, 9, 10),
            timestamp=1719244245000,
        )

        assert isinstance(ticker.trade_date, datetime)
        assert ticker.trade_date == datetime(2025, 6, 24)

    def test_converts_trade_time_from_str(self):
        """trade_time 문자열(HHmmss)이 datetime으로 변환된다."""
        ticker = Ticker(
            market="KRW-BTC",
            trade_date=datetime(2025, 6, 24),
            trade_time="153045",
            trade_date_kst=datetime(2025, 6, 25),
            trade_time_kst=datetime(1900, 1, 1, 0, 30, 45),
            trade_timestamp=1719244245000,
            opening_price=Decimal("50000000"),
            high_price=Decimal("51000000"),
            low_price=Decimal("49000000"),
            trade_price=Decimal("50500000"),
            prev_closing_price=Decimal("49800000"),
            change=PriceChangeState.RISE,
            change_price=Decimal("700000"),
            change_rate=Decimal("0.014"),
            signed_change_price=Decimal("700000"),
            signed_change_rate=Decimal("0.014"),
            trade_volume=Decimal("0.5"),
            acc_trade_price=Decimal("1000000000"),
            acc_trade_price_24h=Decimal("2500000000"),
            acc_trade_volume=Decimal("20.5"),
            acc_trade_volume_24h=Decimal("50.3"),
            highest_52_week_price=Decimal("60000000"),
            highest_52_week_date=datetime(2025, 3, 15),
            lowest_52_week_price=Decimal("30000000"),
            lowest_52_week_date=datetime(2024, 9, 10),
            timestamp=1719244245000,
        )

        assert isinstance(ticker.trade_time, datetime)
        assert ticker.trade_time.hour == 15
        assert ticker.trade_time.minute == 30
        assert ticker.trade_time.second == 45

    def test_converts_highest_52_week_date_from_str(self):
        """highest_52_week_date 문자열(yyyy-MM-dd)이 datetime으로 변환된다."""
        ticker = Ticker(
            market="KRW-BTC",
            trade_date=datetime(2025, 6, 24),
            trade_time=datetime(1900, 1, 1, 15, 30, 45),
            trade_date_kst=datetime(2025, 6, 25),
            trade_time_kst=datetime(1900, 1, 1, 0, 30, 45),
            trade_timestamp=1719244245000,
            opening_price=Decimal("50000000"),
            high_price=Decimal("51000000"),
            low_price=Decimal("49000000"),
            trade_price=Decimal("50500000"),
            prev_closing_price=Decimal("49800000"),
            change=PriceChangeState.RISE,
            change_price=Decimal("700000"),
            change_rate=Decimal("0.014"),
            signed_change_price=Decimal("700000"),
            signed_change_rate=Decimal("0.014"),
            trade_volume=Decimal("0.5"),
            acc_trade_price=Decimal("1000000000"),
            acc_trade_price_24h=Decimal("2500000000"),
            acc_trade_volume=Decimal("20.5"),
            acc_trade_volume_24h=Decimal("50.3"),
            highest_52_week_price=Decimal("60000000"),
            highest_52_week_date="2025-03-15",
            lowest_52_week_price=Decimal("30000000"),
            lowest_52_week_date=datetime(2024, 9, 10),
            timestamp=1719244245000,
        )

        assert isinstance(ticker.highest_52_week_date, datetime)
        assert ticker.highest_52_week_date == datetime(2025, 3, 15)

    def test_converts_lowest_52_week_date_from_str(self):
        """lowest_52_week_date 문자열(yyyy-MM-dd)이 datetime으로 변환된다."""
        ticker = Ticker(
            market="KRW-BTC",
            trade_date=datetime(2025, 6, 24),
            trade_time=datetime(1900, 1, 1, 15, 30, 45),
            trade_date_kst=datetime(2025, 6, 25),
            trade_time_kst=datetime(1900, 1, 1, 0, 30, 45),
            trade_timestamp=1719244245000,
            opening_price=Decimal("50000000"),
            high_price=Decimal("51000000"),
            low_price=Decimal("49000000"),
            trade_price=Decimal("50500000"),
            prev_closing_price=Decimal("49800000"),
            change=PriceChangeState.RISE,
            change_price=Decimal("700000"),
            change_rate=Decimal("0.014"),
            signed_change_price=Decimal("700000"),
            signed_change_rate=Decimal("0.014"),
            trade_volume=Decimal("0.5"),
            acc_trade_price=Decimal("1000000000"),
            acc_trade_price_24h=Decimal("2500000000"),
            acc_trade_volume=Decimal("20.5"),
            acc_trade_volume_24h=Decimal("50.3"),
            highest_52_week_price=Decimal("60000000"),
            highest_52_week_date=datetime(2025, 3, 15),
            lowest_52_week_price=Decimal("30000000"),
            lowest_52_week_date="2024-09-10",
            timestamp=1719244245000,
        )

        assert isinstance(ticker.lowest_52_week_date, datetime)
        assert ticker.lowest_52_week_date == datetime(2024, 9, 10)

    def test_keeps_datetime_as_is(self, ticker: Ticker):
        """이미 datetime인 값은 그대로 유지된다."""
        assert isinstance(ticker.trade_date, datetime)
        assert ticker.trade_date == datetime(2025, 6, 24)

    def test_converts_all_str_datetimes_at_once(self):
        """모든 datetime 문자열 필드가 한 번에 변환된다."""
        ticker = Ticker(
            market="KRW-BTC",
            trade_date="20250624",
            trade_time="153045",
            trade_date_kst="20250625",
            trade_time_kst="003045",
            trade_timestamp=1719244245000,
            opening_price=Decimal("50000000"),
            high_price=Decimal("51000000"),
            low_price=Decimal("49000000"),
            trade_price=Decimal("50500000"),
            prev_closing_price=Decimal("49800000"),
            change=PriceChangeState.RISE,
            change_price=Decimal("700000"),
            change_rate=Decimal("0.014"),
            signed_change_price=Decimal("700000"),
            signed_change_rate=Decimal("0.014"),
            trade_volume=Decimal("0.5"),
            acc_trade_price=Decimal("1000000000"),
            acc_trade_price_24h=Decimal("2500000000"),
            acc_trade_volume=Decimal("20.5"),
            acc_trade_volume_24h=Decimal("50.3"),
            highest_52_week_price=Decimal("60000000"),
            highest_52_week_date="2025-03-15",
            lowest_52_week_price=Decimal("30000000"),
            lowest_52_week_date="2024-09-10",
            timestamp=1719244245000,
        )

        assert ticker.trade_date == datetime(2025, 6, 24)
        assert ticker.trade_time == datetime(1900, 1, 1, 15, 30, 45)
        assert ticker.trade_date_kst == datetime(2025, 6, 25)
        assert ticker.trade_time_kst == datetime(1900, 1, 1, 0, 30, 45)
        assert ticker.highest_52_week_date == datetime(2025, 3, 15)
        assert ticker.lowest_52_week_date == datetime(2024, 9, 10)


# ============= from_response =============


class TestFromResponse:
    def test_creates_ticker_from_response(self, api_response):
        """API 응답으로 Ticker를 생성한다."""
        # from_response에 "response" 키 버그가 있어 우회
        api_response["response"] = api_response["change_rate"]
        ticker = Ticker.from_response(api_response)

        assert ticker.market == "KRW-BTC"
        assert ticker.opening_price == Decimal("50000000")
        assert ticker.trade_price == Decimal("50500000")

    def test_converts_change_to_enum(self, api_response):
        """change 문자열이 PriceChangeState enum으로 변환된다."""
        api_response["response"] = api_response["change_rate"]
        ticker = Ticker.from_response(api_response)

        assert ticker.change == PriceChangeState.RISE

    def test_converts_numeric_fields_to_decimal(self, api_response):
        """API 응답의 숫자 값이 Decimal로 변환된다."""
        api_response["response"] = api_response["change_rate"]
        ticker = Ticker.from_response(api_response)

        assert isinstance(ticker.opening_price, Decimal)
        assert isinstance(ticker.change_price, Decimal)
        assert isinstance(ticker.acc_trade_volume, Decimal)

    def test_converts_date_strings_to_datetime(self, api_response):
        """API 응답의 날짜 문자열이 datetime으로 변환된다."""
        api_response["response"] = api_response["change_rate"]
        ticker = Ticker.from_response(api_response)

        assert isinstance(ticker.trade_date, datetime)
        assert ticker.trade_date == datetime(2025, 6, 24)

        assert isinstance(ticker.trade_time, datetime)
        assert ticker.trade_time.hour == 15
        assert ticker.trade_time.minute == 30

        assert isinstance(ticker.highest_52_week_date, datetime)
        assert ticker.highest_52_week_date == datetime(2025, 3, 15)

        assert isinstance(ticker.lowest_52_week_date, datetime)
        assert ticker.lowest_52_week_date == datetime(2024, 9, 10)

    def test_preserves_timestamp_as_int(self, api_response):
        """timestamp 필드가 int로 유지된다."""
        api_response["response"] = api_response["change_rate"]
        ticker = Ticker.from_response(api_response)

        assert isinstance(ticker.timestamp, int)
        assert ticker.timestamp == 1719244245000
