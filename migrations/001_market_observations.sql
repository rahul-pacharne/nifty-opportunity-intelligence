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
