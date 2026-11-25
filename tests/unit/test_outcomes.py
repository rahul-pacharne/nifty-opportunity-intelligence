from decimal import Decimal

from app.tracking.outcomes import PredictionOutcome, TrackedTrade, drift_detected, scorecard


def test_ignored_and_reported_trades_stay_on_separate_scorecards() -> None:
    trades = [
        TrackedTrade("a", "hypothetical", Decimal("100"), Decimal("130")),
        TrackedTrade("b", "hypothetical", Decimal("100"), Decimal("80")),
        TrackedTrade("c", "reported", Decimal("100"), Decimal("90")),
    ]
    hypothetical = scorecard(trades, "hypothetical")
    reported = scorecard(trades, "reported")
    assert hypothetical.count == 2
    assert hypothetical.winners == 1
    assert reported.count == 1
    assert reported.winners == 0
    assert hypothetical.profit_factor == Decimal("1.5000")


def test_direction_and_magnitude() -> None:
    outcome = PredictionOutcome("a", "up", Decimal("0.80"), Decimal("0.40"))
    assert outcome.direction_hit is True
    assert outcome.magnitude_error == Decimal("0.4000")


def test_drift_when_recent_accuracy_falls() -> None:
    assert drift_detected(Decimal("0.60"), Decimal("0.40")) is True
    assert drift_detected(Decimal("0.60"), Decimal("0.55")) is False
