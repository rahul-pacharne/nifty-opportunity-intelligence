from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.constants import Horizon, IndexSymbol, SignalStatus
from app.notifications.commands import handle_command
from app.notifications.dispatcher import Dispatcher, RecordingChannel
from app.signals.lifecycle import Signal, duplicate_of, expire_due, transition


def _signal(status: SignalStatus = SignalStatus.NOTIFIED, direction: str = "up") -> Signal:
    now = datetime(2026, 11, 25, 9, 0, tzinfo=timezone.utc)
    return Signal(
        signal_id="NOI-NIFTY-20261125-001",
        index=IndexSymbol.NIFTY,
        horizon=Horizon.T1,
        direction=direction,
        status=status,
        created_at=now,
        expires_at=now + timedelta(hours=6),
    )


def test_cannot_skip_from_detected_to_notified() -> None:
    try:
        transition(_signal(SignalStatus.DETECTED), SignalStatus.NOTIFIED)
    except Exception as exc:
        assert type(exc).__name__ == "InvalidTransition"
    else:
        raise AssertionError("expected an invalid transition")


def test_duplicate_open_signal_is_rejected() -> None:
    existing = [_signal()]
    assert duplicate_of(existing, _signal(direction="up")) is True
    assert duplicate_of(existing, _signal(direction="down")) is False


def test_expiry_closes_an_open_signal() -> None:
    signal = _signal()
    expired = expire_due([signal], signal.expires_at)[0]
    assert expired.status is SignalStatus.EXPIRED


def test_dispatcher_retries_then_suppresses_a_second_copy() -> None:
    channel = RecordingChannel("telegram", fail_times=1)
    dispatcher = Dispatcher([channel])
    first = dispatcher.notify("S1", "trade", "body")
    second = dispatcher.notify("S1", "trade", "body")
    assert first[0].status == "sent"
    assert first[0].attempts == 2
    assert second[0].status == "duplicate_suppressed"
    assert len(channel.sent) == 1


def test_unauthorised_user_and_commands_do_not_change_a_signal() -> None:
    signal = _signal()
    denied = handle_command("/accept NOI-NIFTY-20261125-001", "stranger", ("owner",), {signal.signal_id: signal})
    assert denied.ok is False
    accepted = handle_command(
        "/accept NOI-NIFTY-20261125-001",
        "owner",
        ("owner",),
        {signal.signal_id: signal},
    )
    assert accepted.signal is not None
    assert accepted.signal.status is SignalStatus.MANUALLY_ACCEPTED
    reported = handle_command(
        "/entered NOI-NIFTY-20261125-001 102.5",
        "owner",
        ("owner",),
        {signal.signal_id: accepted.signal},
    )
    assert reported.entry_price == Decimal("102.5")
    assert reported.signal is not None
    assert reported.signal.status is SignalStatus.POSITION_REPORTED
