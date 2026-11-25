"""One IST clock check. Buy and sell stay off until the research gate is on."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.constants import IndexSymbol, QualityStatus, Recommendation
from app.data.calendar import MarketCalendar
from app.data.upstox_quotes import INDEX_KEYS, QUOTE_MAX_AGE, fetch_index_quotes
from app.notifications.messages import early_warning, no_trade
from app.runtime.decision_loop import DecisionLoop
from app.runtime.live_runner import ENTRY_ACTIVITIES
from app.runtime.schedule import scheduled_activity
from app.runtime.telegram_gateway import TelegramGateway

REQUIRED = tuple(instrument_id for _, instrument_id in INDEX_KEYS)


@dataclass(frozen=True)
class CheckReport:
    activity: str
    action: str
    sent: tuple[str, ...]


def run_scheduled_check(
    now: datetime,
    *,
    token: str,
    loop: DecisionLoop,
    gateway: TelegramGateway,
    chat_id: str,
    opener=None,
    calendar: MarketCalendar | None = None,
) -> CheckReport:
    if now.tzinfo is None:
        raise ValueError("check time must be timezone-aware")
    activity = scheduled_activity(now, calendar)
    if activity not in ENTRY_ACTIVITIES:
        return CheckReport(activity, "idle", ())
    fetch = fetch_index_quotes(token, now=now) if opener is None else fetch_index_quotes(token, now=now, opener=opener)
    if fetch.error:
        return CheckReport(activity, "degraded", ())
    stored = [loop.repository.add(bar, now=now, max_age=QUOTE_MAX_AGE) for bar in fetch.bars]
    fresh = {bar.instrument_id for bar in stored if bar.quality is QualityStatus.OK}
    if not set(REQUIRED) <= fresh:
        return CheckReport(activity, "degraded", ())
    sent: list[str] = []
    for index in (IndexSymbol.NIFTY, IndexSymbol.BANKNIFTY):
        record = loop.decide(index=index, decision_at=now)
        if record.recommendation is Recommendation.NO_TRADE:
            text = no_trade(signal_id=record.signal_id, reason=record.data_quality)
            alert_type = record.recommendation.value
        elif record.recommendation is Recommendation.WATCHLIST:
            text = early_warning(signal_id=record.signal_id, market=index.value)
            alert_type = record.recommendation.value
        else:
            continue
        status = gateway.deliver(chat_id, record.signal_id, alert_type, text)
        if status == "sent":
            sent.append(record.signal_id)
    return CheckReport(activity, "decided", tuple(sent))
