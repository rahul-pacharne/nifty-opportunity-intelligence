"""Alert text for the sample catalogue. Values are supplied by the caller."""

from __future__ import annotations

from decimal import Decimal


def trade_alert(
    *,
    signal_id: str,
    probability: Decimal,
    expected_gap: Decimal,
    action: str,
    maximum_entry_premium: Decimal | None = None,
    generated_at: str = "IST",
) -> str:
    premium = "not supplied" if maximum_entry_premium is None else str(maximum_entry_premium)
    return (
        f"NOI | TRADE OPPORTUNITY\n"
        f"Signal ID: {signal_id}\n"
        f"Action: {action}\n"
        f"Model probability: {probability}\n"
        f"Expected gap: {expected_gap}\n"
        f"Maximum entry premium: {premium}\n"
        f"Generated at: {generated_at}\n"
        "This is a manually executed trade recommendation.\n"
        "No broker order has been placed."
    )


def early_warning(*, signal_id: str, market: str) -> str:
    return (
        f"Alert type: Early warning\n"
        f"Signal ID: {signal_id}\n"
        f"Market: {market}\n"
        "Recommendation: WATCH\n"
        "No trade recommended at this stage."
    )


def prepare_for_call(*, signal_id: str) -> str:
    return (
        f"Signal ID: {signal_id}\n"
        "Recommendation: PREPARE FOR CALL\n"
        "The final evaluation runs during the premarket session.\n"
        "This is not a buy yet."
    )


def buy_call(
    *,
    signal_id: str,
    maximum_entry_premium: Decimal,
    target_delta: str,
) -> str:
    return (
        f"Trade recommendation: BUY CALL\n"
        f"Signal ID: {signal_id}\n"
        f"Maximum entry premium: {maximum_entry_premium}\n"
        f"Target delta: {target_delta}\n"
        "Liquidity check: supplied by the evaluator\n"
        "Subject to manual confirmation.\n"
        "NOI does not execute broker orders."
    )


def buy_put(*, signal_id: str, market: str, maximum_entry_premium: Decimal) -> str:
    return (
        f"Trade recommendation: BUY PUT\n"
        f"Signal ID: {signal_id}\n"
        f"Market: {market}\n"
        f"Maximum entry premium: {maximum_entry_premium}\n"
        "Subject to manual confirmation.\n"
        "NOI does not execute broker orders."
    )


def no_trade(*, signal_id: str, reason: str) -> str:
    return (
        f"Signal ID: {signal_id}\n"
        "Action: NO TRADE\n"
        f"Reason: {reason}\n"
        "A no-trade decision is a successful risk-management outcome."
    )


def invalidation(*, signal_id: str) -> str:
    return (
        f"Signal ID: {signal_id}\n"
        "Current status: INVALIDATED\n"
        "Do not enter based on the previous signal.\n"
        "The previous recommendation is cancelled."
    )


def premarket_confirmation(*, signal_id: str) -> str:
    return (
        f"Alert type: Premarket confirmation\n"
        f"Signal ID: {signal_id}\n"
        "Option premium must be reevaluated after the open.\n"
        "A large opening gap can make the entry unattractive."
    )


def no_new_entry(*, signal_id: str) -> str:
    return (
        f"Signal ID: {signal_id}\n"
        "The market prediction can be correct and the entry can still be poor.\n"
        "Final decision: NO NEW ENTRY"
    )


def daily_report(*, nifty_status: str, bank_nifty_status: str) -> str:
    return (
        "Report type: Daily intelligence\n"
        f"Nifty status: {nifty_status}\n"
        f"Bank Nifty status: {bank_nifty_status}\n"
        "The two indexes are reported separately."
    )
