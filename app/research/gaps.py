"""Gap labels and horizon snapshots. Labels never leak into the feature side."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.core.constants import (
    DEFAULT_MODERATE_GAP_PERCENT,
    DEFAULT_STRONG_GAP_PERCENT,
    GapClass,
    Horizon,
    QualityStatus,
)
from app.data.calendar import MarketCalendar
from app.data.models import Bar, latest_session_bars


def opening_gap_percent(prior_close: Decimal, next_open: Decimal) -> Decimal:
    if prior_close <= 0:
        raise ValueError("prior close must be positive")
    return ((next_open - prior_close) / prior_close) * Decimal(100)


def classify_gap(
    gap_percent: Decimal,
    *,
    strong: Decimal = DEFAULT_STRONG_GAP_PERCENT,
    moderate: Decimal = DEFAULT_MODERATE_GAP_PERCENT,
) -> GapClass:
    if gap_percent > strong:
        return GapClass.STRONG_UP
    if gap_percent >= moderate:
        return GapClass.MODERATE_UP
    if gap_percent < -strong:
        return GapClass.STRONG_DOWN
    if gap_percent <= -moderate:
        return GapClass.MODERATE_DOWN
    return GapClass.FLAT


@dataclass(frozen=True)
class GapObservation:
    decision_date: date
    target_date: date
    horizon: Horizon
    prior_close: Decimal
    next_open: Decimal
    gap_percent: Decimal
    gap_class: GapClass
    decision_at: datetime


def _by_date(bars: tuple[Bar, ...]) -> dict[date, Bar]:
    return {bar.market_date: bar for bar in latest_session_bars(bars)}


def gap_observations(
    bars: tuple[Bar, ...],
    calendar: MarketCalendar,
    horizon: Horizon,
    *,
    strong: Decimal = DEFAULT_STRONG_GAP_PERCENT,
) -> tuple[GapObservation, ...]:
    """Label the open `steps` sessions after each decision close.

    The target open is the label only. It is not returned as a feature.
    """
    steps = {Horizon.T1: 1, Horizon.T2: 2, Horizon.T3: 3}[horizon]
    series = _by_date(bars)
    observations: list[GapObservation] = []
    for day, bar in series.items():
        target = calendar.shift_session(day, steps)
        target_bar = series.get(target)
        if target_bar is None:
            continue
        if bar.quality is not QualityStatus.OK or target_bar.quality is not QualityStatus.OK:
            continue
        gap = opening_gap_percent(bar.close, target_bar.open)
        observations.append(
            GapObservation(
                decision_date=day,
                target_date=target,
                horizon=horizon,
                prior_close=bar.close,
                next_open=target_bar.open,
                gap_percent=gap.quantize(Decimal("0.0001")),
                gap_class=classify_gap(gap, strong=strong),
                decision_at=bar.available_at,
            )
        )
    return tuple(observations)


def class_rates(observations: tuple[GapObservation, ...]) -> dict[GapClass, Decimal]:
    if not observations:
        return {}
    total = Decimal(len(observations))
    counts = {kind: 0 for kind in GapClass}
    for item in observations:
        counts[item.gap_class] += 1
    return {kind: (Decimal(count) / total).quantize(Decimal("0.0001")) for kind, count in counts.items()}


def continuation_rate(bars: tuple[Bar, ...], calendar: MarketCalendar) -> Decimal | None:
    """Share of T+1 gaps whose session return has the same sign.

    A flat gap is excluded. Continuation means the cash session close
    finished on the same side of the open as the gap.
    """
    labeled = gap_observations(bars, calendar, Horizon.T1)
    series = _by_date(bars)
    matched = 0
    considered = 0
    for item in labeled:
        if item.gap_class is GapClass.FLAT:
            continue
        session = series[item.target_date]
        session_move = session.close - session.open
        gap_move = item.next_open - item.prior_close
        if session_move == 0 or gap_move == 0:
            continue
        considered += 1
        if (session_move > 0) == (gap_move > 0):
            matched += 1
    if considered == 0:
        return None
    return (Decimal(matched) / Decimal(considered)).quantize(Decimal("0.0001"))
