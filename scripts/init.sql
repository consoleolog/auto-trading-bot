-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

CREATE SCHEMA IF NOT EXISTS trading;
CREATE SCHEMA IF NOT EXISTS analytics;

-- =====================================================
-- TRADING SCHEMA TABLES
-- =====================================================

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

-- =====================================================
-- ANALYTICS SCHEMA TABLES
-- =====================================================

-- Technical Signal
CREATE TABLE IF NOT EXISTS analytics.technical_signals
(
    signal_name      TEXT        NOT NULL,
    signal_type      TEXT        NOT NULL,
    signal_value     TEXT        NOT NULL,
    signal_strength  TEXT        NOT NULL,
    signal_direction TEXT        NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (signal_name, signal_type)
);
