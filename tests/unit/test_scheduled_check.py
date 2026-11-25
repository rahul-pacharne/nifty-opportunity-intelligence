from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.constants import IndexSymbol, Recommendation
from app.data.models import Bar
from app.data.upstox_quotes import QuoteResult
from app.runtime.decision_loop import DecisionLoop
from app.runtime.exits import ExitRules, PositionBook
from app.runtime.scheduled_check import run_scheduled_check
from app.runtime.telegram_gateway import MemoryTransport, TelegramGateway

IST = ZoneInfo("Asia/Kolkata")
RULES = ExitRules(Decimal("20"), Decimal("30"), timedelta(hours=6))


def _gateway() -> tuple[TelegramGateway, MemoryTransport, DecisionLoop]:
    loop = DecisionLoop()
    transport = MemoryTransport()
    gateway = TelegramGateway(("owner",), transport, PositionBook(), RULES)
    return gateway, transport, loop


def _fresh(instrument: str, now: datetime, close: str) -> Bar:
    price = Decimal(close)
    return Bar(
        instrument_id=instrument,
        market_date=now.astimezone(IST).date(),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        observation_at=now,
        publication_at=now,
        retrieved_at=now,
        source="upstox",
        version="1",
    )


def test_late_evening_does_not_fetch_or_send(monkeypatch) -> None:
    def fail_fetch(*_args, **_kwargs):
        raise AssertionError("fetch")

    monkeypatch.setattr("app.runtime.scheduled_check.fetch_index_quotes", fail_fetch)
    gateway, transport, loop = _gateway()
    now = datetime(2026, 11, 25, 17, 35, tzinfo=timezone.utc)
    report = run_scheduled_check(now, token="test-token", loop=loop, gateway=gateway, chat_id="owner")
    assert report.activity == "maintenance"
    assert report.action == "idle"
    assert report.sent == ()
    assert transport.messages == []


def test_stale_entry_window_sends_nothing(monkeypatch) -> None:
    now = datetime(2026, 11, 25, 3, 0, tzinfo=timezone.utc)

    def fetch(*_args, **_kwargs):
        old = now - timedelta(hours=6)
        bars = (
            _fresh("NIFTY", old, "100"),
            _fresh("BANKNIFTY", old, "200"),
            _fresh("INDIA_VIX", old, "13"),
        )
        return QuoteResult(bars, (), None)

    monkeypatch.setattr("app.runtime.scheduled_check.fetch_index_quotes", fetch)
    gateway, transport, loop = _gateway()
    report = run_scheduled_check(now, token="test-token", loop=loop, gateway=gateway, chat_id="owner")
    assert report.activity == "premarket_collection"
    assert report.action == "degraded"
    assert transport.messages == []


def test_fresh_entry_window_sends_no_trade_and_not_a_buy(monkeypatch) -> None:
    now = datetime(2026, 11, 25, 3, 0, tzinfo=timezone.utc)

    def fetch(*_args, **_kwargs):
        bars = (
            _fresh("NIFTY", now, "25819"),
            _fresh("BANKNIFTY", now, "63703"),
            _fresh("INDIA_VIX", now, "17"),
        )
        return QuoteResult(bars, (), None)

    monkeypatch.setattr("app.runtime.scheduled_check.fetch_index_quotes", fetch)
    gateway, transport, loop = _gateway()
    report = run_scheduled_check(now, token="test-token", loop=loop, gateway=gateway, chat_id="owner")
    assert report.action == "decided"
    assert len(report.sent) == 2
    assert len(transport.messages) == 2
    assert all("Action: NO TRADE" in text for _, text in transport.messages)
    assert all(record.recommendation is Recommendation.NO_TRADE for record in loop.records)
    assert {record.index for record in loop.records} == {IndexSymbol.NIFTY, IndexSymbol.BANKNIFTY}
    assert "consider_buy_call" not in " ".join(text for _, text in transport.messages)
