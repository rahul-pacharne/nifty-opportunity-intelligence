"""Package F. Paper mode delivers buy and sell, scores ignored alerts, and can be restored."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.core.constants import IndexSymbol, Recommendation
from app.notifications.email import daily_report, monthly_report, weekly_report
from app.notifications.whatsapp import WhatsAppChannel, WhatsAppOptInError
from app.runtime.decision_loop import DecisionLoop
from app.runtime.exits import PositionBook
from app.runtime.live_runner import export_state, restore_state
from app.runtime.telegram_gateway import TelegramGateway
from app.tracking.outcomes import TrackedTrade, scorecard

_TRADE = {Recommendation.BUY_CALL, Recommendation.BUY_PUT}


@dataclass
class PaperEvent:
    signal_id: str
    index: IndexSymbol
    recommendation: Recommendation
    ignored: bool = False
    reported_pnl: Decimal | None = None
    hypothetical_pnl: Decimal | None = None
    alert_type: str = "buy"


@dataclass
class PaperLog:
    emails: list[str] = field(default_factory=list)
    whatsapp_sent: list[str] = field(default_factory=list)
    trades: list[TrackedTrade] = field(default_factory=list)


def publish_paper(
    events: list[PaperEvent],
    *,
    gateway: TelegramGateway,
    chat_id: str,
    whatsapp: WhatsAppChannel,
    whatsapp_recipient: str,
    emails: list[str] | None = None,
) -> PaperLog:
    log = PaperLog(emails=emails if emails is not None else [])
    for event in events:
        body = f"{event.recommendation.value} {event.signal_id}"
        if event.recommendation in _TRADE or event.alert_type == "sell":
            gateway.deliver(chat_id, event.signal_id, event.alert_type, body)
            log.emails.append(daily_report([body]))
            try:
                whatsapp.send(whatsapp_recipient, event.signal_id, event.alert_type, body)
                log.whatsapp_sent.append(event.signal_id)
            except WhatsAppOptInError:
                pass
        if event.ignored and event.hypothetical_pnl is not None:
            log.trades.append(
                TrackedTrade(event.signal_id, "hypothetical", Decimal("0"), event.hypothetical_pnl, event.index)
            )
        if event.reported_pnl is not None:
            log.trades.append(
                TrackedTrade(event.signal_id, "reported", Decimal("0"), event.reported_pnl, event.index)
            )
    log.emails.append(weekly_report(["paper window"]))
    log.emails.append(monthly_report(["paper window"]))
    return log


def restore_paper(
    loop: DecisionLoop,
    book: PositionBook,
    gateway: TelegramGateway,
    state: dict,
) -> None:
    restore_state(loop, book, gateway, state)


def snapshot_paper(loop: DecisionLoop, book: PositionBook, gateway: TelegramGateway) -> dict:
    return export_state(loop, book, gateway)


def index_score(log: PaperLog, index: IndexSymbol, kind: str):
    return scorecard(log.trades, kind, index=index)
