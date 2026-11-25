"""Baseline gap forecasts. A model is not alert-ready until evaluation says so."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.core.constants import DEFAULT_STRONG_GAP_PERCENT, Horizon, IndexSymbol


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Forecast:
    index: IndexSymbol
    horizon: Horizon
    model_version: str
    probability_up: Decimal
    probability_down: Decimal
    probability_flat: Decimal
    expected_gap: Decimal
    lower_gap: Decimal
    upper_gap: Decimal
    sample_size: int
    data_sufficient: bool = True


@dataclass(frozen=True)
class FoldResult:
    train_end: int
    test_start: int
    test_end: int
    brier: Decimal


def _bucket(gap: Decimal, theta: Decimal) -> str:
    if gap > theta:
        return "up"
    if gap < -theta:
        return "down"
    return "flat"


class BaseRateModel:
    """Historical frequencies. This is the benchmark other models must beat."""

    def __init__(
        self,
        index: IndexSymbol,
        horizon: Horizon,
        *,
        theta: Decimal = DEFAULT_STRONG_GAP_PERCENT,
    ) -> None:
        self.index = index
        self.horizon = horizon
        self.theta = theta
        self._gaps: tuple[Decimal, ...] = ()

    @property
    def model_version(self) -> str:
        return f"base-rate-{self.index.value}-{self.horizon.value}-theta-{self.theta}"

    def fit(self, gaps: list[Decimal]) -> None:
        self._gaps = tuple(gaps)

    def predict(self) -> Forecast:
        gaps = self._gaps
        if not gaps:
            return Forecast(
                index=self.index,
                horizon=self.horizon,
                model_version=self.model_version,
                probability_up=Decimal(0),
                probability_down=Decimal(0),
                probability_flat=Decimal(0),
                expected_gap=Decimal(0),
                lower_gap=Decimal(0),
                upper_gap=Decimal(0),
                sample_size=0,
                data_sufficient=False,
            )
        counts = {"up": 0, "down": 0, "flat": 0}
        for gap in gaps:
            counts[_bucket(gap, self.theta)] += 1
        total = Decimal(len(gaps))
        ordered = sorted(gaps)
        lower = ordered[len(ordered) // 4]
        upper = ordered[min(len(ordered) - 1, (len(ordered) * 3) // 4)]
        raw = {
            "up": Decimal(counts["up"]) / total,
            "down": Decimal(counts["down"]) / total,
            "flat": Decimal(counts["flat"]) / total,
        }
        rounded = {name: _q(value) for name, value in raw.items()}
        largest = max(rounded, key=lambda name: (raw[name], name))
        rounded[largest] += Decimal(1) - sum(rounded.values(), Decimal(0))
        return Forecast(
            index=self.index,
            horizon=self.horizon,
            model_version=self.model_version,
            probability_up=rounded["up"],
            probability_down=rounded["down"],
            probability_flat=rounded["flat"],
            expected_gap=_q(sum(gaps, Decimal(0)) / total),
            lower_gap=_q(lower),
            upper_gap=_q(upper),
            sample_size=len(gaps),
            data_sufficient=True,
        )


def brier_score(probabilities: list[tuple[Decimal, Decimal, Decimal]], outcomes: list[str]) -> Decimal:
    if len(probabilities) != len(outcomes) or not outcomes:
        raise ValueError("probabilities and outcomes must be the same non-empty length")
    names = ("up", "down", "flat")
    total = Decimal(0)
    for probs, outcome in zip(probabilities, outcomes):
        for name, probability in zip(names, probs):
            target = Decimal(1) if name == outcome else Decimal(0)
            total += (probability - target) ** 2
    return _q(total / Decimal(len(outcomes)))


def walk_forward(
    gaps: list[Decimal],
    *,
    index: IndexSymbol,
    horizon: Horizon,
    train_size: int,
    test_size: int,
    theta: Decimal = DEFAULT_STRONG_GAP_PERCENT,
) -> tuple[FoldResult, ...]:
    if train_size < 1 or test_size < 1:
        raise ValueError("windows must be positive")
    folds: list[FoldResult] = []
    start = 0
    while start + train_size + test_size <= len(gaps):
        train = gaps[start : start + train_size]
        test = gaps[start + train_size : start + train_size + test_size]
        model = BaseRateModel(index, horizon, theta=theta)
        model.fit(train)
        forecast = model.predict()
        probabilities = [
            (forecast.probability_up, forecast.probability_down, forecast.probability_flat)
        ] * len(test)
        outcomes = [_bucket(gap, theta) for gap in test]
        train_end = start + train_size
        test_start = train_end
        if test_start < train_end:
            raise AssertionError("test window overlaps training")
        folds.append(
            FoldResult(
                train_end=train_end,
                test_start=test_start,
                test_end=test_start + test_size,
                brier=brier_score(probabilities, outcomes),
            )
        )
        start += test_size
    return tuple(folds)


def alerts_approved(folds: tuple[FoldResult, ...], *, minimum_folds: int = 3) -> bool:
    """Phase 4 does not promote a model that has not been compared out of sample.

    The base-rate walk-forward has no competing model here, so alerts stay off.
    """
    return len(folds) >= minimum_folds and False
