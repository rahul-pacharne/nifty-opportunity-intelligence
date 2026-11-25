"""Rule-based regime. Callers must pass only bars available at the decision time."""

from __future__ import annotations

from decimal import Decimal

from app.core.constants import Regime
from app.features.technical import atr, ema


def classify_regime(
    closes: list[Decimal],
    highs: list[Decimal],
    lows: list[Decimal],
) -> Regime:
    if len(closes) < 20 or len(closes) != len(highs) or len(closes) != len(lows):
        return Regime.DATA_INSUFFICIENT
    ema_fast = ema(closes, 5)
    ema_slow = ema(closes, 20)
    atrs = atr(highs, lows, closes, 14)
    if ema_fast[-1] is None or ema_slow[-1] is None or atrs[-1] is None:
        return Regime.DATA_INSUFFICIENT
    recent = [value for value in atrs[-20:] if value is not None]
    if len(recent) < 5:
        return Regime.DATA_INSUFFICIENT
    latest = atrs[-1]
    assert latest is not None
    ordered = sorted(recent)
    low_cut = ordered[max(0, int(len(ordered) * Decimal("0.20")) - 1)]
    high_cut = ordered[min(len(ordered) - 1, int(len(ordered) * Decimal("0.80")))]
    if latest < low_cut:
        return Regime.VOL_COMPRESSION
    if latest > high_cut:
        return Regime.VOL_EXPANSION
    if ema_fast[-1] > ema_slow[-1] and closes[-1] > ema_slow[-1]:
        return Regime.BULLISH
    if ema_fast[-1] < ema_slow[-1] and closes[-1] < ema_slow[-1]:
        return Regime.BEARISH
    return Regime.SIDEWAYS
