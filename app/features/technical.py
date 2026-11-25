"""Indicators. Index i depends only on observations 0..i."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def ema(values: list[Decimal], period: int) -> list[Decimal | None]:
    if period < 1:
        raise ValueError("period must be positive")
    out: list[Decimal | None] = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period], Decimal(0)) / Decimal(period)
    out[period - 1] = _q(seed)
    alpha = Decimal(2) / Decimal(period + 1)
    previous = seed
    for index in range(period, len(values)):
        previous = values[index] * alpha + previous * (1 - alpha)
        out[index] = _q(previous)
    return out


def sma(values: list[Decimal], period: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    if period < 1:
        raise ValueError("period must be positive")
    running = Decimal(0)
    for index, value in enumerate(values):
        running += value
        if index >= period:
            running -= values[index - period]
        if index >= period - 1:
            out[index] = _q(running / Decimal(period))
    return out


def true_ranges(highs: list[Decimal], lows: list[Decimal], closes: list[Decimal]) -> list[Decimal]:
    ranges: list[Decimal] = []
    for index, (high, low) in enumerate(zip(highs, lows)):
        if index == 0:
            ranges.append(high - low)
            continue
        previous_close = closes[index - 1]
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return ranges


def atr(highs: list[Decimal], lows: list[Decimal], closes: list[Decimal], period: int) -> list[Decimal | None]:
    return ema(true_ranges(highs, lows, closes), period)


def adx(highs: list[Decimal], lows: list[Decimal], closes: list[Decimal], period: int = 14) -> list[Decimal | None]:
    """Wilder ADX. Index i uses only bars 0..i."""
    if period < 1:
        raise ValueError("period must be positive")
    size = len(closes)
    out: list[Decimal | None] = [None] * size
    if size <= period * 2 or not (len(highs) == size == len(lows)):
        return out
    plus_dm: list[Decimal] = [Decimal(0)]
    minus_dm: list[Decimal] = [Decimal(0)]
    ranges = true_ranges(highs, lows, closes)
    for index in range(1, size):
        up = highs[index] - highs[index - 1]
        down = lows[index - 1] - lows[index]
        plus_dm.append(up if up > down and up > 0 else Decimal(0))
        minus_dm.append(down if down > up and down > 0 else Decimal(0))
    tr_smooth = sum(ranges[1 : period + 1], Decimal(0))
    plus_smooth = sum(plus_dm[1 : period + 1], Decimal(0))
    minus_smooth = sum(minus_dm[1 : period + 1], Decimal(0))
    dx_values: list[Decimal] = []
    for index in range(period + 1, size):
        tr_smooth = tr_smooth - (tr_smooth / Decimal(period)) + ranges[index]
        plus_smooth = plus_smooth - (plus_smooth / Decimal(period)) + plus_dm[index]
        minus_smooth = minus_smooth - (minus_smooth / Decimal(period)) + minus_dm[index]
        if tr_smooth == 0:
            dx_values.append(Decimal(0))
            continue
        plus_di = Decimal(100) * plus_smooth / tr_smooth
        minus_di = Decimal(100) * minus_smooth / tr_smooth
        total = plus_di + minus_di
        dx_values.append(Decimal(0) if total == 0 else Decimal(100) * abs(plus_di - minus_di) / total)
    if len(dx_values) < period:
        return out
    adx_value = sum(dx_values[:period], Decimal(0)) / Decimal(period)
    start = period * 2
    if start < size:
        out[start] = _q(adx_value)
    for offset, dx in enumerate(dx_values[period:], start=start + 1):
        if offset >= size:
            break
        adx_value = (adx_value * (period - 1) + dx) / Decimal(period)
        out[offset] = _q(adx_value)
    return out


def rsi(closes: list[Decimal], period: int = 14) -> list[Decimal | None]:
    if period < 1:
        raise ValueError("period must be positive")
    out: list[Decimal | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for index in range(1, period + 1):
        change = closes[index] - closes[index - 1]
        gains.append(max(change, Decimal(0)))
        losses.append(max(-change, Decimal(0)))
    avg_gain = sum(gains, Decimal(0)) / Decimal(period)
    avg_loss = sum(losses, Decimal(0)) / Decimal(period)
    out[period] = _rsi_value(avg_gain, avg_loss)
    for index in range(period + 1, len(closes)):
        change = closes[index] - closes[index - 1]
        gain = max(change, Decimal(0))
        loss = max(-change, Decimal(0))
        avg_gain = (avg_gain * (period - 1) + gain) / Decimal(period)
        avg_loss = (avg_loss * (period - 1) + loss) / Decimal(period)
        out[index] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: Decimal, avg_loss: Decimal) -> Decimal:
    if avg_loss == 0:
        return Decimal("100")
    relative = avg_gain / avg_loss
    return _q(Decimal(100) - (Decimal(100) / (1 + relative)))


def bollinger_width(closes: list[Decimal], period: int = 20, stdevs: Decimal = Decimal(2)) -> list[Decimal | None]:
    mids = sma(closes, period)
    out: list[Decimal | None] = [None] * len(closes)
    for index, mid in enumerate(mids):
        if mid is None or mid == 0:
            continue
        window = closes[index - period + 1 : index + 1]
        mean = sum(window, Decimal(0)) / Decimal(period)
        variance = sum((point - mean) ** 2 for point in window) / Decimal(period)
        sigma = variance.sqrt()
        upper = mid + stdevs * sigma
        lower = mid - stdevs * sigma
        out[index] = _q((upper - lower) / mid)
    return out
