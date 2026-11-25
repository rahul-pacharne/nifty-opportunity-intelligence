from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.core.constants import IndexSymbol, QualityStatus, Recommendation
from app.data.models import Bar
from app.options.eligibility import ContractQuote
from app.runtime.decision_loop import DecisionLoop


def _bar(day: date, instrument: str, close: str, *, published: datetime | None = None) -> Bar:
    close_d = Decimal(close)
    stamp = published or datetime(day.year, day.month, day.day, 10, 0, tzinfo=timezone.utc)
    return Bar(
        instrument_id=instrument,
        market_date=day,
        open=close_d - Decimal("1"),
        high=close_d + Decimal("1"),
        low=close_d - Decimal("2"),
        close=close_d,
        observation_at=stamp,
        publication_at=stamp,
        retrieved_at=stamp,
        source="fixture",
        version="1",
    )


def _quote(option_type: str = "CALL") -> ContractQuote:
    delta = Decimal("0.50") if option_type == "CALL" else Decimal("-0.50")
    return ContractQuote(
        instrument_id=f"{option_type}-ATM",
        option_type=option_type,
        strike=Decimal("24000"),
        delta=delta,
        bid=Decimal("100"),
        ask=Decimal("101"),
        volume=1000,
    )


def _rising_history(instrument: str) -> list[Bar]:
    start = date(2026, 11, 2)
    bars = []
    price = Decimal("100")
    for offset in range(14):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        price += Decimal("2")
        bars.append(_bar(day, instrument, str(price)))
    return bars


def test_monday_decision_cannot_see_tuesday_open() -> None:
    loop = DecisionLoop()
    monday = date(2026, 11, 23)
    tuesday = date(2026, 11, 24)
    loop.load(_rising_history(IndexSymbol.NIFTY.value))
    loop.load([
        _bar(monday, IndexSymbol.NIFTY.value, "140"),
        _bar(
            tuesday,
            IndexSymbol.NIFTY.value,
            "200",
            published=datetime(2026, 11, 24, 4, 0, tzinfo=timezone.utc),
        ),
    ])
    decision_at = datetime(2026, 11, 23, 15, 30, tzinfo=timezone.utc)
    record = loop.decide(index=IndexSymbol.NIFTY, decision_at=decision_at, quote=_quote(), capital=Decimal("50000"), expected_gross=Decimal("20"))
    assert record.latest_bar_date < tuesday
    assert record.latest_bar_date == monday


def test_missing_or_quarantined_data_is_no_trade() -> None:
    loop = DecisionLoop()
    bad = _bar(date(2026, 11, 23), IndexSymbol.NIFTY.value, "100")
    bad = Bar(**{**bad.__dict__, "quality": QualityStatus.QUARANTINED, "quality_reason": "stale_quote"})
    loop.load([bad])
    record = loop.decide(
        index=IndexSymbol.NIFTY,
        decision_at=datetime(2026, 11, 23, 15, 30, tzinfo=timezone.utc),
        quote=_quote(),
        capital=Decimal("50000"),
    )
    assert record.recommendation is Recommendation.NO_TRADE
    assert record.data_quality == "missing"


def test_no_completed_gap_has_no_probability_and_is_no_trade() -> None:
    loop = DecisionLoop()
    loop.load([_bar(date(2026, 11, 23), IndexSymbol.NIFTY.value, "100")])
    record = loop.decide(
        index=IndexSymbol.NIFTY,
        decision_at=datetime(2026, 11, 23, 15, 30, tzinfo=timezone.utc),
        quote=_quote(),
        capital=Decimal("50000"),
        expected_gross=Decimal("20"),
    )
    assert record.probability_up is None
    assert record.recommendation is Recommendation.NO_TRADE


def test_each_index_gets_its_own_forecast_row() -> None:
    loop = DecisionLoop()
    loop.load(_rising_history(IndexSymbol.NIFTY.value))
    loop.load(_rising_history(IndexSymbol.BANKNIFTY.value))
    when = datetime(2026, 11, 20, 15, 30, tzinfo=timezone.utc)
    nifty = loop.decide(index=IndexSymbol.NIFTY, decision_at=when, quote=_quote(), capital=Decimal("50000"), expected_gross=Decimal("20"))
    bank = loop.decide(index=IndexSymbol.BANKNIFTY, decision_at=when, quote=_quote(), capital=Decimal("50000"), expected_gross=Decimal("20"))
    assert nifty.index is IndexSymbol.NIFTY
    assert bank.index is IndexSymbol.BANKNIFTY
    assert nifty.model_version != bank.model_version
    assert loop.records[0] is nifty
    again = loop.decide(index=IndexSymbol.NIFTY, decision_at=when, quote=_quote(), capital=Decimal("50000"), expected_gross=Decimal("20"))
    assert loop.records[0].signal_id == nifty.signal_id
    assert again.version == 3
