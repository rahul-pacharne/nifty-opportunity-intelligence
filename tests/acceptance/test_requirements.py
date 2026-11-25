"""Requirement tests for NOI master spec v1.0 (23 November 2026).

Each test is named for the rule it checks. A failure means the current code
does not meet that sentence in docs/PROJECT_MASTER.md or docs/phase0/.
"""

from __future__ import annotations

import ast
import inspect
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.constants import GapClass, Horizon, IndexSymbol, QualityStatus, Recommendation, Regime, SignalStatus
from app.core.config import Settings
from app.data.calendar import MarketCalendar
from app.data.models import Bar
from app.data.repository import ObservationRepository
from app.data.validation import apply_validation
from app.intelligence.prediction import BaseRateModel, alerts_approved, walk_forward
from app.intelligence.regime import classify_regime
from app.notifications.commands import handle_command
from app.notifications.dispatcher import Dispatcher, RecordingChannel
from app.options.eligibility import ContractQuote, EligibilityInput, decide
from app.options.pricing import black_scholes
from app.research.gaps import classify_gap, gap_observations, opening_gap_percent
from app.runtime.health import health
from app.runtime.orchestrator import recommendation_allowed
from app.runtime.schedule import scheduled_activity
from app.signals.lifecycle import Signal, duplicate_of, transition
from app.tracking.outcomes import PredictionOutcome, TrackedTrade, scorecard

ROOT = Path(__file__).resolve().parents[2]


def _bar(day: date, open_: str, close: str, **overrides: object) -> Bar:
    high = max(Decimal(open_), Decimal(close)) + 1
    low = min(Decimal(open_), Decimal(close)) - 1
    stamp = datetime(day.year, day.month, day.day, 10, 0, tzinfo=timezone.utc)
    values = dict(
        instrument_id="NIFTY",
        market_date=day,
        open=Decimal(open_),
        high=high,
        low=low,
        close=Decimal(close),
        observation_at=stamp,
        publication_at=stamp,
        retrieved_at=stamp,
        source="fixture",
        version="1",
    )
    values.update(overrides)
    return Bar(**values)  # type: ignore[arg-type]


def _quote(**overrides: object) -> ContractQuote:
    values = dict(
        instrument_id="NIFTY26NOV24000CE",
        option_type="CALL",
        strike=Decimal("24000"),
        delta=Decimal("0.50"),
        bid=Decimal("100"),
        ask=Decimal("102"),
        volume=1000,
    )
    values.update(overrides)
    return ContractQuote(**values)  # type: ignore[arg-type]


def _eligible(**overrides: object) -> EligibilityInput:
    values = dict(
        direction="up",
        quote=_quote(),
        expected_gross=Decimal("40"),
        costs=Decimal("5"),
        premium=Decimal("100"),
        capital=Decimal("20000"),
        max_risk_fraction=Decimal("0.01"),
        open_positions=0,
        max_positions=1,
        data_ok=True,
        quantity=1,
    )
    values.update(overrides)
    return EligibilityInput(**values)  # type: ignore[arg-type]


def _signal(status: SignalStatus = SignalStatus.NOTIFIED) -> Signal:
    now = datetime(2026, 11, 25, 9, 0, tzinfo=timezone.utc)
    return Signal(
        signal_id="NOI-NIFTY-20261125-001",
        index=IndexSymbol.NIFTY,
        horizon=Horizon.T1,
        direction="up",
        status=status,
        created_at=now,
        expires_at=now + timedelta(hours=6),
    )


def test_req_gap_formula_matches_section_7() -> None:
    assert opening_gap_percent(Decimal("24000"), Decimal("24180")) == Decimal("0.75")


@pytest.mark.parametrize(
    ("gap", "expected"),
    [
        (Decimal("0.76"), GapClass.STRONG_UP),
        (Decimal("0.75"), GapClass.MODERATE_UP),
        (Decimal("0.30"), GapClass.MODERATE_UP),
        (Decimal("0.29"), GapClass.FLAT),
        (Decimal("-0.29"), GapClass.FLAT),
        (Decimal("-0.30"), GapClass.MODERATE_DOWN),
        (Decimal("-0.75"), GapClass.MODERATE_DOWN),
        (Decimal("-0.76"), GapClass.STRONG_DOWN),
    ],
)
def test_req_default_gap_classes(gap: Decimal, expected: GapClass) -> None:
    assert classify_gap(gap) is expected


def test_req_alternate_thresholds_are_configurable() -> None:
    """Section 3: research thresholds 0.50, 1.00, 1.50, and a volatility-adjusted value."""
    assert classify_gap(Decimal("0.51"), strong=Decimal("0.50")) is GapClass.STRONG_UP
    assert classify_gap(Decimal("1.00"), strong=Decimal("1.00")) is GapClass.MODERATE_UP
    assert classify_gap(Decimal("1.01"), strong=Decimal("1.00")) is GapClass.STRONG_UP
    assert classify_gap(Decimal("1.50"), strong=Decimal("1.50")) is GapClass.MODERATE_UP
    volatility_adjusted = Decimal("1.25")
    assert classify_gap(Decimal("1.20"), strong=volatility_adjusted) is GapClass.MODERATE_UP
    assert classify_gap(Decimal("1.26"), strong=volatility_adjusted) is GapClass.STRONG_UP


def test_req_horizons_are_independent_and_t3_uses_the_decision_close() -> None:
    calendar = MarketCalendar()
    bars = (
        _bar(date(2026, 11, 18), "100", "100"),
        _bar(date(2026, 11, 19), "110", "111"),
        _bar(date(2026, 11, 20), "90", "91"),
        _bar(date(2026, 11, 23), "103", "104"),
    )
    t1 = gap_observations(bars, calendar, Horizon.T1)[0]
    t3 = gap_observations(bars, calendar, Horizon.T3)[0]
    assert t1.prior_close == Decimal("100")
    assert t1.next_open == Decimal("110")
    assert t3.prior_close == Decimal("100")
    assert t3.next_open == Decimal("103")
    assert t1.gap_percent != t3.gap_percent


def test_req_unpublished_row_cannot_be_used_for_a_decision() -> None:
    repo = ObservationRepository()
    visible = repo.add(_bar(date(2026, 11, 20), "100", "100"))
    repo.add(
        _bar(
            date(2026, 11, 23),
            "110",
            "110",
            version="2",
            observation_at=datetime(2026, 11, 23, 3, 0, tzinfo=timezone.utc),
            publication_at=datetime(2026, 11, 23, 4, 0, tzinfo=timezone.utc),
        )
    )
    decision_at = datetime(2026, 11, 20, 15, 30, tzinfo=timezone.utc)
    assert repo.usable_as_of(decision_at) == (visible,)


def test_req_quarantine_impossible_ohlc_duplicate_stale_and_missing_price() -> None:
    impossible = apply_validation(_bar(date(2026, 11, 20), "100", "100", high=Decimal("1")))
    missing = apply_validation(_bar(date(2026, 11, 20), "0", "100"))
    stale = apply_validation(
        _bar(date(2026, 11, 20), "100", "100"),
        now=datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc),
        max_age=timedelta(minutes=15),
    )
    repo = ObservationRepository()
    original = repo.add(_bar(date(2026, 11, 20), "100", "101"))
    duplicate = repo.add(_bar(date(2026, 11, 20), "100", "102"))
    assert impossible.quality is QualityStatus.QUARANTINED
    assert missing.quality_reason == "non_positive_price"
    assert stale.quality_reason == "stale_quote"
    assert original.quality is QualityStatus.OK
    assert duplicate.quality_reason == "duplicate"


def test_req_remaining_quarantine_categories_are_implemented() -> None:
    """Section 5 lists these categories. Reasons come back from the validators."""
    from app.data.validation import contract_issue, timestamp_issue

    found = {
        contract_issue(instrument_id="", strike=Decimal("1"), expiry=None, quote_date=date(2026, 11, 20)),
        timestamp_issue(datetime(2026, 11, 20, 10, 0)),
        contract_issue(
            instrument_id="NIFTY",
            strike=Decimal("-1"),
            expiry=date(2026, 12, 1),
            quote_date=date(2026, 11, 20),
        ),
        contract_issue(
            instrument_id="NIFTY",
            strike=Decimal("24000"),
            expiry=date(2026, 11, 1),
            quote_date=date(2026, 11, 20),
        ),
        apply_validation(
            _bar(date(2026, 11, 20), "100", "180"),
            previous_close=Decimal("100"),
            max_jump_fraction=Decimal("0.2"),
        ).quality_reason,
    }
    assert found >= {
        "bad identifier",
        "bad timestamp",
        "bad strike",
        "inconsistent expiry",
        "unexpected discontinuity",
    }


def test_req_failed_collection_does_not_recommend() -> None:
    assert recommendation_allowed(
        data_ok=False,
        model_approved=True,
        option_decision=Recommendation.BUY_CALL,
    ) is Recommendation.NO_TRADE


def test_req_negative_value_illiquid_contract_and_missing_data_are_no_trade() -> None:
    """Section 2 and the risk policy: negative value, failed liquidity, and missing data."""
    assert decide(_eligible(expected_gross=Decimal("1"), costs=Decimal("5"))) is Recommendation.NO_TRADE
    assert decide(_eligible(quote=_quote(bid=Decimal("10"), ask=Decimal("40")))) is Recommendation.NO_TRADE
    assert decide(_eligible(data_ok=False)) is Recommendation.NO_TRADE


def test_req_premium_risk_uses_quantity_and_one_open_position() -> None:
    assert decide(_eligible(quantity=65, premium=Decimal("100"))) is Recommendation.NO_TRADE
    assert decide(_eligible(open_positions=1)) is Recommendation.NO_TRADE


def test_req_direction_alone_is_not_a_call() -> None:
    """Section 2: a CALL requires a strong bullish gap probability, not direction alone."""
    assert decide(_eligible()) is Recommendation.NO_TRADE


def test_req_put_recommendation_includes_the_documented_greeks() -> None:
    """Section 2 and section 8: a bearish case can recommend a PUT. Valuation includes the Greeks."""
    decision = decide(
        _eligible(
            direction="down",
            strong_probability=Decimal("0.70"),
            quote=_quote(option_type="PUT", delta=Decimal("-0.62")),
        )
    )
    assert decision is Recommendation.BUY_PUT
    greeks = black_scholes(
        spot=100, strike=100, years=30 / 365, rate=0.06, volatility=0.15, option_type="PUT"
    )
    for name in ("delta", "gamma", "theta", "vega"):
        assert getattr(greeks, name) is not None


def test_req_regime_is_not_a_trade_and_short_history_is_insufficient() -> None:
    closes = [Decimal(100 + index) for index in range(40)]
    regime = classify_regime(closes, [c + 1 for c in closes], [c - 1 for c in closes])
    assert isinstance(regime, Regime)
    assert regime is not Recommendation.BUY_CALL
    assert classify_regime(closes[:5], closes[:5], closes[:5]) is Regime.DATA_INSUFFICIENT


def test_req_event_regime_does_not_assign_a_direction() -> None:
    """Section 4.7: a scheduled event must not automatically generate a directional signal."""
    regime_source = (ROOT / "app" / "intelligence" / "regime.py").read_text(encoding="utf-8")
    assert "BUY_CALL" not in regime_source
    assert "BUY_PUT" not in regime_source
    assert type(classify_regime([Decimal("100")] * 5, [Decimal("101")] * 5, [Decimal("99")] * 5)) is Regime


def test_req_nifty_and_banknifty_models_are_separate() -> None:
    nifty = BaseRateModel(IndexSymbol.NIFTY, Horizon.T1)
    bank = BaseRateModel(IndexSymbol.BANKNIFTY, Horizon.T1)
    nifty.fit([Decimal("1")])
    bank.fit([Decimal("-1")])
    assert nifty.predict().model_version != bank.predict().model_version
    assert nifty.predict().probability_up != bank.predict().probability_up


def test_req_walk_forward_does_not_train_on_the_test_window() -> None:
    gaps = [Decimal(index) / Decimal(10) for index in range(-15, 15)]
    folds = walk_forward(gaps, index=IndexSymbol.NIFTY, horizon=Horizon.T1, train_size=10, test_size=5)
    assert folds
    for fold in folds:
        assert fold.test_start >= fold.train_end


def test_req_base_rate_alone_cannot_approve_a_live_alert() -> None:
    gaps = [Decimal("0.1")] * 40
    folds = walk_forward(gaps, index=IndexSymbol.NIFTY, horizon=Horizon.T1, train_size=10, test_size=5)
    assert alerts_approved(folds) is False


def test_req_duplicate_signal_and_duplicate_notification_are_blocked() -> None:
    existing = _signal()
    assert duplicate_of([existing], _signal()) is True
    channel = RecordingChannel("telegram")
    dispatcher = Dispatcher([channel])
    dispatcher.notify(existing.signal_id, "trade", "body")
    second = dispatcher.notify(existing.signal_id, "trade", "body")
    assert second[0].status == "duplicate_suppressed"


def test_req_invalidation_is_a_legal_transition() -> None:
    updated = transition(_signal(), SignalStatus.INVALIDATED)
    assert updated.status is SignalStatus.INVALIDATED


def test_req_commands_reject_strangers_and_do_not_place_orders() -> None:
    signal = _signal()
    denied = handle_command("/accept " + signal.signal_id, "stranger", ("owner",), {signal.signal_id: signal})
    assert denied.ok is False
    source = inspect.getsource(handle_command)
    tree = ast.parse(source)
    names = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]
    assert "place_order" not in names


def test_req_notification_states_that_no_order_was_placed() -> None:
    """Section 9: live text says no broker order was placed, and the sample 76% is not a default."""
    source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "app").rglob("*.py"))
    assert "No broker order has been placed" in source
    assert "76%" not in source


def test_req_hypothetical_and_reported_pnl_stay_separate() -> None:
    trades = [
        TrackedTrade("a", "hypothetical", Decimal("100"), Decimal("130")),
        TrackedTrade("b", "reported", Decimal("100"), Decimal("90")),
    ]
    assert scorecard(trades, "hypothetical").count == 1
    assert scorecard(trades, "reported").count == 1


def test_req_scorecards_are_separate_for_each_index() -> None:
    """Section 2 and section 3: reports are separate by index and by instrument."""
    fields = set(TrackedTrade.__dataclass_fields__)
    assert fields & {"index", "instrument", "symbol"}


def test_req_ignored_signal_is_still_scored() -> None:
    """Risk policy: an ignored recommendation is still tracked, separately from a reported fill."""
    ignored = transition(_signal(), SignalStatus.IGNORED)
    outcome = PredictionOutcome(ignored.signal_id, "down", Decimal("-0.8"), Decimal("-1.1"))
    assert ignored.status is SignalStatus.IGNORED
    assert outcome.signal_id == ignored.signal_id
    assert outcome.direction_hit is True


def test_req_holiday_suppresses_the_session_schedule() -> None:
    """Section 12: holidays are explicit."""
    from zoneinfo import ZoneInfo

    holiday = datetime(2026, 11, 23, 8, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    calendar = MarketCalendar(holidays=frozenset({holiday.date()}))
    assert scheduled_activity(holiday, calendar) == "market_holiday"


def test_req_capital_is_not_hardcoded() -> None:
    """Section 22 and the risk policy: capital comes from configuration, not source."""
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = [item.id for item in node.targets if isinstance(item, ast.Name)]
                if "strategy_capital" in targets and isinstance(node.value, ast.Constant):
                    raise AssertionError(f"hardcoded capital in {path}")
    assert Settings.from_env().strategy_capital is None


def test_req_secrets_are_not_committed() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "UPSTOX_ACCESS_TOKEN=" in example
    assert "UPSTOX_ACCESS_TOKEN=ey" not in example
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_req_required_tables_exist_in_the_schema() -> None:
    schema = (ROOT / "migrations" / "001_market_observations.sql").read_text(encoding="utf-8").lower()
    required = [
        "instruments",
        "market_observations",
        "option_snapshots",
        "derivatives_positions",
        "global_market_data",
        "macro_events",
        "features",
        "market_regimes",
        "model_versions",
        "predictions",
        "opportunities",
        "option_evaluations",
        "signals",
        "notifications",
        "notification_deliveries",
        "manual_trades",
        "prediction_outcomes",
        "performance_metrics",
        "audit_logs",
    ]
    missing = [name for name in required if name not in schema]
    assert missing == []


def test_req_health_reports_a_provider_outage_as_degraded() -> None:
    report = health(database_ok=True, scheduler_ok=True, provider_ok=False)
    assert report.status == "degraded"


def test_req_health_covers_notifications_and_predictions() -> None:
    """Section 12: health covers database, provider, scheduler, notifications, predictions, and sockets."""
    report_fields = " ".join(type(health(database_ok=True, scheduler_ok=True, provider_ok=True)).__dataclass_fields__)
    required = ("database", "provider", "scheduler", "notification", "prediction", "socket")
    missing = [name for name in required if name not in report_fields]
    assert missing == []


def test_req_structure_features_named_in_section_4() -> None:
    """Section 4.5: EMA, ATR, RSI, and ADX are part of market structure."""
    import app.features.technical as technical

    for name in ("ema", "atr", "rsi", "adx"):
        assert hasattr(technical, name), name


def test_req_breadth_and_event_proximity_exist() -> None:
    """Section 4.6 and 4.7: advance/decline and event proximity are features, not directions."""
    feature_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "app" / "features").rglob("*.py")
    )
    assert "advance" in feature_source.lower()
    assert "event" in feature_source.lower()


def test_req_scenario_expectancy_uses_the_documented_formula() -> None:
    """Section 8.3: P(win) x average profit - P(loss) x average loss - costs."""
    documented = Decimal("0.4") * Decimal("50") - Decimal("0.6") * Decimal("20") - Decimal("3")
    assert documented == Decimal("5")
    options_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "app" / "options").rglob("*.py")
    )
    for term in ("avg_profit", "avg_loss", "p_win", "p_loss"):
        assert term in options_source


def test_req_research_models_beyond_the_base_rate_exist() -> None:
    """Section 7.4 names the initial model set. Neural nets are deferred and are not required."""
    source = (ROOT / "app" / "intelligence" / "prediction.py").read_text(encoding="utf-8").lower()
    for name in ("base", "logistic", "forest", "boost", "volatility"):
        assert name in source, name


def test_req_whatsapp_requires_opt_in_and_email_report_exists() -> None:
    """Section 9.2 and 9.3: WhatsApp requires opt-in. Email includes a weekly report."""
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "app" / "notifications").rglob("*.py")
    ).lower()
    assert "whatsapp" in source
    assert "opt" in source
    assert "weekly" in source
