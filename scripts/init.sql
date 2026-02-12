-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "timescaledb";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

CREATE SCHEMA IF NOT EXISTS trading;

-- =====================================================
-- TRADING SCHEMA TABLES
-- =====================================================

-- Trades
CREATE TABLE IF NOT EXISTS trading.trades
(
    id             UUID PRIMARY KEY     DEFAULT gen_random_uuid(),               -- 기본키
    market         TEXT        NOT NULL,                                         -- 페어의 코드
    timeframe      TEXT        NOT NULL,                                         -- 거래 중인 페어의 기간
    side           TEXT        NOT NULL DEFAULT 'bid',                           -- 매수/매도 여부
    status         TEXT        NOT NULL DEFAULT 'open',                          -- 현재 거래 상태
    bid_order_uuid TEXT        NOT NULL,                                         -- 매수 주문 uuid
    bid_price      NUMERIC     NOT NULL,                                         -- 매수 평단가
    bid_volume     NUMERIC     NOT NULL,                                         -- 매수 수량
    bid_amount     NUMERIC GENERATED ALWAYS AS (bid_price * bid_volume) STORED,  -- 총 매수금액 (자동계산)
    bid_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),                           -- 매수 체결 시간
    ask_order_uuid TEXT,                                                         -- 매도 주문 uuid
    ask_price      NUMERIC,                                                      -- 매도 평단가
    ask_volume     NUMERIC,                                                      -- 매도 수량
    ask_amount     NUMERIC GENERATED ALWAYS AS ( ask_price * ask_volume) STORED, -- 총 매도금액
    ask_at         TIMESTAMPTZ,                                                  -- 매도 체결 시간
    pnl_krw        NUMERIC,                                                      -- KRW 로 환산한 손익
    pnl_pct        NUMERIC,                                                      -- 손익 퍼센트(%)
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),                           -- 생성 시간
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()                            -- 업데이트 시간
);

-- Strategies
CREATE TABLE IF NOT EXISTS trading.strategy_signals
(
    market        TEXT        NOT NULL,               -- 페어의 코드
    timeframe     TEXT        NOT NULL,               -- 거래 중인 페어의 기간
    strategy_name TEXT        NOT NULL,               -- 전략명
    status        TEXT        NOT NULL,               -- 전략 상태
    metadata      JSONB       NOT NULL,               -- 세부 시그널 데이터
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- 생성 시간
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- 업데이트 시간
    CONSTRAINT strategy_signals_pk PRIMARY KEY (market, timeframe, strategy_name)
);

-- Candles
CREATE TABLE IF NOT EXISTS trading.candles
(
    time                    TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- 시간
    timeframe               TEXT        NOT NULL,               -- 캔들 조회 기간
    market                  TEXT        NOT NULL,               -- 페어의 코드
    candle_date_time_utc    TIMESTAMPTZ NOT NULL,               -- 캔들 구간의 시작 시각 (UTC 기준) [형식] yyyy-MM-dd'T'HH:mm:ss
    candle_date_time_kst    TIMESTAMPTZ NOT NULL,               -- 캔들 구간의 시작 시각 (KST 기준) [형식] yyyy-MM-dd'T'HH:mm:ss
    opening_price           NUMERIC     NOT NULL,               -- 시가. 해당 캔들의 첫 거래 가격입니다.
    high_price              NUMERIC     NOT NULL,               -- 고가. 해당 캔들의 최고 거래 가격입니다.
    low_price               NUMERIC     NOT NULL,               -- 저가. 해당 캔들의 최저 거래 가격입니다.
    trade_price             NUMERIC     NOT NULL,               -- 종가. 해당 페어의 현재 가격입니다.
    timestamp               BIGINT      NOT NULL,               -- 해당 캔들의 마지막 틱이 저장된 시각의 타임스탬프 (ms)
    candle_acc_trade_price  NUMERIC     NOT NULL,               -- 해당 캔들 동안의 누적 거래 금액
    candle_acc_trade_volume NUMERIC     NOT NULL,               -- 해당 캔들 동안의 누적 거래된 디지털 자산의 수량
    unit                    INTEGER,                            -- 캔들 집계 시간 단위 (분)
    prev_closing_price      NUMERIC,                            -- 전일 종가 (UTC 0시 기준)
    change_price            NUMERIC,                            -- 전일 종가 대비 가격 변화.
    change_rate             NUMERIC,                            -- 전일 종가 대비 가격 변화율.
    converted_trade_price   NUMERIC,                            -- 종가 환산 가격.
    CONSTRAINT candles_pk PRIMARY KEY (time, timeframe, market)
);

-- Convert to hypertable
SELECT create_hypertable('trading.candles', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_candles_time ON trading.candles (market, time DESC);

-- Tickers
CREATE TABLE IF NOT EXISTS trading.tickers
(
    time                  TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- 시간
    market                TEXT        NOT NULL,               -- 페어(거래쌍)의 코드
    trade_date            TIMESTAMPTZ NOT NULL,               -- 최근 체결 일자 (UTC 기준) [형식] yyyyMMdd
    trade_time            TIMESTAMPTZ NOT NULL,               -- 최근 체결 시각 (UTC 기준) [형식] HHmmss
    trade_date_kst        TIMESTAMPTZ NOT NULL,               -- 최근 체결 일자 (KST 기준) [형식] yyyyMMdd
    trade_time_kst        TIMESTAMPTZ NOT NULL,               -- 최근 체결 시각 (KST 기준) [형식] HHmmss
    trade_timestamp       BIGINT,                             -- 체결 시각의 밀리초단위 타임스탬프
    opening_price         NUMERIC     NOT NULL,               -- 시가. 해당 캔들의 첫 거래 가격입니다.
    high_price            NUMERIC     NOT NULL,               -- 고가. 해당 캔들의 최고 거래 가격입니다.
    low_price             NUMERIC     NOT NULL,               -- 저가. 해당 캔들의 최저 거래 가격입니다.
    trade_price           NUMERIC     NOT NULL,               -- 종가. 해당 페어의 현재 가격입니다.
    prev_closing_price    NUMERIC     NOT NULL,               -- 전일 종가 (UTC 0시 기준)
    change                TEXT        NOT NULL,               -- 가격 변동 상태
    change_price          NUMERIC     NOT NULL,               -- 전일 종가 대비 가격 변화(절대값)
    change_rate           NUMERIC     NOT NULL,               -- 전일 종가 대비 가격 변화 (절대값)
    signed_change_price   NUMERIC     NOT NULL,               -- 전일 종가 대비 가격 변화.
    signed_change_rate    NUMERIC     NOT NULL,               -- 전일 종가 대비 가격 변화율
    trade_volume          NUMERIC     NOT NULL,               -- 최근 거래 수량
    acc_trade_price       NUMERIC     NOT NULL,               -- 누적 거래 금액 (UTC 0시 기준)
    acc_trade_price_24h   NUMERIC     NOT NULL,               -- 24시간 누적 거래 금액
    acc_trade_volume      NUMERIC     NOT NULL,               -- 누적 거래량 (UTC 0시 기준)
    acc_trade_volume_24h  NUMERIC     NOT NULL,               -- 24시간 누적 거래량
    highest_52_week_price NUMERIC     NOT NULL,               -- 52주 신고가
    highest_52_week_date  TIMESTAMPTZ NOT NULL,               -- 52주 신고가 달성일 [형식] yyyy-MM-dd
    lowest_52_week_price  NUMERIC     NOT NULL,               -- 52주 신저가
    lowest_52_week_date   TIMESTAMPTZ NOT NULL,               -- 52주 신저가 달성일 [형식] yyyy-MM-dd
    timestamp             BIGINT      NOT NULL,               -- 현재가 정보가 반영된 시각의 타임스탬프(ms)
    CONSTRAINT tickers_pk PRIMARY KEY (time)
);

-- Convert to hypertable
SELECT create_hypertable('trading.tickers', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_tickers_time ON trading.candles (market, time DESC);

-- Orders
CREATE TABLE IF NOT EXISTS trading.orders
(
    market           TEXT,             -- 페어 코드
    uuid             UUID PRIMARY KEY, -- 주문의 유일 식별자
    side             TEXT,             -- 주문 방향(매수/매도)
    ord_type         TEXT,             -- 주문 유형
    price            NUMERIC,          -- 주문 단가 또는 총액(지정가 주문의 경우 단가, 시장가 매수 주문의 경우 매수 총액입니다.)
    state            TEXT,             -- 주문 상태 (wait: 체결 대기, watch: 예약 주문 대기, done: 체결 완료, cancel: 주문 취소)
    created_at       TIMESTAMPTZ,      -- 주문 생성 시각(KST 기준)
    volume           NUMERIC,          -- 주문 요청 수량
    remaining_volume NUMERIC,          -- 체결 후 남은 주문 양
    executed_volume  NUMERIC,          -- 체결된 양
    reserved_fee     NUMERIC,          -- 수수료로 예약된 비용
    remaining_fee    NUMERIC,          -- 사용된 수수료
    paid_fee         NUMERIC,          -- 사용된 수수료
    locked           NUMERIC,          -- 거래에 사용 중인 비용
    trades_count     INTEGER,          -- 해당 주문에 대한 체결 건수
    time_in_force    TEXT,             -- 주문 체결 옵션
    identifier       TEXT,             -- 주문 생성시 클라이언트가 지정한 주문 식별자.
    smp_type         TEXT,             -- 자전거래 체결 방지(Self-Match Prevention) 모드
    prevented_volume NUMERIC,          -- 자전거래 방지로 인해 취소된 수량. (동일 사용자의 주문 간 체결이 발생하지 않도록 설정(SMP)에 따라 취소된 주문 수량입니다.)
    prevented_locked NUMERIC           -- 자전거래 방지로 인해 해제된 자산. (자전거래 체결 방지 설정으로 인해 취소된 주문의 잔여 자산입니다.)
);
