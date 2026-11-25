"""Contract filters and the BUY CALL / BUY PUT / NO TRADE decision."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.constants import Recommendation

_DELTA_BANDS = (
    (Decimal("0.45"), Decimal("0.55")),
    (Decimal("0.60"), Decimal("0.70")),
)


@dataclass(frozen=True)
class ContractQuote:
    instrument_id: str
    option_type: str
    strike: Decimal
    delta: Decimal
    bid: Decimal
    ask: Decimal
    volume: int


@dataclass(frozen=True)
class EligibilityInput:
    direction: str
    quote: ContractQuote | None
    expected_gross: Decimal
    costs: Decimal
    premium: Decimal
    capital: Decimal | None
    max_risk_fraction: Decimal
    open_positions: int
    max_positions: int
    data_ok: bool
    quantity: int = 1
    minimum_net: Decimal = Decimal("0")
    max_spread_fraction: Decimal = Decimal("0.05")
    minimum_volume: int = 1


def spread_fraction(quote: ContractQuote) -> Decimal | None:
    if quote.bid <= 0 or quote.ask <= 0 or quote.ask < quote.bid:
        return None
    mid = (quote.bid + quote.ask) / Decimal(2)
    if mid <= 0:
        return None
    return (quote.ask - quote.bid) / mid


def expected_net_value(expected_gross: Decimal, costs: Decimal) -> Decimal:
    return expected_gross - costs


def delta_in_research_band(delta: Decimal) -> bool:
    magnitude = abs(delta)
    return any(low <= magnitude <= high for low, high in _DELTA_BANDS)


def select_by_delta(quotes: list[ContractQuote], target: Decimal) -> ContractQuote | None:
    if not quotes:
        return None
    return min(quotes, key=lambda quote: abs(quote.delta - target))


def decide(item: EligibilityInput) -> Recommendation:
    if not item.data_ok or item.quote is None:
        return Recommendation.NO_TRADE
    if item.open_positions >= item.max_positions:
        return Recommendation.NO_TRADE
    if item.capital is None or item.capital <= 0 or item.quantity < 1:
        return Recommendation.NO_TRADE
    if not delta_in_research_band(item.quote.delta):
        return Recommendation.NO_TRADE
    premium_at_risk = item.premium * Decimal(item.quantity)
    if premium_at_risk > item.capital * item.max_risk_fraction:
        return Recommendation.NO_TRADE
    width = spread_fraction(item.quote)
    if width is None or width > item.max_spread_fraction or item.quote.volume < item.minimum_volume:
        return Recommendation.NO_TRADE
    net = expected_net_value(item.expected_gross, item.costs)
    if net <= item.minimum_net:
        return Recommendation.NO_TRADE
    if item.direction == "up" and item.quote.option_type == "CALL":
        return Recommendation.BUY_CALL
    if item.direction == "down" and item.quote.option_type == "PUT":
        return Recommendation.BUY_PUT
    return Recommendation.NO_TRADE
