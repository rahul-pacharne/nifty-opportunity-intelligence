"""WhatsApp delivery. A recipient must already have opted in."""

from __future__ import annotations

from decimal import Decimal


class WhatsAppOptInError(PermissionError):
    """The recipient has not opted in."""


class WhatsAppChannel:
    def __init__(self, opted_in: frozenset[str], template_cost: Decimal = Decimal("0.01")) -> None:
        self.opted_in = opted_in
        self.template_cost = template_cost
        self.sent: list[tuple[str, str]] = []
        self.deliveries: list[tuple[str, str, str]] = []
        self.spend = Decimal("0")

    def send(self, recipient: str, signal_id: str, category: str, body: str) -> None:
        if recipient not in self.opted_in:
            raise WhatsAppOptInError(recipient)
        self.sent.append((signal_id, body))
        self.deliveries.append((recipient, signal_id, "sent"))
        self.spend += self.template_cost
