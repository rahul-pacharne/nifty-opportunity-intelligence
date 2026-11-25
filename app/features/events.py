"""Event proximity. A nearby event is context. It does not assign a direction."""

from __future__ import annotations

from datetime import date


def event_proximity_days(session: date, event_day: date) -> int:
    return abs((event_day - session).days)
