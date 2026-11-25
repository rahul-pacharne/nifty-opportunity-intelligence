from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.constants import Recommendation
from app.data.calendar import MarketCalendar
from app.runtime.health import health
from app.runtime.orchestrator import recommendation_allowed
from app.runtime.schedule import scheduled_activity


def test_provider_outage_is_degraded_not_healthy() -> None:
    report = health(database_ok=True, scheduler_ok=True, provider_ok=False)
    assert report.status == "degraded"


def test_database_outage_is_down() -> None:
    report = health(database_ok=False, scheduler_ok=True, provider_ok=True)
    assert report.status == "down"


def test_unapproved_model_cannot_recommend() -> None:
    decision = recommendation_allowed(
        data_ok=True,
        model_approved=False,
        option_decision=Recommendation.BUY_CALL,
    )
    assert decision is Recommendation.NO_TRADE


def test_bad_data_cannot_recommend() -> None:
    decision = recommendation_allowed(
        data_ok=False,
        model_approved=True,
        option_decision=Recommendation.BUY_PUT,
    )
    assert decision is Recommendation.NO_TRADE


def test_holiday_during_the_session_is_not_live_monitoring() -> None:
    moment = datetime(2026, 11, 23, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    calendar = MarketCalendar(holidays=frozenset({moment.date()}))
    assert scheduled_activity(moment, calendar) == "market_holiday"


def test_premarket_slot() -> None:
    moment = datetime(2026, 11, 25, 8, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert scheduled_activity(moment) == "premarket_collection"
