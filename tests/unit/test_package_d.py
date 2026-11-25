from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.constants import IndexSymbol, Recommendation
from app.data.calendar import MarketCalendar
from app.data.models import Bar
from app.options.eligibility import ContractQuote
from app.runtime.decision_loop import DecisionLoop
from app.runtime.exits import ExitRules, PositionBook
from app.runtime.live_runner import UpstoxClient, export_state, ingest, restore_state, run_clock
from app.runtime.telegram_gateway import MemoryTransport, TelegramGateway

IST = ZoneInfo("Asia/Kolkata")
RULES = ExitRules(Decimal("20"), Decimal("30"), timedelta(hours=6))


def _bar(day: date, instrument: str, close: str, published: datetime) -> Bar:
    close_d = Decimal(close)
    return Bar(
        instrument_id=instrument,
        market_date=day,
        open=close_d,
        high=close_d + 1,
        low=close_d - 1,
        close=close_d,
        observation_at=published,
        publication_at=published,
        retrieved_at=published,
        source="upstox",
        version="1",
    )


def _setup():
    loop = DecisionLoop()
    book = PositionBook()
    transport = MemoryTransport()
    gateway = TelegramGateway(("owner",), transport, book, RULES)
    return loop, book, gateway, transport


def test_upstox_token_comes_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "env-token")
    client = UpstoxClient(lambda: [])
    assert client.token == "env-token"
    assert client.quotes() == []
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN")
    assert UpstoxClient(lambda: [_bar(date(2026, 11, 25), "NIFTY", "1", datetime.now(timezone.utc))]).quotes() is None
    assert "env-token" not in open("app/runtime/live_runner.py", encoding="utf-8").read()


def test_stale_quote_cannot_create_a_buy() -> None:
    loop, book, gateway, transport = _setup()
    old = datetime(2026, 11, 20, 3, 30, tzinfo=IST)
    now = datetime(2026, 11, 25, 8, 30, tzinfo=IST)
    ingest(loop, [_bar(date(2026, 11, 20), IndexSymbol.NIFTY.value, "100", old)], now=now, max_age=timedelta(hours=1))
    result = run_clock(
        now,
        loop=loop,
        book=book,
        gateway=gateway,
        chat_id="owner",
        upstox_ok=True,
        series_ok=True,
        quote=ContractQuote("C", "CALL", Decimal("1"), Decimal("0.5"), Decimal("10"), Decimal("10.1"), 100),
        capital=Decimal("50000"),
        expected_gross=Decimal("20"),
    )
    assert result.sent == ()
    assert transport.messages == []
    assert loop.records[0].recommendation is Recommendation.NO_TRADE


def test_provider_down_and_holiday_send_nothing() -> None:
    loop, book, gateway, transport = _setup()
    moment = datetime(2026, 11, 25, 8, 30, tzinfo=IST)
    down = run_clock(moment, loop=loop, book=book, gateway=gateway, chat_id="owner", upstox_ok=False, series_ok=True)
    assert down.health.status == "degraded"
    assert down.sent == ()
    holiday = datetime(2026, 11, 23, 8, 30, tzinfo=IST)
    calendar = MarketCalendar(holidays=frozenset({holiday.date()}))
    closed = run_clock(holiday, loop=loop, book=book, gateway=gateway, chat_id="owner", calendar=calendar)
    assert closed.activity == "market_holiday"
    assert closed.sent == ()
    assert transport.messages == []


def test_restart_keeps_the_position_and_does_not_resend() -> None:
    loop, book, gateway, transport = _setup()
    gateway.deliver("owner", "NOI-1", "buy", "BUY CALL")
    book.report_entry(
        signal_id="NOI-1",
        instrument="NIFTY-CALL",
        premium=Decimal("100"),
        entry_session=date(2026, 11, 25),
        entered_at=datetime(2026, 11, 25, 4, 0, tzinfo=timezone.utc),
        rules=ExitRules(Decimal("20"), Decimal("30"), timedelta(hours=6)),
    )
    state = export_state(loop, book, gateway)
    restored_loop, restored_book, restored_gateway, restored_transport = _setup()
    restore_state(restored_loop, restored_book, restored_gateway, state)
    assert "NOI-1" in restored_book.positions
    assert restored_gateway.deliver("owner", "NOI-1", "buy", "BUY CALL") == "duplicate_suppressed"
    assert restored_transport.messages == []
