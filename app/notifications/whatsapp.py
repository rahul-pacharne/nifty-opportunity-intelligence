"""WhatsApp delivery. A recipient must already have opted in."""

from __future__ import annotations


class WhatsAppOptInError(PermissionError):
    """The recipient has not opted in."""


class WhatsAppChannel:
    def __init__(self, opted_in: frozenset[str]) -> None:
        self.opted_in = opted_in
        self.sent: list[tuple[str, str]] = []

    def send(self, recipient: str, signal_id: str, category: str, body: str) -> None:
        if recipient not in self.opted_in:
            raise WhatsAppOptInError(recipient)
        self.sent.append((signal_id, body))
