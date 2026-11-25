"""Notification text is filled by the caller. Example percentages are not defaults."""

from __future__ import annotations

from decimal import Decimal


def trade_alert(*, signal_id: str, probability: Decimal, expected_gap: Decimal, action: str) -> str:
    return (
        f"NOI | TRADE OPPORTUNITY\n"
        f"Signal ID: {signal_id}\n"
        f"Action: {action}\n"
        f"Model probability: {probability}\n"
        f"Expected gap: {expected_gap}\n"
        "This is a manually executed trade recommendation.\n"
        "No broker order has been placed."
    )
