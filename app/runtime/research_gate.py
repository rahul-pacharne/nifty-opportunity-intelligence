"""Package E. One index can be approved without approving the other."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.constants import DEFAULT_STRONG_GAP_PERCENT, Horizon, IndexSymbol
from app.intelligence.prediction import BaseRateModel, _bucket, brier_score


@dataclass(frozen=True)
class IndexGateReport:
    index: IndexSymbol
    sample_size: int
    model_brier: Decimal
    baseline_brier: Decimal
    strong_gap_precision: Decimal | None
    strong_gap_recall: Decimal | None
    magnitude_error: Decimal
    option_net: Decimal
    approved: bool


def _challenger(previous: Decimal, theta: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    if previous > theta:
        return Decimal("0.80"), Decimal("0.10"), Decimal("0.10")
    if previous < -theta:
        return Decimal("0.10"), Decimal("0.80"), Decimal("0.10")
    return Decimal("0.20"), Decimal("0.20"), Decimal("0.60")


def evaluate_index(
    gaps: list[Decimal],
    *,
    index: IndexSymbol,
    option_net: Decimal,
    holdout: int = 6,
    theta: Decimal = DEFAULT_STRONG_GAP_PERCENT,
) -> IndexGateReport:
    if len(gaps) <= holdout + 1:
        return IndexGateReport(index, len(gaps), Decimal(0), Decimal(0), None, None, Decimal(0), option_net, False)
    train = gaps[:-holdout]
    final = gaps[-holdout:]
    baseline = BaseRateModel(index, Horizon.T1, theta=theta)
    baseline.fit(train)
    forecast = baseline.predict()
    base_probs = [(forecast.probability_up, forecast.probability_down, forecast.probability_flat)] * len(final)
    outcomes = [_bucket(gap, theta) for gap in final]
    previous = train[-1]
    model_probs = []
    for gap in final:
        model_probs.append(_challenger(previous, theta))
        previous = gap
    model_brier = brier_score(model_probs, outcomes)
    baseline_brier = brier_score(base_probs, outcomes)
    predicted_up = [probs[0] >= probs[1] and probs[0] >= probs[2] for probs in model_probs]
    actual_up = [outcome == "up" for outcome in outcomes]
    true_positive = sum(1 for pred, actual in zip(predicted_up, actual_up) if pred and actual)
    predicted_positive = sum(1 for pred in predicted_up if pred)
    actual_positive = sum(1 for actual in actual_up if actual)
    precision = Decimal(true_positive) / Decimal(predicted_positive) if predicted_positive else None
    recall = Decimal(true_positive) / Decimal(actual_positive) if actual_positive else None
    magnitude_error = sum((abs(gap - forecast.expected_gap) for gap in final), Decimal(0)) / Decimal(len(final))
    approved = model_brier < baseline_brier and option_net >= 0
    return IndexGateReport(
        index=index,
        sample_size=len(final),
        model_brier=model_brier,
        baseline_brier=baseline_brier,
        strong_gap_precision=precision,
        strong_gap_recall=recall,
        magnitude_error=magnitude_error,
        option_net=option_net,
        approved=approved,
    )
