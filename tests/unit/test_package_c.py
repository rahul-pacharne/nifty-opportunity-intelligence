from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.runtime.exits import ExitRules, PositionBook
from app.runtime.telegram_gateway import MemoryTransport, TelegramGateway

NOW = datetime(2026, 11, 25, 9, 0, tzinfo=timezone.utc)
RULES = ExitRules(Decimal("20"), Decimal("30"), timedelta(hours=6))


def _gateway(fail_times: int = 0) -> tuple[TelegramGateway, MemoryTransport]:
    transport = MemoryTransport(fail_times=fail_times)
    gateway = TelegramGateway(("owner",), transport, PositionBook(), RULES)
    return gateway, transport


def test_unknown_user_gets_nothing_and_changes_nothing() -> None:
    gateway, transport = _gateway()
    assert gateway.handle("stranger", "/status", now=NOW) == "unauthorised"
    assert gateway.deliver("stranger", "NOI-1", "buy", "BUY CALL") == "rejected"
    assert transport.messages == []
    assert gateway.book.positions == {}


def test_the_same_buy_is_sent_once() -> None:
    gateway, transport = _gateway()
    assert gateway.deliver("owner", "NOI-1", "buy", "BUY CALL") == "sent"
    assert gateway.deliver("owner", "NOI-1", "buy", "BUY CALL") == "duplicate_suppressed"
    assert transport.messages == [("owner", "BUY CALL")]


def test_a_failed_send_does_not_create_a_signal() -> None:
    gateway, _transport = _gateway(fail_times=2)
    before = list(gateway.signals)
    assert gateway.deliver("owner", "NOI-1", "buy", "BUY CALL") == "failed"
    assert gateway.signals == before
    assert ("NOI-1", "buy") not in gateway.sent


def test_entered_stores_the_premium_and_arms_a_sell() -> None:
    gateway, _transport = _gateway()
    assert gateway.handle("owner", "/entered NOI-9 105", now=NOW, instrument="NIFTY-CALL") == "position_reported"
    position = gateway.book.positions["NOI-9"]
    assert position.entry_premium == Decimal("105")
    alert = gateway.book.check("NOI-9", now=NOW, premium=Decimal("150"))
    assert alert is not None
    assert alert.signal_id == "NOI-9"
