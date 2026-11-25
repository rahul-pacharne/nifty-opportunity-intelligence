"""Package A. One decision from saved bars. Past decisions are never overwritten."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.constants import Horizon, IndexSymbol, Recommendation
from app.data.calendar import MarketCalendar
from app.data.models import Bar
from app.data.repository import ObservationRepository
from app.features.technical import ema
from app.intelligence.prediction import BaseRateModel
from app.options.eligibility import ContractQuote, EligibilityInput, decide
from app.research.gaps import gap_observations


@dataclass(frozen=True)
class StoredDecision:
    version: int
    index: IndexSymbol
    decision_at: datetime
    recommendation: Recommendation
    signal_id: str
    model_version: str
    probability_up: Decimal | None
    probability_down: Decimal | None
    probability_flat: Decimal | None
    expected_gap: Decimal | None
    data_quality: str
    feature_ema: Decimal | None
    latest_bar_date: object | None


class DecisionLoop:
    def __init__(self, repository: ObservationRepository | None = None, calendar: MarketCalendar | None = None) -> None:
        self.repository = repository or ObservationRepository(calendar)
        self.calendar = calendar or MarketCalendar()
        self.records: list[StoredDecision] = []

    def load(self, bars: list[Bar]) -> None:
        for bar in bars:
            self.repository.add(bar)

    def decide(
        self,
        *,
        index: IndexSymbol,
        decision_at: datetime,
        quote: ContractQuote | None = None,
        capital: Decimal | None = None,
        costs: Decimal = Decimal("0"),
        expected_gross: Decimal = Decimal("0"),
        quantity: int = 1,
    ) -> StoredDecision:
        visible = self.repository.usable_as_of(decision_at, index.value)
        version = len(self.records) + 1
        signal_id = f"NOI-{index.value}-{decision_at:%Y%m%d}-{version:03d}"
        if not visible:
            return self._append(
                version=version,
                index=index,
                decision_at=decision_at,
                recommendation=Recommendation.NO_TRADE,
                signal_id=signal_id,
                model_version="",
                probability_up=None,
                probability_down=None,
                probability_flat=None,
                expected_gap=None,
                data_quality="missing",
                feature_ema=None,
                latest_bar_date=None,
            )
        ordered = tuple(sorted(visible, key=lambda bar: bar.market_date))
        closes = [bar.close for bar in ordered]
        feature = ema(closes, 5)[-1]
        gaps = [
            item.gap_percent
            for item in gap_observations(ordered, self.calendar, Horizon.T1)
            if item.decision_at <= decision_at
        ]
        model = BaseRateModel(index, Horizon.T1)
        model.fit(gaps)
        forecast = model.predict()
        if not forecast.data_sufficient:
            recommendation = Recommendation.NO_TRADE
            direction = ""
            probability = None
        else:
            direction, probability = _direction(forecast.probability_up, forecast.probability_down, forecast.probability_flat)
            if direction == "flat":
                recommendation = Recommendation.WATCHLIST
            else:
                recommendation = decide(
                    EligibilityInput(
                        direction=direction,
                        quote=quote,
                        expected_gross=expected_gross,
                        costs=costs,
                        premium=quote.ask if quote is not None else Decimal("0"),
                        capital=capital,
                        max_risk_fraction=Decimal("0.01"),
                        open_positions=0,
                        max_positions=1,
                        data_ok=True,
                        quantity=quantity,
                        strong_probability=probability,
                    )
                )
        stored = self._append(
            version=version,
            index=index,
            decision_at=decision_at,
            recommendation=recommendation,
            signal_id=signal_id,
            model_version=forecast.model_version,
            probability_up=forecast.probability_up if forecast.data_sufficient else None,
            probability_down=forecast.probability_down if forecast.data_sufficient else None,
            probability_flat=forecast.probability_flat if forecast.data_sufficient else None,
            expected_gap=forecast.expected_gap if forecast.data_sufficient else None,
            data_quality="ok" if forecast.data_sufficient else "no_probability",
            feature_ema=feature,
            latest_bar_date=ordered[-1].market_date,
        )
        return stored

    def _append(self, **kwargs: object) -> StoredDecision:
        record = StoredDecision(**kwargs)  # type: ignore[arg-type]
        self.records.append(record)
        return record


def _direction(up: Decimal, down: Decimal, flat: Decimal) -> tuple[str, Decimal]:
    if up >= down and up >= flat:
        return "up", up
    if down >= up and down >= flat:
        return "down", down
    return "flat", flat
