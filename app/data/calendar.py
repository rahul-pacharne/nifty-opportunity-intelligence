"""Session calendar. Weekends and injected holidays are closed. Special sessions can be opened."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class MarketCalendar:
    holidays: frozenset[date] = frozenset()
    special_sessions: frozenset[date] = frozenset()

    def is_session(self, day: date) -> bool:
        if day in self.special_sessions:
            return True
        if day.weekday() >= 5:
            return False
        return day not in self.holidays

    def sessions_between(self, start: date, end: date) -> tuple[date, ...]:
        if end < start:
            return ()
        days = []
        cursor = start
        while cursor <= end:
            if self.is_session(cursor):
                days.append(cursor)
            cursor += timedelta(days=1)
        return tuple(days)

    def next_session(self, day: date) -> date:
        cursor = day + timedelta(days=1)
        while not self.is_session(cursor):
            cursor += timedelta(days=1)
        return cursor

    def previous_session(self, day: date) -> date:
        cursor = day - timedelta(days=1)
        while not self.is_session(cursor):
            cursor -= timedelta(days=1)
        return cursor

    def shift_session(self, day: date, sessions: int) -> date:
        if sessions == 0:
            if not self.is_session(day):
                raise ValueError("anchor is not a session")
            return day
        cursor = day
        step = 1 if sessions > 0 else -1
        remaining = abs(sessions)
        while remaining:
            cursor = self.next_session(cursor) if step > 0 else self.previous_session(cursor)
            remaining -= 1
        return cursor
