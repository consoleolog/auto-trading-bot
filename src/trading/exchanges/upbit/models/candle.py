from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from ..codes import Unit


@dataclass
class Candle:
    """
    캔들(봉) 데이터 모델.

    Attributes:
        market (str): 페어의 코드
        candle_date_time_utc (datetime): 캔들 구간의 시작 시각 (UTC 기준) [형식] yyyy-MM-dd'T'HH:mm:ss
        candle_date_time_kst (datetime): 캔들 구간의 시작 시각 (KST 기준) [형식] yyyy-MM-dd'T'HH:mm:ss
        opening_price (Decimal): 시가. 해당 캔들의 첫 거래 가격입니다.
        high_price (Decimal): 고가. 해당 캔들의 최고 거래 가격입니다.
        low_price (Decimal): 저가. 해당 캔들의 최저 거래 가격입니다.
        trade_price (Decimal): 종가. 해당 페어의 현재 가격입니다.
        candle_acc_trade_price (Decimal): 해당 캔들 동안의 누적 거래 금액
        candle_acc_trade_volume (Decimal): 해당 캔들 동안의 누적 거래된 디지털 자산의 수량
        unit (int): 캔들 집계 시간 단위 (분)
        prev_closing_price (Decimal): 전일 종가 (UTC 0시 기준)
        change_price (Decimal): 전일 종가 대비 가격 변화.
                                "trade_price" - "prev_closing_price"로 계산되며,
                                현재 종가가 전일 종가보다 얼마나 상승 또는 하락했는지를 나타냅니다.

                                양수(+): 현재 종가가 전일 종가보다 상승한 경우
                                음수(-): 현재 종가가 전일 종가보다 하락한 경우
                                0: 전일 종가와 동일하여 가격 변화가 없는 경우
        change_rate (Decimal): 전일 종가 대비 가격 변화율.
                                ("trade_price" - "prev_closing_price") ÷ "prev_closing_price" 으로 계산됩니다.

                                양수(+): 가격 상승
                                음수(-): 가격 하락
                                0: 전일 종가와 동일하여 가격 변화가 없는 경우
                                [예시] 0.015 = 1.5% 상승
        converted_trade_price (Decimal): 종가 환산 가격.
                                            converted_trade_price 에 요청된 통화 기준으로 환산된 종가입니다.

                                            요청에 converted_trade_price 미포함시, 이 필드는 제공되지 않습니다.
                                            현재는 원화(KRW)로의 변환만 지원합니다.
        timestamp (int): 해당 캔들의 마지막 틱이 저장된 시각의 타임스탬프 (ms)
    """

    market: str

    # 캔들 시간 정보
    candle_date_time_utc: datetime
    candle_date_time_kst: datetime

    # OHLC
    opening_price: Decimal
    high_price: Decimal
    low_price: Decimal
    trade_price: Decimal

    timestamp: int

    # 거래량/거래 대금
    candle_acc_trade_price: Decimal
    candle_acc_trade_volume: Decimal

    # 분 봉일 때(MINUTE)
    unit: Unit | None

    # 일 봉일 때(DAY)
    prev_closing_price: Decimal
    change_price: Decimal
    change_rate: Decimal
    converted_trade_price: Decimal

    # 주, 월, 년 봉일 때 (WEEK, MONTH, YEAR)
    first_day_of_period: datetime

    def __post_init__(self):
        for field_name in [
            "opening_price",
            "high_price",
            "low_price",
            "trade_price",
            "candle_acc_trade_price",
            "candle_acc_trade_volume",
            "prev_closing_price",
            "change_price",
            "change_rate",
            "converted_trade_price",
        ]:
            value = getattr(self, field_name)
            if isinstance(value, (int, float, str)):
                setattr(self, field_name, Decimal(str(value)))

        if isinstance(self.unit, int):
            self.unit = Unit(self.unit)

    @property
    def body_size(self) -> Decimal:
        return abs(self.trade_price - self.opening_price)

    @property
    def range_size(self) -> Decimal:
        return self.high_price - self.low_price

    @property
    def body_ratio(self) -> float:
        if self.range_size == 0:
            return 0.0
        return float(self.body_size / self.range_size)

    @property
    def is_bullish(self) -> bool:
        return self.trade_price > self.opening_price

    @property
    def is_bearish(self) -> bool:
        return self.trade_price < self.opening_price

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            market=data.get("market", ""),
            candle_date_time_utc=data.get("candle_date_time_utc", datetime.now(timezone.utc)),
            candle_date_time_kst=data.get("candle_date_time_kst", datetime.now(timezone.utc) + timedelta(hours=9)),
            opening_price=data.get("opening_price", Decimal("0.0")),
            high_price=data.get("high_price", Decimal("0.0")),
            low_price=data.get("low_price", Decimal("0.0")),
            trade_price=data.get("trade_price", Decimal("0.0")),
            timestamp=data.get("timestamp", 0),
            candle_acc_trade_price=data.get("candle_acc_trade_price", Decimal("0.0")),
            candle_acc_trade_volume=data.get("candle_acc_trade_volume", Decimal("0.0")),
            unit=data.get("unit"),
            prev_closing_price=data.get("prev_closing_price", Decimal("0.0")),
            change_price=data.get("change_price", Decimal("0.0")),
            change_rate=data.get("change_rate", Decimal("0.0")),
            converted_trade_price=data.get("converted_trade_price", Decimal("0.0")),
            first_day_of_period=data.get("first_day_of_period", datetime.now(timezone.utc)),
        )

    def to_dict(self) -> dict:
        return {
            "market": self.market,
            "candle_date_time_utc": self.candle_date_time_utc,
            "candle_date_time_kst": self.candle_date_time_kst,
            "opening_price": self.opening_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "trade_price": self.trade_price,
            "timestamp": self.timestamp,
            "candle_acc_trade_price": self.candle_acc_trade_price,
            "candle_acc_trade_volume": self.candle_acc_trade_volume,
            "unit": self.unit,
            "prev_closing_price": self.prev_closing_price,
            "change_price": self.change_price,
            "change_rate": self.change_rate,
            "converted_trade_price": self.converted_trade_price,
            "first_day_of_period": self.first_day_of_period,
        }
