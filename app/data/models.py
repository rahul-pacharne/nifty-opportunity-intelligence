"""Point-in-time market records. Payloads stay immutable."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.core.constants import IndexSymbol, QualityStatus


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    symbol: IndexSymbol
    kind: str
    expiry: date | None = None
    strike: Decimal | None = None
    option_type: str | None = None


@dataclass(frozen=True)
class Bar:
    instrument_id: str
    market_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    observation_at: datetime
    publication_at: datetime | None
    retrieved_at: datetime
    source: str
    version: str
    quality: QualityStatus = QualityStatus.OK
    quality_reason: str | None = None

    @property
    def available_at(self) -> datetime:
        return self.publication_at or self.observation_at


@dataclass(frozen=True)
class CoverageReport:
    first_date: date | None
    last_date: date | None
    row_count: int
    usable_count: int
    quarantined_count: int
    missing_sessions: tuple[date, ...]
    duplicate_keys: tuple[str, ...]
    rows_with_publication_time: int
