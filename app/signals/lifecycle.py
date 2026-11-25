"""Allowed status changes. Invalid transitions raise rather than skipping ahead."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from app.core.constants import Horizon, IndexSymbol, SignalStatus
from app.core.exceptions import NoiError

_TRANSITIONS: dict[SignalStatus, frozenset[SignalStatus]] = {
    SignalStatus.DETECTED: frozenset({SignalStatus.WATCHLIST, SignalStatus.INVALIDATED, SignalStatus.EXPIRED}),
    SignalStatus.WATCHLIST: frozenset({SignalStatus.CONFIRMED, SignalStatus.INVALIDATED, SignalStatus.EXPIRED}),
    SignalStatus.CONFIRMED: frozenset(
        {SignalStatus.TRADE_RECOMMENDED, SignalStatus.INVALIDATED, SignalStatus.EXPIRED}
    ),
    SignalStatus.TRADE_RECOMMENDED: frozenset(
        {SignalStatus.NOTIFIED, SignalStatus.INVALIDATED, SignalStatus.EXPIRED}
    ),
    SignalStatus.NOTIFIED: frozenset(
        {
            SignalStatus.MANUALLY_ACCEPTED,
            SignalStatus.POSITION_REPORTED,
            SignalStatus.IGNORED,
            SignalStatus.INVALIDATED,
            SignalStatus.EXPIRED,
        }
    ),
    SignalStatus.MANUALLY_ACCEPTED: frozenset({SignalStatus.POSITION_REPORTED, SignalStatus.IGNORED}),
    SignalStatus.POSITION_REPORTED: frozenset({SignalStatus.CLOSED}),
    SignalStatus.IGNORED: frozenset({SignalStatus.EVALUATED}),
    SignalStatus.CLOSED: frozenset({SignalStatus.EVALUATED}),
    SignalStatus.INVALIDATED: frozenset(),
    SignalStatus.EXPIRED: frozenset(),
    SignalStatus.EVALUATED: frozenset(),
}

_EXPIRABLE = frozenset(
    status for status, targets in _TRANSITIONS.items() if SignalStatus.EXPIRED in targets
)

_OPEN = frozenset(
    {
        SignalStatus.DETECTED,
        SignalStatus.WATCHLIST,
        SignalStatus.CONFIRMED,
        SignalStatus.TRADE_RECOMMENDED,
        SignalStatus.NOTIFIED,
        SignalStatus.MANUALLY_ACCEPTED,
        SignalStatus.POSITION_REPORTED,
    }
)


class InvalidTransition(NoiError):
    """The requested status is not a legal next step."""


@dataclass(frozen=True)
class Signal:
    signal_id: str
    index: IndexSymbol
    horizon: Horizon
    direction: str
    status: SignalStatus
    created_at: datetime
    expires_at: datetime
    reported_entry: Decimal | None = None
    reported_exit: Decimal | None = None


def transition(signal: Signal, status: SignalStatus) -> Signal:
    if status not in _TRANSITIONS[signal.status]:
        raise InvalidTransition(f"{signal.status.value} cannot move to {status.value}")
    return replace(signal, status=status)


def expire_due(signals: list[Signal], now: datetime) -> list[Signal]:
    updated: list[Signal] = []
    for signal in signals:
        if signal.status in _EXPIRABLE and now >= signal.expires_at:
            updated.append(transition(signal, SignalStatus.EXPIRED))
        else:
            updated.append(signal)
    return updated


def duplicate_of(existing: list[Signal], candidate: Signal) -> bool:
    for signal in existing:
        if signal.status not in _OPEN:
            continue
        if (
            signal.index is candidate.index
            and signal.horizon is candidate.horizon
            and signal.direction == candidate.direction
        ):
            return True
    return False
