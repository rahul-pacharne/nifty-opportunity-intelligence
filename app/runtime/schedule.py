"""Market-aware clock. Times are interpreted in Asia/Kolkata."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.data.calendar import MarketCalendar

IST = ZoneInfo("Asia/Kolkata")


def scheduled_activity(moment: datetime, calendar: MarketCalendar | None = None) -> str:
    local = moment.astimezone(IST)
    calendar = calendar or MarketCalendar()
    if not calendar.is_session(local.date()) and _during_cash_session(local.hour, local.minute):
        return "market_holiday"
    minutes = local.hour * 60 + local.minute
    if 6 * 60 + 30 <= minutes < 8 * 60:
        return "overnight_global_analysis"
    if 8 * 60 <= minutes < 9 * 60 + 15:
        return "premarket_collection"
    if minutes == 9 * 60 + 15:
        return "opening_assessment"
    if 9 * 60 + 15 < minutes < 12 * 60:
        return "live_monitoring"
    if 12 * 60 <= minutes < 14 * 60:
        return "midsession_assessment"
    if 14 * 60 <= minutes < 14 * 60 + 30:
        return "overnight_opportunity_evaluation"
    if 14 * 60 + 30 <= minutes < 15 * 60:
        return "prediction_refresh"
    if 15 * 60 <= minutes <= 15 * 60 + 20:
        return "final_trade_eligibility"
    if 15 * 60 + 20 < minutes < 16 * 60:
        return "post_close_derivatives"
    if 16 * 60 <= minutes < 22 * 60:
        return "evening_forecast"
    return "maintenance"


def _during_cash_session(hour: int, minute: int) -> bool:
    minutes = hour * 60 + minute
    return 9 * 60 + 15 <= minutes <= 15 * 60 + 30
