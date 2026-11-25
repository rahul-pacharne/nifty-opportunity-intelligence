"""Telegram commands update records only. There is no broker method on this path."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from app.core.constants import SignalStatus
from app.signals.lifecycle import InvalidTransition, Signal, transition


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    message: str
    signal: Signal | None = None
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None


def handle_command(text: str, user_id: str, allowed: tuple[str, ...], signals: dict[str, Signal]) -> CommandResult:
    if user_id not in allowed:
        return CommandResult(False, "unauthorised")
    parts = text.strip().split()
    if not parts:
        return CommandResult(False, "empty")
    command = parts[0]
    if command in {"/start", "/status", "/today", "/signals", "/performance"}:
        return CommandResult(True, command)
    if command not in {"/accept", "/ignore", "/entered", "/exit"} or len(parts) < 2:
        return CommandResult(False, "invalid_command")
    signal = signals.get(parts[1])
    if signal is None:
        return CommandResult(False, "unknown_signal")
    try:
        if command == "/accept":
            return CommandResult(True, "accepted", transition(signal, SignalStatus.MANUALLY_ACCEPTED))
        if command == "/ignore":
            return CommandResult(True, "ignored", transition(signal, SignalStatus.IGNORED))
        price = Decimal(parts[2]) if len(parts) > 2 else None
        if price is None:
            return CommandResult(False, "price_required")
        if command == "/entered":
            updated = replace(transition(signal, SignalStatus.POSITION_REPORTED), reported_entry=price)
            return CommandResult(True, "position_reported", updated, entry_price=price)
        updated = replace(transition(signal, SignalStatus.CLOSED), reported_exit=price)
        return CommandResult(True, "closed", updated, exit_price=price)
    except InvalidTransition:
        return CommandResult(False, "invalid_transition")
    except InvalidOperation:
        return CommandResult(False, "invalid_price")
