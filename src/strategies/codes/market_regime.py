from enum import Enum


class MarketRegime(Enum):
    """시장 국면 분류.

    시장의 현재 상태를 분류하여 적절한 트레이딩 전략을 선택하는 데 사용됩니다.
    각 국면은 가격 움직임의 패턴과 방향성을 기반으로 판단됩니다.

    Attributes:
        STABLE_BULL: 안정적인 상승 추세
        END_OF_BULL: 상승 추세의 끝
        START_OF_BEAR: 하락 추세의 시작
        STABLE_BEAR: 안정적인 하락 추세
        END_OF_BEAR: 하락 추세의 끝
        START_OF_BULL: 상승 추세의 시작
        UNKNOWN: 시장 국면을 판단할 수 없거나 데이터가 불충분한 상태
    """

    STABLE_BULL = 1
    END_OF_BULL = 2
    START_OF_BEAR = 3
    STABLE_BEAR = 4
    END_OF_BEAR = 5
    START_OF_BULL = 6
    UNKNOWN = 0
