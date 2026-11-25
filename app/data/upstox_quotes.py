"""Read index quotes from Upstox. This module never places an order."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from app.core.constants import QualityStatus
from app.data.models import Bar

IST = ZoneInfo("Asia/Kolkata")
QUOTES_URL = "https://api.upstox.com/v2/market-quote/quotes"
QUOTE_MAX_AGE = timedelta(minutes=20)

# Upstox instrument keys. The stored id is the one the decision loop already uses.
INDEX_KEYS = (
    ("NSE_INDEX|Nifty 50", "NIFTY"),
    ("NSE_INDEX|Nifty Bank", "BANKNIFTY"),
    ("NSE_INDEX|India VIX", "INDIA_VIX"),
)


@dataclass(frozen=True)
class QuoteResult:
    bars: tuple[Bar, ...]
    missing: tuple[str, ...]
    error: str | None


def fetch_index_quotes(token: str, *, now: datetime, opener=urlopen) -> QuoteResult:
    if not token or now.tzinfo is None:
        return QuoteResult((), tuple(instrument_id for _, instrument_id in INDEX_KEYS), "unavailable")
    query = urlencode({"instrument_key": ",".join(key for key, _ in INDEX_KEYS)}, quote_via=quote)
    request = Request(
        f"{QUOTES_URL}?{query}",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with opener(request, timeout=20) as response:
            payload = json.loads(response.read().decode())
    except HTTPError as exc:
        error = "unauthorized" if exc.code == 401 else "unavailable"
        return QuoteResult((), tuple(instrument_id for _, instrument_id in INDEX_KEYS), error)
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return QuoteResult((), tuple(instrument_id for _, instrument_id in INDEX_KEYS), "unavailable")
    return parse_index_quotes(payload, now=now)


def parse_index_quotes(payload: dict, *, now: datetime) -> QuoteResult:
    if now.tzinfo is None:
        return QuoteResult((), tuple(instrument_id for _, instrument_id in INDEX_KEYS), "unavailable")
    status = payload.get("status")
    data = payload.get("data")
    if status not in (None, "success") or not isinstance(data, dict):
        return QuoteResult((), tuple(instrument_id for _, instrument_id in INDEX_KEYS), "unavailable")
    found: dict[str, Bar] = {}
    for feed_key, raw in data.items():
        if not isinstance(raw, dict):
            continue
        instrument_id = _instrument_id(str(feed_key), raw.get("instrument_token"))
        if instrument_id is None or instrument_id in found:
            continue
        bar = _bar_from_quote(instrument_id, raw, now=now)
        if bar is not None:
            found[instrument_id] = bar
    missing = tuple(instrument_id for _, instrument_id in INDEX_KEYS if instrument_id not in found)
    error = "incomplete" if missing else None
    return QuoteResult(tuple(found[instrument_id] for _, instrument_id in INDEX_KEYS if instrument_id in found), missing, error)


def _instrument_id(feed_key: str, token: object) -> str | None:
    wanted = {key: instrument_id for key, instrument_id in INDEX_KEYS}
    candidates = []
    if isinstance(token, str) and token.strip():
        candidates.append(token.strip())
    if feed_key:
        candidates.append(feed_key.replace(":", "|", 1))
    for candidate in candidates:
        if candidate in wanted:
            return wanted[candidate]
    return None


def _bar_from_quote(instrument_id: str, raw: dict, *, now: datetime) -> Bar | None:
    ohlc = raw.get("ohlc") if isinstance(raw.get("ohlc"), dict) else {}
    last_price = _decimal(raw.get("last_price"))
    close = last_price if last_price is not None and last_price > 0 else _decimal(ohlc.get("close"))
    open_price = _decimal(ohlc.get("open")) or close
    high = _decimal(ohlc.get("high")) or close
    low = _decimal(ohlc.get("low")) or close
    if close is None or open_price is None or high is None or low is None:
        return None
    high = max(high, open_price, close)
    low = min(low, open_price, close)
    exchange_at = _exchange_time(raw.get("timestamp")) or _exchange_time(raw.get("last_trade_time"))
    observation_at = exchange_at or now
    version = observation_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    bar = Bar(
        instrument_id=instrument_id,
        market_date=observation_at.astimezone(IST).date(),
        open=open_price,
        high=high,
        low=low,
        close=close,
        observation_at=observation_at,
        publication_at=exchange_at,
        retrieved_at=now,
        source="upstox",
        version=version,
    )
    if exchange_at is None:
        return replace(bar, quality=QualityStatus.QUARANTINED, quality_reason="missing_exchange_time")
    return bar


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except Exception:
        return None
    if not number.is_finite():
        return None
    return number


def _exchange_time(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=IST)
    return parsed
