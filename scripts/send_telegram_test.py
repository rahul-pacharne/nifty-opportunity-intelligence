#!/usr/bin/env python3
"""Send one test message with NOI_TELEGRAM_BOT_TOKEN. Does not print the token."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.notifications.telegram_api import load_env_file, send_message


def main() -> int:
    load_env_file(ROOT / ".env")
    settings = Settings.from_env()
    missing = []
    if not settings.telegram_bot_token:
        missing.append("NOI_TELEGRAM_BOT_TOKEN")
    if not settings.telegram_allowed_user_ids:
        missing.append("NOI_TELEGRAM_ALLOWED_USER_IDS")
    if missing:
        print("missing: " + ", ".join(missing))
        return 2
    chat_id = settings.telegram_allowed_user_ids[0]
    send_message(
        settings.telegram_bot_token,
        chat_id,
        "NOI test. No broker order has been placed.",
    )
    print(f"sent to {chat_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(1)
