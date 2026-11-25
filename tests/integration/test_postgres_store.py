import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.core.constants import IndexSymbol, QualityStatus, Recommendation
from app.data.models import Bar
from app.runtime.persistence import PostgresStore, open_store
from app.runtime.exits import ExitRules
from app.runtime.live_runner import run_clock
from app.runtime.session import open_runtime
from app.runtime.telegram_gateway import MemoryTransport

URL = os.environ.get("NOI_TEST_DATABASE_URL", "postgresql://noi:noi@127.0.0.1:5432/noi_test")
IST = ZoneInfo("Asia/Kolkata")
RULES = ExitRules(Decimal("20"), Decimal("30"), timedelta(hours=6))


def _truncate(store: PostgresStore) -> None:
    store._connection.execute(
        """
        TRUNCATE TABLE
            notification_deliveries,
            notifications,
            option_evaluations,
            opportunities,
            features,
            manual_trades,
            signals,
            predictions,
            prediction_outcomes,
            market_observations,
            instruments,
            model_versions,
            audit_logs
        RESTART IDENTITY CASCADE
        """
    )
    store._connection.commit()


@pytest.fixture()
def database_url():
    pytest.importorskip("psycopg")
    try:
        store = open_store(URL)
    except Exception as exc:
        if os.environ.get("NOI_REQUIRE_POSTGRES") == "1":
            raise
        pytest.skip(f"postgres unavailable: {exc}")
    _truncate(store)
    store.close()
    return URL


def _bar(day: date, instrument: str, close: str, *, published: datetime | None = None, high: str | None = None) -> Bar:
    close_d = Decimal(close)
    stamp = published or datetime(day.year, day.month, day.day, 10, 0, tzinfo=timezone.utc)
    return Bar(
        instrument_id=instrument,
        market_date=day,
        open=close_d - Decimal("1"),
        high=Decimal(high) if high is not None else close_d + Decimal("1"),
        low=close_d - Decimal("2"),
        close=close_d,
        observation_at=stamp,
        publication_at=stamp,
        retrieved_at=stamp,
        source="fixture",
        version="1",
    )


def test_usable_rows_hide_future_publication_and_keep_corrections(database_url: str) -> None:
    store = open_store(database_url)
    early = store.add(_bar(date(2026, 11, 20), "NIFTY", "24050"))
    store.add(
        _bar(
            date(2026, 11, 23),
            "NIFTY",
            "24100",
            published=datetime(2026, 11, 23, 4, 0, tzinfo=timezone.utc),
        )
    )
    visible = store.usable_as_of(datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc), "NIFTY")
    assert visible == (early,)

    rejected = store.add(_bar(date(2026, 11, 24), "NIFTY", "100", high="50"))
    corrected = store.add(_bar(date(2026, 11, 24), "NIFTY", "24200"))
    assert rejected.quality_reason == "high_below_extreme"
    assert corrected.quality is QualityStatus.OK
    day = store.usable_as_of(datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc), "NIFTY")
    assert day[-1] == corrected

    duplicate = store.add(_bar(date(2026, 11, 20), "NIFTY", "25000"))
    assert duplicate.quality_reason == "duplicate"
    again = store.usable_as_of(datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc), "NIFTY")
    assert again == (early,)
    report = store.coverage("NIFTY")
    assert report.usable_count == 3
    assert report.quarantined_count == 2
    assert report.duplicate_keys == ("NIFTY|2026-11-20|fixture|1",)
    with pytest.raises(ValueError):
        store.usable_as_of(datetime(2026, 11, 20, 12, 0))
    store.close()


def test_restart_keeps_the_decision_the_alert_and_the_position(database_url: str) -> None:
    loop, book, gateway, store = open_runtime(
        database_url,
        allowed_user_ids=("owner",),
        transport=MemoryTransport(),
        rules=RULES,
    )
    moment = datetime(2026, 11, 25, 8, 30, tzinfo=IST)
    result = run_clock(moment, loop=loop, book=book, gateway=gateway, chat_id="owner")
    assert result.activity == "premarket_collection"
    assert result.sent == ()
    signal_id = loop.records[0].signal_id
    assert loop.records[0].recommendation is Recommendation.NO_TRADE
    assert gateway.deliver("owner", signal_id, "no_trade", "NO TRADE") == "duplicate_suppressed"

    entered = book.report_entry(
        signal_id=signal_id,
        instrument="NIFTY-CALL",
        premium=Decimal("100"),
        entry_session=date(2026, 11, 25),
        entered_at=datetime(2026, 11, 25, 10, 0, tzinfo=IST),
        rules=RULES,
    )
    assert book.record_exit_price(signal_id, Decimal("90")) == Decimal("90")
    alert = book.check(signal_id, now=datetime(2026, 11, 25, 18, 0, tzinfo=IST), invalidated=True)
    assert alert is not None
    assert alert.reason == "invalidation"
    store.close()

    restored_loop, restored_book, restored_gateway, restored = open_runtime(
        database_url,
        allowed_user_ids=("owner",),
        transport=MemoryTransport(),
        rules=RULES,
    )
    assert restored_loop.records[0].signal_id == signal_id
    assert restored_loop.records[0].version == 1
    second = restored_loop.decide(index=IndexSymbol.NIFTY, decision_at=moment + timedelta(minutes=5))
    assert second.version == 2
    assert second.signal_id != signal_id
    assert restored_gateway.deliver("owner", signal_id, "no_trade", "NO TRADE") == "duplicate_suppressed"
    position = restored_book.positions[signal_id]
    assert position.instrument == entered.instrument
    assert position.entry_premium == Decimal("100")
    assert position.sold is True
    assert position.sell_reason == "invalidation"
    assert restored.exit_premium(signal_id) == Decimal("90")
    assert restored_book.check(signal_id, now=moment, invalidated=True) is None
    restored.close()
