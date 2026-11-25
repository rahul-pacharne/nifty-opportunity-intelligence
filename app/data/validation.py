"""Quarantine rules for OHLC and quotes. Invalid rows are kept, not dropped silently."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

from app.core.constants import QualityStatus
from app.data.models import Bar


def _positive(value: Decimal) -> bool:
    return value > 0


def quarantine_reason(bar: Bar, *, now: datetime | None = None, max_age: timedelta | None = None) -> str | None:
    prices = (bar.open, bar.high, bar.low, bar.close)
    if not all(_positive(price) for price in prices):
        return "non_positive_price"
    if bar.high < max(bar.open, bar.close, bar.low):
        return "high_below_extreme"
    if bar.low > min(bar.open, bar.close, bar.high):
        return "low_above_extreme"
    if bar.observation_at.tzinfo is None or bar.retrieved_at.tzinfo is None:
        return "naive_timestamp"
    if bar.publication_at is not None and bar.publication_at.tzinfo is None:
        return "naive_timestamp"
    if not bar.instrument_id or not bar.source or not bar.version:
        return "missing_lineage"
    if max_age is not None and now is not None:
        if now - bar.observation_at > max_age:
            return "stale_quote"
    return None


def apply_validation(bar: Bar, *, now: datetime | None = None, max_age: timedelta | None = None) -> Bar:
    reason = quarantine_reason(bar, now=now, max_age=max_age)
    if reason is None:
        return bar
    return replace(bar, quality=QualityStatus.QUARANTINED, quality_reason=reason)
