from datetime import date, datetime, timezone
from decimal import Decimal

from app.core.constants import GapClass, Horizon
from app.data.calendar import MarketCalendar
from app.data.models import Bar
from app.research.gaps import classify_gap, continuation_rate, gap_observations, opening_gap_percent


def _bar(day: date, open_: str, close: str) -> Bar:
    high = str(max(Decimal(open_), Decimal(close)) + 1)
    low = str(min(Decimal(open_), Decimal(close)) - 1)
    stamp = datetime(day.year, day.month, day.day, 10, 0, tzinfo=timezone.utc)
    return Bar(
        instrument_id="NIFTY",
        market_date=day,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        observation_at=stamp,
        publication_at=stamp,
        retrieved_at=stamp,
        source="fixture",
        version="1",
    )


def test_gap_formula_matches_the_specification() -> None:
    gap = opening_gap_percent(Decimal("100"), Decimal("101"))
    assert gap == Decimal("1")


def test_default_classes() -> None:
    assert classify_gap(Decimal("0.80")) is GapClass.STRONG_UP
    assert classify_gap(Decimal("0.40")) is GapClass.MODERATE_UP
    assert classify_gap(Decimal("0")) is GapClass.FLAT
    assert classify_gap(Decimal("-0.40")) is GapClass.MODERATE_DOWN
    assert classify_gap(Decimal("-0.90")) is GapClass.STRONG_DOWN


def test_t3_label_does_not_use_the_intermediate_open_as_the_prior_close() -> None:
    calendar = MarketCalendar()
    bars = (
        _bar(date(2026, 11, 18), "100", "100"),
        _bar(date(2026, 11, 19), "110", "110"),
        _bar(date(2026, 11, 20), "90", "90"),
        _bar(date(2026, 11, 23), "103", "103"),
    )
    labeled = gap_observations(bars, calendar, Horizon.T3)
    first = labeled[0]
    assert first.decision_date == date(2026, 11, 18)
    assert first.target_date == date(2026, 11, 23)
    assert first.prior_close == Decimal("100")
    assert first.next_open == Decimal("103")
    assert first.gap_percent == Decimal("3.0000")


def test_continuation_uses_the_session_after_the_gap() -> None:
    calendar = MarketCalendar()
    bars = (
        _bar(date(2026, 11, 19), "100", "100"),
        _bar(date(2026, 11, 20), "102", "103"),
    )
    rate = continuation_rate(bars, calendar)
    assert rate == Decimal("1.0000")
