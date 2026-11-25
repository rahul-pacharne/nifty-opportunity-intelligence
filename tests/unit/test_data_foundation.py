from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.core.constants import QualityStatus
from app.core.config import Settings
from app.data.calendar import MarketCalendar
from app.data.models import Bar
from app.data.repository import ObservationRepository
from app.data.validation import apply_validation


def _bar(**overrides: object) -> Bar:
    base = dict(
        instrument_id="NIFTY",
        market_date=date(2026, 11, 20),
        open=Decimal("24000"),
        high=Decimal("24100"),
        low=Decimal("23900"),
        close=Decimal("24050"),
        observation_at=datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc),
        publication_at=datetime(2026, 11, 20, 10, 5, tzinfo=timezone.utc),
        retrieved_at=datetime(2026, 11, 20, 10, 6, tzinfo=timezone.utc),
        source="nse",
        version="1",
    )
    base.update(overrides)
    return Bar(**base)  # type: ignore[arg-type]


def test_impossible_ohlc_is_quarantined() -> None:
    stored = apply_validation(_bar(high=Decimal("100")))
    assert stored.quality is QualityStatus.QUARANTINED
    assert stored.quality_reason == "high_below_extreme"


def test_stale_quote_is_quarantined() -> None:
    stored = apply_validation(
        _bar(),
        now=datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc),
        max_age=timedelta(hours=1),
    )
    assert stored.quality_reason == "stale_quote"


def test_repository_hides_rows_published_after_the_decision() -> None:
    repo = ObservationRepository()
    early = repo.add(_bar())
    repo.add(
        _bar(
            market_date=date(2026, 11, 23),
            version="2",
            publication_at=datetime(2026, 11, 23, 4, 0, tzinfo=timezone.utc),
            observation_at=datetime(2026, 11, 23, 3, 30, tzinfo=timezone.utc),
        )
    )
    visible = repo.usable_as_of(datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc))
    assert visible == (early,)


def test_duplicate_does_not_replace_the_original() -> None:
    repo = ObservationRepository()
    original = repo.add(_bar(close=Decimal("24050")))
    duplicate = repo.add(_bar(close=Decimal("99999")))
    assert original.quality is QualityStatus.OK
    assert duplicate.quality_reason == "duplicate"
    visible = repo.usable_as_of(datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc))
    assert visible == (original,)


def test_calendar_skips_weekends_and_holidays() -> None:
    calendar = MarketCalendar(holidays=frozenset({date(2026, 11, 23)}))
    assert calendar.is_session(date(2026, 11, 21)) is False
    assert calendar.is_session(date(2026, 11, 23)) is False
    assert calendar.next_session(date(2026, 11, 20)) == date(2026, 11, 24)


def test_coverage_reports_a_missing_session() -> None:
    calendar = MarketCalendar()
    repo = ObservationRepository(calendar)
    repo.add(_bar(market_date=date(2026, 11, 19)))
    repo.add(
        _bar(
            market_date=date(2026, 11, 23),
            version="2",
            observation_at=datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc),
            publication_at=datetime(2026, 11, 23, 10, 5, tzinfo=timezone.utc),
        )
    )
    report = repo.coverage("NIFTY")
    assert date(2026, 11, 20) in report.missing_sessions
    assert report.usable_count == 2


def test_settings_do_not_require_a_token(monkeypatch) -> None:
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("NOI_STRATEGY_CAPITAL", raising=False)
    settings = Settings.from_env()
    assert settings.upstox_access_token is None
    assert settings.strategy_capital is None
    assert settings.max_overnight_positions == 1
