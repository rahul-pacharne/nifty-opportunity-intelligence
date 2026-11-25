from decimal import Decimal

from app.core.constants import Recommendation
from app.options.eligibility import ContractQuote, EligibilityInput, decide, select_by_delta
from app.options.pricing import black_scholes


def _quote(**overrides: object) -> ContractQuote:
    base = dict(
        instrument_id="NIFTY-CALL",
        option_type="CALL",
        strike=Decimal("24000"),
        delta=Decimal("0.50"),
        bid=Decimal("100"),
        ask=Decimal("102"),
        volume=1000,
    )
    base.update(overrides)
    return ContractQuote(**base)  # type: ignore[arg-type]


def _input(quote: ContractQuote | None, **overrides: object) -> EligibilityInput:
    base = dict(
        direction="up",
        quote=quote,
        expected_gross=Decimal("50"),
        costs=Decimal("5"),
        premium=Decimal("100"),
        capital=Decimal("20000"),
        max_risk_fraction=Decimal("0.01"),
        open_positions=0,
        max_positions=1,
        data_ok=True,
    )
    base.update(overrides)
    return EligibilityInput(**base)  # type: ignore[arg-type]


def test_atm_call_delta_is_near_one_half() -> None:
    greeks = black_scholes(spot=100, strike=100, years=30 / 365, rate=0.06, volatility=0.15, option_type="CALL")
    assert Decimal("0.45") < greeks.delta < Decimal("0.65")
    assert greeks.price > 0


def test_put_delta_is_negative() -> None:
    greeks = black_scholes(spot=100, strike=100, years=30 / 365, rate=0.06, volatility=0.15, option_type="PUT")
    assert greeks.delta < 0


def test_negative_net_value_is_no_trade() -> None:
    decision = decide(_input(_quote(), expected_gross=Decimal("1"), costs=Decimal("5")))
    assert decision is Recommendation.NO_TRADE


def test_wide_market_is_no_trade() -> None:
    decision = decide(_input(_quote(bid=Decimal("10"), ask=Decimal("20"))))
    assert decision is Recommendation.NO_TRADE


def test_passing_call_is_a_manual_recommendation() -> None:
    decision = decide(_input(_quote()))
    assert decision is Recommendation.BUY_CALL


def test_selector_picks_the_closer_delta() -> None:
    chosen = select_by_delta(
        [
            _quote(instrument_id="far", delta=Decimal("0.20")),
            _quote(instrument_id="near", delta=Decimal("0.62")),
        ],
        Decimal("0.65"),
    )
    assert chosen is not None
    assert chosen.instrument_id == "near"
