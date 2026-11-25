"""Postgres store for bars, decisions, deliveries, and reported positions.

One connection is used by a single thread. Writes commit before they return.
A second process sees them and will not send an alert that was already sent.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.core.constants import Horizon, IndexSymbol, QualityStatus, Recommendation, SignalStatus
from app.data.calendar import MarketCalendar
from app.data.models import Bar, CoverageReport
from app.data.validation import apply_validation
from app.runtime.decision_loop import StoredDecision
from app.runtime.exits import ExitRules, OpenPosition

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def split_sql(script: str) -> tuple[str, ...]:
    statements: list[str] = []
    current: list[str] = []
    for raw in script.splitlines():
        stripped = raw.strip()
        if not current and (not stripped or stripped.startswith("--")):
            continue
        current.append(raw)
        if stripped.endswith(";"):
            text = "\n".join(current).strip()[:-1].strip()
            if text:
                statements.append(text)
            current = []
    tail = "\n".join(current).strip().rstrip(";").strip()
    if tail:
        statements.append(tail)
    return tuple(statements)


def connect(url: str):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)


def apply_migrations(connection, directory: Path | None = None) -> list[str]:
    directory = directory or MIGRATIONS_DIR
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    connection.commit()
    applied: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        found = connection.execute(
            "SELECT filename FROM schema_migrations WHERE filename = %s",
            (path.name,),
        ).fetchone()
        if found:
            connection.commit()
            continue
        for statement in split_sql(path.read_text(encoding="utf-8")):
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations (filename, applied_at) VALUES (%s, now())",
            (path.name,),
        )
        connection.commit()
        applied.append(path.name)
    return applied


def open_store(url: str, calendar: MarketCalendar | None = None) -> PostgresStore:
    connection = connect(url)
    try:
        apply_migrations(connection)
    except Exception:
        connection.close()
        raise
    return PostgresStore(connection, calendar=calendar)


class PostgresStore:
    def __init__(self, connection, calendar: MarketCalendar | None = None) -> None:
        self._connection = connection
        self._calendar = calendar or MarketCalendar()

    def close(self) -> None:
        self._connection.close()

    def add(
        self,
        bar: Bar,
        *,
        now: datetime | None = None,
        max_age: timedelta | None = None,
    ) -> Bar:
        from psycopg.errors import UniqueViolation

        stored = apply_validation(bar, now=now, max_age=max_age)
        try:
            self._ensure_instrument(stored)
            if stored.quality is QualityStatus.OK and self._has_usable(stored):
                stored = replace(stored, quality=QualityStatus.QUARANTINED, quality_reason="duplicate")
            self._insert_bar(stored)
            self._connection.commit()
        except UniqueViolation:
            self._connection.rollback()
            stored = replace(stored, quality=QualityStatus.QUARANTINED, quality_reason="duplicate")
            try:
                self._ensure_instrument(stored)
                self._insert_bar(stored)
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        except Exception:
            self._connection.rollback()
            raise
        return stored

    def usable_as_of(self, decision_at: datetime, instrument_id: str | None = None) -> tuple[Bar, ...]:
        if decision_at.tzinfo is None:
            raise ValueError("decision timestamp must be timezone-aware")
        rows = self._fetchall(
            """
            SELECT instrument_id, market_date, open, high, low, close,
                   observation_at, publication_at, retrieved_at, source, version,
                   quality, quality_reason
            FROM market_observations
            WHERE quality = 'ok'
              AND (CAST(%s AS text) IS NULL OR instrument_id = %s)
              AND COALESCE(publication_at, observation_at) <= %s
            ORDER BY market_date, id
            """,
            (instrument_id, instrument_id, decision_at),
        )
        return tuple(_bar_from_row(row) for row in rows)

    def coverage(self, instrument_id: str) -> CoverageReport:
        rows = self._fetchall(
            """
            SELECT instrument_id, market_date, source, version, quality, quality_reason, publication_at
            FROM market_observations
            WHERE instrument_id = %s
            ORDER BY market_date, id
            """,
            (instrument_id,),
        )
        usable = [row for row in rows if row["quality"] == QualityStatus.OK.value]
        dates = [row["market_date"] for row in usable]
        missing: tuple = ()
        if dates:
            expected = self._calendar.sessions_between(min(dates), max(dates))
            present = set(dates)
            missing = tuple(day for day in expected if day not in present)
        duplicates = tuple(
            f"{row['instrument_id']}|{row['market_date'].isoformat()}|{row['source']}|{row['version']}"
            for row in rows
            if row["quality_reason"] == "duplicate"
        )
        return CoverageReport(
            first_date=min(dates) if dates else None,
            last_date=max(dates) if dates else None,
            row_count=len(rows),
            usable_count=len(usable),
            quarantined_count=len(rows) - len(usable),
            missing_sessions=missing,
            duplicate_keys=duplicates,
            rows_with_publication_time=sum(1 for row in rows if row["publication_at"] is not None),
        )

    def save_decision(self, record: StoredDecision) -> None:
        try:
            if record.model_version:
                self._connection.execute(
                    """
                    INSERT INTO model_versions (model_version, index_symbol, horizon, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (model_version) DO NOTHING
                    """,
                    (record.model_version, record.index.value, Horizon.T1.value, record.decision_at),
                )
            prediction = self._connection.execute(
                """
                INSERT INTO predictions (
                    index_symbol, horizon, model_version, expected_gap,
                    probability_up, probability_down, probability_flat,
                    data_quality, created_at, signal_id, decision_at,
                    recommendation, version, feature_ema, latest_bar_date
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    record.index.value,
                    Horizon.T1.value,
                    record.model_version,
                    record.expected_gap,
                    record.probability_up,
                    record.probability_down,
                    record.probability_flat,
                    record.data_quality,
                    record.decision_at,
                    record.signal_id,
                    record.decision_at,
                    record.recommendation.value,
                    record.version,
                    record.feature_ema,
                    record.latest_bar_date,
                ),
            ).fetchone()
            self._connection.execute(
                """
                INSERT INTO signals (
                    signal_id, prediction_id, status, created_at, index_symbol, horizon, direction
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (signal_id) DO NOTHING
                """,
                (
                    record.signal_id,
                    prediction["id"],
                    _status_for(record.recommendation),
                    record.decision_at,
                    record.index.value,
                    Horizon.T1.value,
                    _direction_label(record),
                ),
            )
            self._connection.execute(
                """
                INSERT INTO opportunities (prediction_id, status, created_at)
                VALUES (%s, %s, %s)
                """,
                (prediction["id"], record.recommendation.value, record.decision_at),
            )
            if record.feature_ema is not None and record.latest_bar_date is not None:
                self._connection.execute(
                    """
                    INSERT INTO features (instrument_id, market_date, name, value, available_at)
                    VALUES (%s, %s, 'ema_5', %s, %s)
                    """,
                    (record.index.value, record.latest_bar_date, record.feature_ema, record.decision_at),
                )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def load_decisions(self) -> list[StoredDecision]:
        rows = self._fetchall(
            """
            SELECT signal_id, index_symbol, decision_at, recommendation, version,
                   model_version, probability_up, probability_down, probability_flat,
                   expected_gap, data_quality, feature_ema, latest_bar_date
            FROM predictions
            WHERE signal_id IS NOT NULL
              AND recommendation IS NOT NULL
              AND version IS NOT NULL
              AND decision_at IS NOT NULL
            ORDER BY version, id
            """,
            (),
        )
        return [
            StoredDecision(
                version=int(row["version"]),
                index=IndexSymbol(row["index_symbol"]),
                decision_at=row["decision_at"],
                recommendation=Recommendation(row["recommendation"]),
                signal_id=row["signal_id"],
                model_version=row["model_version"],
                probability_up=row["probability_up"],
                probability_down=row["probability_down"],
                probability_flat=row["probability_flat"],
                expected_gap=row["expected_gap"],
                data_quality=row["data_quality"],
                feature_ema=row["feature_ema"],
                latest_bar_date=row["latest_bar_date"],
            )
            for row in rows
        ]

    def save_delivery(
        self,
        chat_id: str,
        signal_id: str,
        alert_type: str,
        status: str,
        attempts: int,
        body: str,
    ) -> None:
        try:
            note = self._connection.execute(
                """
                INSERT INTO notifications (signal_id, category, body, created_at)
                VALUES (%s, %s, %s, now())
                RETURNING id
                """,
                (signal_id, alert_type, body),
            ).fetchone()
            self._connection.execute(
                """
                INSERT INTO notification_deliveries (
                    notification_id, channel, status, attempts, signal_id, alert_type, chat_id
                ) VALUES (%s, 'telegram', %s, %s, %s, %s, %s)
                """,
                (note["id"], status, attempts, signal_id, alert_type, chat_id),
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def load_sent(self) -> set[tuple[str, str]]:
        rows = self._fetchall(
            """
            SELECT signal_id, alert_type
            FROM notification_deliveries
            WHERE status = 'sent' AND signal_id IS NOT NULL AND alert_type IS NOT NULL
            """,
            (),
        )
        return {(row["signal_id"], row["alert_type"]) for row in rows}

    def save_position(self, position: OpenPosition) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO manual_trades (
                    signal_id, entry_premium, exit_premium, reported_at,
                    instrument, entry_session, premium_stop, premium_target,
                    holding_seconds, sold, sell_reason
                ) VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (signal_id) DO UPDATE SET
                    entry_premium = EXCLUDED.entry_premium,
                    reported_at = EXCLUDED.reported_at,
                    instrument = EXCLUDED.instrument,
                    entry_session = EXCLUDED.entry_session,
                    premium_stop = EXCLUDED.premium_stop,
                    premium_target = EXCLUDED.premium_target,
                    holding_seconds = EXCLUDED.holding_seconds,
                    sold = EXCLUDED.sold,
                    sell_reason = EXCLUDED.sell_reason
                """,
                (
                    position.signal_id,
                    position.entry_premium,
                    position.entered_at,
                    position.instrument,
                    position.entry_session,
                    position.rules.premium_stop,
                    position.rules.premium_target,
                    int(position.rules.holding_time.total_seconds()),
                    position.sold,
                    position.sell_reason,
                ),
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def save_exit_price(self, signal_id: str, price: Decimal) -> None:
        try:
            self._connection.execute(
                "UPDATE manual_trades SET exit_premium = %s WHERE signal_id = %s",
                (price, signal_id),
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def load_positions(self) -> dict[str, OpenPosition]:
        rows = self._fetchall(
            """
            SELECT signal_id, entry_premium, reported_at, instrument, entry_session,
                   premium_stop, premium_target, holding_seconds, sold, sell_reason
            FROM manual_trades
            WHERE instrument IS NOT NULL
              AND entry_session IS NOT NULL
              AND premium_stop IS NOT NULL
              AND premium_target IS NOT NULL
              AND holding_seconds IS NOT NULL
              AND entry_premium IS NOT NULL
            """,
            (),
        )
        positions: dict[str, OpenPosition] = {}
        for row in rows:
            positions[row["signal_id"]] = OpenPosition(
                signal_id=row["signal_id"],
                instrument=row["instrument"],
                entry_premium=row["entry_premium"],
                entry_session=row["entry_session"],
                entered_at=row["reported_at"],
                rules=ExitRules(
                    row["premium_stop"],
                    row["premium_target"],
                    timedelta(seconds=int(row["holding_seconds"])),
                ),
                sold=bool(row["sold"]),
                sell_reason=row["sell_reason"],
            )
        return positions

    def exit_premium(self, signal_id: str) -> Decimal | None:
        rows = self._fetchall(
            "SELECT exit_premium FROM manual_trades WHERE signal_id = %s",
            (signal_id,),
        )
        if not rows:
            return None
        return rows[0]["exit_premium"]

    def counts(self) -> dict[str, int]:
        queries = {
            "market_observations": "SELECT COUNT(*) AS n FROM market_observations",
            "predictions": "SELECT COUNT(*) AS n FROM predictions",
            "signals": "SELECT COUNT(*) AS n FROM signals",
            "notification_deliveries": "SELECT COUNT(*) AS n FROM notification_deliveries",
            "manual_trades": "SELECT COUNT(*) AS n FROM manual_trades",
        }
        return {name: int(self._fetchall(sql, ())[0]["n"]) for name, sql in queries.items()}

    def record_audit(self, event: str, payload: str) -> int:
        try:
            row = self._connection.execute(
                """
                INSERT INTO audit_logs (event, payload, recorded_at)
                VALUES (%s, %s, now())
                RETURNING id
                """,
                (event, payload),
            ).fetchone()
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return int(row["id"])

    def _ensure_instrument(self, bar: Bar) -> None:
        self._connection.execute(
            """
            INSERT INTO instruments (instrument_id, symbol, kind)
            VALUES (%s, %s, 'index')
            ON CONFLICT (instrument_id) DO NOTHING
            """,
            (bar.instrument_id, bar.instrument_id),
        )

    def _has_usable(self, bar: Bar) -> bool:
        row = self._connection.execute(
            """
            SELECT 1 AS found
            FROM market_observations
            WHERE instrument_id = %s AND market_date = %s AND source = %s
              AND version = %s AND quality = 'ok'
            """,
            (bar.instrument_id, bar.market_date, bar.source, bar.version),
        ).fetchone()
        return row is not None

    def _insert_bar(self, bar: Bar) -> None:
        self._connection.execute(
            """
            INSERT INTO market_observations (
                instrument_id, market_date, open, high, low, close,
                observation_at, publication_at, retrieved_at, source, version,
                quality, quality_reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                bar.instrument_id,
                bar.market_date,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.observation_at,
                bar.publication_at,
                bar.retrieved_at,
                bar.source,
                bar.version,
                bar.quality.value,
                bar.quality_reason,
            ),
        )

    def _fetchall(self, sql: str, params: tuple) -> list:
        try:
            rows = list(self._connection.execute(sql, params).fetchall())
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return rows


def _bar_from_row(row) -> Bar:
    return Bar(
        instrument_id=row["instrument_id"],
        market_date=row["market_date"],
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        observation_at=row["observation_at"],
        publication_at=row["publication_at"],
        retrieved_at=row["retrieved_at"],
        source=row["source"],
        version=row["version"],
        quality=QualityStatus(row["quality"]),
        quality_reason=row["quality_reason"],
    )


def _status_for(recommendation: Recommendation) -> str:
    if recommendation in {Recommendation.BUY_CALL, Recommendation.BUY_PUT}:
        return SignalStatus.TRADE_RECOMMENDED.value
    if recommendation is Recommendation.WATCHLIST:
        return SignalStatus.WATCHLIST.value
    return SignalStatus.DETECTED.value


def _direction_label(record: StoredDecision) -> str:
    up = record.probability_up
    down = record.probability_down
    flat = record.probability_flat
    if up is None or down is None or flat is None:
        return ""
    if up >= down and up >= flat:
        return "up"
    if down >= up and down >= flat:
        return "down"
    return "flat"
