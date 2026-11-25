"""Package B. Sell rules apply only after the owner reports an entry."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class ExitRules:
    premium_stop: Decimal
    premium_target: Decimal
    holding_time: timedelta


@dataclass(frozen=True)
class OpenPosition:
    signal_id: str
    instrument: str
    entry_premium: Decimal
    entry_session: date
    entered_at: datetime
    rules: ExitRules
    sold: bool = False
    sell_reason: str | None = None


@dataclass(frozen=True)
class SellAlert:
    signal_id: str
    instrument: str
    reason: str
    message: str


def sell_message(signal_id: str, instrument: str, reason: str) -> str:
    return (
        f"Trade recommendation: SELL\n"
        f"Signal ID: {signal_id}\n"
        f"Instrument: {instrument}\n"
        f"Reason: {reason}\n"
        "No broker order has been placed."
    )


class PositionBook:
    def __init__(self) -> None:
        self.positions: dict[str, OpenPosition] = {}
        self._sent_sells: set[str] = set()

    def report_entry(
        self,
        *,
        signal_id: str,
        instrument: str,
        premium: Decimal,
        entry_session: date,
        entered_at: datetime,
        rules: ExitRules,
    ) -> OpenPosition:
        position = OpenPosition(
            signal_id=signal_id,
            instrument=instrument,
            entry_premium=premium,
            entry_session=entry_session,
            entered_at=entered_at,
            rules=rules,
        )
        self.positions[signal_id] = position
        return position

    def record_exit_price(self, signal_id: str, price: Decimal) -> Decimal | None:
        """Record a sale the owner already made. This does not decide to sell."""
        if signal_id not in self.positions:
            return None
        return price

    def check(
        self,
        signal_id: str,
        *,
        now: datetime,
        premium: Decimal | None = None,
        invalidated: bool = False,
        entry_session_opened: bool = False,
    ) -> SellAlert | None:
        position = self.positions.get(signal_id)
        if position is None or position.sold or signal_id in self._sent_sells:
            return None
        reason = _reason(position, now=now, premium=premium, invalidated=invalidated, entry_session_opened=entry_session_opened)
        if reason is None:
            return None
        self.positions[signal_id] = replace(position, sold=True, sell_reason=reason)
        self._sent_sells.add(signal_id)
        return SellAlert(
            signal_id=signal_id,
            instrument=position.instrument,
            reason=reason,
            message=sell_message(signal_id, position.instrument, reason),
        )


def _reason(
    position: OpenPosition,
    *,
    now: datetime,
    premium: Decimal | None,
    invalidated: bool,
    entry_session_opened: bool,
) -> str | None:
    if invalidated:
        return "invalidation"
    if premium is not None:
        change = premium - position.entry_premium
        if change < 0 and abs(change) > position.rules.premium_stop:
            return "premium_stop"
        if change > position.rules.premium_target:
            return "premium_target"
    if entry_session_opened or now - position.entered_at >= position.rules.holding_time:
        return "time_stop"
    return None
