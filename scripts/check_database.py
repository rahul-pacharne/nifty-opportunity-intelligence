#!/usr/bin/env python3
"""Apply pending SQL migrations and confirm NOI_DATABASE_URL can be written.

Does not call Upstox and does not send Telegram. Does not print secrets.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.notifications.telegram_api import load_env_file


def _public_error(exc: BaseException) -> str:
    text = re.sub(r"postgres(?:ql)?://\S+", "postgresql://…", str(exc))
    return text.splitlines()[0]


def main() -> int:
    load_env_file(ROOT / ".env")
    settings = Settings.from_env()
    if not settings.database_url:
        print("missing: NOI_DATABASE_URL")
        return 2
    try:
        from app.runtime.persistence import PostgresStore, apply_migrations, connect
    except ImportError:
        print("psycopg is not installed. Run: python3 -m pip install 'psycopg[binary]'")
        return 2
    try:
        connection = connect(settings.database_url)
    except ModuleNotFoundError:
        print("psycopg is not installed. Run: python3 -m pip install 'psycopg[binary]'")
        return 2
    except Exception as exc:
        print(f"database connection failed: {_public_error(exc)}")
        return 1
    store = PostgresStore(connection)
    try:
        applied = apply_migrations(connection)
        store.record_audit("database_check", "read and write succeeded")
        counts = store.counts()
    except Exception as exc:
        print(f"database check failed: {_public_error(exc)}")
        return 1
    finally:
        store.close()
    print("applied: " + (", ".join(applied) if applied else "none"))
    print("upstox token: " + ("set" if settings.upstox_access_token else "missing"))
    for name, count in counts.items():
        print(f"{name}: {count}")
    print("database ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
