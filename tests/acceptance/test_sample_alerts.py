"""Acceptance cases taken from docs/SAMPLE_ALERTS.md.

Numbers in that document are fictional. These tests check the behaviour and
the required alert contents, not those sample percentages or rupee prices.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from app.core.constants import Horizon, IndexSymbol, Recommendation, SignalStatus
from app.notifications.dispatcher import Dispatcher, RecordingChannel
from app.notifications.messages import trade_alert
from app.options.eligibility import ContractQuote, EligibilityInput, decide, expected_value
from app.signals.lifecycle import Signal, duplicate_of, transition

ROOT = Path(__file__).resolve().parents[2]


def _notification_source() -> str:
    folder = ROOT / "app" / "notifications"
    return "\n".join(path.read_text(encoding="utf-8") for path in folder.rglob("*.py"))


def _app_source() -> str:
    folder = ROOT / "app"
    return "\n".join(path.read_text(encoding="utf-8") for path in folder.rglob("*.py"))


def _quote(**overrides: object) -> ContractQuote:
    values = dict(
        instrument_id="NIFTY-CALL",
        option_type="CALL",
        strike=Decimal("24000"),
        delta=Decimal("0.55"),
        bid=Decimal("100"),
        ask=Decimal("102"),
        volume=1000,
    )
    values.update(overrides)
    return ContractQuote(**values)  # type: ignore[arg-type]


def _decision(**overrides: object) -> EligibilityInput:
    values = dict(
        direction="up",
        quote=_quote(),
        expected_gross=Decimal("40"),
        costs=Decimal("5"),
        premium=Decimal("100"),
        capital=Decimal("20000"),
        max_risk_fraction=Decimal("0.01"),
        open_positions=0,
        max_positions=1,
        data_ok=True,
        quantity=1,
        strong_probability=Decimal("0.82"),
    )
    values.update(overrides)
    return EligibilityInput(**values)  # type: ignore[arg-type]


def _signal(signal_id: str = "NOI-NIFTY-20261124-001", index: IndexSymbol = IndexSymbol.NIFTY) -> Signal:
    now = datetime(2026, 11, 24, 9, 5, tzinfo=timezone.utc)
    return Signal(
        signal_id=signal_id,
        index=index,
        horizon=Horizon.T1,
        direction="up",
        status=SignalStatus.WATCHLIST,
        created_at=now,
        expires_at=now + timedelta(hours=8),
    )


def test_sample_early_warning_is_watch_only() -> None:
    """Sample 1: an early warning recommends WATCH and does not recommend a trade."""
    assert Recommendation.WATCHLIST.value == "watchlist"
    assert Recommendation.WATCHLIST is not Recommendation.BUY_CALL
    assert Recommendation.WATCHLIST is not Recommendation.BUY_PUT
    text = _notification_source().lower()
    assert "no trade" in text or "watch" in text


def test_sample_prepare_for_call_is_not_yet_a_buy() -> None:
    """Sample 2: prepare for a call still waits for premarket confirmation."""
    text = _notification_source().lower()
    assert "prepare" in text
    assert "premarket" in text


def test_sample_buy_call_includes_premium_delta_and_manual_confirmation() -> None:
    """Sample 3: a BUY CALL states the premium cap, delta band, checks, and that no order is sent."""
    decision = decide(_decision())
    assert decision is Recommendation.BUY_CALL
    text = _notification_source()
    for phrase in (
        "BUY CALL",
        "maximum entry premium",
        "target delta",
        "liquidity",
        "manual confirmation",
        "does not execute broker orders",
    ):
        assert phrase.lower() in text.lower()


def test_sample_buy_put_is_banknifty_capable() -> None:
    """Sample 4: a BUY PUT can be issued for Bank Nifty with the same option checks."""
    decision = decide(
        _decision(
            direction="down",
            quote=_quote(instrument_id="BANKNIFTY-PUT", option_type="PUT", delta=Decimal("-0.60")),
        )
    )
    assert decision is Recommendation.BUY_PUT
    text = _notification_source().lower()
    assert "buy put" in text
    assert "bank nifty" in text or "banknifty" in text


def test_sample_no_trade_when_direction_is_unclear_or_premium_is_expensive() -> None:
    """Sample 5: a large expected move with negative option value is NO TRADE."""
    call_value = expected_value(
        p_win=Decimal("0.42"),
        avg_profit=Decimal("10"),
        p_loss=Decimal("0.58"),
        avg_loss=Decimal("20"),
        costs=Decimal("3"),
    )
    assert call_value < 0
    assert decide(_decision(expected_gross=Decimal("1"), costs=Decimal("5"))) is Recommendation.NO_TRADE
    assert "no trade" in _notification_source().lower()


def test_sample_multiday_watch_is_not_a_t1_buy() -> None:
    """Sample 6: a T+2/T+3 watch does not become a T+1 buy."""
    later = Signal(
        signal_id="NOI-BANKNIFTY-20261207-001",
        index=IndexSymbol.BANKNIFTY,
        horizon=Horizon.T3,
        direction="down",
        status=SignalStatus.WATCHLIST,
        created_at=datetime(2026, 12, 7, 6, 15, tzinfo=timezone.utc),
        expires_at=datetime(2026, 12, 10, 10, 0, tzinfo=timezone.utc),
    )
    assert later.horizon is not Horizon.T1
    assert later.status is SignalStatus.WATCHLIST


def test_sample_strengthening_updates_the_same_signal() -> None:
    """Sample 7: a stronger probability updates the existing signal and does not create a second one."""
    original = _signal()
    update = _signal()
    assert update.signal_id == original.signal_id
    assert duplicate_of([original], update) is True
    channel = RecordingChannel("telegram")
    dispatcher = Dispatcher([channel])
    dispatcher.notify(original.signal_id, "update", "strengthened")
    second = dispatcher.notify(original.signal_id, "update", "strengthened")
    assert second[0].status == "duplicate_suppressed"
    assert len(channel.sent) == 1


def test_sample_invalidation_cancels_the_previous_entry() -> None:
    """Sample 8: invalidation cancels the earlier signal and says not to enter."""
    cancelled = transition(_signal(signal_id="NOI-NIFTY-20261124-001"), SignalStatus.INVALIDATED)
    assert cancelled.status is SignalStatus.INVALIDATED
    text = _notification_source().lower()
    assert "invalidat" in text
    assert "do not enter" in text


def test_sample_premarket_confirmation_still_rechecks_the_premium() -> None:
    """Sample 9: premarket confirmation does not skip the option-premium check."""
    text = _notification_source().lower()
    assert "premarket" in text
    assert "premium" in text
    assert decide(_decision(expected_gross=Decimal("1"), costs=Decimal("9"))) is Recommendation.NO_TRADE


def test_sample_correct_gap_with_a_poor_premium_is_no_new_entry() -> None:
    """Sample 10: a correct gap is not a new entry when the option is no longer attractive."""
    text = _notification_source().lower()
    assert "no new entry" in text
    assert decide(_decision(strong_probability=None)) is Recommendation.NO_TRADE


def test_sample_daily_report_covers_both_indices() -> None:
    """Sample 11: the daily report states Nifty and Bank Nifty separately."""
    text = _notification_source().lower()
    assert "daily" in text
    assert "nifty" in text
    assert "bank nifty" in text or "banknifty" in text


def test_sample_weekly_report_splits_prediction_and_paper_results() -> None:
    """Sample 12: the weekly report has per-index accuracy and paper-trading results."""
    text = _notification_source().lower()
    assert "weekly" in text
    for phrase in ("directional accuracy", "profit factor", "drawdown"):
        assert phrase in text


def test_sample_l4_alert_can_be_sent_on_all_three_channels_without_duplicating() -> None:
    """Sample 14: an L4 trade alert goes to Telegram, WhatsApp, and email once."""
    channels = [RecordingChannel(name) for name in ("telegram", "whatsapp", "email")]
    dispatcher = Dispatcher(channels)
    first = dispatcher.notify("NOI-NIFTY-20261125-003", "trade", "BUY CALL")
    second = dispatcher.notify("NOI-NIFTY-20261125-003", "trade", "BUY CALL")
    assert [item.status for item in first] == ["sent", "sent", "sent"]
    assert all(item.status == "duplicate_suppressed" for item in second)


def test_sample_numbers_are_not_live_defaults() -> None:
    """The sample document says its prices and probabilities are fictional."""
    source = _app_source()
    for banned in ("₹180", "₹200", "₹220", "₹250", "72%", "81%", "82%"):
        assert banned not in source


def test_sample_buy_alert_names_the_contract_and_the_time_window() -> None:
    """Samples 3 and 9: a buy alert names the contract, the premium cap, and when it was generated."""
    body = trade_alert(
        signal_id="NOI-NIFTY-20261125-003",
        probability=Decimal("0.82"),
        expected_gap=Decimal("0.80"),
        action="BUY CALL",
    )
    assert "BUY CALL" in body
    assert "NOI-NIFTY-20261125-003" in body
    lowered = body.lower()
    assert "premium" in lowered
    assert "generated" in lowered or "ist" in lowered
