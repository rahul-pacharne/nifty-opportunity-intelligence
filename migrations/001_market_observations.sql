-- Phase 1 store. Later phases add prediction and signal tables.
-- Historical rows are not updated in place. A correction is a new version.

CREATE TABLE IF NOT EXISTS instruments (
    instrument_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    expiry DATE,
    strike NUMERIC,
    option_type TEXT
);

CREATE TABLE IF NOT EXISTS market_observations (
    id BIGSERIAL PRIMARY KEY,
    instrument_id TEXT NOT NULL REFERENCES instruments (instrument_id),
    market_date DATE NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    observation_at TIMESTAMPTZ NOT NULL,
    publication_at TIMESTAMPTZ,
    retrieved_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    version TEXT NOT NULL,
    quality TEXT NOT NULL,
    quality_reason TEXT,
    UNIQUE (instrument_id, market_date, source, version)
);

CREATE INDEX IF NOT EXISTS market_observations_as_of
    ON market_observations (instrument_id, observation_at);

CREATE TABLE IF NOT EXISTS option_snapshots (
    id BIGSERIAL PRIMARY KEY,
    instrument_id TEXT NOT NULL,
    market_date DATE NOT NULL,
    strike NUMERIC NOT NULL,
    expiry DATE NOT NULL,
    option_type TEXT NOT NULL,
    bid NUMERIC,
    ask NUMERIC,
    implied_volatility NUMERIC,
    open_interest NUMERIC,
    volume NUMERIC,
    observation_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    quality TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS derivatives_positions (
    id BIGSERIAL PRIMARY KEY,
    market_date DATE NOT NULL,
    participant TEXT NOT NULL,
    long_contracts NUMERIC,
    short_contracts NUMERIC,
    publication_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS global_market_data (
    id BIGSERIAL PRIMARY KEY,
    instrument_id TEXT NOT NULL,
    observation_at TIMESTAMPTZ NOT NULL,
    close NUMERIC NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS macro_events (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS features (
    id BIGSERIAL PRIMARY KEY,
    instrument_id TEXT NOT NULL,
    market_date DATE NOT NULL,
    name TEXT NOT NULL,
    value NUMERIC,
    available_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS market_regimes (
    id BIGSERIAL PRIMARY KEY,
    instrument_id TEXT NOT NULL,
    market_date DATE NOT NULL,
    regime TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS model_versions (
    model_version TEXT PRIMARY KEY,
    index_symbol TEXT NOT NULL,
    horizon TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    index_symbol TEXT NOT NULL,
    horizon TEXT NOT NULL,
    model_version TEXT NOT NULL,
    expected_gap NUMERIC,
    probability_up NUMERIC,
    probability_down NUMERIC,
    probability_flat NUMERIC,
    data_quality TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
    id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS option_evaluations (
    id BIGSERIAL PRIMARY KEY,
    opportunity_id BIGINT NOT NULL,
    instrument_id TEXT NOT NULL,
    expected_net NUMERIC,
    premium_at_risk NUMERIC
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY,
    prediction_id BIGINT,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    signal_id TEXT NOT NULL,
    category TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    id BIGSERIAL PRIMARY KEY,
    notification_id BIGINT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS manual_trades (
    id BIGSERIAL PRIMARY KEY,
    signal_id TEXT NOT NULL,
    entry_premium NUMERIC,
    exit_premium NUMERIC,
    reported_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS prediction_outcomes (
    id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT NOT NULL,
    actual_gap NUMERIC,
    recorded_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    index_symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    metric TEXT NOT NULL,
    value NUMERIC,
    as_of DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    event TEXT NOT NULL,
    payload TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL
);
