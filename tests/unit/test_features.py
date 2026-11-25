from decimal import Decimal

from app.core.constants import Regime
from app.features.technical import ema, rsi
from app.intelligence.regime import classify_regime


def test_ema_does_not_use_the_future() -> None:
    closes = [Decimal(value) for value in range(1, 11)]
    full = ema(closes, 3)
    truncated = ema(closes[:5], 3)
    assert full[:5] == truncated


def test_rsi_is_bounded() -> None:
    rising = [Decimal(value) for value in range(1, 30)]
    values = rsi(rising, 14)
    assert values[-1] == Decimal("100")


def test_short_history_is_data_insufficient() -> None:
    closes = [Decimal("100")] * 5
    assert classify_regime(closes, closes, closes) is Regime.DATA_INSUFFICIENT


def test_rising_market_is_bullish_and_not_a_trade_enum() -> None:
    closes = [Decimal(100 + index) for index in range(40)]
    highs = [close + 1 for close in closes]
    lows = [close - 1 for close in closes]
    regime = classify_regime(closes, highs, lows)
    assert regime is Regime.BULLISH
    assert not hasattr(regime, "order")
