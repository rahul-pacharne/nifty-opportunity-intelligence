"""The only path that may emit a recommendation. Bad data or an unapproved model cannot."""

from __future__ import annotations

from app.core.constants import Recommendation


def recommendation_allowed(
    *,
    data_ok: bool,
    model_approved: bool,
    option_decision: Recommendation,
) -> Recommendation:
    if not data_ok or not model_approved:
        return Recommendation.NO_TRADE
    return option_decision
