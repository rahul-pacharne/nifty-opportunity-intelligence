#!/usr/bin/env python3
"""Run the IST clock once. Outside an entry window it sends nothing and does not fetch.

Buy and sell stay off. Does not place an order and does not print secrets.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.notifications.telegram_api import load_env_file, send_message
from app.runtime.exits import ExitRules
from app.runtime.live_runner import ENTRY_ACTIVITIES
from app.runtime.schedule import IST, scheduled_activity
from app.runtime.scheduled_check import run_scheduled_check


class _TelegramTransport:
    def __init__(self, token: str) -> None:
        self._token = token

    def send(self, chat_id: str, text: str) -> None:
        send_message(self._token, chat_id, text)


def main() -> int:
    load_env_file(ROOT / ".env")
    now = datetime.now(timezone.utc)
    print(now.astimezone(IST).strftime("%Y-%m-%d %H:%M IST"))
    activity = scheduled_activity(now)
    if activity not in ENTRY_ACTIVITIES:
        print(f"activity: {activity}")
        print("sent: none")
        return 0
    settings = Settings.from_env()
    if not settings.upstox_access_token:
        print("missing: UPSTOX_ACCESS_TOKEN")
        return 2
    if not settings.telegram_bot_token or not settings.telegram_allowed_user_ids:
        print("missing: NOI_TELEGRAM_BOT_TOKEN or NOI_TELEGRAM_ALLOWED_USER_IDS")
        return 2
    from app.runtime.session import open_runtime

    rules = ExitRules(Decimal("20"), Decimal("30"), timedelta(hours=6))
    loop, _book, gateway, store = open_runtime(
        settings.database_url,
        allowed_user_ids=settings.telegram_allowed_user_ids,
        transport=_TelegramTransport(settings.telegram_bot_token),
        rules=rules,
    )
    try:
        report = run_scheduled_check(
            now,
            token=settings.upstox_access_token,
            loop=loop,
            gateway=gateway,
            chat_id=settings.telegram_allowed_user_ids[0],
        )
    finally:
        store.close()
    print(f"activity: {report.activity}")
    print(f"action: {report.action}")
    print("sent: " + (", ".join(report.sent) if report.sent else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
