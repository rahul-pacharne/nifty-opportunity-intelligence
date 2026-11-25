"""Product constants from the approved baseline. Thresholds stay configurable."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum


class IndexSymbol(str, Enum):
    NIFTY = "NIFTY"
    BANKNIFTY = "BANKNIFTY"


class Horizon(str, Enum):
    T1 = "T+1"
    T2 = "T+2"
    T3 = "T+3"


class GapClass(str, Enum):
    STRONG_UP = "strong_gap_up"
    MODERATE_UP = "moderate_gap_up"
    FLAT = "flat"
    MODERATE_DOWN = "moderate_gap_down"
    STRONG_DOWN = "strong_gap_down"


class QualityStatus(str, Enum):
    OK = "ok"
    QUARANTINED = "quarantined"


class Recommendation(str, Enum):
    BUY_CALL = "consider_buy_call"
    BUY_PUT = "consider_buy_put"
    WATCHLIST = "watchlist"
    NO_TRADE = "no_trade"


class SignalStatus(str, Enum):
    DETECTED = "DETECTED"
    WATCHLIST = "WATCHLIST"
    CONFIRMED = "CONFIRMED"
    TRADE_RECOMMENDED = "TRADE_RECOMMENDED"
    NOTIFIED = "NOTIFIED"
    MANUALLY_ACCEPTED = "MANUALLY_ACCEPTED"
    IGNORED = "IGNORED"
    POSITION_REPORTED = "POSITION_REPORTED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"
    EVALUATED = "EVALUATED"


class Regime(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    VOL_COMPRESSION = "volatility_compression"
    VOL_EXPANSION = "volatility_expansion"
    HIGH_UNCERTAINTY = "high_uncertainty"
    EVENT_RISK = "event_driven_risk"
    DATA_INSUFFICIENT = "data_insufficient"


DEFAULT_STRONG_GAP_PERCENT = Decimal("0.75")
DEFAULT_MODERATE_GAP_PERCENT = Decimal("0.30")
DEFAULT_MAX_OVERNIGHT_POSITIONS = 1
DEFAULT_MAX_RISK_FRACTION = Decimal("0.01")
RESEARCH_GAP_THRESHOLDS = (
    Decimal("0.50"),
    Decimal("0.75"),
    Decimal("1.00"),
    Decimal("1.50"),
)
