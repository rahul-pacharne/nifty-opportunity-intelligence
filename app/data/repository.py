"""In-memory observation store with point-in-time reads.

PostgreSQL is the deployment store. This repository is the tested contract:
usable rows only, no row whose available time is after the decision time,
and duplicate keys are quarantined rather than overwriting history.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.core.constants import QualityStatus
from app.data.calendar import MarketCalendar
from app.data.models import Bar, CoverageReport
from app.data.validation import apply_validation


def _key(bar: Bar) -> str:
    return f"{bar.instrument_id}|{bar.market_date.isoformat()}|{bar.source}|{bar.version}"


class ObservationRepository:
    def __init__(self, calendar: MarketCalendar | None = None) -> None:
        self._calendar = calendar or MarketCalendar()
        self._rows: list[Bar] = []
        self._seen: set[str] = set()

    def add(self, bar: Bar) -> Bar:
        stored = apply_validation(bar)
        key = _key(stored)
        if key in self._seen:
            stored = replace(stored, quality=QualityStatus.QUARANTINED, quality_reason="duplicate")
        self._seen.add(key)
        self._rows.append(stored)
        return stored

    def usable_as_of(self, decision_at: datetime, instrument_id: str | None = None) -> tuple[Bar, ...]:
        if decision_at.tzinfo is None:
            raise ValueError("decision timestamp must be timezone-aware")
        selected = []
        for bar in self._rows:
            if bar.quality is not QualityStatus.OK:
                continue
            if instrument_id is not None and bar.instrument_id != instrument_id:
                continue
            if bar.available_at <= decision_at:
                selected.append(bar)
        return tuple(selected)

    def coverage(self, instrument_id: str) -> CoverageReport:
        rows = [bar for bar in self._rows if bar.instrument_id == instrument_id]
        usable = [bar for bar in rows if bar.quality is QualityStatus.OK]
        dates = [bar.market_date for bar in usable]
        missing: tuple[date, ...] = ()
        if dates:
            expected = self._calendar.sessions_between(min(dates), max(dates))
            present = {bar.market_date for bar in usable}
            missing = tuple(day for day in expected if day not in present)
        duplicates = tuple(
            _key(bar) for bar in rows if bar.quality_reason == "duplicate"
        )
        return CoverageReport(
            first_date=min(dates) if dates else None,
            last_date=max(dates) if dates else None,
            row_count=len(rows),
            usable_count=len(usable),
            quarantined_count=len(rows) - len(usable),
            missing_sessions=missing,
            duplicate_keys=duplicates,
            rows_with_publication_time=sum(1 for bar in rows if bar.publication_at is not None),
        )
