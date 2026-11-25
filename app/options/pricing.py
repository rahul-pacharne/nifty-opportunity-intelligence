"""European Black-Scholes prices and Greeks. Nifty and Bank Nifty options are European."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass(frozen=True)
class Greeks:
    price: Decimal
    delta: Decimal
    gamma: Decimal
    theta: Decimal
    vega: Decimal


def black_scholes(
    *,
    spot: float,
    strike: float,
    years: float,
    rate: float,
    volatility: float,
    option_type: str,
) -> Greeks:
    if spot <= 0 or strike <= 0 or years <= 0 or volatility <= 0:
        raise ValueError("spot, strike, time, and volatility must be positive")
    if option_type not in {"CALL", "PUT"}:
        raise ValueError("option_type must be CALL or PUT")
    sqrt_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * volatility**2) * years) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    discount = math.exp(-rate * years)
    if option_type == "CALL":
        price = spot * _cdf(d1) - strike * discount * _cdf(d2)
        delta = _cdf(d1)
    else:
        price = strike * discount * _cdf(-d2) - spot * _cdf(-d1)
        delta = _cdf(d1) - 1.0
    gamma = _pdf(d1) / (spot * volatility * sqrt_t)
    vega = spot * _pdf(d1) * sqrt_t / 100.0
    theta = (
        -(spot * _pdf(d1) * volatility) / (2.0 * sqrt_t)
        - rate * strike * discount * (_cdf(d2) if option_type == "CALL" else _cdf(-d2))
    ) / 365.0
    return Greeks(
        price=Decimal(str(round(price, 4))),
        delta=Decimal(str(round(delta, 4))),
        gamma=Decimal(str(round(gamma, 6))),
        theta=Decimal(str(round(theta, 4))),
        vega=Decimal(str(round(vega, 4))),
    )
