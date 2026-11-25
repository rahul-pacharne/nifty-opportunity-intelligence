from datetime import timedelta
from decimal import Decimal

from app.core.constants import IndexSymbol, Recommendation
from app.notifications.whatsapp import WhatsAppChannel, WhatsAppOptInError
from app.runtime.decision_loop import DecisionLoop
from app.runtime.exits import ExitRules, PositionBook
from app.runtime.paper import PaperEvent, index_score, publish_paper, restore_paper, snapshot_paper
from app.runtime.telegram_gateway import MemoryTransport, TelegramGateway

RULES = ExitRules(Decimal("20"), Decimal("30"), timedelta(hours=6))


def test_hypothetical_and_reported_results_are_separate_per_index() -> None:
    gateway = TelegramGateway(("owner",), MemoryTransport(), PositionBook(), RULES)
    whatsapp = WhatsAppChannel(frozenset({"owner"}))
    log = publish_paper(
        [
            PaperEvent("N-1", IndexSymbol.NIFTY, Recommendation.BUY_CALL, ignored=True, hypothetical_pnl=Decimal("15")),
            PaperEvent("B-1", IndexSymbol.BANKNIFTY, Recommendation.BUY_PUT, reported_pnl=Decimal("-5")),
        ],
        gateway=gateway,
        chat_id="owner",
        whatsapp=whatsapp,
        whatsapp_recipient="owner",
    )
    nifty = index_score(log, IndexSymbol.NIFTY, "hypothetical")
    bank = index_score(log, IndexSymbol.BANKNIFTY, "reported")
    assert nifty.count == 1
    assert bank.count == 1
    assert index_score(log, IndexSymbol.NIFTY, "reported").count == 0
    assert any(message.startswith("Weekly") for message in log.emails)
    assert whatsapp.spend > 0


def test_whatsapp_without_opt_in_receives_nothing() -> None:
    gateway = TelegramGateway(("owner",), MemoryTransport(), PositionBook(), RULES)
    whatsapp = WhatsAppChannel(frozenset())
    log = publish_paper(
        [PaperEvent("N-2", IndexSymbol.NIFTY, Recommendation.BUY_CALL)],
        gateway=gateway,
        chat_id="owner",
        whatsapp=whatsapp,
        whatsapp_recipient="stranger",
    )
    assert log.whatsapp_sent == []
    assert whatsapp.sent == []
    try:
        whatsapp.send("stranger", "N-2", "buy", "text")
        raised = False
    except WhatsAppOptInError:
        raised = True
    assert raised is True


def test_restore_does_not_send_a_delivered_buy_again() -> None:
    transport = MemoryTransport()
    gateway = TelegramGateway(("owner",), transport, PositionBook(), RULES)
    loop = DecisionLoop()
    gateway.deliver("owner", "N-3", "buy", "BUY CALL")
    state = snapshot_paper(loop, gateway.book, gateway)
    restored_transport = MemoryTransport()
    restored = TelegramGateway(("owner",), restored_transport, PositionBook(), RULES)
    restore_paper(DecisionLoop(), restored.book, restored, state)
    assert restored.deliver("owner", "N-3", "buy", "BUY CALL") == "duplicate_suppressed"
    assert restored_transport.messages == []
