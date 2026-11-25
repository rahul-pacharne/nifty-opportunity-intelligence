from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.runtime.exits import ExitRules, PositionBook


RULES = ExitRules(premium_stop=Decimal("20"), premium_target=Decimal("30"), holding_time=timedelta(hours=6))
NOW = datetime(2026, 11, 25, 4, 0, tzinfo=timezone.utc)


def test_unreported_position_never_sells() -> None:
    book = PositionBook()
    assert book.check("missing", now=NOW, premium=Decimal("50"), invalidated=True) is None


def test_sell_uses_the_buy_signal_id_and_states_no_order() -> None:
    book = PositionBook()
    book.report_entry(
        signal_id="NOI-NIFTY-1",
        instrument="NIFTY-CALL",
        premium=Decimal("100"),
        entry_session=date(2026, 11, 25),
        entered_at=NOW,
        rules=RULES,
    )
    alert = book.check("NOI-NIFTY-1", now=NOW, premium=Decimal("140"))
    assert alert is not None
    assert alert.signal_id == "NOI-NIFTY-1"
    assert alert.reason == "premium_target"
    assert "No broker order has been placed." in alert.message


def test_hold_is_silent_and_a_sell_is_not_repeated() -> None:
    book = PositionBook()
    book.report_entry(
        signal_id="NOI-NIFTY-2",
        instrument="NIFTY-PUT",
        premium=Decimal("100"),
        entry_session=date(2026, 11, 25),
        entered_at=NOW,
        rules=RULES,
    )
    assert book.check("NOI-NIFTY-2", now=NOW, premium=Decimal("110")) is None
    first = book.check("NOI-NIFTY-2", now=NOW, invalidated=True)
    second = book.check("NOI-NIFTY-2", now=NOW, invalidated=True)
    assert first is not None and first.reason == "invalidation"
    assert second is None


def test_exit_command_records_a_price_without_deciding_to_sell() -> None:
    book = PositionBook()
    book.report_entry(
        signal_id="NOI-NIFTY-3",
        instrument="NIFTY-CALL",
        premium=Decimal("100"),
        entry_session=date(2026, 11, 25),
        entered_at=NOW,
        rules=RULES,
    )
    recorded = book.record_exit_price("NOI-NIFTY-3", Decimal("90"))
    assert recorded == Decimal("90")
    assert book.positions["NOI-NIFTY-3"].sold is False
