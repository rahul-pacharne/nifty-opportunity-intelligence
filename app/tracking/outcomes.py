"""Scorecards keep hypothetical recommendations apart from reported fills."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.core.constants import DEFAULT_STRONG_GAP_PERCENT


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PredictionOutcome:
    signal_id: str
    predicted_direction: str
    predicted_gap: Decimal
    actual_gap: Decimal

    @property
    def direction_hit(self) -> bool:
        if self.predicted_direction == "up":
            return self.actual_gap > 0
        if self.predicted_direction == "down":
            return self.actual_gap < 0
        return abs(self.actual_gap) <= DEFAULT_STRONG_GAP_PERCENT

    @property
    def magnitude_error(self) -> Decimal:
        return _q(abs(self.actual_gap - self.predicted_gap))


@dataclass(frozen=True)
class TrackedTrade:
    signal_id: str
    kind: str
    entry_premium: Decimal
    exit_premium: Decimal

    @property
    def pnl(self) -> Decimal:
        return _q(self.exit_premium - self.entry_premium)


@dataclass(frozen=True)
class Scorecard:
    kind: str
    count: int
    winners: int
    average_win: Decimal | None
    average_loss: Decimal | None
    profit_factor: Decimal | None


def scorecard(trades: list[TrackedTrade], kind: str) -> Scorecard:
    selected = [trade for trade in trades if trade.kind == kind]
    wins = [trade.pnl for trade in selected if trade.pnl > 0]
    losses = [trade.pnl for trade in selected if trade.pnl < 0]
    gross_profit = sum(wins, Decimal(0))
    gross_loss = abs(sum(losses, Decimal(0)))
    factor = _q(gross_profit / gross_loss) if gross_loss else None
    return Scorecard(
        kind=kind,
        count=len(selected),
        winners=len(wins),
        average_win=_q(gross_profit / Decimal(len(wins))) if wins else None,
        average_loss=_q(sum(losses, Decimal(0)) / Decimal(len(losses))) if losses else None,
        profit_factor=factor,
    )


def drift_detected(older_hit_rate: Decimal, recent_hit_rate: Decimal, *, drop: Decimal = Decimal("0.15")) -> bool:
    return older_hit_rate - recent_hit_rate >= drop
