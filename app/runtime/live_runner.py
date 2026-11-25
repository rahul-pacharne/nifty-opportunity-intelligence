"""Package D. Upstox quotes and the IST clock drive buy and sell checks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.data.models import Bar
from app.data.calendar import MarketCalendar
from app.runtime.decision_loop import DecisionLoop
from app.runtime.exits import PositionBook
from app.runtime.health import HealthReport, health
from app.runtime.schedule import scheduled_activity
from app.runtime.telegram_gateway import TelegramGateway
from app.core.constants import Recommendation
from app.options.eligibility import ContractQuote

ENTRY_ACTIVITIES = frozenset({"premarket_collection", "prediction_refresh", "final_trade_eligibility"})
SELL_ACTIVITIES = frozenset({"opening_assessment"})


@dataclass(frozen=True)
class ClockResult:
    activity: str
    health: HealthReport
    sent: tuple[str, ...]


class UpstoxClient:
    """Token is read from the environment. Callers do not pass a secret in code."""

    def __init__(self, fetch) -> None:
        self._fetch = fetch
        self.token = os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip() or None

    def quotes(self) -> list[Bar] | None:
        if not self.token:
            return None
        return self.fetch_quotes()

    def fetch_quotes(self) -> list[Bar] | None:
        try:
            return self._fetch()
        except OSError:
            return None


def ingest(loop: DecisionLoop, bars: list[Bar], *, now: datetime, max_age: timedelta) -> None:
    for bar in bars:
        loop.repository.add(bar, now=now, max_age=max_age)


def run_clock(
    moment: datetime,
    *,
    loop: DecisionLoop,
    book: PositionBook,
    gateway: TelegramGateway,
    chat_id: str,
    calendar: MarketCalendar | None = None,
    upstox_ok: bool = True,
    series_ok: bool = True,
    index_symbol=None,
    quote: ContractQuote | None = None,
    capital: Decimal | None = None,
    expected_gross: Decimal = Decimal("0"),
) -> ClockResult:
    from app.core.constants import IndexSymbol

    calendar = calendar or MarketCalendar()
    activity = scheduled_activity(moment, calendar)
    report = health(
        database_ok=True,
        scheduler_ok=True,
        provider_ok=upstox_ok and series_ok,
    )
    if activity == "market_holiday" or not upstox_ok or not series_ok:
        return ClockResult(activity, report, ())
    sent: list[str] = []
    index = index_symbol or IndexSymbol.NIFTY
    if activity in ENTRY_ACTIVITIES:
        record = loop.decide(
            index=index,
            decision_at=moment,
            quote=quote,
            capital=capital,
            expected_gross=expected_gross,
        )
        if record.recommendation in {Recommendation.BUY_CALL, Recommendation.BUY_PUT}:
            started = datetime.now(tz=moment.tzinfo)
            status = gateway.deliver(chat_id, record.signal_id, "buy", record.recommendation.value)
            elapsed = datetime.now(tz=moment.tzinfo) - started
            if status == "sent" and elapsed <= timedelta(seconds=60):
                sent.append(record.signal_id)
    if activity in SELL_ACTIVITIES:
        for signal_id, position in list(book.positions.items()):
            alert = book.check(signal_id, now=moment, entry_session_opened=True)
            if alert is None:
                continue
            status = gateway.deliver(chat_id, alert.signal_id, "sell", alert.message)
            if status == "sent":
                sent.append(alert.signal_id)
            _ = position
    return ClockResult(activity, report, tuple(sent))


def export_state(loop: DecisionLoop, book: PositionBook, gateway: TelegramGateway) -> dict:
    return {
        "records": list(loop.records),
        "positions": dict(book.positions),
        "sent": set(gateway.sent),
    }


def restore_state(loop: DecisionLoop, book: PositionBook, gateway: TelegramGateway, state: dict) -> None:
    loop.records = list(state["records"])
    book.positions = dict(state["positions"])
    gateway.sent = set(state["sent"])
