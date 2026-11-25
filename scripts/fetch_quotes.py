#!/usr/bin/env python3
"""Fetch Nifty, Bank Nifty, and India VIX quotes and store them.

Does not send Telegram and does not place an order. Does not print the token.
A quote older than 20 minutes is stored as stale and cannot be used for a buy.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.data.upstox_quotes import QUOTE_MAX_AGE, fetch_index_quotes
from app.notifications.telegram_api import load_env_file


def _public_error(exc: BaseException) -> str:
    text = re.sub(r"postgres(?:ql)?://\S+", "postgresql://…", str(exc))
    text = re.sub(r"Bearer\s+\S+", "Bearer …", text)
    return text.splitlines()[0]


def main() -> int:
    load_env_file(ROOT / ".env")
    settings = Settings.from_env()
    if not settings.upstox_access_token:
        print("missing: UPSTOX_ACCESS_TOKEN")
        return 2
    now = datetime.now(timezone.utc)
    result = fetch_index_quotes(settings.upstox_access_token, now=now)
    if result.error == "unauthorized":
        print("upstox rejected the token")
        return 1
    if result.error == "unavailable":
        detail = f" ({result.detail})" if result.detail else ""
        print(f"upstox quotes unavailable{detail}")
        return 1
    try:
        from app.runtime.persistence import open_store
    except ImportError:
        print("psycopg is not installed. Run: python3 -m pip install 'psycopg[binary]'")
        return 2
    try:
        store = open_store(settings.database_url)
    except ModuleNotFoundError:
        print("psycopg is not installed. Run: python3 -m pip install 'psycopg[binary]'")
        return 2
    except Exception as exc:
        print(f"database connection failed: {_public_error(exc)}")
        return 1
    try:
        for bar in result.bars:
            stored = store.add(bar, now=now, max_age=QUOTE_MAX_AGE)
            reason = stored.quality_reason or "ok"
            print(
                f"{stored.instrument_id} close={stored.close} quality={stored.quality.value} reason={reason}"
            )
        counts = store.counts()
    except Exception as exc:
        print(f"database write failed: {_public_error(exc)}")
        return 1
    finally:
        store.close()
    print("missing: " + (", ".join(result.missing) if result.missing else "none"))
    print(f"market_observations: {counts['market_observations']}")
    return 0 if result.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
