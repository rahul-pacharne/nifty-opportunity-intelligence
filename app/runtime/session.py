"""Open the decision loop, position book, and Telegram gateway on one database."""

from __future__ import annotations

from app.data.calendar import MarketCalendar
from app.runtime.persistence import PostgresStore, open_store
from app.runtime.decision_loop import DecisionLoop
from app.runtime.exits import ExitRules, PositionBook
from app.runtime.telegram_gateway import TelegramGateway


def open_runtime(
    url: str,
    *,
    allowed_user_ids: tuple[str, ...],
    transport,
    rules: ExitRules,
    calendar: MarketCalendar | None = None,
) -> tuple[DecisionLoop, PositionBook, TelegramGateway, PostgresStore]:
    store = open_store(url, calendar=calendar)
    book = PositionBook(store=store)
    gateway = TelegramGateway(allowed_user_ids, transport, book, rules, store=store)
    loop = DecisionLoop(repository=store, calendar=calendar, store=store)
    return loop, book, gateway, store
