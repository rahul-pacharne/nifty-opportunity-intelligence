-- Restart state for decisions, deliveries, and reported positions.
-- Usable bars stay unique. A quarantined row may share the same source version
-- so a later correction can be stored.

ALTER TABLE market_observations
    DROP CONSTRAINT IF EXISTS market_observations_instrument_id_market_date_source_versio_key;

CREATE UNIQUE INDEX IF NOT EXISTS market_observations_usable_key
    ON market_observations (instrument_id, market_date, source, version)
    WHERE quality = 'ok';

ALTER TABLE predictions ADD COLUMN IF NOT EXISTS signal_id TEXT;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS decision_at TIMESTAMPTZ;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS recommendation TEXT;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS version INTEGER;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS feature_ema NUMERIC;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS latest_bar_date DATE;

ALTER TABLE signals ADD COLUMN IF NOT EXISTS index_symbol TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS horizon TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS direction TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS reported_entry NUMERIC;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS reported_exit NUMERIC;

ALTER TABLE notification_deliveries ADD COLUMN IF NOT EXISTS signal_id TEXT;
ALTER TABLE notification_deliveries ADD COLUMN IF NOT EXISTS alert_type TEXT;
ALTER TABLE notification_deliveries ADD COLUMN IF NOT EXISTS chat_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS notification_deliveries_sent_once
    ON notification_deliveries (signal_id, alert_type)
    WHERE status = 'sent';

ALTER TABLE manual_trades ADD COLUMN IF NOT EXISTS instrument TEXT;
ALTER TABLE manual_trades ADD COLUMN IF NOT EXISTS entry_session DATE;
ALTER TABLE manual_trades ADD COLUMN IF NOT EXISTS premium_stop NUMERIC;
ALTER TABLE manual_trades ADD COLUMN IF NOT EXISTS premium_target NUMERIC;
ALTER TABLE manual_trades ADD COLUMN IF NOT EXISTS holding_seconds INTEGER;
ALTER TABLE manual_trades ADD COLUMN IF NOT EXISTS sold BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE manual_trades ADD COLUMN IF NOT EXISTS sell_reason TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS manual_trades_signal_id_key
    ON manual_trades (signal_id);
