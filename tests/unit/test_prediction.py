from decimal import Decimal

from app.core.constants import Horizon, IndexSymbol
from app.intelligence.prediction import BaseRateModel, alerts_approved, walk_forward


def test_uneven_buckets_still_sum_to_one() -> None:
    model = BaseRateModel(IndexSymbol.NIFTY, Horizon.T1, theta=Decimal("0.75"))
    model.fit([Decimal("1"), Decimal("-1"), Decimal("0")])
    forecast = model.predict()
    total = forecast.probability_up + forecast.probability_down + forecast.probability_flat
    assert total == Decimal("1.0000")
    assert forecast.data_sufficient is True


def test_empty_sample_is_not_a_forecast() -> None:
    model = BaseRateModel(IndexSymbol.NIFTY, Horizon.T1)
    forecast = model.predict()
    assert forecast.data_sufficient is False
    assert forecast.sample_size == 0


def test_probabilities_sum_to_one_and_name_the_index() -> None:
    model = BaseRateModel(IndexSymbol.NIFTY, Horizon.T1, theta=Decimal("0.75"))
    model.fit([Decimal("1"), Decimal("-1"), Decimal("0"), Decimal("0.2")])
    forecast = model.predict()
    total = forecast.probability_up + forecast.probability_down + forecast.probability_flat
    assert total == Decimal("1.0000")
    assert forecast.index is IndexSymbol.NIFTY
    assert forecast.horizon is Horizon.T1
    assert "BANKNIFTY" not in forecast.model_version


def test_banknifty_model_is_a_different_version() -> None:
    nifty = BaseRateModel(IndexSymbol.NIFTY, Horizon.T2)
    bank = BaseRateModel(IndexSymbol.BANKNIFTY, Horizon.T3)
    assert nifty.model_version != bank.model_version


def test_walk_forward_never_trains_on_the_test_rows() -> None:
    gaps = [Decimal(index) / Decimal(10) for index in range(-20, 20)]
    folds = walk_forward(
        gaps,
        index=IndexSymbol.NIFTY,
        horizon=Horizon.T1,
        train_size=10,
        test_size=5,
    )
    assert folds
    for fold in folds:
        assert fold.test_start == fold.train_end
        assert fold.test_end > fold.test_start


def test_base_rate_walk_forward_does_not_approve_alerts() -> None:
    gaps = [Decimal("0")] * 40
    folds = walk_forward(
        gaps,
        index=IndexSymbol.BANKNIFTY,
        horizon=Horizon.T1,
        train_size=10,
        test_size=5,
    )
    assert alerts_approved(folds) is False
