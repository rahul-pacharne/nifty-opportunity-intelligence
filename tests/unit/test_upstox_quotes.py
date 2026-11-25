import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from urllib.error import HTTPError

from app.data.models import latest_session_bars
from app.data.models import Bar
from app.data.upstox_quotes import INDEX_KEYS, QUOTES_URL, fetch_index_quotes, parse_index_quotes
from app.runtime.decision_loop import DecisionLoop
from app.core.constants import IndexSymbol, QualityStatus

NOW = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)


def _payload(**overrides: dict) -> dict:
    data = {
        "NSE_INDEX:Nifty 50": {
            "instrument_token": "NSE_INDEX|Nifty 50",
            "last_price": 26180.25,
            "timestamp": "2026-11-25T15:15:00+05:30",
            "ohlc": {"open": 26100, "high": 26200, "low": 26050, "close": 26090},
        },
        "NSE_INDEX:Nifty Bank": {
            "instrument_token": "NSE_INDEX|Nifty Bank",
            "last_price": 55210.5,
            "timestamp": "2026-11-25T15:15:00+05:30",
            "ohlc": {"open": 55100, "high": 55300, "low": 55000, "close": 55120},
        },
        "NSE_INDEX:India VIX": {
            "instrument_token": "NSE_INDEX|India VIX",
            "last_price": 13.42,
            "timestamp": "2026-11-25T15:15:00+05:30",
            "ohlc": {"open": 13.1, "high": 13.8, "low": 12.9, "close": 13.2},
        },
    }
    data.update(overrides)
    return {"status": "success", "data": data}


def test_quotes_use_the_last_price_and_the_exchange_time() -> None:
    result = parse_index_quotes(_payload(), now=NOW)
    assert result.error is None
    assert result.missing == ()
    nifty = result.bars[0]
    assert nifty.instrument_id == "NIFTY"
    assert nifty.close == Decimal("26180.25")
    assert nifty.open == Decimal("26100")
    assert nifty.market_date.isoformat() == "2026-11-25"
    assert nifty.publication_at is not None
    assert nifty.publication_at.utcoffset() == timedelta(hours=5, minutes=30)
    assert nifty.source == "upstox"
    assert [bar.instrument_id for bar in result.bars] == ["NIFTY", "BANKNIFTY", "INDIA_VIX"]


def test_a_missing_series_is_incomplete() -> None:
    payload = _payload()
    del payload["data"]["NSE_INDEX:Nifty Bank"]
    result = parse_index_quotes(payload, now=NOW)
    assert result.error == "incomplete"
    assert result.missing == ("BANKNIFTY",)
    assert [bar.instrument_id for bar in result.bars] == ["NIFTY", "INDIA_VIX"]


def test_missing_exchange_time_is_quarantined() -> None:
    payload = _payload()
    payload["data"]["NSE_INDEX:Nifty 50"].pop("timestamp")
    result = parse_index_quotes(payload, now=NOW)
    nifty = result.bars[0]
    assert nifty.quality is QualityStatus.QUARANTINED
    assert nifty.quality_reason == "missing_exchange_time"


def test_naive_exchange_time_is_read_as_ist() -> None:
    payload = _payload()
    payload["data"]["NSE_INDEX:Nifty 50"]["timestamp"] = "2026-11-25T15:15:00"
    result = parse_index_quotes(payload, now=NOW)
    assert result.bars[0].observation_at.utcoffset() == timedelta(hours=5, minutes=30)


def test_request_asks_only_for_quotes_and_hides_the_token(monkeypatch) -> None:
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["timeout"] = timeout
        body = json.dumps(_payload()).encode()
        return BytesIO(body)

    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    result = fetch_index_quotes("test-token", now=NOW, opener=opener)
    assert result.error is None
    assert seen["url"].startswith(QUOTES_URL)
    assert "order" not in seen["url"]
    assert seen["authorization"] == "Bearer test-token"
    assert seen["timeout"] == 20
    source = open("app/data/upstox_quotes.py", encoding="utf-8").read()
    assert "test-token" not in source
    assert "/order" not in source
    for key, _instrument_id in INDEX_KEYS:
        assert key.replace(" ", "%20").replace("|", "%7C") in seen["url"] or key in seen["url"]


def test_unauthorized_does_not_echo_the_token() -> None:
    def opener(request, timeout):
        raise HTTPError(request.full_url, 401, "unauthorized", hdrs=None, fp=BytesIO(b"secret test-token"))

    result = fetch_index_quotes("test-token", now=NOW, opener=opener)
    assert result.error == "unauthorized"
    assert result.bars == ()
    assert "test-token" not in result.error


def test_latest_session_bar_replaces_an_earlier_quote() -> None:
    bars = []
    for offset, close in enumerate(("1", "2", "3", "4")):
        day = datetime(2026, 11, 2 + offset, tzinfo=timezone.utc)
        bars.append(
            Bar(
                instrument_id="NIFTY",
                market_date=day.date(),
                open=Decimal(close),
                high=Decimal(close),
                low=Decimal(close),
                close=Decimal(close),
                observation_at=day,
                publication_at=day,
                retrieved_at=day,
                source="upstox",
                version="1",
            )
        )
    last_day = datetime(2026, 11, 6, tzinfo=timezone.utc)
    early = Bar(
        instrument_id="NIFTY",
        market_date=last_day.date(),
        open=Decimal("10"),
        high=Decimal("10"),
        low=Decimal("10"),
        close=Decimal("10"),
        observation_at=last_day,
        publication_at=last_day,
        retrieved_at=last_day,
        source="upstox",
        version="1",
    )
    later = Bar(
        instrument_id="NIFTY",
        market_date=last_day.date(),
        open=Decimal("10"),
        high=Decimal("20"),
        low=Decimal("10"),
        close=Decimal("20"),
        observation_at=last_day + timedelta(minutes=5),
        publication_at=last_day + timedelta(minutes=5),
        retrieved_at=last_day + timedelta(minutes=5),
        source="upstox",
        version="2",
    )
    assert latest_session_bars((later, early)) == (later,)
    loop = DecisionLoop()
    loop.load([*bars, early, later])
    record = loop.decide(index=IndexSymbol.NIFTY, decision_at=last_day + timedelta(minutes=10))
    assert record.latest_bar_date == last_day.date()
    assert record.feature_ema == Decimal("6.0000")
