"""Package C. Telegram sends alerts and accepts commands from allow-listed users."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.runtime.exits import ExitRules, PositionBook


@dataclass
class MemoryTransport:
    fail_times: int = 0
    messages: list[tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        if self.messages is None:
            self.messages = []

    def send(self, chat_id: str, text: str) -> None:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError("telegram unavailable")
        assert self.messages is not None
        self.messages.append((chat_id, text))


class TelegramGateway:
    def __init__(
        self,
        allowed_user_ids: tuple[str, ...],
        transport: MemoryTransport,
        book: PositionBook,
        rules: ExitRules,
        store=None,
    ) -> None:
        self.allowed = set(allowed_user_ids)
        self.transport = transport
        self.book = book
        self.rules = rules
        self.store = store
        self.sent: set[tuple[str, str]] = set(store.load_sent()) if store is not None else set()
        self.deliveries: list[tuple[str, str, str, str]] = []
        self.signals: list[str] = []

    def deliver(self, chat_id: str, signal_id: str, alert_type: str, text: str) -> str:
        if chat_id not in self.allowed:
            self.deliveries.append((chat_id, signal_id, alert_type, "rejected"))
            return "rejected"
        key = (signal_id, alert_type)
        if key in self.sent:
            self.deliveries.append((chat_id, signal_id, alert_type, "duplicate_suppressed"))
            return "duplicate_suppressed"
        attempts = 0
        while attempts < 2:
            attempts += 1
            try:
                self.transport.send(chat_id, text)
            except ConnectionError:
                continue
            if self.store is not None:
                self.store.save_delivery(chat_id, signal_id, alert_type, "sent", attempts, text)
            self.sent.add(key)
            self.deliveries.append((chat_id, signal_id, alert_type, "sent"))
            return "sent"
        self.deliveries.append((chat_id, signal_id, alert_type, "failed"))
        return "failed"

    def handle(self, chat_id: str, text: str, *, now: datetime, instrument: str = "NIFTY-CALL") -> str:
        if chat_id not in self.allowed:
            return "unauthorised"
        parts = text.strip().split()
        if not parts:
            return "empty"
        command = parts[0]
        if command in {"/start", "/status", "/today", "/signals", "/performance"}:
            return command
        if command == "/entered" and len(parts) >= 3:
            try:
                premium = Decimal(parts[2])
            except InvalidOperation:
                return "invalid_price"
            self.book.report_entry(
                signal_id=parts[1],
                instrument=instrument,
                premium=premium,
                entry_session=now.date(),
                entered_at=now,
                rules=self.rules,
            )
            return "position_reported"
        if command == "/exit" and len(parts) >= 3:
            try:
                price = Decimal(parts[2])
            except InvalidOperation:
                return "invalid_price"
            recorded = self.book.record_exit_price(parts[1], price)
            return "recorded" if recorded is not None else "unknown_signal"
        if command in {"/accept", "/ignore"} and len(parts) >= 2:
            return command
        return "invalid_command"
